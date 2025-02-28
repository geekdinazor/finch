from PyQt5.QtCore import QModelIndex, QTimer
from PyQt5.QtWidgets import QInputDialog, QMessageBox
from finch.services.s3_service import ObjectType
from finch.utils.strings import format_list_with_conjunction
from finch.views.error import show_error_dialog
from finch.models.file_tree_model import S3Node


def _create_delete_dialog_info(nodes, indexes):
    """Create delete dialog information based on node types"""
    # Filter out child nodes if their parent is also being deleted
    filtered_nodes = []
    filtered_indexes = []
    
    for node, index in zip(nodes, indexes):
        # Check if any parent of this node is in the nodes list
        parent_in_list = False
        current = node
        while current.parent and not parent_in_list:
            if current.parent in nodes:
                parent_in_list = True
            current = current.parent
        
        if not parent_in_list:
            filtered_nodes.append(node)
            filtered_indexes.append(index)

    # Extract node information
    node_info = {
        'names': [node.name for node in filtered_nodes],
        'keys': [node.key for node in filtered_nodes],
        'types': [node.type for node in filtered_nodes],
        'buckets': [node.bucket for node in filtered_nodes],
        'nodes': filtered_nodes,  # Keep the filtered nodes for deletion
        'indexes': filtered_indexes  # Keep the corresponding indexes
    }
    
    # Create display names for details
    display_names = [
        f'"{key}" (on "{bucket}" bucket)' 
        for key, bucket in zip(node_info['keys'], node_info['buckets'])
    ]
    details = f"* {format_list_with_conjunction(display_names, seperator=' \n* ', conjunction='\n*')}"

    # Determine message and title based on type and count
    if all(t == ObjectType.BUCKET for t in node_info['types']):
        object_type = ObjectType.BUCKET
        message = (
            f"You're going to delete {format_list_with_conjunction(node_info['names'])} bucket(s).\n\n"
            "All objects will be deleted from this bucket(s). This operation cannot be undone. Are you sure?"
        )
        
    elif all(t == ObjectType.FOLDER for t in node_info['types']):
        object_type = ObjectType.FOLDER
        if len(node_info['names']) == 1:
            message = (
                f"You're going to delete folder {node_info['names'][0]}.\n\n"
                "All objects will be deleted from this folder. This operation cannot be undone. Are you sure?"
            )
        else:
            message = (
                f"You're going to delete {node_info['names'][0]} and {len(node_info['names']) - 1} more folders.\n"
                "Please review folders before deleting.\n\n"
                "This operation cannot be undone. Are you sure?"
            )
            
    elif all(t == ObjectType.FILE for t in node_info['types']):
        object_type = ObjectType.FILE
        if len(node_info['names']) == 1:
            message = (
                f"You're going to delete file {node_info['names'][0]}.\n\n"
                "This operation cannot be undone. Are you sure?"
            )
        else:
            message = (
                f"You're going to delete {node_info['names'][0]} and {len(node_info['names']) - 1} more files.\n"
                "Please review files before deleting.\n\n"
                "This operation cannot be undone. Are you sure?"
            )
    else:
        return None, None, None, None, None

    title = f"Delete {object_type.name.title()}(s)"
    
    return message, title, details, object_type, node_info


def global_delete(tree_view=None):
    """Handle global delete action based on selection"""
    if not tree_view:
        return
        
    selected_indexes = tree_view.selectionModel().selectedRows()
    selected_nodes = [tree_view.model.get_node(index) for index in selected_indexes]
    
    # Get dialog information
    message, title, details, object_type, node_info = _create_delete_dialog_info(selected_nodes, selected_indexes)
    if not message:
        show_error_dialog("Cannot delete mixed types of objects")
        return
        
    # Show confirmation dialog
    dlg = QMessageBox()
    dlg.setIcon(QMessageBox.Warning)
    dlg.setWindowTitle(title)
    dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    dlg.setDefaultButton(QMessageBox.No)
    dlg.setText(message)
    dlg.setDetailedText(details)
    
    if dlg.exec_() == QMessageBox.Yes:
        try:
            if object_type == ObjectType.BUCKET:
                # For buckets, delete from root
                for index in node_info['indexes']:
                    tree_view._s3_service.delete_bucket(node_info['nodes'][0].bucket)
                    tree_view.model.removeRow(index.row())
                
            elif object_type == ObjectType.FOLDER or object_type == ObjectType.FILE:
                # Delete objects from S3 and remove from model
                for index, node in zip(node_info['indexes'], node_info['nodes']):
                    if object_type == ObjectType.FOLDER:
                        tree_view._s3_service.delete_object(node.bucket, node.key + '/')
                    else:
                        tree_view._s3_service.delete_object(node.bucket, node.key)
                        
                    # Remove from model
                    parent = index.parent()
                    if parent.isValid():
                        tree_view.model.removeRow(index.row(), parent)
                
        except Exception as e:
            show_error_dialog(f"Error deleting objects: {str(e)}")

def restore_bucket_states(tree_view, bucket_states):
    """Restore the expanded state of buckets by name"""
    for row in range(tree_view.model.rowCount()):
        index = tree_view.model.index(row, 0)
        node = tree_view.model.get_node(index)
        if node and node.type == ObjectType.BUCKET:
            if node.name in bucket_states:
                tree_view.setExpanded(index, bucket_states[node.name])


def global_create(tree_view=None):
    """Handle global create action based on selection"""
    if not tree_view:
        return
        
    selected_indexes = tree_view.selectionModel().selectedRows()
    
    try:
        if not selected_indexes:
            # No selection - create bucket
            bucket_name, ok = QInputDialog.getText(
                tree_view,
                "Create Bucket",
                "Enter bucket name:"
            )
            if ok and bucket_name:
                tree_view._s3_service.create_bucket(bucket_name)
                # Create new bucket node
                new_node = S3Node(
                    name=bucket_name,
                    type=ObjectType.BUCKET,
                    bucket=bucket_name
                )
                tree_view.model.appendRow(QModelIndex(), new_node)
                
        if len(selected_indexes) == 1:
            # Get selected node
            selected_index = selected_indexes[0]
            selected_node = tree_view.model.get_node(selected_index)
                
            # Get folder name
            folder_name, ok = QInputDialog.getText(
                tree_view,
                "Create Folder",
                "Enter folder name:"
            )
            
            if ok and folder_name:
                try:
                    # Determine full path based on selection
                    if selected_node.type == ObjectType.BUCKET:
                        folder_path = folder_name
                        bucket_name = selected_node.name
                    elif selected_node.type == ObjectType.FOLDER:
                        if selected_node.key:
                            base_path = selected_node.key.rstrip('/')
                            folder_path = f"{base_path}/{folder_name}"
                        else:
                            folder_path = folder_name
                        bucket_name = selected_node.bucket
                    
                    # Create the folder in S3
                    tree_view._s3_service.create_folder(bucket_name, folder_path)
                    
                    # Create new folder node
                    new_node = S3Node(
                        name=folder_name,
                        type=ObjectType.FOLDER,
                        bucket=bucket_name,
                        key=folder_path
                    )
                    
                    # Always append the new node first
                    tree_view.model.appendRow(selected_index, new_node)
                    
                    # If not expanded, expand it after a delay
                    if not tree_view.isExpanded(selected_index):
                        QTimer.singleShot(100, lambda: tree_view.expand(selected_index))
                    
                except Exception as e:
                    show_error_dialog(f"Error creating folder: {str(e)}")
                
    except Exception as e:
        show_error_dialog(str(e))










