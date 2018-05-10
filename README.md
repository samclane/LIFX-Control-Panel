# LIFX-Control-Panel 

<img align="right" width="120" height="120"
     title="LIFX-Control-Panel Logo" src="https://i.imgur.com/pm4Lzgx.png">
     
As LIFX [no longer supports their Windows 10 app](https://www.windowscentral.com/lifx-drops-support-windows-10), I created an open-source alternative for controlling LIFX-brand smart lights. 

<p align="center">
  <img src="https://i.imgur.com/7LqocH6.png" alt="Screenshot" width="285" height="438">
</p>

The application uses [mclarkk](https://github.com/mclarkk)'s [lifxlan](https://github.com/mclarkk/lifxlan) module to discover and send commands to the lights.

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
