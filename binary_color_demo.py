#!/usr/bin/env python
# This demo of the rainbow hat is an elemenary lesson on binary
# and RGB colors.  You can specify a 3 bit binary number by touching
# the touch pads (one at a time) to toggle them on or off.
# The corresponding base 10, octal, or hex value is displayed on the
# alphanumeric display (they are all the same since we only have 3 bits
# to work with).  The corresponding rainbow light will be lit, with the
# color being the sum of the colors shown above the touch pads (red,
# green, blue).  There are two exceptions, which are:
# For all bits zero, rainbow light 0 will be a dim white.
# For all bits one, all rainbow lights will be on.
# A midi note will be played based on the value when a touch pad is pressed.

import atexit
import rainbowhat as rh
import signal

# Clear the alphanumeric display
rh.display.clear()
rh.display.show()

# Clear the lights above the touch pads.
# The colors are fixed in hardware:
# A red
# B green
# C blue
# So all the parameters to the rgb call take are a one or a zero
# for each, turning it on or off respectively.
rh.lights.rgb(0,0,0)

# Clear the rainbow
rh.rainbow.clear()
rh.rainbow.show()

# Initialize all 3 bits to False
bit_state = [False, False, False]

def get_value():
    """Get the integer value of the three bits (0 - 7)."""
    value = 0
    # This may seem a bit backwards, giving bit number 0 a value of
    # 4, but that's what we need to do to put the least significant
    # bit on the right, as is customary.  That would be above touch
    # pad C, which has the channel value of 2.  So touch pad A, which
    # has a channel value of 0, is the most significant bit.
    if bit_state[0]:
        # Most significant bit 
        value += 4
    if bit_state[1]:
        value += 2
    if bit_state[2]:
        # Least significant bit
        value += 1
    return value

def display_value(value):
    """Display the given value on the alphanumeric display."""
    rh.display.print_hex(value)
    rh.display.show()

def do_rainbow(value):
    """Light up the rainbow light corresponding to the given value (0-7).

    There is no light #7, so for that case, light them all.
    Use the three bits as RGB values to determine the color, except in
    the case of zero.  In that case, do a dim white."""
    rh.rainbow.clear()
    if value == 0:
        # Don't want the light to be off, so do a dim white.
        red = 10
        green = 10
        blue = 10
    else:
        # Use the bits as RGB values for the color.  Yes, we could
        # make it brighter, up to 255, if we wanted.
        brightness = 100
        red = brightness if bit_state[0] else 0
        green = brightness if bit_state[1] else 0
        blue = brightness if bit_state[2] else 0
    if value < 7:
        # Normal case.  Turn on the pixel corresponding to the value
        rh.rainbow.set_pixel(value, red, green, blue)
    else:
        # There is no pixel for 7, so for it we'll turn on the entire rainbow
        for i in range(7):
            rh.rainbow.set_pixel(i, red, green, blue)
    rh.rainbow.show()

def beep(value):
    """Do a beep, middle C or above."""
    MIDDLE_C = 60
    rh.buzzer.midi_note(MIDDLE_C + value, .5)

@rh.touch.press()
def touch_a(channel):
    """Define a function for a button press.

    Bind it to the press event defined in touch.py."""
    # Toggle the state of the bit specified by channel
    if bit_state[channel]:
        # Bit is currently on.  Turn it off.
        bit_state[channel] = 0
    else:
        # Bit is currently off.  Turn it on.
        bit_state[channel] = 1

    # Set the state of the lights above the touch pads
    rh.lights.rgb(bit_state[0], bit_state[1], bit_state[2])
    # Calculate the integer value
    value = get_value()
    # Display the integer value on the alphanumeric display
    display_value(value)
    # Turn on the appropriate rainbow light(s)
    do_rainbow(value)
    # Play a tone
    beep(value)
        
# No need for any processing on button release
#@rh.touch.release()
#def release(channel):
#    print("Button release!")

signal.pause() # Pause the main thread so it doesn't exit
