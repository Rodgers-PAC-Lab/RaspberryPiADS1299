import time
import RPi.GPIO as GPIO
import spidev
from threading import Semaphore, Lock, Thread

spi = spidev.SpiDev()
spi.open(0,0)
spi.max_speed_hz = 4000000
spi.mode = 0b01

GPIO.setmode(GPIO.BOARD)
GPIO.setup(40,GPIO.OUT,initial=GPIO.HIGH)
GPIO.output(40,GPIO.LOW)

GPIO.setup(15,GPIO.OUT,initial=GPIO.HIGH)
GPIO.setup(16,GPIO.OUT,initial=GPIO.HIGH)

#Set START high
GPIO.output(16,GPIO.HIGH)
#Wake up from Standby mode
#spi.xfer([0x02])
#Stop RDATAC
#spi.xfer([0x11])

# result = spi.xfer([0x21])
# result2 = spi.xfer([0x00])
# result3=spi.xfer([0x00])
# result4 = spi.xfer([0x00])

singleresult=spi.xfer([0x00,0x00,0x00,0x00])
time.sleep(0.0001)
GPIO.output(40,GPIO.HIGH)
#print([result,result2,result3,result4])
print(singleresult)