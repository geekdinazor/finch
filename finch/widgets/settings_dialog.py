from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
    QWidget, QCheckBox, QLabel, QFrame, QStackedWidget,
    QListWidgetItem, QToolBar, QTableView, QHeaderView,
    QAction, QStyledItemDelegate, QItemDelegate, QStyle, QStyleOptionButton, QApplication, QAbstractItemView
)
from PyQt5.QtCore import Qt, QSize, QRect, QPoint
from PyQt5.QtGui import QIcon, QFont, QPalette

from finch.config import CHECK_FOLDER_CONTENTS
from finch.models.credentials_model import CredentialsModel


class SettingsDialog(QDialog):
    # Define icon map as class attribute
    ICON_MAP = {
        "Credentials": "credentials.svg",
        "UI Settings": "settings.svg",
        "S3 Settings": "settings.svg",
        "Logging": "settings.svg",
        "About": "about.svg"
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(1200, 500)
        
        # Create main layout
        layout = QHBoxLayout()
        self.setLayout(layout)
        
        # Create list widget for navigation
        self.list_widget = QListWidget()
        self.list_widget.setFixedWidth(200)
        self.list_widget.setFrameShape(QFrame.NoFrame)

        # Get system colors for better theme compatibility
        palette = self.palette()
        base_color = palette.color(QPalette.Base)
        text_color = palette.color(QPalette.Text)

        # Determine theme and create colors with proper opacity
        is_light_theme = self.palette().color(QPalette.Window).lightness() > 128
        highlight_color = "#1B5E20" if is_light_theme else "#388E3C"  # Dark/Light Material Green 900/700
        hover_color = "#1E1E1E" if is_light_theme else "#FFFFFF"
        hover_rgba = f"rgba({int(hover_color[1:3], 16)}, {int(hover_color[3:5], 16)}, {int(hover_color[5:7], 16)}, 0.07)"

        # Create border color with opacity
        border_rgba = f"rgba({text_color.red()}, {text_color.green()}, {text_color.blue()}, 0.2)"

        self.list_widget.setStyleSheet(f"""
            QListWidget, QListView {{
                background-color: {base_color.name()};
                border-right: 1px solid {text_color.name()};
                color: {text_color.name()};
                outline: 0;  /* Remove focus outline */
            }}
            QListWidget::item, QListView::item {{
                padding: 10px;
                border-bottom: 1px solid {border_rgba};
            }}
            QListWidget::item:selected, QListView::item:selected {{
                background-color: {highlight_color};
                color: white;
                font-weight: bold;
            }}
            QListWidget::item:hover:!selected, QListView::item:hover:!selected {{
                background-color: {hover_rgba};
            }}
            /* Override system highlight color */
            QListWidget::item:selected:active, QListView::item:selected:active,
            QListWidget::item:selected:!active, QListView::item:selected:!active {{
                background-color: {highlight_color};
                color: white;
            }}
        """)
        
        # Set icon size for list items
        self.list_widget.setIconSize(QSize(20, 20))

        # Create stacked widget for pages
        self.stack = QStackedWidget()
        
        # Add pages one by one
        self._add_page("Credentials", self._create_credentials_page())
        self._add_page("UI Settings", self._create_ui_settings_page())
        self._add_page("S3 Settings", self._create_s3_settings_page())
        self._add_page("Logging", self._create_logging_page())
        self._add_page("About", self._create_about_page())
        
        # Connect list selection to stack
        self.list_widget.currentRowChanged.connect(self.stack.setCurrentIndex)

        # Select first item
        self.list_widget.setCurrentRow(0)

        # Add widgets to layout
        layout.addWidget(self.list_widget)
        layout.addWidget(self.stack, 1)
        
        # Remove margins between list and stack
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

    def _add_page(self, title, page_widget):
        """Add a page to both list and stack"""
        item = QListWidgetItem()
        
        if title in self.ICON_MAP:
            item.setIcon(QIcon(f":/icons/{self.ICON_MAP[title]}"))
        
        item.setText(title)
        self.list_widget.addItem(item)
        self.stack.addWidget(page_widget)

    def _create_page_widget(self):
        """Create a base widget for a settings page"""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        page.setLayout(layout)
        return page, layout

    def _add_category_title(self, layout, title):
        """Add a category title to a settings page"""
        title_container = QWidget()
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_container.setLayout(title_layout)
        
        if title in self.ICON_MAP:
            icon_label = QLabel()
            icon = QIcon(f":/icons/{self.ICON_MAP[title]}")
            icon_label.setPixmap(icon.pixmap(QSize(24, 24)))
            icon_label.setContentsMargins(0, 0, 10, 0)  # Add right margin
            title_layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setWeight(QFont.Light)
        title_label.setFont(title_font)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        title_container.setContentsMargins(0, 0, 0, 20)  # Bottom margin
        layout.addWidget(title_container)

    def _create_credentials_page(self):
        page, layout = self._create_page_widget()
        self._add_category_title(layout, "Credentials")
        
        try:
            # Create toolbar
            credential_toolbar = QToolBar("Credential")
            credential_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            
            # Add credential action
            add_row_action = QAction(page)
            add_row_action.setText("&Create Credential")
            add_row_action.setIcon(QIcon(':/icons/new-credential.svg'))
            credential_toolbar.addAction(add_row_action)
            
            # Create table view with model
            self.table_data = QTableView(page)
            self.credentials_model = CredentialsModel()
            self.table_data.setModel(self.credentials_model)

            self.table_data.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.table_data.setSelectionMode(QAbstractItemView.SingleSelection)
            
            # Configure header
            header = self.table_data.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeToContents)
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QHeaderView.Stretch)
            
            # Style table
            self.table_data.setStyleSheet("""
            QTableView::item {
                padding: 5px;
            }
            """)
            
            # Set up delegates
            table_view_editor_delegate = self.TableViewEditorDelegate(self.table_data)
            self.table_data.setItemDelegate(table_view_editor_delegate)
            
            # Password delegate for column 5
            password_delegate = self.PasswordDelegate(self.table_data)
            self.table_data.setItemDelegateForColumn(5, password_delegate)
            
            # SSL delegates for columns 2 and 3
            ssl_delegate = self.CheckBoxDelegate(self.table_data)
            self.table_data.setItemDelegateForColumn(2, ssl_delegate)
            self.table_data.setItemDelegateForColumn(3, ssl_delegate)
            
            # Add widgets to layout
            layout.addWidget(credential_toolbar)
            layout.addWidget(self.table_data)
            
        except Exception as e:
            error_label = QLabel(f"Error loading credentials: {str(e)}")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)
        
        return page

    def _create_ui_settings_page(self):
        page, layout = self._create_page_widget()
        self._add_category_title(layout, "UI Settings")

        # Create check empty folders option
        check_empty = QCheckBox("Check Empty Buckets && Folders")
        check_empty.setChecked(CHECK_FOLDER_CONTENTS)
        check_empty.stateChanged.connect(self._on_check_empty_changed)

        # Add description with system color
        description = QLabel(
            "This option removes the expand arrow from empty buckets and folders. "
            "It may slows down the navigation and increase the S3 costs."
        )
        description.setWordWrap(True)

        # Use system colors with reduced opacity for description
        palette = self.palette()
        text_color = palette.color(QPalette.Text)
        description.setStyleSheet(f"color: {text_color.name()}99;")  # 60% opacity

        # Add to layout
        layout.addWidget(check_empty)
        layout.addWidget(description)
        layout.addStretch()

        return page

    def _create_s3_settings_page(self):
        page, layout = self._create_page_widget()
        self._add_category_title(layout, "S3 Settings")
        layout.setAlignment(Qt.AlignTop)  # Center empty page
        return page

    def _create_logging_page(self):
        page, layout = self._create_page_widget()
        self._add_category_title(layout, "Logging")
        layout.setAlignment(Qt.AlignTop)  # Center empty page
        return page

    def _create_about_page(self):
        page, layout = self._create_page_widget()
        self._add_category_title(layout, "About")
        layout.setAlignment(Qt.AlignTop)

        # Add icon
        icon = QIcon(":/icons/icon.png").pixmap(QSize(100, 100))
        icon_label = QLabel()
        icon_label.setPixmap(icon)
        icon_label.setAlignment(Qt.AlignCenter)

        # Add title
        title_label = QLabel("Finch S3 Client")
        title_label.setFont(QFont('sans', 30))
        title_label.setAlignment(Qt.AlignCenter)

        # Add subtitle with links
        subtitle_label = QLabel(
            'In memoriam of <a href="https://personofinterest.fandom.com/wiki/Root">root</a> and '
            '<a href="https://personofinterest.fandom.com/wiki/Harold_Finch">Harold Finch</a>'
        )
        subtitle_font = QFont('sans', 12)
        subtitle_font.setItalic(True)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setOpenExternalLinks(True)

        # Add version
        version_label = QLabel('v1.0 BETA')
        version_label.setFont(subtitle_font)
        version_label.setAlignment(Qt.AlignCenter)

        # Add contributors section
        contributors_label = QLabel("<strong>Contributors:</strong>")
        contributors_label.setContentsMargins(0, 20, 0, 0)
        contributors_label.setAlignment(Qt.AlignCenter)

        # Add contributors list
        contributors = ['Furkan Kalkan <furkankalkan@mantis.com.tr>']
        contributors_text = QLabel('\n'.join(contributors))
        contributors_text.setAlignment(Qt.AlignCenter)

        # Add all widgets to layout
        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addWidget(version_label)
        layout.addWidget(contributors_label)
        layout.addWidget(contributors_text)
        layout.addStretch()

        return page

    def _on_check_empty_changed(self, state):
        """Handle check empty folders option change"""
        import finch.config as config
        config.CHECK_FOLDER_CONTENTS = bool(state)
        # Notify tree view to refresh if needed
        if hasattr(self.parent(), 's3_tree'):
            self.parent().s3_tree.refresh()

    class TableViewEditorDelegate(QItemDelegate):
        def setEditorData(self, editor, index):
            editor.setAutoFillBackground(True)
            editor.setText(index.data())

    class PasswordDelegate(QStyledItemDelegate):
        def __init__(self, parent=None):
            super().__init__(parent)

        def initStyleOption(self, option, index):
            super().initStyleOption(option, index)

            style = option.widget.style() or QApplication.style()
            hint = style.styleHint(QStyle.SH_LineEdit_PasswordCharacter)
            if len(index.data()) > 0:
                option.text = chr(hint) * 6

    class CheckBoxDelegate(QStyledItemDelegate):
        def __init__(self, parent=None):
            super().__init__(parent)

        def createEditor(self, parent, option, index):
            return None

        def editorEvent(self, event, model, option, index):
            if not index.isValid():
                return False
                
            if event.type() == event.MouseButtonRelease:
                try:
                    current_value = index.data(Qt.EditRole)
                    if current_value is None:
                        current_value = False
                    return model.setData(index, not bool(current_value), Qt.EditRole)
                except Exception as e:
                    print(f"Error in checkbox delegate: {str(e)}")
                    return False
            return False

        def paint(self, painter, option, index):
            if not index.isValid():
                return
                
            try:
                painter.save()
                
                # Get the style from the parent widget
                style = option.widget.style() or QApplication.style()
                
                # Draw the item background
                style.drawControl(QStyle.CE_ItemViewItem, option, painter, option.widget)
                
                # Setup the style option for the checkbox
                check_option = QStyleOptionButton()
                check_option.state = QStyle.State_Enabled
                
                # Safely get the value
                value = index.data(Qt.EditRole)
                if value is None:
                    value = False
                    
                if bool(value):
                    check_option.state |= QStyle.State_On
                else:
                    check_option.state |= QStyle.State_Off
                    
                # Center the checkbox
                check_rect = style.subElementRect(QStyle.SE_CheckBoxIndicator, check_option, option.widget)
                if check_rect.isValid():
                    check_point = QPoint(
                        option.rect.x() + option.rect.width() // 2 - check_rect.width() // 2,
                        option.rect.y() + option.rect.height() // 2 - check_rect.height() // 2
                    )
                    check_option.rect = QRect(check_point, check_rect.size())
                    
                    # Draw the checkbox using the native style
                    style.drawControl(QStyle.CE_CheckBox, check_option, painter, option.widget)
                
                painter.restore()
                
            except Exception as e:
                print(f"Error painting checkbox: {str(e)}")
                if painter.isActive():
                    painter.restore()
