# Courtesy of Adrian Rosebrock from:
# https://www.pyimagesearch.com/2015/06/01/home-surveillance-and-motion-detection-with-the-raspberry-pi-python-and-opencv/
# import the necessary packages
import uuid
import os
 
class TempImage:
    def __init__(self, basePath="./", ext=".jpg"):
        # construct the file path
        self.path = "{base_path}/{rand}{ext}".format(base_path=basePath,
            rand=str(uuid.uuid4()), ext=ext)
 
    def cleanup(self):
        # remove the file
        os.remove(self.path)
