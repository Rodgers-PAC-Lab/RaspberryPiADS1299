import spidev
import RPi.GPIO as GPIO
import time
import datetime
import numpy as np
import pandas
import threading
import queue
import os

# This is where chunks are written
data_directory = os.path.expanduser('~/data')
if not os.path.exists(data_directory):
    os.mkdir(data_directory)

# This is where diagnostics are written
diag_directory = os.path.expanduser('~/diagnostics')
if not os.path.exists(diag_directory):
    os.mkdir(diag_directory)

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
def acquire_data(listened_pin):
    GPIO.output(CS_FAKE, GPIO.LOW)
    results = spi.xfer2(([0x00] * 27))
    GPIO.output(CS_FAKE, GPIO.HIGH)
    q.put_nowait(results)
    sample_read_times.append(datetime.datetime.now())

powerup()
startup()
Testsignal_setup()
spi.xfer2([0x08])
spi.xfer2([0x10])
speed = 16000000
save_times_l = []
sample_read_times = []

q = queue.Queue(maxsize=20000)
print("listening")
GPIO.add_event_detect(DRDY_PIN, GPIO.FALLING, callback=acquire_data)

# If a file called 'stop' exists in this directory, remove it
if os.path.exists('stop'):
    os.remove('stop')

# Keep doing this until a file called 'stop' is created in this directory
try:
    while not os.path.exists('stop'):
        # Check if the queue is long enough to write to disk
        #print("got into while True")
        if q.qsize() > 4000:
            # Get all of the data out of the queue
            data_to_write = []
            while True:
                try:
                    data = q.get_nowait()
                    #print(data)
                except queue.Empty:
                    break

                data_to_write.append(data)

            # Here is where we would interpret the bytes
            # using struct.unpack or whatever
            # For now just concatenate
            concatted = np.concatenate(
                data_to_write, dtype=np.uint8, casting='unsafe')

            # Write the concatenated/interpreted data to disk
            # TODO: instead of always using the same filename, we
            # would use a dated filename
            #print('writing to disk')

            # Generate a filename
            time_now = datetime.datetime.now()
            time_now_string = time_now.strftime('%Y%m%d_%H%M%S%f')

            # Save the data
            print('Saved chunk at {}'.format(time_now))
            save_times_l.append(time_now)
            filename = os.path.join(data_directory,
                'chunk_{}'.format(time_now_string))
            np.save(filename, concatted)

        # This sleep just keeps this while-loop from running too
        # frequently
        time.sleep(.1)

except:
    raise

finally:
    # Stop the timer from adding more data to the queue
    # Replace this with a cancellation of the pigpio callback
    GPIO.remove_event_detect(DRDY_PIN)

# If a file called 'stop' exists in this directory, remove it
if os.path.exists('stop'):
    os.remove('stop')

# Extract the time of the sample reads
sample_read_times_arr = np.array(sample_read_times)

# Save the diagnostics
np.save(os.path.join(diag_directory, 'sample_read_times_arr'), sample_read_times_arr)
np.save(os.path.join(diag_directory, 'save_times_arr'), np.array(save_times_l))

# meant=np.mean(diffs)
# stds= np.std(diffs)
spi.xfer2([0x11])
spi.xfer2([0x11])
spi.xfer2([0x0A])

print(getSPS(speeds))
# print(len(results_l), 'samples collected ', round(meant * 1000,5),
#       'ms apart, with a std dev of ', round(stds * 1000,5), 'ms. Sample speed was',
#       getSPS(speeds))
closeout()
