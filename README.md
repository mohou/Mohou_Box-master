# Mohou_Box
=========

Mohou box is the 3D printer control software. Mohou box supports all Printrun compatible printers as well as Makerbots (Makerbot Replicator2 etc.). This is its client part. Server part is located at 

http://yun.mohou.com.

The phone app part is located at

Andoid version:　http://android.myapp.com/myapp/detail.htm?apkName=com.mohou.printer.

iphone verion: apple app store.

Functions:

1) Autodetection and autoconnection

No need to select port or baudrate, mohou box autodetects the 3D printer.

2) Remote control

Keep an eye on the temperatures of your hotends and print bed and adapt them on the fly.
Move the print head along all axes, extrude, retract or just define your own custom controls.
Start, stop or just pause your current print job, you are in full control at any time.

3) Monitoring

Web Cameras support(Watch remotely how your printer is printing your model).

Installation
------------
You already have Python 2.7, pip and virtualenv set up on your system:

1. Checkout mohou box: `git clone https://github.com/mohou/Mohou_Box-master`
2. Change into the home folder: `cd /home/pi`
3. Create a user-owned virtual environment therein: `virtualenv oprint`
4. `cp -r Mohou_Box-master/* /home/pi/oprint/lib/python2.7/site-packages/`
5. `cd /home/pi/oprint/lib/python2.7/site-packages/`
6. `mv boxAgent boxAgent-1.0.0-py2.7.egg`
7. `mv boxPrint boxPrint-1.0.0-py2.7.egg`
8. `mv boxUpdate boxUpdate-1.0.0-py2.7.egg`

Dependencies
------------

Mohou box depends on a couple of python modules to do its job. 

        psutil, tornado, pyyaml, network-interfaces



