"""<b>Load Single Image</b> loads a single image for use in all image cycles
<hr>

<i>Note:</i> For most purposes, you will probably want to use the <b>LoadImages</b>
module, not <b>LoadSingleImage</b>.

This module tells CellProfiler where to retrieve a single image and gives the image a
meaningful name by which the other modules can access it. The module 
executes only the first time through the pipeline; thereafter the image
is accessible to all subsequent processing cycles. This is
particularly useful for loading an image like an illumination correction
image for use by the <b>CorrectIlluminationApply</b> module, when that single
image will be used to correct all images in the analysis run.

See also <b>LoadImages</b>.

"""
__version__="Revision: $1 "

# CellProfiler is distributed under the GNU General Public License.
# See the accompanying file LICENSE for details.
# 
# Developed by the Broad Institute
# Copyright 2003-2010
# 
# Please see the AUTHORS file for credits.
# 
# Website: http://www.cellprofiler.org

import hashlib
import numpy as np
import re
import os

import cellprofiler.cpimage as cpi
import cellprofiler.cpmodule as cpm
import cellprofiler.measurements as cpmeas
import cellprofiler.preferences as cpprefs
import cellprofiler.settings as cps
from loadimages import LoadImagesImageProvider
from cellprofiler.gui.help import USING_METADATA_TAGS_REF, USING_METADATA_HELP_REF
from cellprofiler.preferences import standardize_default_folder_names, DEFAULT_INPUT_FOLDER_NAME, DEFAULT_OUTPUT_FOLDER_NAME

DIR_CUSTOM_FOLDER = "Custom folder"
DIR_CUSTOM_WITH_METADATA = "Custom with metadata"

class LoadSingleImage(cpm.CPModule):

    module_name = "LoadSingleImage"
    category = "File Processing"
    variable_revision_number = 1
    def create_settings(self):
        """Create the settings during initialization
        
        """
        self.dir_choice = cps.Choice(
            "Folder containing the image file",
            [DEFAULT_INPUT_FOLDER_NAME,
             DEFAULT_OUTPUT_FOLDER_NAME,
             DIR_CUSTOM_FOLDER,
             DIR_CUSTOM_WITH_METADATA], 
            doc = '''It is best to store the image you want to load 
            in either the input or output folder, so that the correct image is loaded into 
            the pipeline and typos are avoided.  If you must store it in another folder, 
            select <i>Custom folder</i>. You can use metadata from the image set to
            construct the folder name by selecting <i>Custom with metadata</i>.''')
        
        self.custom_directory = cps.Text(
            "Name of the folder containing the image file",".",
            doc='''If you chose <i>Custom with metadata</i> above, you can
            specify a path based on metadata associated with the
            image set. %s. For instance, if you have a "Plate" metadata element,
            you can specify a path name of "./\g&lt;Plate&gt;" to get files
            from the folder associated with your image's plate.
            You can prefix the folder name with "." (a period) to make the 
            root folder the Default Input Folder or "&" (an ampersand) 
            to make the root folder the Default Output Folder. %s. '''%(USING_METADATA_TAGS_REF,USING_METADATA_HELP_REF))
        
        self.file_settings = []
        self.add_file(can_remove = False)
        self.add_button = cps.DoSomething("", "Add another image", self.add_file)

    def add_file(self, can_remove = True):
        """Add settings for another file to the list"""
        group = cps.SettingsGroup()
        if can_remove:
            group.append("divider", cps.Divider(line=False))
        def get_directory_fn():
            if self.dir_choice == DEFAULT_INPUT_FOLDER_NAME:
                return cpprefs.get_default_image_directory()
            elif self.dir_choice == DEFAULT_OUTPUT_FOLDER_NAME:
                return cpprefs.get_default_output_directory()
            elif self.dir_choice == DIR_CUSTOM_FOLDER:
                return self.custom_directory.value
            return os.curdir()
        
        group.append("file_name", cps.FilenameText(
            "Filename of the image to load (Include the extension, e.g., .tif)",
            "None",
            get_directory_fn = get_directory_fn,
            exts = [("Tagged image file (*.tif)","*.tif"),
                    ("Portable network graphics (*.png)", "*.png"),
                    ("JPEG file (*.jpg)", "*.jpg"),
                    ("Bitmap file (*.bmp)", "*.bmp"),
                    ("GIF file (*.gif)", "*.gif"),
                    ("Matlab image (*.mat)","*.mat"),
                    ("All files (*.*)", "*.*")],doc = """
                    The filename can be constructed in one of two ways:
                    <ul>
                    <li>As a fixed filename (e.g., <i>Exp1_D03f00d0.tif</i>). 
                    <li>Using the metadata associated with an image set in 
                    <b>LoadImages</b> or <b>LoadData</b>. This is especially useful 
                    if you want your output given a unique label according to the
                    metadata corresponding to an image group. The name of the metadata 
                    to substitute is included in a special tag format embedded 
                    in your file specification. %s. %s</li>
                    </ul>
                    In either case, the extension, if any, should be included."""% (USING_METADATA_TAGS_REF,USING_METADATA_HELP_REF) ))
        group.append("image_name", cps.FileImageNameProvider("Name the image that will be loaded", 
                    "OrigBlue", doc = '''What do you want to call the image you are loading? 
                    You can use this name to select the image in downstream modules.'''))
        if can_remove:
            group.append("remove", cps.RemoveSettingButton("", "Remove this image", self.file_settings, group))
        self.file_settings.append(group)

    def settings(self):
        """Return the settings in the order in which they appear in a pipeline file"""
        result = [self.dir_choice, self.custom_directory]
        for file_setting in self.file_settings:
            result += [file_setting.file_name, file_setting.image_name]
        return result

    def visible_settings(self):
        result = [self.dir_choice]
        if self.dir_choice in (DIR_CUSTOM_FOLDER, DIR_CUSTOM_WITH_METADATA):
            result += [self.custom_directory]
        for file_setting in self.file_settings:
            result += file_setting.visible_settings()
        result.append(self.add_button)
        return result 

    def prepare_settings(self, setting_values):
        """Adjust the file_settings depending on how many files there are"""
        count = (len(setting_values)-2)/2
        del self.file_settings[count:]
        while len(self.file_settings) < count:
            self.add_file()

    def prepare_to_create_batch(self, pipeline, image_set_list, fn_alter_path):
        '''Prepare to create a batch file
        
        This function is called when CellProfiler is about to create a
        file for batch processing. It will pickle the image set list's
        "legacy_fields" dictionary. This callback lets a module prepare for
        saving.
        
        pipeline - the pipeline to be saved
        image_set_list - the image set list to be saved
        fn_alter_path - this is a function that takes a pathname on the local
                        host and returns a pathname on the remote host. It
                        handles issues such as replacing backslashes and
                        mapping mountpoints. It should be called for every
                        pathname stored in the settings or legacy fields.
        '''
        if self.dir_choice == DIR_DEFAULT_IMAGE_FOLDER:
            self.dir_choice.value = DIR_CUSTOM_FOLDER
            self.custom_directory.value = cpprefs.get_default_image_directory()
        elif self.dir_choice == DIR_DEFAULT_OUTPUT_FOLDER:
            self.dir_choice.value = DIR_CUSTOM_FOLDER
            self.custom_directory.value = cpprefs.get_default_output_directory()
        elif self.dir_choice == DIR_CUSTOM_FOLDER:
            self.custom_directory.value = cpprefs.get_absolute_path(
                self.custom_directory.value)
        elif self.dir_choice == DIR_CUSTOM_WITH_METADATA:
            path = self.custom_directory.value
            end_new_style = path.find("\\g<")
            end_old_style = path.find("\(?")
            end = (end_new_style 
                   if (end_new_style != -1 and 
                       (end_old_style == -1 or end_old_style > end_new_style))
                   else end_old_style)
            if end != -1:
                pre_path = path[:end]
                pre_path = cpprefs.get_absolute_path(pre_path)
                pre_path = fn_alter_path(pre_path)
                path = pre_path + path[end:]
                self.custom_directory.value = path
                return True
        self.custom_directory.value = fn_alter_path(self.custom_directory.value)
        return True

    def get_base_directory(self, workspace):
        if self.dir_choice == DEFAULT_INPUT_FOLDER_NAME:
            base_directory = cpprefs.get_default_image_directory()
        elif self.dir_choice == DEFAULT_OUTPUT_FOLDER_NAME:
            base_directory = cpprefs.get_default_output_directory()
        elif self.dir_choice in (DIR_CUSTOM_FOLDER, DIR_CUSTOM_WITH_METADATA):
            base_directory = self.custom_directory.value
            if self.dir_choice == DIR_CUSTOM_WITH_METADATA:
                base_directory = workspace.measurements.apply_metadata(base_directory)
            if (base_directory[:2] == '.'+ os.sep or
                (os.altsep and base_directory[:2] == '.'+os.altsep)):
                # './filename' -> default_image_folder/filename
                base_directory = os.path.join(cpprefs.get_default_image_directory(),
                                              base_directory[2:])
            elif (base_directory[:2] == '&'+ os.sep or
                  (os.altsep and base_directory[:2] == '&'+os.altsep)):
                base_directory = os.path.join(cpprefs.get_default_output_directory(),
                                              base_directory[2:])
        return base_directory
    
    def get_file_names(self, workspace):
        """Get the files for the current image set
        
        workspace - workspace for current image set
        
        returns a dictionary of image_name keys and file path values
        """
        result = {}
        for file_setting in self.file_settings:
            file_pattern = file_setting.file_name.value
            file_name = workspace.measurements.apply_metadata(file_pattern)
            result[file_setting.image_name.value] = file_name
                
        return result
            
    def run(self, workspace):
        dict = self.get_file_names(workspace)
        root = self.get_base_directory(workspace)
        statistics = [("Image name","File")]
        m = workspace.measurements
        for image_name in dict.keys():
            provider = LoadImagesImageProvider(image_name, root, 
                                               dict[image_name])
            workspace.image_set.providers.append(provider)
            #
            # Add measurements
            #
            m.add_measurement('Image','FileName_'+image_name, dict[image_name])
            m.add_measurement('Image','PathName_'+image_name, root)
            pixel_data = provider.provide_image(workspace.image_set).pixel_data
            digest = hashlib.md5()
            digest.update(np.ascontiguousarray(pixel_data).data)
            m.add_measurement('Image','MD5Digest_'+image_name, digest.hexdigest())
            statistics += [(image_name, dict[image_name])]
        if workspace.frame:
            title = "Load single image: image cycle # %d"%(workspace.measurements.image_set_number+1)
            figure = workspace.create_or_find_figure(title=title,
                                                     subplots=(1,1))
            figure.subplot_table(0,0, statistics)
    
    def get_measurement_columns(self, pipeline):
        columns = []
        for file_setting in self.file_settings:
            image_name = file_setting.image_name.value
            columns += [(cpmeas.IMAGE, '_'.join((feature, image_name)), coltype)
                        for feature, coltype in (
                            ('FileName', cpmeas.COLTYPE_VARCHAR_FILE_NAME),
                            ('PathName', cpmeas.COLTYPE_VARCHAR_PATH_NAME),
                            ('MD5Digest', cpmeas.COLTYPE_VARCHAR_FORMAT % 32))]
        return columns
    
    def upgrade_settings(self, setting_values, variable_revision_number, module_name, from_matlab):
                
        DIR_DEFAULT_IMAGE_FOLDER = "Default input folder"
        DIR_DEFAULT_OUTPUT_FOLDER = "Default output folder"

        if from_matlab and variable_revision_number == 4:
            new_setting_values = list(setting_values)
            # The first setting was blank in Matlab. Now it contains
            # the directory choice
            if setting_values[1] == '.':
                new_setting_values[0] = DIR_DEFAULT_IMAGE_FOLDER
            elif setting_values[1] == '&':
                new_setting_values[0] = DIR_DEFAULT_OUTPUT_FOLDER
            else:
                new_setting_values[0] = DIR_CUSTOM_FOLDER
            #
            # Remove "Do not use" images
            #
            for i in [8, 6, 4]:
                if new_setting_values[i+1] == cps.DO_NOT_USE:
                    del new_setting_values[i:i+2]
            setting_values = new_setting_values
            from_matlab = False
            variable_revision_number = 1
        #
        # Minor revision: default image folder -> default input folder
        #
        if variable_revision_number == 1 and not from_matlab:
            if setting_values[0].startswith("Default image"):
                setting_values = [DIR_DEFAULT_IMAGE_FOLDER] + setting_values[1:] 
                
        # Standardize input/output directory name references
        SLOT_DIRCHOICE = 0
        setting_values = standardize_default_folder_names(setting_values,SLOT_DIRCHOICE)
        
        return setting_values, variable_revision_number, from_matlab

