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
import os
from os.path import isfile, join
import maya.cmds as cmds
from xml.dom import minidom
import xml.etree.ElementTree as et

# External
from maya_tools.utils.maya_utils import get_assets_from_refs, get_maya_pipe_context, IOM
from gen_utils.pipe_enums import FileExtensions
from gen_utils.utils import IO, AutoVivification
from maya_tools.guis.maya_guis import PreviewImage

#----------------------------------------------------------------------------------------#
#--------------------------------------------------------------------------- FUNCTIONS --#

#----------------------------------------------------------------------------------------#
#----------------------------------------------------------------------------- CLASSES --#

class PoseLibraryUtil(object):
    """
    Class for the utils for the GUI.
    """
    def __init__(self, context=None):

        self.context = context
        if not self.context:
            self.context = get_maya_pipe_context()

        self.rigs = None
        self.pose_search_dir = None
        self.proj_data_path = None
        self.proj_imgs_path = None

        self.match_char_dict = None
        self.pose_paths = None

        self.curr_char    = None
        self.curr_char_ns = None


    def gather_info(self):
        """
        Will gather the information at the start.
        """
        # Check for any referenced rigs in the current Maya file. The tool won't launch if
        # there aren't any rigs in the scene.
        self.rigs = self.check_for_rigs()
        if not self.rigs:
            return None

        # Get the project's pose_library tool's data and images directory. If there is
        # Get the project's pose_library tool's data and images directory. If there is
        # no data dir or we can't make the dir then we can't load any poses.
        data, imgs = self.get_pose_dir()
        if not data:
            return None

        # Match the referenced rigs to a character. This keeps the naming consistent.
        self.match_rigs_to_char()

        # Find any poses for any characters. We'll make a dictionary all we found.
        self.find_poses()


    def change_char(self, new_char=None, new_char_ns=None):
        """
        Update the current character and character namespace we're working on.
        """
        # If the combo box is empty or is the string "None", don't do anything.
        if new_char == "" or new_char == "None":
            self.curr_char = None
            self.curr_char_ns = None
            return None

        # If the combo box is None then don't do anything.
        if new_char is None or new_char_ns is None:
            self.curr_char = None
            self.curr_char_ns = None
            return None

        # When we have valid data, then set the class attrs.
        self.curr_char = new_char
        self.curr_char_ns = new_char_ns



    def check_for_rigs(self):
        """
        Will check the current file for any rigs referenced.

        :return: Success of the operation.
        :type: bool
        """
        # Ensure we have a context to work with.
        if not self.context:
            IO.error("Could not find the context of the current Maya file.")
            return None

        # Get all references in the file.
        all_refs = get_assets_from_refs(self.context)
        if not all_refs:
            IO.error('Could not find any references in the current Maya file.')
            return None

        return all_refs


    def get_pose_paths(self, pose_name):
        """
        This will get the pose's data from the pose_paths dicitionary

        :param pose_name: The pose's name we're looking for.
        :type: str
        """
        # With the character we're currently working on, find a match in the poses dict.
        char = self.curr_char
        pose_data = None
        pose_img = None
        for pose in self.pose_paths[char]:

            # Even if the label's name is "sit.png" it can still find "sit" in it, and we
            # got a match.
            if pose == pose_name:
                pose_data = self.pose_paths[char][pose]["data"]
                pose_img = self.pose_paths[char][pose]["img"]
                break

        return pose_data, pose_img


    def get_pose_dir(self):
        """
        Gets the pose data from txt files and image files.

        :return: The file paths to the project's pose library data and imgs.
        :type: str, str
        """
        # Get the paths we need.
        kwargs = {"tool": "pose_library"}
        self.proj_data_path = self.context.eval_path(formula="pr_project_tools_data_dir",
                                                     **kwargs)
        self.proj_imgs_path = self.context.eval_path(formula="pr_project_tools_imgs_dir",
                                                     **kwargs)

        # If the data directory doesn't exist then try to make it.
        if not os.path.exists(self.proj_data_path):
            try:
                os.makedirs(self.proj_data_path, exist_ok=False)
            except WindowsError or OSError:
                IOM.error("Error trying to create the tool's \"data\" directory.")

        # If the imgs directory doesn't exist then try to make it.
        if not os.path.exists(self.proj_imgs_path):
            try:
                os.makedirs(self.proj_imgs_path, exist_ok=True)
            except WindowsError or OSError:
                IOM.error("Error trying to create the tool's \"imgs\" directory.")

        return self.proj_data_path, self.proj_imgs_path


    def match_rigs_to_char(self):
        """
        Matching namespaces to characters, so multiple namespaced rigs can share poses
        if their character is the same.

        :return: The dictionary created to match namespaces with characters. Looks like:
                 {"Tom": ["Tom", "Tom1", "Tom2", "Tom3"],
                  "octoNinja": ["octoNinja", "octoNinja1"]}
        :type: dict
        """
        # The dictionary holding the characters and their namespaces.
        self.match_char_dict = {}

        # Iterate through all the rigs we found and make a dictionary key for it.
        for item in self.rigs:
            if item.name not in self.match_char_dict:
                self.match_char_dict[item.name] = []
                self.match_char_dict[item.name].append(item.asset_ns)
            else:
                self.match_char_dict[item.name].append(item.asset_ns)

        return self.match_char_dict


    def find_poses(self):
        """
        Finds the poses in the project data path, and tries to find an image if it exists.

        :return: The dictionary of the character and its poses we found, holding the
                 data and img file paths.
                 {"octoNinja": {"sit": {"data": "C:/...", "img": "C:/..."}},
                               {"blink": {"data": "C:/...", "img": "C:/..."},
                  "character2": {"sit": {"data": "C:/...", "img": "C:/..."}}}
        :type: dict
        """
        # Check if the file path is empty.
        if not os.listdir(self.proj_data_path):
            IOM.warning("This project's pose library is empty.")
            return None

        # Find only the files, no directories.
        only_files = [f for f in os.listdir(self.proj_data_path) if \
                                isfile(join(self.proj_data_path, f))]

        # Find the characters from the data directory and add them to a dictionary.
        self.pose_paths = {}
        for curr_file in only_files:
            # Just use the base name without the file extension.
            base_name = os.path.splitext(curr_file)[0]
            # Get the index of the characters from the file path.
            # So character_A_pose_title.xml will get "character_A" and the pose is
            # "pose_title".
            char = None
            pose = None
            char_list = self.match_char_dict.keys()
            for search_char in char_list:
                # curr_file.find will search the string from the beginning until the
                # length of the search char's length. We get the exact character's
                # name on the start of the file to ensure the pose belongs to the char.
                search_char_len = len(search_char)
                char_start_index = curr_file.find(search_char, 0, search_char_len)
                # If the character is found, then get the char and pose from it.
                if char_start_index != -1:
                    char = base_name[:search_char_len]
                    pose = base_name[search_char_len+1:]
                    break
                else:
                    # the string.find will return -1 if it can't find it, so continue.
                    continue

            # If we didn't find a matching character or pose then skip this file.
            if char is None or pose is None:
                continue

            # Ensure the character is in the scene at all.
            if char not in self.match_char_dict.keys():
                continue

            # Check if the character is in the dictionary already.
            if not char in self.pose_paths:
                self.pose_paths[char] = {}

            # Check if the pose already exists, we don't want to collide.
            if not pose in self.pose_paths[char]:
                self.pose_paths[char][pose] = {"data": "%s/%s" % \
                                                    (self.proj_data_path, curr_file)}
                img_file = "%s.png" % curr_file[:-4]
                self.pose_paths[char][pose]["img"] = "%s/%s" % \
                                                    (self.proj_imgs_path, img_file)
            else:
                continue


    def _apply_attrs(self, xml_path):
        """
        Applies the attributes from the xml file to the appropriate controls.

        :param xml_path: The full path to an XML file on disk.
        :type: str
        """
        # Get the contents of the XML file.
        contents = self._read_xml(xml_path)
        namespace = self.curr_char_ns

        # Iterate through the contents dict, adding the namespace to each name.
        # And setting the attributes.
        for control in contents:
            ns_control = "%s:%s" % (namespace, control)
            for attr in contents[control]:
                value = float(contents[control][attr])
                cmds.setAttr("%s.%s" % (ns_control, attr), value)


    def _read_xml(self, xml_path):
        """
        Reads the contents of an XML file and returns it.

        :param xml_path: The full path to an XML file on disk.
        :type: str

        :return: The contents of the XML file.
        :type: dict
        """
        # Make sure the file exists.
        if not os.path.isfile(xml_path):
            IOM.error("The file path given can't be found on disk.")
            return None

        # Read in the XML and get the root.
        xml_fh = et.parse(xml_path)
        root = xml_fh.getroot()

        # Find the children of the root node. and add it to a dictionary.
        contents = AutoVivification()
        xml_ctrls = root.getchildren()
        for ctrl in xml_ctrls:
            ctrl_attrs = ctrl.getchildren()
            for ctrl_attr in ctrl_attrs:
                value = ctrl_attr.attrib["value"]
                contents[ctrl.tag][ctrl_attr.tag] = value

        return contents

    def update_pose_data(self, pose_selected, overwrite_sel_set=False):
        """
        Gather the pose paths needed, updates the pose data, and overwrite the selection
        set if applicable.

        :param pose_selected: The pose we're updating.
        :type: str

        :param overwrite_sel_set: Determine if this will overwrite the old selection set.
        :type: bool
        """
        # Get the relevant pose paths.
        pose_data, pose_img = self.get_pose_paths(pose_selected)

        # Update the pose's XML, which will overwrite everything.
        # In the future give the option to use the same controls or a new selection set.
        if pose_data:
            if overwrite_sel_set == True:
                self._update_sel_and_attrs(pose_data)
            else:
                self._update_attrs(pose_data)



    def _update_sel_and_attrs(self, pose_data):
        """
        Updates the selected pose's XML file.

        :param pose_data: The path to the pose's XML file.
        :type: str
        """
        # Get whatever is currently selected.
        selected_list = cmds.ls(selection=True)
        IOM.warning("Here is what controls will be written out: %s" % selected_list)

        # Ensure at least one object is selected.
        if not selected_list:
            IOM.error("Nothing is selected, please select controls to save out a pose.")
            return None

        # Verify every control in the currently selected is under the same namespace.
        char = self.curr_char
        if not self.verify_selection(selected_list, char):
            IOM.error("Selected failed verification step.")
            return None

        # We can now write the xml.
        xml_path = pose_data
        if not self.write_xml(selected_list, xml_path):
            IOM.error("Unable to write the XML")
            return None


    def _update_attrs(self, pose_data):
        """
        Reads the XML data, and selects all the controls that were in the file. Then
        we can use the update_sel_and_attrs function to update it.

        :param pose_data: The path to the pose's XML file.
        :type: str
        """
        # Get a dictionary of the contents.
        contents = self._read_xml(pose_data)

        # Loop through the contents and select all that is a CC
        namespace = self.curr_char_ns
        selected_list = []
        for control in contents:
            ns_control = "%s:%s" % (namespace, control)
            selected_list.append(ns_control)

        # Select the items, and update them using the update_sel_and_attrs function.
        cmds.select(selected_list)
        self._update_sel_and_attrs(pose_data)


    def update_thbnail(self, pose_selected=None):
        """
        Confirm with the user first. Update the thumbnail of the selected widget by
        taking another screenshot and overwriting the old one.

        :param pose_selected: The pose we will update the thumbnail to.
        :type: str

        :return: The image path.
        :type: str
        """
        # Get the pose img file path.
        pose_data, pose_img = self.get_pose_paths(pose_selected)

        if pose_img:
            # Derive the file name from the pose_img file path. Then capture the viewport.
            file_name = os.path.basename(pose_img)
            self.viewport_capture(file_name)

            return pose_img

        # If we didn't get a pose_img, then we return None.
        else:
            return None



    def write_xml(self, selected, xml_path=None):
        """
        Writes out the xml using what was selected.

        :param selected: Verifying the selected is handled before calling this function.
        :type: list

        :param xml_path: The file path we are writing to.
        :type: str

        :return: Success of the operation.
        :type: bool
        """
        # Check for the XML path.
        if not xml_path:
            IOM.error("No XML path entered in writing the XML.")
            return False

        # Make an XML document and write some contents to it.
        xml_doc = minidom.Document()
        root = xml_doc.createElement("root")
        xml_doc.appendChild(root)

        # Add to the XMl just the names of the controls without namespaces. So
        # for "octoNinja:l_eye_CC" will just save "l_eye_CC" to the XML.
        # In the loop, "item" is "octoNinja:l_eye_CC" which we can get the attr from.
        # "just_cc" is the "l_eye_CC" that we write to the XML.
        # When we read, we will apply the namespace to apply the pose.
        for item in selected:
            just_cc = item.split(":")[1]
            control_curve = xml_doc.createElement(just_cc)
            root.appendChild(control_curve)

            # Get the list of attributes that are keyable. Remove any dividers.
            keyable_attrs = cmds.listAttr(item, keyable=True)
            keyable_attrs = [x for x in keyable_attrs if not x.find("__") == 0]

            # Loop through all the keyable attributes and write them out.
            for curr_attr in keyable_attrs:
                attr_element = xml_doc.createElement(curr_attr)
                control_curve.appendChild(attr_element)
                attr_value = cmds.getAttr("%s.%s" % (item, curr_attr))
                attr_value = "%.3f" % attr_value
                attr_element.setAttribute("value", attr_value)

        # Now that we have everything in the XML instance, write the file to disk.
        xml_str = xml_doc.toprettyxml(indent="    ")
        with open(xml_path, "w") as fh:
            fh.write(xml_str)
        fh.close()
        return True


    def write_pose_file(self, pose_name):
        """
        Writes the file out to the project's tool settings directory.

        :param pose_name: The pose's name we'll make the name of the file with the char.
        :type: str

        :return: The path to the XML we wrote out.
        :type: str
        """
        # Verify we have a data file we can write to.
        if not self.proj_data_path:
            IOM.error("There is no data directory to write out to.")
            return None

        # Find the character the namespace in the combo box matches to.
        char = self.curr_char
        file_name = "%s_%s" % (char, pose_name)
        xml_path = "%s/%s.xml" % (self.proj_data_path, file_name)
        img_path = "%s/%s.png" % (self.proj_imgs_path, file_name)

        # Get the currently selected items from the scene.
        selected_list = cmds.ls(selection=True)
        if not selected_list:
            IOM.error("Nothing is selected, please select controls to save out a pose.")
            return None

        # Verify every control in the currently selection is under the same namespace.
        if not self.verify_selection(selected_list, char):
            IOM.error("Selected failed verification step.")
            return None

        # We can now write to the xml.
        if not self.write_xml(selected_list, xml_path):
            IOM.error("Unable to write the XML")
            return None

        # If this is the first file in the library, make it a dictionary we can add to.
        if self.pose_paths is None:
            self.pose_paths = {}

        # Add the pose info to the pose dictionary.
        if not char in self.pose_paths.keys():
            self.pose_paths[char] = {pose_name: None}
        self.pose_paths[char][pose_name] = {"data": xml_path, "img": img_path}

        return xml_path


    def viewport_capture(self, file_name):
        """
        This will set up the viewport to capture then use the PreviewImage class.
        """
        # Add these values to a RenderResEnum like a square dimension.
        width = 100
        height = 100

        # Make the destination file path.
        dest_file = "%s/%s" % (self.proj_imgs_path, file_name)

        # Make a temporary file for whatever context we are working in.
        import tempfile
        temp_dir = tempfile.mkdtemp()
        temp_file = temp_dir + "/" + file_name

        # Hide all the nurbs curves from every panel to get a clean screenshot.
        view_panels = cmds.getPanel(type="modelPanel")
        for curr_panel in view_panels:
            cmds.modelEditor(curr_panel, edit=True, nurbsCurves=False)

        # Get a screenshot from the PreviewImage
        preview = PreviewImage(temp_file, dest_file, width, height)
        preview.init_gui()
        preview.exec_()

        # Unhide all the nurbs curves.
        for curr_panel in view_panels:
            cmds.modelEditor(curr_panel, edit=True, nurbsCurves=True)


    def add_pose(self, pose_name, char):
        """
        Writes the pose file and take a screenshot.

        :param pose_name: The name of the pose.
        :type: str

        :param char: The character for the pose.
        :type: str
        """
        # Write the data out to an xml file.
        if not self.write_pose_file(pose_name):
            IOM.error("Writing the file failed.")
            return None

        # Capture the viewport for the screenshot.
        file_name = "%s_%s.%s" % (char, pose_name, FileExtensions.PNG)
        self.viewport_capture(file_name)


    def verify_selection(self, selected, char):
        """
        Verify the selected. Ensure the selected are all the same namespace, and the
        namespace has is consistent with the current combobox.

        :param selected: There is always something selected b/c if there is nothing
                         selected then its handled before this function.
        :type: list

        :param char: The current character we're making poses for. It's not the same as
                     what's in the combobox, but pointing to the generic character unlike
                     what the combobox has with namespaces. "octoNinja" (genereic
                     character) vs. "octoNinja1" (instance namespace).
        :type: str

        :return: Whether the selected is valid to work with.
        :type: bool
        """
        # Get the current_ns from the first element.
        current_ns = selected[0].split(":")[0]

        # Check for any that don't match the first obj's namespace.
        for item in selected[1:]:
            item_ns = item.split(":")[0]
            if not item_ns == current_ns:
                IOM.error("\"%s\" is not in the same namespace as the other selected " \
                          "items." % item)
                return False

        # We can comfortably say all the items selected are under the same rig b/c
        # they're under the same namespace. Now check if the current_ns is matching
        # the current generic character we got from matching in the combo box.
        if not char in current_ns:
            IOM.error("\"%s\" is not in \"%s\" so we can't make a pose for this " \
                      "character." % (char, current_ns))
            return False

        return True


    def apply_pose(self, pose_name, char):
        """
        Applies the pose by getting the info from the XML.

        :param pose_name: The pose's name.
        :type: str

        :param char: The character we're applying it to.
        :type: str
        """
        # Locate it in the poses dictionary.
        pose_data = None
        for pose in self.pose_paths[char]:
            # Even if the label's name is "sit.png" it can still find "sit" in it, and we
            # got a match.
            if pose in pose_name:
                pose_data = self.pose_paths[char][pose]["data"]
                break

        if pose_data:
            self._apply_attrs(pose_data)
            IOM.success("Applied: %s" % pose)


    def delete_pose(self, pose_selected):
        """
        Delete the files, and remove from the pose_path dictionary.

        :param pose_selected: The pose we will delete.
        :type: str
        """
        # Get the pose paths necessary.
        pose_data, pose_img = self.get_pose_paths(pose_selected)

        # Delete the pose's XML file.
        if pose_data:
            try:
                os.remove(pose_data)
            except WindowsError or OSError:
                IO.error("Unable to delete: \n%s" % pose_data)

        # Delete the pose's image file.
        if pose_img:
            try:
                os.remove(pose_img)
            except WindowsError or OSError:
                IO.error("Unable to delete: \n%s" % pose_data)

        # Derive the pose from the pose_selected then remove from the dictionary.
        char = self.curr_char
        self.pose_paths[char].pop(pose_selected)


    def select_pose_ctrls(self, pose_selected):
        """
        Selects the pose's controls.
        """
        # Get the pose data we can work with.
        pose_data, pose_img = self.get_pose_paths(pose_selected)

        # Get the info from the pose data doc.
        contents = self._read_xml(pose_data)
        namespace = self.curr_char_ns

        # Iterate through the contents dict, adding the namespace to the ctrl and select.
        cmds.select(clear=True)
        for control in contents:
            ns_control = "%s:%s" % (namespace, control)
            cmds.select(ns_control, add=True)

