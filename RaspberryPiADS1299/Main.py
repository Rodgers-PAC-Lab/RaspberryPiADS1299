#import spidev
import RPi.GPIO as GPIO
#import RaspberryPiADS1299
#from time import time, sleep
#from threading import Semaphore, Lock, Thread
#

""" ADS1299 PINS """
START_PIN = 22
nRESET_PIN = 23
nPWRDN_PIN = 24
DRDY_PIN = 25

GPIO.setmode(GPIO.BCM)

# setup control pins
#GPIO.setup(START_PIN, GPIO.IN)
#GPIO.setup(nRESET_PIN, GPIO.IN)
#GPIO.setup(START_PIN, GPIO.IN, initial=GPIO.LOW)
#GPIO.setup(nRESET_PIN, GPIO.IN, initial=GPIO.LOW)
#GPIO.setup(nPWRDN_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(nPWRDN_PIN, GPIO.OUT)
GPIO.cleanup()