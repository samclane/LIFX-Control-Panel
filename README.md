# LIFX-Control-Panel 

<img align="right" width="120" height="120" title="LIFX-Control-Panel Logo" src="icon.png">
     
LIFX-Control-Panel is an open source application for controlling your LIFX brand lights. It integrates simple features, 
such as monitoring and changing bulb color, with more advanced ones, like:
 
 * Average Screen Color
 * Color Eyedropper
 * Custom color palette
 * Keybindings

<p align="center">
  <img src="screenshot.png" alt="Screenshot" width="306" height=629>
</p>

The application uses [mclarkk](https://github.com/mclarkk)'s [lifxlan](https://github.com/mclarkk/lifxlan) module to 
discover and send commands to the lights.

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

# Building
LIFX-Control-Panel uses PyInstaller. After downloading the repository, open a command window in the `LIFX-Control-Panel`
directory, and run `pyinstaller gui.pyw`. This should generate the necessary file structure to build the project.
Note: Delete `gui.spec`, we will be using one of the following `.spec` files included in the repository:

* `main.spec`
  * This is the file that is used to build the main binary. The console, as well as verbose logging methods, are disabled.
* `debug.spec`
  * This spec file enables the console to run in the background, as well as verbose logging.
* `demo.spec`
  * The demo mode simulates adding several "dummy" lights to the LAN, allowing the software to be demonstrated on networks
  that do not have any LIFX devices on them.

To build the project, simply open a command window in the same folder and run `pyinstaller --onefile <FILE>.spec`, where
`<FILE>` is the name of the build you want (`main`, `debug`, or `demo`). This should generate an `.exe` in the `/dist` 
folder of the project. 

If you want all 3 builds quickly, and you're on Windows, simply run `build_all.bat` in the command prompt. It will 
call `pyinstaller` on all 3 `spec` files previously mentioned. 

If you need help using PyInstaller, more instructions are located [here](https://pythonhosted.org/PyInstaller/usage.html).

# Testing progress
I have currently only tested on the following operating systems:
* Windows 10

and on the following LIFX devices:
* LIFX A19 Firmware v2.76
* LIFX A13 Firmware v2.76 
* LIFX Z   Firmware v1.22
* LIFX Mini White Firmware v3.41

# Donate
LIFX-Control-Panel will always be free and open source. However, if you appreciate the work I'm doing and would like to 
contribute financially, you can donate below. Thanks for your support!

<a href='https://ko-fi.com/J3J8LZKP' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://az743702.vo.msecnd.net/cdn/kofi3.png?v=0' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>

[![paypal](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://www.paypal.me/sawyermclane)
