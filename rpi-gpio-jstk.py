""" rpi-gpio-jstk.py by Chris Swan 9 Aug 2012
GPIO Joystick driver for Raspberry Pi for use with 80s 5 switch joysticks
based on python-uinput/examples/joystick.py by tuomasjjrasanen
https://github.com/tuomasjjrasanen/python-uinput/blob/master/examples/joystick.py
requires uinput kernel module (sudo modprobe uinput)
requires python-uinput (git clone https://github.com/tuomasjjrasanen/python-uinput)
requires (from http://pypi.python.org/pypi/RPi.GPIO/0.3.1a)
for detailed usage see http://blog.thestateofme.com/2012/08/10/raspberry-pi-gpio-joystick/
"""


import uinput
import time
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BOARD)
# Up, Down, left, right, fire
GPIO.setup(11, GPIO.IN)
GPIO.setup(13, GPIO.IN)
GPIO.setup(15, GPIO.IN)
GPIO.setup(16, GPIO.IN)
GPIO.setup(7, GPIO.IN)

events = (uinput.BTN_JOYSTICK, uinput.ABS_X + (0, 255, 0, 0), uinput.ABS_Y + (0, 255, 0, 0))

device = uinput.Device(events)

# Bools to keep track of movement
fire = False
up = False
down = False
left = False
right = False

# Center joystick
# syn=False to emit an "atomic" (128, 128) event.
device.emit(uinput.ABS_X, 128, syn=False)
device.emit(uinput.ABS_Y, 128)

while True:
  if (not fire) and (not GPIO.input(7)):  # Fire button pressed
    fire = True
    device.emit(uinput.BTN_JOYSTICK, 1)
  if fire and GPIO.input(7):              # Fire button released
    fire = False
    device.emit(uinput.BTN_JOYSTICK, 0) 
  if (not up) and (not GPIO.input(11)):   # Up button pressed
    up = True
    device.emit(uinput.ABS_Y, 0)          # Zero Y
  if up and GPIO.input(11):               # Up button released
    up = False
    device.emit(uinput.ABS_Y, 128)        # Center Y
  if (not down) and (not GPIO.input(13)): # Down button pressed
    down = True
    device.emit(uinput.ABS_Y, 255)        # Max Y
  if down and GPIO.input(13):             # Down button released
    down = False
    device.emit(uinput.ABS_Y, 128)        # Center Y
  if (not left) and (not GPIO.input(15)): # Left button pressed
    left = True
    device.emit(uinput.ABS_X, 0)          # Zero X
  if left and GPIO.input(15):             # Left button released
    left = False
    device.emit(uinput.ABS_X, 128)        # Center X
  if (not right) and (not GPIO.input(16)):# Right button pressed
    right = True
    device.emit(uinput.ABS_X, 255)        # Max X
  if right and GPIO.input(16):            # Right button released
    right = False
    device.emit(uinput.ABS_X, 128)        # Center X
  time.sleep(.02)  # Poll every 20ms (otherwise CPU load gets too high)
