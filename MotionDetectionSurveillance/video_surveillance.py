#!/usr/bin/python3
# Video Surveillance System with Motion Detection for the Raspberry Pi 3 B+, Pi Camera, and,
# optionally, the Rainbow Hat.
# The Motion Detection portion of this code (which is the bulk of it) was taken from:
# https://www.pyimagesearch.com/2015/06/01/home-surveillance-and-motion-detection-with-the-raspberry-pi-python-and-opencv/
# and modified just a bit.
# Much thanks to Adrian Rosebrock for that!
#
# Directory structure:
# |--- video_surveillance.py
# |--- video_recorder.py
# |--- conf.json
# |--- pyimagesearch
# |    |--- __init__.py
# |    |--- tempimage.py
#
# This program requires:
#   OpenCV, which can be installed per these instructions:
#     http://www.life2coding.com/install-opencv-3-4-0-python-3-raspberry-pi-3/
#     (non-trivial, but went pretty smoothly for me)
#
#   imutils (see pyimagesearch link above)
#   video_recorder (companion module to this one)
#   tempimage.py (courtesy of Adrian Rosebrock)
#   conf.json 
#     min_area can be tweaked to control how small an area of motion
#       you want to trigger recording.  A setting of 100 results in motion detection being
#       triggered by large snowflakes!  You may or may not be down with that.
#     NOTE:  If you change the values for resolution, you will need to make corresponding
#     changes to x_min, x_max, y_min, and y_max (largely by trial and error.  You may want
#     to temporarily uncomment the following line below: #print("x:", x, "y:", y, "w:", w, "h:", h))
#
# Detection of motion is used to start a video recording.  After a certain amount of time since
# the last detection of motion, it will time out and end the recording.  Filenames are the time
# of the start of each recording.
from enum import Enum
from picamera import PiCamera
from picamera.array import PiRGBArray
from pyimagesearch.tempimage import TempImage
from video_recorder import VideoRecorder
import argparse
import cv2
import datetime
import enum
import imutils
import json
import time
import warnings
 
# Enumeration for the possible states of the system.  It starts out IDLE.
# When a frame is determined to have motion, it goes to ACTIVE.
# At the next frame that has no motion, it goes to RECORDING.
# After a certain amount of time (idle_timeout in conf.json), if no further
# motion has been detected, it will go to IDLE.
class State(Enum):
    IDLE =  0
    RECORDING = 1
    ACTIVE = 2

# Start out in the IDLE state.
state = State.IDLE
  
# Construct the argument parser and parse the arguments.
ap = argparse.ArgumentParser()
ap.add_argument("-c", "--conf", required=True,	help="Path to the JSON configuration file")
args = vars(ap.parse_args())

 
# Filter warnings.
warnings.filterwarnings("ignore")

# Load the configuration.
conf = json.load(open(args["conf"]))
	
# Initialize the camera and grab a reference to the raw camera capture.
camera = PiCamera()
camera.resolution = tuple(conf["resolution"])
camera.framerate = conf["fps"]
rawCapture = PiRGBArray(camera, size=tuple(conf["resolution"]))
 
# Pass the camera object to the Video Recorder.
VideoRecorder.set_camera(camera)
 
# Set the dir to write the video files to in the Video Recorder
VideoRecorder.set_videos_dir(conf["write_dir"]) 
 
# Allow the camera to warmup, then initialize the average frame, last
# uploaded timestamp, and frame motion counter.
print("[INFO] warming up...")
time.sleep(conf["camera_warmup_time"])
avg = None

# Initialize to a long time ago (in a galaxy far, far away...).
last_active_time = datetime.datetime(datetime.MINYEAR, 1, 1)

# Get the min and max x and y values for the timestamp exclusion
# code below.  If the resolution is changed in the conf.json file,
# these need to be adjusted as well.  
x_min = conf["x_min"]
x_max = conf["x_max"]
y_min = conf["y_min"]
y_max = conf["y_max"]

# Capture frames from the camera (endless loop, till quit).
for f in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
    # Grab the raw NumPy array representing the image and initialize
    # the timestamp and active/idle text.
    frame = f.array

    # Resize the frame, convert it to grayscale, and blur it.
    frame = imutils.resize(frame, width=960)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)
 
    # If the average frame is None, initialize it
    if avg is None:
        print("[INFO] starting background model...")
        avg = gray.copy().astype("float")
        rawCapture.truncate(0)
        continue
 
    # Accumulate the weighted average between the current frame and
    # previous frames, then compute the difference between the current
    # frame and running average.
    cv2.accumulateWeighted(gray, avg, 0.5)
    frameDelta = cv2.absdiff(gray, cv2.convertScaleAbs(avg))
	
    # Threshold the delta image, dilate the thresholded image to fill
    # in holes, then find contours on thresholded image
    thresh = cv2.threshold(frameDelta, conf["delta_thresh"], 255, cv2.THRESH_BINARY)[1]
    thresh = cv2.dilate(thresh, None, iterations=2)
    cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = cnts[0] if imutils.is_cv2() else cnts[1]
 
    # Figure out the new state.  Start by assuming no motion is detected, so
    # set the new state to either IDLE or RECORDING, depending on time since
    # motion was last detected.  Then the loop can overwrite the state with
    # ACTIVE if any adequate contours were found.
    timestamp = datetime.datetime.now()
    # If it's been longer than idle_timeout since the scene has had activity,
    # set the text to Idle, otherwise, Idle, Recording.
    elapsed_time = timestamp - last_active_time
    if elapsed_time.seconds > conf["idle_timeout"]:
        new_state = State.IDLE
    else:
        new_state = State.RECORDING
        
    # Loop over the contours.
    for c in cnts:
        # If the contour is too small, ignore it.
        # This is a value you may want to tweak to your own preference.
        if cv2.contourArea(c) < conf["min_area"]:
            continue

        # Compute the bounding box for the contour
        (x, y, w, h) = cv2.boundingRect(c)
        
        # Exclude the area of the timestamp from processing of detected motion.
        # We don't want the updating of that to be detected as motion and keep
        # the recording alive forever.
        # NOTE:  These values
        if not (x_min <= x <= x_max and y_min <= y <= y_max):
            # Temporary info to help determine / tun the above values.
            # May still need some teaking for the lower limit of x, for hour,
            # day, year changes.  Probably not worth the effort though.
            #print("x:", x, "y:", y, "w:", w, "h:", h)
            new_state = State.ACTIVE    
 
            # Draw the bounding box on the frame, and update the text.
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
            # Update the last_active_time to now (keep the recording going).
            last_active_time = datetime.datetime.now()
 
    if new_state == State.ACTIVE:
        # Motion has been detected, so the scene is now ACTIVE.
        if state == State.IDLE:
            # Transitioning from IDLE to ACTIVE, so we need to start recording.
            VideoRecorder.start()
        state = State.ACTIVE
        
    elif new_state == State.RECORDING:
        state = State.RECORDING
    
    elif new_state == State.IDLE:
        if state != State.IDLE:
            # Transitioning from RECORDING to IDLE.  Stop the recording.
            state = State.IDLE
            VideoRecorder.stop()
 
    # draw the text on the frame
    if state == State.IDLE:
        text = "Idle."
    elif state == State.RECORDING:
        text = "Idle, Recording..."
    elif state == State.ACTIVE:
        text = "Active, Recording..."
    else:
        raise ValueError("Unexpected value for state: ", state)
    
    cv2.putText(frame, "Status: {}".format(text), (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
		
    # Check to see if the frame should be displayed to screen.
    if conf["show_video"]:
        # Display the security feed.
        cv2.imshow("Video Surveillance", frame)
        key = cv2.waitKey(1) & 0xFF
 
        # If the `q` key is pressed, break from the loop.
        if key == ord("q"):
            print("q pressed, time to quit")
            if state != State.IDLE:
                VideoRecorder.stop()
            VideoRecorder.quit()
            print("now exit")
            exit(0)
 
    # Clear the stream in preparation for the next frame.
    rawCapture.truncate(0)
    
