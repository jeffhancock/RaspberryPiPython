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

def get_free_space_GB(dir):
    """Get the amount of free space, in GB, in the given directory."""
    statvfs = os.statvfs(dir)
    space_bytes = statvfs.f_frsize * statvfs.f_bfree # block size x free blocks
    print('Free bytes: ', space_bytes)
    free_GB = space_bytes / (1024 ** 3)
    return free_GB

def ensure_space(dir):
    """Ensure there is FREE_SPACE_GB gigabytes of free space in the specified directory.

    If not, delete the oldest file until there is.  Oldest is determined by filename,
    which is adequate for the purposes of this program, but not in general.
    """
    gigabytes = get_free_space_GB(dir)
    while gigabytes < FREE_SPACE_GB: 
        print('Getting low on space!')
        files = sorted(os.listdir(dir))
        oldest = files[0]
        print('About to delete oldest file: ', oldest)
        os.remove(dir + oldest)
        gigabytes = get_free_space_GB(dir)    
    print('Got enough space: ', gigabytes, ' GB')

def update_time_annotation():
    """Update the annotation time in the video, and start a new timer for the next update."""
    global recording
    global annotation_timer
    if recording:
        camera.annotate_text = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        camera.wait_recording(0)
        annotation_timer = Timer(ANNOTATION_TIMER_INTERVAL_SEC, update_time_annotation)
        annotation_timer.start()

def start():
    """Start a recording."""
    ensure_space(VIDEOS_DIRECTORY)
    global recording
    global duration
    global annotation_timer
    recording = True
    now = datetime.datetime.now()

    # Compute how many seconds left in the minute
    duration = 60 - now.second
    if duration == 0:
        duration = 60
    
    # Add time for minutes left in the hour
    duration += (59 - now.minute) * 60

    print('Will record for', duration, 'seconds.')

    fn = now.strftime('%Y-%m-%d_%p_%I:%M:%S.h264')
    
    fullPathFilename = VIDEOS_DIRECTORY + fn

    print('File name: ', fn)
    print('Full path filename: ', fullPathFilename)

    camera.start_preview()
    camera.annotate_background = picamera.Color('black')
    camera.annotate_text = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    camera.start_recording(fullPathFilename)
    annotation_timer = Timer(ANNOTATION_TIMER_INTERVAL_SEC, update_time_annotation)
    annotation_timer.start()
    print('Starting recording')
    rainbowhat.display.print_str(RECORDING)
    rainbowhat.display.show()

def stop():
    """Stop the recording in progress"""
    camera.stop_recording()
    camera.stop_preview()
    rainbowhat.display.print_str(READY)
    rainbowhat.display.show()
    annotation_timer.cancel()
    recording_timer.cancel()

def continue_recording():
    """Stop the recording in progress and start a new one.

    This is meant to happen on hour boundaries.
    """
    global recording_timer
    camera.stop_recording()
    camera.stop_preview()
    print('Stopping recording')
    start()
    # Set a timer for when to close out the file and start a new one
    recording_timer = Timer(duration, continue_recording)
    recording_timer.start()

def record():
    """Start a recording and set a timer for when it to stop and start a new one."""
    global recording_timer
    start()
    # Set the timer
    recording_timer = Timer(duration, continue_recording)
    recording_timer.start()

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
    global recording
    
    print(channel)
    
    # Play a tone, slightly different for each button.
    beep(channel * 5)
    
    if channel == 0: # Button A
        # Start recording
        record()
    
    if channel == 1: # Button B
        # Stop recording
        if recording:
            print('Stopping recording')
            recording = False # Used by update_time_annotation to know when to quit
                              # setting its timer.
            stop()
    
    if channel == 2: #B Button C
        if recording:
            print('Stopping recording before exiting')
            stop()
        rainbowhat.display.clear()
        rainbowhat.display.show()
        print('Exiting')
        sys.exit(0)
    
    if channel > 2:
        print('Unexpected button touched!  How did that happen?!')
        if recording:
            print('Stopping recording before exiting')
            stop()
            rainbowhat.display.clear()
            rainbowhat.display.show()
        print('Exiting')
        sys.exit(0)
    
# Start of main program.  Indicate ready on the display and wait for
# a button to be touched.
rainbowhat.display.print_str(READY)
rainbowhat.display.show()
signal.pause() # Pause the main thread so it doesn't exit