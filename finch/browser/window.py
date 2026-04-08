import asyncio
import functools
import logging
import os

log = logging.getLogger(__name__)

from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QMainWindow, QTreeView, QVBoxLayout, QWidget,
    QMenu, QInputDialog, QMessageBox, QFileDialog,
)

from finch.browser.model import S3FileTreeModel
from finch.config import ObjectType, app_settings
from finch.settings.credentials import CredentialsManager
from finch.s3 import s3_service, S3Object
from finch.settings import SettingsDialog
from finch.browser.about import AboutDialog
from finch.tools.acl import ACLWindow
from finch.tools.cors import CORSWindow
from finch.transfers.download import MultiDownloadProgressDialog
from finch.transfers.upload import UploadDialog
from finch.utils import async_slot
from finch.utils.dialogs import TimeIntervalDialog
from finch.utils.error import show_error_dialog
from finch.utils.ui import center_window, resource_path
from finch.browser.widgets.search import SearchWidget, SearchScope
from finch.browser.widgets.spinner import QProgressIndicator
from finch.browser.widgets.toolbars import init_toolbars


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.credentials_manager = None
        self.download_dialog = None
        self.upload_dialog = None
        self.search_widget = None
        self.tree_widget = None
        self.tree_model = None

        self.creds_toolbar, self.file_toolbar, self.settings_toolbar = init_toolbars(self)
        self.creds_toolbar.credential_selector.currentIndexChanged.connect(self.on_credential_changed)

        self.resize(1200, 700)
        self.setWindowTitle("Finch S3 Client")

        self.widget = QWidget()
        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignTop)
        self.widget.setLayout(self.layout)
        self.tree_widget_wrapper = QWidget()
        self.tree_widget_wrapper_lay = QVBoxLayout()
        self.tree_widget_wrapper.setLayout(self.tree_widget_wrapper_lay)

        self.spinner = QProgressIndicator(self.widget)

        self.reload_credentials()
        self.layout.addWidget(self.tree_widget_wrapper)
        self.setCentralWidget(self.widget)

        center_window(self)

    # ── Credentials ────────────────────────────────────────────────────────

    @property
    def credential_selector(self):
        return self.creds_toolbar.credential_selector

    def reload_credentials(self, selected_index=0):
        self.credentials_manager = CredentialsManager()
        self.creds_toolbar.populate(
            self.credentials_manager.list_credentials_names(), selected_index
        )
        self.refresh()

    def open_settings(self, start_page: int = SettingsDialog.PAGE_CREDENTIALS) -> None:
        dlg = SettingsDialog(parent=self, start_page=start_page)
        dlg.settings_changed.connect(
            functools.partial(self.reload_credentials, self.credential_selector.currentIndex())
        )
        dlg.exec()

    # ── Tree setup ─────────────────────────────────────────────────────────

    def on_credential_changed(self, cred_index):
        if self.credential_selector.itemData(cred_index) != 0:
            try:
                cred_name = self.credential_selector.itemText(cred_index)
                cred = self.credentials_manager.get_credential(cred_name)
                s3_service.set_credential(cred)
                self._reset_tree()
            except Exception as e:
                show_error_dialog(e, show_traceback=True)

    def _reset_tree(self):
        if self.tree_widget is None:
            self.tree_widget = QTreeView()
            self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
            self.tree_widget.customContextMenuRequested.connect(self._show_context_menu)
            self.tree_widget.setSortingEnabled(True)
            self.tree_widget.setSelectionMode(QTreeView.ExtendedSelection)
            header = self.tree_widget.header()
            header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
            self.tree_widget_wrapper_lay.addWidget(self.tree_widget)

        self.tree_model = S3FileTreeModel()
        self.tree_widget.setModel(self.tree_model)
        self.tree_widget.sortByColumn(0, Qt.AscendingOrder)
        self.tree_widget.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.tree_model.loading_started.connect(self.spinner.start)
        self.tree_model.loading_finished.connect(self.spinner.stop)
        self.tree_model.load_buckets()

    # ── Selection helpers ──────────────────────────────────────────────────

    def get_selected_node(self):
        rows = self.tree_widget.selectionModel().selectedRows()
        if rows:
            return rows[0].data(Qt.UserRole)
        return None

    def get_bucket_name_from_selected_item(self):
        rows = self.tree_widget.selectionModel().selectedRows()
        if rows:
            node = rows[0].data(Qt.UserRole)
            if node and node.s3_object:
                obj = node.s3_object
                return obj.name if obj.type == ObjectType.BUCKET else obj.bucket_name
        return None

    def get_object_key_from_selected_item(self):
        rows = self.tree_widget.selectionModel().selectedRows()
        if rows:
            node = rows[0].data(Qt.UserRole)
            if node and node.s3_object:
                return node.s3_object.key
        return None

    def _on_selection_changed(self, selected, deselected):
        rows = self.tree_widget.selectionModel().selectedRows()
        self.file_toolbar.update_state(rows)

    # ── Context menu ───────────────────────────────────────────────────────

    def _show_context_menu(self, position):
        indexes = self.tree_widget.selectedIndexes()
        if not indexes:
            return
        node = indexes[0].data(Qt.UserRole)
        if not node:
            return
        obj_type = node.s3_object.type

        menu = QMenu()
        if obj_type == ObjectType.BUCKET:
            act = QAction("Delete Bucket")
            act.setIcon(QIcon(resource_path('img/trash.svg')))
            act.triggered.connect(self.delete_bucket)
            menu.addAction(act)

            act = QAction("Create Folder")
            act.setIcon(QIcon(resource_path('img/new-folder.svg')))
            act.triggered.connect(self.create_folder)
            menu.addAction(act)

            tools_menu = menu.addMenu("Tools")
            tools_menu.setIcon(QIcon(resource_path('img/tools.svg')))
            act = QAction("CORS Configurations", self)
            act.setIcon(QIcon(resource_path('img/globe.svg')))
            act.triggered.connect(self.show_cors_window)
            tools_menu.addAction(act)
            act = QAction("ACL Configuration", self)
            act.setIcon(QIcon(resource_path('img/tools.svg')))
            act.triggered.connect(self.show_acl_window)
            tools_menu.addAction(act)

        elif obj_type == ObjectType.FOLDER:
            act = QAction("Delete Folder")
            act.setIcon(QIcon(resource_path('img/trash.svg')))
            act.triggered.connect(self.delete_folder)
            menu.addAction(act)

            act = QAction("Create Folder")
            act.setIcon(QIcon(resource_path('img/new-folder.svg')))
            act.triggered.connect(self.create_folder)
            menu.addAction(act)

        elif obj_type == ObjectType.FILE:
            act = QAction("Download File(s)")
            act.setIcon(QIcon(resource_path('img/save.svg')))
            act.triggered.connect(self.download_files)
            menu.addAction(act)

            act = QAction("Delete File")
            act.setIcon(QIcon(resource_path('img/trash.svg')))
            act.triggered.connect(self.delete_file)
            menu.addAction(act)

            tools_menu = menu.addMenu("Tools")
            tools_menu.setIcon(QIcon(resource_path('img/tools.svg')))
            act = QAction("Get Presigned Download URL", self)
            act.setIcon(QIcon(resource_path('img/globe.svg')))
            act.triggered.connect(self.get_presigned_download_url)
            tools_menu.addAction(act)

        menu.exec(self.tree_widget.viewport().mapToGlobal(position))

    # ── S3 actions ─────────────────────────────────────────────────────────

    @async_slot
    async def create_bucket(self) -> None:
        bucket_name, ok = QInputDialog.getText(self, 'Create Bucket', 'Please enter bucket name')
        if ok:
            try:
                await asyncio.to_thread(s3_service.create_bucket, bucket_name)
                self.tree_model.insert_child(
                    self.tree_model._root,
                    S3Object(key=bucket_name, name=bucket_name, type=ObjectType.BUCKET),
                )
            except Exception as e:
                show_error_dialog(e, show_traceback=True)

    @async_slot
    async def create_folder(self) -> None:

        folder_name, ok = QInputDialog.getText(self, 'Create Folder', 'Please enter folder name')
        if ok:
            parent_node = self.get_selected_node()
            bucket_name = self.get_bucket_name_from_selected_item()
            parent_key = self.get_object_key_from_selected_item()
            folder_path = f"{parent_key}{folder_name}/" if parent_key else f"{folder_name}/"
            try:
                await asyncio.to_thread(s3_service.create_folder, bucket_name, folder_path)
                if parent_node and parent_node.is_loaded:
                    new_node = self.tree_model.insert_child(
                        parent_node,
                        S3Object(key=folder_path, name=folder_name,
                                 type=ObjectType.FOLDER, bucket_name=bucket_name),
                    )
                    if app_settings.check_folder_contents:
                        new_node.is_loaded = True
            except Exception as e:
                show_error_dialog(e, show_traceback=True)

    @async_slot
    async def delete_bucket(self) -> None:

        node = self.get_selected_node()
        bucket_name = self.get_bucket_name_from_selected_item()
        empty = await asyncio.to_thread(s3_service.is_bucket_empty, bucket_name)
        msg = ("You are going to delete this bucket. This operation cannot be undone. Are you sure?"
               if empty else
               "You are going to delete a non-empty bucket. All objects will be deleted. "
               "This operation cannot be undone. Are you sure?")
        dlg = QMessageBox(self)
        dlg.setIcon(QMessageBox.Warning)
        dlg.setWindowTitle("Warning")
        dlg.setText(msg)
        dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if dlg.exec() == QMessageBox.Yes:
            try:
                await asyncio.to_thread(s3_service.delete_bucket, bucket_name)
                self.tree_model.remove_node(node)
            except Exception as e:
                show_error_dialog(e, show_traceback=True)

    @async_slot
    async def delete_folder(self) -> None:

        node = self.get_selected_node()
        bucket_name = self.get_bucket_name_from_selected_item()
        folder_key = self.get_object_key_from_selected_item()
        dlg = QMessageBox(self)
        dlg.setIcon(QMessageBox.Warning)
        dlg.setWindowTitle("Warning")
        dlg.setText("All objects in this folder will be deleted. This operation cannot be undone. Are you sure?")
        dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if dlg.exec() == QMessageBox.Yes:
            try:
                await asyncio.to_thread(s3_service.delete_folder, bucket_name, folder_key)
                self.tree_model.remove_node(node)
            except Exception as e:
                show_error_dialog(e, show_traceback=True)

    @async_slot
    async def delete_file(self) -> None:

        node = self.get_selected_node()
        bucket_name = self.get_bucket_name_from_selected_item()
        object_key = self.get_object_key_from_selected_item()
        dlg = QMessageBox(self)
        dlg.setIcon(QMessageBox.Warning)
        dlg.setWindowTitle("Warning")
        dlg.setText("The selected file will be permanently deleted. This operation cannot be undone. Are you sure?")
        dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if dlg.exec() == QMessageBox.Yes:
            try:
                await asyncio.to_thread(s3_service.delete_object, bucket_name, object_key)
                self.tree_model.remove_node(node)
            except Exception as e:
                show_error_dialog(e, show_traceback=True)

    def create(self) -> None:
        rows = self.tree_widget.selectionModel().selectedRows() if self.tree_widget else []
        if not rows:
            self.create_bucket()
        else:
            node = rows[0].data(Qt.UserRole)
            if node and node.s3_object.type in (ObjectType.BUCKET, ObjectType.FOLDER):
                self.create_folder()

    @async_slot
    async def delete(self) -> None:

        rows = self.tree_widget.selectionModel().selectedRows()
        if not rows:
            return
        nodes = [n for r in rows if (n := r.data(Qt.UserRole))]
        if not nodes:
            return

        if len(nodes) == 1:
            dispatch = {
                ObjectType.BUCKET: self.delete_bucket,
                ObjectType.FOLDER: self.delete_folder,
                ObjectType.FILE:   self.delete_file,
            }
            handler = dispatch.get(nodes[0].s3_object.type)
            if handler:
                handler()
            return

        file_nodes = self._remove_redundant_children(
            [n for n in nodes if n.s3_object.type == ObjectType.FILE]
        )
        if not file_nodes:
            return

        names = [n.s3_object.name for n in file_nodes]
        bullet_list = "\n".join(f"  - {n}" for n in names[:20])
        suffix = f"\n  ... and {len(names) - 20} more" if len(names) > 20 else ""
        msg = (f"The following {len(names)} files will be permanently deleted:\n\n"
               f"{bullet_list}{suffix}\n\nThis operation cannot be undone. Are you sure?")
        dlg = QMessageBox(self)
        dlg.setIcon(QMessageBox.Warning)
        dlg.setWindowTitle("Confirm Bulk Delete")
        dlg.setText(msg)
        dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if dlg.exec() == QMessageBox.Yes:
            try:
                await asyncio.gather(*[
                    asyncio.to_thread(s3_service.delete_object,
                                      n.s3_object.bucket_name, n.s3_object.key)
                    for n in file_nodes
                ])
                for n in file_nodes:
                    self.tree_model.remove_node(n)
            except Exception as e:
                show_error_dialog(e, show_traceback=True)

    @staticmethod
    def _remove_redundant_children(nodes: list) -> list:
        keys = {n.s3_object.key for n in nodes}
        return [
            node for node in nodes
            if not any(
                other != node.s3_object.key and node.s3_object.key.startswith(other)
                for other in keys
            )
        ]

    # ── Transfers ──────────────────────────────────────────────────────────

    def upload_file(self) -> None:
        node = self.get_selected_node()
        if not node:
            return
        bucket_name = self.get_bucket_name_from_selected_item()
        folder_key = node.s3_object.key if node.s3_object.type == ObjectType.FOLDER else None
        file_dialog = QFileDialog()
        file_dialog.setWindowTitle("Select files to upload.")
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        if file_dialog.exec():
            for file in file_dialog.selectedFiles():
                file_name = os.path.basename(file)
                folder = folder_key[:-1] if folder_key else None
                s3_key = f"{folder}/{file_name}" if folder else file_name

                def on_success(f=file, sk=s3_key, fn=file_name, fk=folder_key):
                    parent_node = self.tree_model.find_node(bucket_name, fk or '')
                    if parent_node is not None and parent_node.is_loaded:
                        self.tree_model.insert_child(
                            parent_node,
                            S3Object(
                                key=sk,
                                name=fn,
                                type=ObjectType.FILE,
                                size=os.path.getsize(f),
                                bucket_name=bucket_name,
                            )
                        )

                self.upload_dialog = UploadDialog(file, bucket_name, folder_key,
                                                  on_success=on_success)
                self.upload_dialog.exec()

    def download_files(self) -> None:
        rows = self.tree_widget.selectionModel().selectedRows()
        if not rows:
            return
        file_list = [
            (node.s3_object.bucket_name, node.s3_object.key)
            for row in rows
            if (node := row.data(Qt.UserRole)) and node.s3_object.type == ObjectType.FILE
        ]
        if not file_list:
            return
        local_path = QFileDialog.getExistingDirectory(self, "Select folder to download")
        if local_path:
            self.download_dialog = MultiDownloadProgressDialog(file_list, local_path)
            self.download_dialog.exec()

    # ── Tools ──────────────────────────────────────────────────────────────

    def show_cors_window(self) -> None:
        rows = self.tree_widget.selectionModel().selectedRows()
        if rows:
            node = rows[0].data(Qt.UserRole)
            if node and node.s3_object.type == ObjectType.BUCKET:
                self.cors_window = CORSWindow(bucket_name=self.get_bucket_name_from_selected_item())
                self.cors_window.show()

    def show_acl_window(self) -> None:
        rows = self.tree_widget.selectionModel().selectedRows()
        if rows:
            node = rows[0].data(Qt.UserRole)
            if node and node.s3_object.type == ObjectType.BUCKET:
                self.acl_window = ACLWindow(bucket_name=self.get_bucket_name_from_selected_item())
                self.acl_window.show()

    @async_slot
    async def get_presigned_download_url(self) -> None:

        rows = self.tree_widget.selectionModel().selectedRows()
        if not rows:
            return
        node = rows[0].data(Qt.UserRole)
        if not node or node.s3_object.type != ObjectType.FILE:
            return
        bucket_name = self.get_bucket_name_from_selected_item()
        file_key = self.get_object_key_from_selected_item()
        expires_dialog = TimeIntervalDialog(
            parent=self,
            title="Expire Time?",
            default_unit=TimeIntervalDialog.Unit.HOURS,
            default_value=1,
            max_seconds=604800,
        )
        if expires_dialog.exec():
            url = await asyncio.to_thread(
                s3_service.generate_presigned_url, bucket_name, file_key,
                expires_dialog.value_as_seconds,
            )
            QMessageBox.information(self, f"Presigned URL for {file_key}", url)

    # ── Misc ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self.on_credential_changed(self.credential_selector.currentIndex())
        if self.search_widget is not None and self.search_widget.isVisible():
            self.file_toolbar.disable_search()

    def search(self) -> None:
        scopes = []
        if self.tree_widget:
            for row in self.tree_widget.selectionModel().selectedRows():
                node = row.data(Qt.UserRole)
                if not node or not node.s3_object:
                    continue
                obj = node.s3_object
                if obj.type == ObjectType.BUCKET:
                    scopes.append(SearchScope(bucket_name=obj.name))
                elif obj.type == ObjectType.FOLDER:
                    scopes.append(SearchScope(bucket_name=obj.bucket_name, prefix=obj.key))
        self.search_widget = SearchWidget(main_widget=self, scopes=scopes)
        self.file_toolbar.disable_search()
        self.layout.addWidget(self.search_widget)

    def open_about_window(self) -> None:
        AboutDialog(parent=self).exec()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.spinner and self.tree_widget_wrapper:
            wr = self.tree_widget_wrapper.geometry()
            self.spinner.move(
                wr.x() + wr.width() - self.spinner.width() - 8,
                wr.y() + 8,
            )
