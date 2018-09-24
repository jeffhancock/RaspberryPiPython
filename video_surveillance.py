#!/usr/bin/env python
#
#           Raspberry Pi Video Surveillance program.
#
# This program for the Raspberry Pi requires both the camera
# (Pi NoIR Camera V2 in my case), and the Rainbow Hat.  The
# A, B, C touch buttons on the hat are used to control the
# program:
#
# A - Start recording video
# B - Stop recording video
# C - Quit program (Stop first if currently recording)
#
# The alphanumeric display shows status:
#
# RDY - Program is running, ready to start recording.
# REC - Recording video
# blank - Program has exited.
#
# Video is recorded in one hour blocks, ending at hour boundaries.
# Therefore, the first block after a start will be for the remainder
# of the current clock hour, so it can be anywhere from near zero to
# an hour in length.  After that, files start and end on hour boundaries.
# The name of the file is the start time of the period it covers.
# If there is less than FREE_SPACE_GB of free disk space remaining when
# it is time to start a new file, the oldest file(s) will be deleted
# until there is.
#
# There is a 1 second resolution timestamp in the video, at the top.
#
# Customize VIDEOS_DIRECTORY below to where you want the files to go.

import datetime
import os
import picamera
import rainbowhat
import signal
import sys
from threading import Timer
from time import sleep

class VideoRecorder:

    #VIDEOS_DIRECTORY = '/home/pi/Camera/Videos/'  # On the SD card.  Good for quicker testing
                                                   # of deleting oldest file(s) when too full.
    VIDEOS_DIRECTORY = '/media/pi/My Passport/SurveillanceVideos/'  # Big space for real use

    READY = 'RDY'
    RECORDING = 'REC'
    FREE_SPACE_GB = 10   # The amount of spacek, in GB, to free up before starting a recording.
                         # Files should be about 7.2 GB for an hour of video, so 10 should leave
                         # enough headroom.
    ANNOTATION_TIMER_INTERVAL_SEC = 1 # Number of seconds between updates of the timestamp that
                                      # appears in the video.
                                  
    camera = picamera.PiCamera()
    recording = False              # True when a recording is in progress
    duration = 0                   # The duration, in seconds, of video to record
    annotation_timer = None        # Timer to update the time annotation in the video
    recording_timer = None         # Timer to close out the recording file and start
                                   # a new one

    # Indicate ready on the display and wait for a button to be touched.
    rainbowhat.display.print_str(READY)
    rainbowhat.display.show()

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
        """Ensure there is FREE_SPACE_GB gigabytes of free space in the specified directory.

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
        """Update the annotation time in the video, and start a new timer for the next update."""
        if cls.recording:
            cls.camera.annotate_text = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cls.camera.wait_recording(0)
            cls.annotation_timer = Timer(cls.ANNOTATION_TIMER_INTERVAL_SEC, cls.update_time_annotation)
            cls.annotation_timer.start()

    @classmethod
    def start(cls):
        """Start a recording."""
        cls.ensure_space(cls.VIDEOS_DIRECTORY)
        cls.recording = True
        now = datetime.datetime.now()

        # Compute how many seconds left in the minute
        cls.duration = 60 - now.second
        if cls.duration == 0:
            cls.duration = 60
    
        # Add time for minutes left in the hour
        cls.duration += (59 - now.minute) * 60

        print('Will record for', cls.duration, 'seconds.')

        fn = now.strftime('%Y-%m-%d_%p_%I:%M:%S.h264')
    
        fullPathFilename = cls.VIDEOS_DIRECTORY + fn

        print('File name: ', fn)
        print('Full path filename: ', fullPathFilename)

        cls.camera.start_preview()
        cls.camera.annotate_background = picamera.Color('black')
        cls.camera.annotate_text = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cls.camera.start_recording(fullPathFilename)
        cls.annotation_timer = Timer(cls.ANNOTATION_TIMER_INTERVAL_SEC, cls.update_time_annotation)
        cls.annotation_timer.start()
        print('Starting recording')
        rainbowhat.display.print_str(cls.RECORDING)
        rainbowhat.display.show()

    @classmethod
    def stop(cls):
        """Stop the recording in progress"""
        print('Stopping recording')
        cls.recording = False
        cls.camera.stop_recording()
        cls.camera.stop_preview()
        rainbowhat.display.print_str(cls.READY)
        rainbowhat.display.show()
        cls.annotation_timer.cancel()
        cls.recording_timer.cancel()

    @classmethod
    def quit(cls):
        rainbowhat.display.clear()
        rainbowhat.display.show()

    @classmethod
    def continue_recording(cls):
        """Stop the recording in progress and start a new one.

        This is meant to happen on hour boundaries.
        """
        cls.camera.stop_recording()
        cls.camera.stop_preview()
        print('Stopping recording')
        cls.start()
        # Set a timer for when to close out the file and start a new one
        cls.recording_timer = Timer(cls.duration, cls.continue_recording)
        cls.recording_timer.start()

    @classmethod
    def record(cls):
        """Start a recording and set a timer for when it to stop and start a new one."""
        cls.start()
        # Set the timer
        cls.recording_timer = Timer(cls.duration, cls.continue_recording)
        cls.recording_timer.start()

def beep(value):
    """Do a beep, middle C.

    Just to give feedback on a button touch.
    """
    MIDDLE_C = 60
    rainbowhat.buzzer.midi_note(MIDDLE_C + value, .5)

@rainbowhat.touch.press()
def touch_a(channel):
    """Define a function for a button press.

    Bind it to the press event defined in touch.py.
    """
    print(channel)
    
    # Play a tone, slightly different for each button.
    beep(channel * 5)
    if channel == 0: # Button A
        # Start recording
        VideoRecorder.record()
    
    if channel == 1: # Button B
        # Stop recording
        if VideoRecorder.recording:
            VideoRecorder.stop()
    
    if channel == 2: #B Button C
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
        sys.exit(0)
    
# Start of main program.  
signal.pause() # Pause the main thread so it doesn't exit