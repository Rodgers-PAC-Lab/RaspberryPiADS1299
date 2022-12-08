from RaspberryPiADS1299 import ADS1299_API
from time import time, sleep
import RPi.GPIO as GPIO
import spidev
from threading import Semaphore, Lock, Thread
# init ads api
ads = ADS1299_API()

# init device
ads.openDevice()
def DefaultCallback(data):
    pass
#    print(repr(data))
# attach default callback
ads.registerClient(DefaultCallback)
# configure ads
ads.configure(nb_channels=1,sampling_rate=1000)
def SPI_readSingleReg(reg):
    ads.spi_lock.acquire()
    print(reg,"register here")
    ads.spi.xfer2([reg | 0x20, 0x00])
    ads.spi_lock.release()
print("ADS1299 API test stream starting_Readme")

# begin test streaming
ads.startTestStream()

# begin EEG streaming
ads.startEegStream()

# wait
sleep(10)
print("Reading register CONFIG1")
REG_CONFIG1 = 0x01
recd = SPI_readSingleReg(REG_CONFIG1)
print(recd, "recd")
#sleep(10)
print("ADS1299 API test stream stopping")

# stop device
ads.stopStream()
# clean up
ads.closeDevice()
sleep(1)
print("Test Over")