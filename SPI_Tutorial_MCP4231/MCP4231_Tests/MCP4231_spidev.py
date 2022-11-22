#!/usr/bin/python
#
# MCP4231_SPI_Test.py
#	Test SPI-POTX2 card on the Raspberry Pi using RPI_SPI8 SPI mux card
# 	Makes triangle waves
#
# Hardware
# RPI_SPI8 SPI mux card Wiki page:
#	http://land-boards.com/blwiki/index.php?title=RPI_SPI8
# SPI-POTX2 Dual Digital Pot Wiki page:
#	http://land-boards.com/blwiki/index.php?title=SPI-POTX2
#
# Software
# Original mcp4151 (digital pot) code at
#	https://www.takaitra.com/mcp4151-digital-potentiometer-raspberry-pi/
# Setup SPI at
#	https://www.takaitra.com/spi-device-raspberry-pi/
#
# Run with -
# chmod +x MCP4231_SPI_Test.py
# sudo ./MCP4231_SPI_Test.py

import spidev
import time
import RPi.GPIO  as  GPIO


spi = spidev.SpiDev()
spi.open(0, 0)		# bus,device
spi.max_speed_hz = 976000	# speed

GPIO.setmode(GPIO.BOARD)
CSpin = 24
GPIO.setup(CSpin, GPIO.OUT, initial=GPIO.LOW)
# write_pot(potNum,input)
#	potNum - 0,1 - the two pots on the SPI-POTX2 card
#	potVal = 0-127 - 7-bit pot value
def write_pot(potNum,potVal):
	msb = (potNum & 1) << 4		# x << 4 = x*2^4 = x*16
	lsb = potVal & 0x7F
	spi.xfer([msb, lsb])
