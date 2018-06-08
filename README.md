# LIFX-Control-Panel 

<img align="right" width="120" height="120"
     title="LIFX-Control-Panel Logo" src="https://raw.githubusercontent.com/samclane/LIFX-Control-Panel/master/icon.png">
     
LIFX-Control-Panel is an open source application for controlling your LIFX brand lights. It integrates simple features, 
such as monitoring and changing bulb color, with more advanced ones, like Average Screen Color, Color Eyedropper, and more.

<p align="center">
  <img src="https://raw.githubusercontent.com/samclane/LIFX-Control-Panel/master/screenshot.png" alt="Screenshot" width="306" height=533>
</p>

The application uses [mclarkk](https://github.com/mclarkk)'s [lifxlan](https://github.com/mclarkk/lifxlan) module to discover and send commands to the lights.

# Quick Start
Go over to [releases](https://github.com/samclane/LIFX-Control-Panel/releases) and download the latest `.exe` file.

The `LIFX-Control-Panel-debug.exe` is a debug version that runs with a console in the background, and uses a verbose
`lifxlan` network logger.

`LIFX-Control-Panel-demo.exe` features several "Dummy" bulbs in addition to any real devices on your network. You can use
this distribution to test the software on computers that do not have a LIFX device on the LAN. 

Starting the program takes a moment, as it first must scan your LAN for any LIFX devices. 

# Running the source code
To install the dependencies, run `pip install -r requirements.txt`. PyHook3 has given me some grief installing from pip
in the past, but your millage may vary. 

To run the code from source, simply run `python gui.pyw` from the command line. To run with "Dummy" devices included, 
run `python dummy_devices.py`.

# Testing progress
I have currently only tested on the following operating systems:
* Windows 10

and on the following LIFX devices:
* LIFX A19 Firmware v2.75
* LIFX A13 Firmware v2.75
* LIFX Z   Firmware v1.22

# Donate
LIFX-Control-Panel will always be free and open source. However, if you appriciate the work I'm doing and would like to contribute financially, you can donate below. Thanks for your support!

[![paypal](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://www.paypal.me/sawyermclane)
