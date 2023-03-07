import spidev
import RPi.GPIO as GPIO
import time
import datetime
import numpy as np
import pandas
import threading
import queue


#""" ADS1299 PINS """
START_PIN = 22  #Physical pin 15
nRESET_PIN = 23 #Physical pin 16
nPWRDN_PIN = 24 #Physical pin 18
DRDY_PIN = 25   #Physical pin 22
CS_FAKE = 21    #Physical pin 40

GPIO.setmode(GPIO.BCM)

# setup control pins
GPIO.setup(START_PIN, GPIO.OUT, initial= GPIO.LOW)
GPIO.setup(nRESET_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(nPWRDN_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(DRDY_PIN,GPIO.IN)
GPIO.setup(CS_FAKE,GPIO.OUT, initial = GPIO.LOW)

spi = spidev.SpiDev()
spi.open(0,0)
spi.max_speed_hz = 19000000
#spi.max_speed_hz = 4000000
spi.mode = 0b01
spi.no_cs = True
speeds = {
        '0x90': '16k SPS = every 0.0000625 seconds',
        '0x91': '8k SPS = every 0.000125 seconds',
        '0x92': '4k SPS = every 0.00025 seconds',
        '0x93': '2k SPS = every 0.0005 seconds',
        '0x94': '1k SPS = every 0.001 seconds',
        '0x95': '500 SPS = every 0.002 seconds',
        '0x96': '250 SPS = every 0.004 seconds'
        }
def powerup():
    GPIO.output(CS_FAKE, GPIO.LOW) #CS low
    GPIO.output(nRESET_PIN, GPIO.LOW) #reset low
    GPIO.output(START_PIN,GPIO.LOW) #start-cs low
    time.sleep(0.0023)
    GPIO.output(CS_FAKE, GPIO.HIGH) #CS high
    time.sleep(0.006)
    GPIO.output(nRESET_PIN, GPIO.HIGH) #reset high
def startup():
    GPIO.output(CS_FAKE, GPIO.LOW) #CS low
    spi.xfer2([0x11])
    time.sleep(0.001)
    GPIO.output(nRESET_PIN, GPIO.LOW) #reset low
    time.sleep(0.002)
    GPIO.output(nRESET_PIN, GPIO.HIGH) #reset high
    spi.xfer2([0x11])
    time.sleep(0.003)
    spi.xfer2([0x0A])
def RREG(Reg_address):
    # Reads a single register
    spi.xfer2([0x11])
    spi.xfer2([0x11])
    time.sleep(0.05)
    r = 0x20 | int(Reg_address)
    regread = spi.xfer2([r,0x00,0x00],4000000)
    reg_readback = hex(regread[2])
    return reg_readback
def WREG(Reg_address, value):
    # Writes a single register
    spi.xfer2([0x11])
    spi.xfer2([0x11])
    w = 0x40 | int(Reg_address)
    spi.xfer2([w,0x00,value],4000000)
    reg_readback = RREG(Reg_address)
    print("Register ", hex(Reg_address), " is set to:", RREG(Reg_address))
    return reg_readback
def Testsignal_setup():
    spi.xfer2([0x11])
    spi.xfer2([0x11])
    #WREG(0x01,int(0x94))    # Set CONFIG1 w sample speed
    WREG(0x01, int(0x92))  # Set CONFIG1 w sample speed
    WREG(0x03,int(0xE0))  # Set CONFIG3 to use internal reference
    WREG(0x02, int(0xD0))  # Set CONFIG2 for internal test
    chregs = [0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C]
    read = []
    for n in chregs:
      WREG(n,int(0x05))  # Set test signal as channel input
      check = RREG(n)  # Read the register to check it changed
      read.append(check)  # Add that read value to a list
    return read
def closeout():
    spi.close()
    GPIO.cleanup()
def CStoggled_RDATAC(n_samples=10,speed=16000000):
    """Return n_samples of data from 8 channels

    Returns a list of lists. The length of the main list is n_samples,
    and the length of each sub-list is 8 channels.
    """
    # This is where results will be stored
    res_l = []
    bytes_l = []
    start_time = time.time()
    # Iterate over the number of samples requested
    for n_sample in range(n_samples):
        # Capture 27 bytes -- 8 channels, 1 sample, plus a header
        #    s.sel()
        GPIO.output(CS_FAKE, GPIO.LOW)
        results = spi.xfer2(([0x00] * 27),speed)
        GPIO.output(CS_FAKE, GPIO.HIGH)
        print(time.time() - start_time)

        # Iterate over channels, skipping the first "channel" which is c0000c
        sample_l = []
        sbytes_l = []
        for channel in range(1, 9):
            # Slice out the 3 bytes corresponding to this channel
            sample_byt = results[channel * 3:(channel + 1) * 3]

            # Convert that sample to int
            sample_int = int.from_bytes(sample_byt, 'big', signed=True)

            # Store
            sample_l.append(sample_int)
            sbytes_l.append(sample_byt)
        res_l.append(sample_l)
        bytes_l.append(sbytes_l)
    GPIO.output(CS_FAKE, GPIO.LOW)
    end_time = time.time()
    timer = end_time - start_time
    print("It took ", timer, " seconds")
    return res_l, bytes_l,timer
def getSPS(speeds):
    regbyte=RREG(1)
    SPS = speeds[regbyte]
    return SPS

def read_on_DRDY(n_samples, speed=16000000):
   res_l = []
   bytes_l = []
   start_time = time.time()
   for n_sample in range(n_samples):
       # Wait for DRDY or timeout after 5 s
       channel = GPIO.wait_for_edge(DRDY_PIN, GPIO.RISING, timeout=5000)
       if channel is None:
           print('Timeout occured')
       else:
           # Iterate over the number of samples requested
           # Capture 27 bytes -- 8 channels, 1 sample, plus a header
           GPIO.output(CS_FAKE, GPIO.LOW)
           results = spi.xfer2(([0x00] * 27),speed)
           GPIO.output(CS_FAKE, GPIO.HIGH)
           print(time.time() - start_time)

           # Iterate over channels, skipping the first "channel" which is c0000c
           sample_l = []
           sbytes_l = []
           for channel in range(1, 9):
               # Slice out the 3 bytes corresponding to this channel
               sample_byt = results[channel * 3:(channel + 1) * 3]

               # Convert that sample to int
               sample_int = int.from_bytes(sample_byt, 'big', signed=True)

               # Store
               sample_l.append(sample_int)
               sbytes_l.append(sample_byt)
       res_l.append(sample_l)
       bytes_l.append(sbytes_l)
       GPIO.output(CS_FAKE, GPIO.LOW)
       end_time = time.time()
       timer = end_time - start_time
       print("It took ", timer, " seconds")
   return res_l, bytes_l,timer
def parse_resl(results):
    parsedres_l = []
    for n_result in range(0,len(results)):
        sample_l = []
        sbytes_l = []
        single = results[n_result]
        for channel in range(1, 9):
            sample_byt = []
            # Slice out the 3 bytes corresponding to this channel
            sample_byt = single[channel * 3:(channel + 1) * 3]

            # Convert that sample to int
            sample_int = int.from_bytes(sample_byt, 'big', signed=True)

            # Store
            sample_l.append(sample_int)
            sbytes_l.append(sample_byt)
        parsedres_l.append(sample_l)
    return parsedres_l
def callback(channel):
    GPIO.output(CS_FAKE, GPIO.LOW)
    results = spi.xfer2(([0x00] * 27), speed)
    GPIO.output(CS_FAKE, GPIO.HIGH)

    results_l.append(results)
    tresults_l.append(datetime.datetime.now())


powerup()
startup()
Testsignal_setup()
spi.xfer2([0x08])
spi.xfer2([0x10])

speed = 16000000
results_l = []
tresults_l = []

GPIO.add_event_detect(DRDY_PIN, GPIO.FALLING, callback=callback)
time.sleep(1)
GPIO.remove_event_detect(DRDY_PIN)

time.sleep(1)
tresults_arr = np.array(tresults_l)
tresults_arr = np.array(list(map(lambda x: x.total_seconds(), tresults_arr - tresults_arr[0])))
diffs=np.diff(tresults_arr)
meant=np.mean(diffs)
stds= np.std(diffs)
spi.xfer2([0x11])
spi.xfer2([0x11])
spi.xfer2([0x0A])
closeout()
print(len(results_l),'samples collected ', meant*1000,'ms apart, with a std dev of ',stds*1000, 'ms')
