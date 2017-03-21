# peak8005.py 
# (C) 2017 Patrick Menschel
import serial
import threading
import sys
from queue import Queue
import time

class peak8005():
    def __init__(self,port='/dev/ttyUSB0'):
        try:
            self._ser = serial.Serial(port=port,baudrate=9600,timeout=0.1,bytesize=serial.SEVENBITS,parity=serial.PARITY_EVEN)
            self._ser.flushInput()
        except serial.SerialException:
            print('Unable to open Serial Port {0}'.format(port))
            sys.exit(0)
            
    def print_rx(self):
        data = self._ser.read(20)
        if data:
            print(" ".join(["{0:02x}".format(b) for b in data]))
        else:
            time.sleep(1)
        return    
        
    
                        
if __name__ == '__main__':
    my_peak8005 = peak8005()
    try:        
        while True:
            my_peak8005.print_rx()
    except KeyboardInterrupt:
        print('Exit')
        
