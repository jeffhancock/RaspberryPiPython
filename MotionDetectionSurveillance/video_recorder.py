#!/usr/bin/env python
#
#           Raspberry Pi Video Recorder.
#
# This program for the Raspberry Pi 3 B+ requires the camera
# (Pi NoIR Camera V2 in my case), but the Rainbow Hat is optional.
# This module is  used by video_surveillance.py, which does the motion
# sensing and calls start() and stop().
#
# The C touch button on the hat can be used to stop the program
# (the usual way is the q button).
#
# The alphanumeric display shows status:
#
# IDLE - Not recording.
# REC  - Recording video
# blank - Program has exited.
#
# The name of each video file is the start time of the period it covers.
# If there is less than FREE_SPACE_GB of free disk space remaining when
# it is time to start a new file, the oldest file(s) will be deleted
# until there is.
#
# There is a 1 second resolution timestamp in the video, at the top.
#
# You can customize VIDEOS_DIRECTORY below to where you want the files to go,
# but it will be overwritten by what's in conf.json, so you really need to
# change it there.

import datetime
import json
import os
import picamera
try:
    import rainbowhat
    rh_found = True
except ImportError:
    rh_found = False
import signal
import sys
from threading import Timer
from time import sleep

class VideoRecorder:

    #VIDEOS_DIRECTORY = '/home/pi/Camera/Videos/'  # On the SD card.  Good for quicker testing
                                                   # of deleting oldest file(s) when too full.
    VIDEOS_DIRECTORY = '/media/pi/My Passport/SurveillanceVideos/'  # Big space for real use

    READY = 'IDLE'
    RECORDING = 'REC '
    FREE_SPACE_GB = 10   # The amount of spacek, in GB, to free up before starting a recording.
                         # Files should be about 7.2 GB for an hour of video, so 10 should leave
                         # enough headroom.
    ANNOTATION_TIMER_INTERVAL_SEC = 1 # Number of seconds between updates of the timestamp that
                                      # appears in the video.
                                  
    camera = None
    recording = False
    annotation_timer = None        # Timer to update the time annotation in the video
    videos_dir = VIDEOS_DIRECTORY  # A call to set_videos_dir will overwrite this

    if rh_found:
        # Indicate ready on the display and wait for a button to be touched.
        rainbowhat.display.print_str(READY)
        rainbowhat.display.show()

    @classmethod
    def set_camera(cls, cam):
        """Set the camera object

        It can't instantiate its own, and has to share it with the motion detection code.
        """
        cls.camera = cam

    @classmethod
    def set_videos_dir(cls, dir):
        """Change the videos director from the hard coded default"""
        cls.videos_dir = dir

    @classmethod
    def get_free_space_GB(cls, dir):
        """Get the amount of free space, in GB, in the given directory."""
        statvfs = os.statvfs(dir)
        space_bytes = statvfs.f_frsize * statvfs.f_bfree # block size x free blocks
        print('Free bytes: ', space_bytes)
        free_GB = space_bytes / (1024 ** 3)
        return free_GB

    @classmethod
    def ensure_space(cls, dir):
        """Ensure there is FREE_SPACE_GB gigabytes of free space in the specified directory
        
        If not, delete the oldest file until there is.  Oldest is determined by filename,
        which is adequate for the purposes of this program, but not in general.
        """
        gigabytes = cls.get_free_space_GB(dir)
        while gigabytes < cls.FREE_SPACE_GB: 
            print('Getting low on space!')
            files = sorted(os.listdir(dir))
            oldest = files[0]
            print('About to delete oldest file: ', oldest)
            os.remove(dir + oldest)
            gigabytes = cls.get_free_space_GB(dir)    
        print('Got enough space: ', gigabytes, ' GB')

    @classmethod
    def update_time_annotation(cls):
        """Update the annotation time in the video, and start a new timer for the next update"""
        if cls.recording:
            cls.camera.annotate_text = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cls.camera.wait_recording(0)
            cls.annotation_timer = Timer(cls.ANNOTATION_TIMER_INTERVAL_SEC, cls.update_time_annotation)
            cls.annotation_timer.start()

    @classmethod
    def start(cls):
        """Start a recording"""
        cls.ensure_space(cls.videos_dir)
        cls.recording = True
        now = datetime.datetime.now()

        fn = now.strftime('%Y-%m-%d_%p_%I-%M-%S.h264')
    
        fullPathFilename = cls.videos_dir + fn

        print('File name: ', fn)
        print('Full path filename: ', fullPathFilename)

        cls.camera.annotate_background = picamera.Color('black')
        cls.camera.annotate_text = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cls.camera.start_recording(fullPathFilename)
        cls.annotation_timer = Timer(cls.ANNOTATION_TIMER_INTERVAL_SEC, cls.update_time_annotation)
        cls.annotation_timer.start()
        print('Starting recording')
        if rh_found:
            rainbowhat.display.print_str(cls.RECORDING)
            rainbowhat.display.show()

    @classmethod
    def stop(cls):
        """Stop the recording in progress"""
        print('Stopping recording')
        cls.recording = False
        cls.camera.stop_recording()
        cls.annotation_timer.cancel()
        if rh_found:
            rainbowhat.display.print_str(cls.READY)
            rainbowhat.display.show()
        

    @classmethod
    def quit(cls):
        if rh_found:
            rainbowhat.display.clear()
            rainbowhat.display.show()

def beep(value):
    """Do a beep, middle C
    
    Just to give feedback on a button touch.
    """
    if rh_found:
        MIDDLE_C = 60
        rainbowhat.buzzer.midi_note(MIDDLE_C + value, .5)

if rh_found:
    @rainbowhat.touch.press()
    def touch_a(channel):
        """Define a function for a button press
    
        Bind it to the press event defined in touch.py.
        """
        print(channel)
        if channel == 2: # Button C
            # Play a tone, slightly different for each button.
            beep(channel * 5)
        
            if VideoRecorder.recording:
                VideoRecorder.stop()
            VideoRecorder.quit()
            print('Exiting')
            sys.exit(0)
    
        if channel > 2:
            print('Unexpected button touched!  How did that happen?!')
            if VideoRecorder.recording:
                VideoRecorder.stop()
            VideoRecorder.quit()
            print('Exiting')
            raise ValueError("Bad value for channel.  No such button!")
