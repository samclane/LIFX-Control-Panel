# LIFX-Control-Panel
As LIFX [no longer supports their Windows 10 app](https://www.windowscentral.com/lifx-drops-support-windows-10), I created an open-source alternative for controlling LIFX-brand smart lights. 

![screenshot](https://i.imgur.com/iTdwmSi.png)

The application uses [mclarkk](https://github.com/mclarkk)'s [lifxlan](https://github.com/mclarkk/lifxlan) module to discover and send commands to the lights.

It uses the tk framework for the GUI.

# Quick Start
Go over to [releases](https://github.com/samclane/LIFX-Control-Panel/releases) and download the latest `.exe` file.

Starting the program takes a moment, as it first must scan your LAN for any LIFX devices. 

# Running the source code
To run the code from source, simply run `python gui.pyw` from the command line

# Testing progress
I have currently only tested on the following operating systems:
* Windows 10

and on the following LIFX devices:
* LIFX A19 Firmware v2.75
