import time
import pigpio
import os
import numpy as np
import time
import datetime

#os.system('sudo killall pigpiod')
#os.system('sudo pigpiod -t 0 -x 1111110000111111111111110000')

#""" ADS1299 PINS """
START_PIN = 22  #Physical pin 15
nRESET_PIN = 23 #Physical pin 16
nPWRDN_PIN = 24 #Physical pin 18
DRDY_PIN = 25   #Physical pin 22
CS = 8    #Physical pin 24

pi = pigpio.pi(host='192.168.11.222')
print ("I'm in")
h = pi.spi_open(0,16000000,1)
#slowh =pi.spi_open(0,4000000,1)

def powerup():
    pi.write(CS,0)
    pi.write(nRESET_PIN,0)
    pi.write(START_PIN,0)
    time.sleep(0.0023)
    pi.write(CS,1)
    time.sleep(0.006)
    pi.write(nRESET_PIN,1)
def startup():
    pi.write(CS,0)
    pi.spi_xfer(h,[0x11])
    time.sleep(0.001)
    pi.write(nRESET_PIN,0)
    time.sleep(0.002)
    pi.write(nRESET_PIN,1)
    pi.spi_xfer(h,[0x11])
    time.sleep(0.003)
    pi.spi_xfer(h,[0x0A])

def RREG(Reg_address):
    # Reads a single register
    pi.spi_xfer(h,[0x11])
    pi.spi_xfer(h,[0x11])
    time.sleep(0.05)
    r = 0x20 | int(Reg_address)
    pi.spi_xfer(h,[r])
    time.sleep(0.001)
    pi.spi_xfer(h,[0x00])
    time.sleep(0.001)
    regread = pi.spi_xfer(h, [0x00])
    reg_readback = regread[1].hex()
    return reg_readback
def WREG(Reg_address, value):
    # Writes a single register
    pi.spi_xfer(h, [0x11])
    pi.spi_xfer(h, [0x11])
    time.sleep(0.05)
    w = 0x40 | int(Reg_address)
    pi.spi_xfer(h, [w])
    time.sleep(0.001)
    pi.spi_xfer(h, [0x00])
    time.sleep(0.001)
    pi.spi_xfer(h, [value])
    reg_readback = RREG(Reg_address)
    print("Register ", hex(Reg_address), " is set to:", RREG(Reg_address))
    return reg_readback
def Testsignal_setup():
    pi.spi_xfer(h,[0x11])
    time.sleep(0.001)
    pi.spi_xfer(h,[0x11])
    time.sleep(0.001)
    WREG(0x01,int(0x94))    # Set CONFIG1 w sample speed
    time.sleep(0.001)
    WREG(0x03,int(0xE0))  # Set CONFIG3 to use internal reference
    time.sleep(0.001)
    WREG(0x02, int(0xD0))  # Set CONFIG2 for internal test
    chregs = [0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C]
    read = []
    for n in chregs:
      WREG(n,int(0x05))  # Set test signal as channel input
      check = RREG(n)  # Read the register to check it changed
      read.append(check)  # Add that read value to a list
      time.sleep(0.001)
    return read
def DRDY_Callback(gpio,level,tick):
    pi.write(CS,0)
    results = pi.spi_xfer(h,([0x00] * 27))
    pi.write(CS,1)
    #results_l.append(0)
    results_l.append(results[1].hex())
    tresults_l.append(datetime.datetime.now())
# print(tick)

powerup()
startup()
pi.spi_xfer(h,[0x08])
pi.spi_xfer(h,[0x10])
results_l = []
tresults_l = []

listen = pi.callback(DRDY_PIN,pigpio.FALLING_EDGE,DRDY_Callback)
time.sleep(1)
#listen.cancel()

time.sleep(1)
#tresults_arr = np.array(tresults_l)
#tresults_arr = np.array(list(map(lambda x: x.total_seconds(), tresults_arr - tresults_arr[0])))
#diffs=np.diff(tresults_arr)
#meant=np.mean(diffs)
# stds= np.std(diffs)
pi.spi_xfer(h,[0x11])
pi.spi_xfer(h,[0x11])
pi.spi_xfer(h,[0x0A])

#print(len(results_l),'samples collected ', meant*1000,'ms apart, with a std dev of ',stds*1000, 'ms')
