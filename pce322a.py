# pce322a.py 
# (C) 2017 Patrick Menschel
import serial
import time
import datetime
import struct
import random
import threading
import queue
import os
import numpy
import subprocess


def int2bcd(i):
    return int(i/10) << 4 | i%10

def bcd2int(i):
    return ((i >> 4) * 10)+ (i & 0xF)
    
def simulate_pce322a():
    ser = serial.Serial(port="COM1",baudrate=115200,timeout=0.1)
    dbvalue = 35.0
    dataframe = bytearray()
    try:
        while True:
            data = ser.read(2)
            if data == b"\xAC\xFF":
                break
        cnt = 0
        while True:
            dbvalue += random.randint(-1,1)
            if dbvalue < 30:
                dbvalue = 30
            elif dbvalue > 130:
                dbvalue = 130

            cmd = ser.read(ser.inWaiting())
            if cmd:
                print("Command {0}".format(["{0:02X}".format(x) for x in cmd]))
            ct = datetime.datetime.now()
            formatteddate = bytearray([int2bcd(int(ct.year%100)),int2bcd(ct.month),int2bcd(ct.day),int2bcd(ct.hour),int2bcd(ct.minute),int2bcd(ct.second)])        
            dataframe.clear()
            
            dataframe.append(0x7F)
            dataframe.extend(struct.pack(">H",int(dbvalue*10)))
            if cnt < 10:
                dataframe.extend((0,3,0))
                
                cnt += 1
                dataframe.extend(formatteddate)
                dataframe.append(0)
            else:
                dataframe.extend((0,3,3))
                cnt = 0
                dataframe.extend(formatteddate)
                dataframe.append(0)
            ser.write(dataframe)
            time.sleep(0.1)

    except KeyboardInterrupt:
        pass
    

class pce_log():
    def __init__(self,fname=None,duration=None):
        self.fname = fname
        if self.fname == None:
            fct = datetime.datetime.now()
            self.fname = os.path.join("/home/shares/public/",fct.strftime("%Y%m%d_%H%M%S.txt"))
        self.starttime = None
        self.endtime = None
        self.maxtime = None
        self.maxvalue = None
        self.mintime = None
        self.minvalue = None
        self.average = None
        self.values = []
        self.mutex = threading.Lock()
        if duration:
            assert(isinstance(duration,datetime.timedelta))
            self.timer = threading.Timer(duration.total_seconds(),self.on_timer)
            self.timer.start()
        
        
    def update_stats(self,timestamp,dbvalue):
        with self.mutex:
            if self.starttime == None:
                self.starttime = timestamp
                self.maxtime = timestamp
                self.maxvalue = dbvalue
                self.mintime = timestamp
                self.minvalue = dbvalue            
            else:
                if dbvalue > self.maxvalue:
                    self.maxtime = timestamp
                    self.maxvalue = dbvalue
                elif dbvalue < self.minvalue:
                    self.mintime = timestamp
                    self.minvalue = dbvalue
                     
            self.endtime = timestamp
            self.values.append(dbvalue)
        return
        
    
    def write_log_file(self,fname=None):
        with self.mutex:
            self.average = numpy.mean(self.values)
            fileheader = """STANDARD SOUND LEVER MERTER DATA LOGGER SamplingRate:0.10;
Time Format: 0
StartTime:{starttime}
EndTime:{endtime}
Max:{maxvalue} {maxtime}
Min:{minvalue} {mintime}
SampleRate:0.10 s
DataNumber:{datanumber}
Average:{average}
HighAlarm:80.0
LowAlarm:20.0
Unit:dBA
""".format(starttime=self.starttime,
           endtime=self.endtime,
           maxvalue=self.maxvalue,
           maxtime=self.maxtime,
           minvalue=self.minvalue,
           mintime=self.mintime,
           datanumber=len(self.values),
           average=self.average)

            if fname:
                fn = fname
            else:
                fn = self.fname
            with open(fn,"w") as f:
                f.write(fileheader)
                for val in self.values:
                    f.write("{0:02}\n".format(val))
        return
    
    def stop(self):
        return self.write_log_file()
        
    def on_timer(self):
        print("Duration Timer Exceeded")
        return self.stop()
    
    def wait(self):
        if self.timer:
            self.timer.join()
        return


        
    
class pce322a():
    def __init__(self,port="/dev/ttyUSB0",debug_level=1):
        self.debug_level=debug_level
        self.ser = serial.Serial(port=port,baudrate=115200,timeout=1)
        if not self.ser.isOpen():
            self.ser.open()
            
        self.rx_mutex = threading.Lock()
        self.tx_mutex = threading.Lock()
        self.framequeue = queue.Queue()
        self.rx_data = bytearray()
        
        self.listeners = []
        
        self.rx_handler = threading.Thread(target=self.handle_rx)
        self.rx_handler.setDaemon(True)
        
        self.measurement_handler = threading.Thread(target=self.handle_measurement)
        self.measurement_handler.setDaemon(True)
        
        self.measurement_handler.start()
        self.rx_handler.start()    
        
        
    def start_streaming_data(self):
        return self.send_command(b"\xAC\xFF")
    
    def send_command(self,cmd):
        with self.tx_mutex:
            return self.ser.write(cmd)
    
    def push_light_switch(self):
        return self.send_command(cmd=b"\xaa\xf6")
        
    def handle_rx(self):
        framelength = 13
        startofframe = 0x7F
        self.ser.flushInput()
        while not self.ser.inWaiting():
            if self.debug_level:
                print("START COMMUNICATION")
            self.start_streaming_data()
            time.sleep(2)
                        
        while True:
            with self.rx_mutex:
                self.rx_data.extend(self.ser.read(framelength-len(self.rx_data)))                
                #1. need data
                if self.rx_data:                    
                    #2. need start of frame at idx 0
                    if startofframe in self.rx_data:
                        idx = self.rx_data.index(startofframe)
                        if idx != 0:
                            #realign the frame window
                            self.rx_data = bytearray(self.rx_data[idx:])
                    #3. need complete frame to continue
                    while len(self.rx_data) >= framelength:
                        #interpret one frame each time
                        self.interpret_frame(data=bytearray(self.rx_data[:framelength]))
                        self.rx_data = bytearray(self.rx_data[framelength:])#maybe 0
                        
        return # non reachable
                            
                            
    def interpret_frame(self,data):
        dbvalue = float(struct.unpack(">H",data[1:3])[0]/10)
        year = bcd2int(data[6])+2000
        month = bcd2int(data[7])
        day = bcd2int(data[8])
        hour = bcd2int(data[9]&0x7F)
        minute = bcd2int(data[10])
        second = bcd2int(data[11])
        
        try:
            timestamp = datetime.datetime(year,month,day,hour,minute,second)
        except ValueError:
            timestamp = "INVALID"
        self.framequeue.put((timestamp,dbvalue))
        return
    
    
    def handle_measurement(self):
        while True:
            timestamp,dbvalue = self.framequeue.get()
            if self.debug_level:
                print("{0} {1}".format(timestamp,dbvalue),end='\r')
            for listener in self.listeners:
                listener.update_stats(timestamp,dbvalue)
            
        return #non reachable

    
    def stop(self):
        for listener in self.listeners:
            listener.stop()
        return
            
    def log(self,duration=None,fname=None):
        log_obj = pce_log(fname=fname,duration=duration)
        self.listeners.append(log_obj)
        return log_obj
        

    
def selftest(testmode,port,duration=datetime.timedelta(minutes=5)):
    my_pce322a = None
    try:
        if testmode == "simulate_pce322a":
            simulate_pce322a() 
        elif testmode == "read_pce322a":
            my_pce322a = pce322a(port=port)
            while True:
                x = my_pce322a.log(datetime.timedelta(hours=8))
                x.wait()

    except KeyboardInterrupt:
        if my_pce322a:
            my_pce322a.stop()
    return     
    
if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-c", "--command", dest="command", default='read_pce322a',
                      help="COMMAND to execute", metavar="COMMAND")
    parser.add_option("-p", "--port", dest="port", default='/dev/ttyUSB0',
                      help="PORT device to use", metavar="PORT")
    (options, args) = parser.parse_args()
 
    selftest(testmode=options.command,port=options.port)
    
    
    
