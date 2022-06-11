#!/usr/bin/env python
#SETMODE 777

#----------------------------------------------------------------------------------------#
#------------------------------------------------------------------------------ HEADER --#

"""
:author:
    username

:synopsis:
    A one line summary of what this module does.

:description:
    A detailed description of what this module does.

:applications:
    Any applications that are required to run this script, i.e. Maya.

:see_also:
    Any other code that you have written that this module is similar to.
"""

#----------------------------------------------------------------------------------------#
#----------------------------------------------------------------------------- IMPORTS --#

# Default Python Imports
from PySide2 import QtGui, QtCore, QtWidgets
import os

# External
from maya_tools.guis.maya_gui_utils import get_maya_window
from maya_tools.utils.maya_utils import get_maya_pipe_context, IOM
from maya_tools.guis.maya_guis import ConfirmDialog
from maya_tools.utils.pose_library_utils import PoseLibraryUtil

#----------------------------------------------------------------------------------------#
#--------------------------------------------------------------------------- FUNCTIONS --#

#----------------------------------------------------------------------------------------#
#----------------------------------------------------------------------------- CLASSES --#

class PoseLibraryGUI(QtWidgets.QDialog):
    """
    Class for the GUI.
    """
    def __init__(self, context=None):
        QtWidgets.QDialog.__init__(self, parent=get_maya_window())

        self.context = context
        if not self.context:
            self.context = get_maya_pipe_context()

        self.flow_layout = None

        self.char_cb             = None
        self.selected_wrapper    = None
        self.selected_widget     = None
        self.selected_img_widget = None

        self.curr_char    = None
        self.curr_char_ns = None

        self.util = PoseLibraryUtil(self.context)


    def init_gui(self):
        """
        Builds the GUI the user will use. The tool will not show if there aren't any
        rigs referenced in the current file.
        """
        # Gather the info for the util object.
        self.util.gather_info()

        # The main hb and add the scroll area and selection layout.
        main_hb = QtWidgets.QHBoxLayout(self)
        main_hb.addWidget(self.create_scroll_area())
        main_hb.addLayout(self.create_selection_menu())

        # Add the referenced rigs to the character combobox.
        rigs_ns = []
        curr_rigs = self.util.rigs
        for char in curr_rigs:
            rigs_ns.append(char.asset_ns)
        self.char_cb.addItems(rigs_ns)

        # QDialog settings.
        self.setWindowTitle("Pose Library")
        self.setMinimumSize(500, 325)
        self.show()


    def create_scroll_area(self):
        """
        Creates the scroll area housing all the poses and their thumbnails.

        :return: The scroll area widget gui we add to the window.
        :type: QtWidgets.QScrollArea
        """
        # Base group box to parent to the scroll area.
        group_box = QtWidgets.QGroupBox()
        scroll_area = QtWidgets.QScrollArea()

        # Flow layout
        self.flow_layout = FlowLayout()

        # Set the layout of the group box then set the scroll area's widget to the grpbox.
        # Also set the parameters of the scroll area.
        group_box.setLayout(self.flow_layout)
        scroll_area.setWidget(group_box)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumWidth(250)

        return scroll_area


    def create_selection_menu(self):
        """
        Creates the side bar for all the options.

        :return: A vertical box layout.
        :type: QtWidgets.QVBoxLayout
        """
        main_vb = QtWidgets.QVBoxLayout()

        # The character combo box.
        self.char_cb = QtWidgets.QComboBox()
        self.char_cb.addItems(["None"])
        self.char_cb.currentIndexChanged["QString"].connect(self.char_changed)
        main_vb.addWidget(self.char_cb)

        # Add a new pose button.
        add_btn = QtWidgets.QPushButton("Add")
        add_btn.clicked.connect(self.add_btn_clicked)
        main_vb.addWidget(add_btn)

        # Apply a pose button.
        apply_btn = QtWidgets.QPushButton("Apply")
        apply_btn.clicked.connect(self.apply_btn_clicked)
        main_vb.addWidget(apply_btn)

        # Select pose's controls
        pose_ctrl_btn = QtWidgets.QPushButton("Pose Controls")
        pose_ctrl_btn.clicked.connect(self.sel_pose_ctrls)
        main_vb.addWidget(pose_ctrl_btn)

        # Update a pose button.
        update_pose_btn = QtWidgets.QPushButton("Update Pose")
        update_pose_btn.clicked.connect(self.update_pose_btn_clicked)
        main_vb.addWidget(update_pose_btn)

        # Update Pose options to overwrite the selection set or not.
        self.overwrite_pose_cb = QtWidgets.QCheckBox("Overwrite Selection Set")
        main_vb.addWidget(self.overwrite_pose_cb)

        # Update thumbnail button.
        update_thbnail_btn = QtWidgets.QPushButton("Update Thumbnail")
        update_thbnail_btn.clicked.connect(self.update_thbnail_btn_clicked)
        main_vb.addWidget(update_thbnail_btn)

        # Delete the pose button.
        delete_btn = QtWidgets.QPushButton("Delete")
        delete_btn.clicked.connect(self.del_btn_clicked)
        main_vb.addWidget(delete_btn)

        # Options button for the other options button. Will be useful when implementing
        # locally so the user can set their file destination and save out.
        # options_btn = QtWidgets.QPushButton("Options")
        # main_vb.addWidget(options_btn)

        return main_vb


    def char_changed(self, item):
        """
        Clears the scroll area and populates the character's poses.

        :param item: The new item the combo box changed to.
        :type: str
        """
        # Verify the item changed.
        value = str(item)
        if value == "None" or value == "":
            self.clear_scroll_area()
            self.util.change_char()
            return None

        # Clear the scroll area.
        self.clear_scroll_area()

        # Reset the current character and namespaces.
        self.curr_char = self.find_match_from_cb()
        self.curr_char_ns = value
        self.util.change_char(self.curr_char, self.curr_char_ns)

        # Set the selected and populate the scroll area with the current character.
        self.selected_wrapper = None
        self.selected_widget = None
        self.selected_img_widget = None
        self.populate_scroll_area()


    def clear_scroll_area(self):
        """
        Clears the scroll area by removing all the widgets.
        """
        # Remove all the items in reverse order.
        for layout_index in reversed(range(self.flow_layout.count())):

            # Dig to the qlabel widgets.
            widget_item = self.flow_layout.itemAt(layout_index)
            curr_widget = widget_item.widget()
            widget_vb = curr_widget.layout()
            qlabel = widget_vb.itemAt(1).widget()
            qlabel_img = widget_vb.itemAt(0).widget()

            # Remove the inner widgets then the widget.
            qlabel.setParent(None)
            qlabel_img.setParent(None)
            curr_widget.setParent(None)


    def find_match_from_cb(self):
        """
        Finds the character for the combo box. B/c the combo box only holds the
        namespaces from the RefAssetData, we can use our dictionary to track which asset
        the namespace is with.

        :return: The character from the combo box.
        :type: str
        """
        # Iterate through the match_char_dict finding a character to match up with a
        # namespace.
        found_char = None
        char_dict = self.util.match_char_dict
        for char in char_dict:
            if self.char_cb.currentText() in char_dict[char]:
                found_char = char
                return found_char

        # If we didn't find a character from the combobox, something went wrong from
        # populating the combobox to find this.
        if not found_char:
            IOM.error("The combo box does not have a match in the char dictionary.")
            return None


    def populate_scroll_area(self):
        """
        Populates the scroll area with what was found
        """
        # Get the character from the combo box.
        char = self.curr_char

        # Check if the pose_paths has anything or that the character has any poses.
        pose_paths = self.util.pose_paths
        if pose_paths is None or not char in pose_paths.keys():
            return None

        # Get the characters poses.
        poses = pose_paths[char]
        for pose in poses:
            self.create_pose_display(char, pose)


    def item_clicked(self):
        """
        Set label and image widgets from what was selected.
        """
        if self.sender():
            # Using the obj name, we can find out the widget of the label and img.
            clicked_obj_name = str(self.sender().objectName())

            # Find the title qlabel, image qlabel, and the wrapper widget.
            qlabel, img_widget, wrapper = self._find_widget(clicked_obj_name)

            # If we didn't get a qlabel then we don't do anything.
            if not qlabel:
                IOM.warning("Can't find a label to set selected" % qlabel)
                return None

            # If this is the first time selecting anything then set it to the sender.
            if not self.selected_widget:
                self.selected_wrapper = wrapper
                self.selected_widget = qlabel
                self.selected_img_widget = img_widget

            # Set the widget before this one to display as unselected.
            self.selected_wrapper.setStyleSheet("background-color: #2B2B2B")

            # Then set the current widget to display as selected.
            self.selected_wrapper = wrapper
            self.selected_widget = qlabel
            self.selected_img_widget = img_widget
            self.selected_wrapper.setStyleSheet("background-color: #45733D")


    def add_btn_clicked(self):
        """
        Creates a new pose, and adds to the GUI after the files are created.
        """
        # Asks the user what the name should be.
        text, ok = QtWidgets.QInputDialog().getText(self, "Name your pose", "Pose name:")

        # If nothing is entered, then quit.
        if text == "":
            return None

        # Get the character name and make the file name we'll write out.
        char = self.curr_char

        self.util.add_pose(text, char)

        # Create the GUI element added onto the scroll area.
        self.create_pose_display(char, text)


    def create_pose_display(self, char=None, pose_name=None):
        """
        Creates the VBox and QLabel GUI elements for the pose. Creating
        "octoNinja_turn_wheel". "octoNinja" is the prefix, and "turn_wheel" is the suffix.

        :param char: The character's name, will be the suffix.
        :type: str

        :param pose_name: The pose's name, will be the prefix.
        :type: str
        """
        # Check if there is a character or pose name passed in.
        if char is None or pose_name is None:
            return None
        # The base vb we'll add the inner widgets to.
        add_vb = QtWidgets.QVBoxLayout()

        # If the image already exists, use that, otherwise we just put its name.
        pose_paths = self.util.pose_paths
        image_path = pose_paths[char][pose_name]["img"]
        if os.path.exists(image_path):
            img_lbl = SignalLabel(image=image_path)
        else:
            img_lbl = SignalLabel(text="%s" % pose_name)

        # We distinguish the img and title by adding ".png" to the ObjectName.
        # This is also where we set the minimumHeight.
        img_lbl.setObjectName("%s.png" % pose_name)
        img_lbl.setMinimumHeight(100)
        img_lbl.labelClicked.connect(self.item_clicked)

        # The pose title
        title_lbl = SignalLabel("%s" % pose_name)
        title_lbl.setObjectName("%s" % pose_name)
        title_lbl.labelClicked.connect(self.item_clicked)

        # Add to the pose vbox.
        add_vb.addWidget(img_lbl)
        add_vb.addWidget(title_lbl)

        # Add it to the flow layout by making a wrapper widget to put the vb in.
        wrapper_widget = QtWidgets.QWidget()
        wrapper_widget.setLayout(add_vb)
        wrapper_widget.setStyleSheet("background-color: #2B2B2B")
        self.flow_layout.addWidget(wrapper_widget)


    def apply_btn_clicked(self):
        """
        Apply button is clicked and will check whatever is the selected widget to apply
        it.
        """
        # Check if anything is selected first.
        if not self.selected_widget:
            IOM.error("Nothing is selected.")
            return None

        # Get the character from the combo box.
        pose_selected = self.selected_widget.objectName()
        char = self.curr_char

        # Try to apply the pose.
        self.util.apply_pose(pose_selected, char)


    def update_pose_btn_clicked(self):
        """
        Confirms the change with the user, then updates the pose by updating the XML,
        handling if the user wants to overwrite the selection set.
        """
        # Confirms with the user if they want to overwrite the pose.
        title = "Update Pose"
        message = "Are you sure you want to overwrite this pose's data?"
        confirm_dialog = ConfirmDialog(message=message, title=title)
        confirm_dialog.init_gui()
        if not confirm_dialog.result:
            return None

        # Ensure there is a selected pose.
        if not self.selected_widget:
            IOM.error("There is no selected item.")
            return None

        # Get the pose name and use it to find the info in the poses dictionary.
        pose_selected = self.selected_widget.objectName()
        if self.overwrite_pose_cb.isChecked() == True:
            self.util.update_pose_data(pose_selected, True)
        else:
            self.util.update_pose_data(pose_selected)


    def update_thbnail_btn_clicked(self):
        """
        Confirm with the user first. Update the thumbnail of the selected widget by
        taking another screenshot and overwriting the old one.
        """
        # Confirms with the user if they want to overwrite the thumbnail.
        title = "Update Thumbnail"
        message = "Are you sure you want to overwrite this pose's thumbnail?"
        confirm_dialog = ConfirmDialog(message=message, title=title)
        confirm_dialog.init_gui()
        if not confirm_dialog.result:
            return None

        # Ensure there is a selected pose.
        if not self.selected_widget:
            IOM.error("There is no selected item.")
            return None

        # Get the pose name and use it to find the info in the poses dictionary.
        pose_selected = self.selected_widget.objectName()

        # Try to update the thumbnail.
        pose_img = self.util.update_thbnail(pose_selected)

        # If we didn't get a valid img path, then don't change the thumbnail.
        if not pose_img:
            return None
        self.selected_img_widget.setPixmap(pose_img)


    def _find_widget(self, obj_name):
        """
        Attempts to finds a widget in the layout with the name sent in.

        :param obj_name: The object name we're looking for.
        :type: str

        :return: The QLabel widget the name is attached to, and the qlabel of the img.
        :type: QtWidgets.QLabel, QtWidgets.QLabel
        """
        # Start at the flow layout.
        wrapper = None
        qlabel = None
        qlabel_img = None
        for layout_index in range(self.flow_layout.count()):
            # Derive the vbox from the widget item and match it with the title of what
            # was selected.
            widget_item = self.flow_layout.itemAt(layout_index)
            curr_widget = widget_item.widget()
            widget_vb = curr_widget.layout()

            # We can get the GUI item's title then test if it is within the obj_name.
            # So "pose_name.png" will still find the item_title "pose_name".
            item_title = widget_vb.itemAt(1).widget().text()
            if item_title in obj_name:
                # 0 is the img, 1 is the label under.
                wrapper = curr_widget
                qlabel = widget_vb.itemAt(1).widget()
                qlabel_img = widget_vb.itemAt(0).widget()

        # If we didn't get a qlabel then we don't do anything.
        if not qlabel:
            return None

        return qlabel, qlabel_img, wrapper


    def del_btn_clicked(self):
        """
        Confirm with the user on the change. Delete the files then delete them from the
        class's pose_paths dictionary.
        """
        # Confirms with the user if they want to delete the pose.
        title = "Delete Pose"
        message = "Are you sure you want to delete this pose?\n" \
                  "This will delete from the network drive, meaning other animators\n" \
                  "will also have this pose deleted."
        confirm_dialog = ConfirmDialog(message=message, title=title)
        confirm_dialog.init_gui()
        if not confirm_dialog.result:
            return None

        # Ensure there is a selected pose.
        if not self.selected_widget:
            IOM.error("There is no selected item.")
            return None

        # Get the pose name and use it to find the info in the poses dictionary.
        pose_selected = self.selected_widget.objectName()
        self.util.delete_pose(pose_selected)

        # Clear the scroll area then repopulate it.
        self.clear_scroll_area()
        self.populate_scroll_area()
        self.selected_widget = None


    def sel_pose_ctrls(self):
        """
        Selects the pose's controls.
        """
        # Ensure there is a selected pose.
        if not self.selected_widget:
            IOM.error("There is no selected item.")
            return None

        # Get the pose name and use it to find the info in the poses dictionary.
        pose_selected = self.selected_widget.objectName()
        self.util.select_pose_ctrls(pose_selected)


class FlowLayout(QtWidgets.QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super(FlowLayout, self).__init__(parent)

        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)

        self.setSpacing(spacing)

        self.itemList = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if index >= 0 and index < len(self.itemList):
            return self.itemList[index]

        return None

    def takeAt(self, index):
        if index >= 0 and index < len(self.itemList):
            return self.itemList.pop(index)

        return None

    def expandingDirections(self):
        return QtCore.Qt.Orientations(QtCore.Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.doLayout(QtCore.QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()

        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())

        margin, _, _, _ = self.getContentsMargins()

        size += QtCore.QSize(2 * margin, 2 * margin)
        return size

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0

        for item in self.itemList:
            wid = item.widget()
            spaceX = self.spacing() + wid.style().layoutSpacing(
                                                        QtWidgets.QSizePolicy.PushButton,
                                                        QtWidgets.QSizePolicy.PushButton,
                                                        QtCore.Qt.Horizontal)
            spaceY = self.spacing() + wid.style().layoutSpacing(
                                                        QtWidgets.QSizePolicy.PushButton,
                                                        QtWidgets.QSizePolicy.PushButton,
                                                        QtCore.Qt.Vertical)
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))

            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())

        return y + lineHeight - rect.y()


class SignalLabel(QtWidgets.QLabel):
    """
    Child of QLabel to create a signal and shoot it whenever the mouse is pressed. Also
    will handle adding images and the dimensions.
    """
    labelClicked = QtCore.Signal(str) # can be other types (list, dict, object...)

    def __init__(self, text=None, image=None, parent=None):
        super(SignalLabel, self).__init__(parent)
        if text:
            self.setText(text)
        if image:
            self.setPixmap(image)

        self.setFixedWidth(100)

    def mousePressEvent(self, event):
        self.labelClicked.emit("emit the signal")


