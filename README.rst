# soundmeter
=======================

The project's goal is to develop autonomous datalogging and evaluation of a soundmeter device.
The basic setup is a Raspberry Pi, that is connected to the soundmeter device with USB.
The Raspberry Pi logs live data to files and serves them via Samba/NFS directory.
Recording of noise sample is to be done by USB audio card with "arecord".
