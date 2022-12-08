import time
import RPi.GPIO as GPIO
import spidev
from threading import Semaphore, Lock, Thread

spi = spidev.SpiDev()
spi.open(0,0)
spi.max_speed_hz = 4000000
spi.mode = 0b01
