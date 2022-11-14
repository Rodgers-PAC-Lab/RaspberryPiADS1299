"""
# file: ADS1299_API.py
# author: Frederic Simard (frederic.simard.1@outlook.com)
# version: Fall 2017
# descr: This files implements the basic features required to operate the ADS1299 using the SPI port
         of a Raspberry Pi (tested on RPi 3, Raspbian Lite Jessie).
         
         The API handles the communication over the SPI port and uses a separate thread - managed by GPIO - 
         to process samples sent by the ADS1299. Samples received are pushed to a registered callback in 
         the form of a numpy Array with a length equal to the number of channels (think of observer pattern).
         
         A default Callback that prints out values on screen is provided in this file and registered in the test script.
         
         A stubbed mode is also available to develop with the API offline, in that mode random numbers are
         returned at a rate close to the defined sampling rate. Stubbed mode becomes active whenever spidev
         cannot be imported properly. 
         
         Public methods overview:
         
             Basic operations:
                - init, initialise the API
                - openDevice, open SPI, power-up/reset sequence the ADS1299 and push default configuration
                - closeDevice, close SPI, power down ADS1299
                
            Configuration:
                - configure, is the public interface to change system configuration. It uses optional parameters
                        - nb_channels, sets the number of channels {1,8}, default 8
                        - sampling_rate, sets the sampling rate {250,500,1000,2000*}, default 500
                        - bias_enabled, used to enable/disable Bias drive {True,False}, default True
                    Note: changing any option will interrupt any active stream
                    Note: 2000Hz sampling rate is unstable, it requires the 24 bits conversion to be done in a different thread
                    Note: gain is set to 24 and is not configurable, should you add this functionnality, make sure to 
                
                - registerClient, add a callback to use for data
                
            Control:
                - startEegStreaming, starts streaming of eeg data using active configuration
                - startTestStream, starts streaming of test data (generated by ADS1299)
                - stopStreaming, stop any on-going stream
                - reset ADS1299, toggle reset pin on ADS1299
            
         Hardware configuration:
            The Raspberry Pi 3 is used as a reference
            
                Signal  |  RPi Pin  |  ADS Pin
                --------------------------------
                MOSI    |     19    |    DIN
                MISO    |     21    |    DOUT
                SCLK    |     23    |    SCLK
                CS      |     24    |    CS
                --------------------------------
                START   |     15    |    START
                RESET   |     16    |    nRESET
                PWRDN   |     18    |    nPWRDN
                DRDY    |     22    |    DRDY
         
            The pins for the SPI port cannot be changed. CS can be flipped, if using /dev/spidev0.1 instead.
            The GPIOS can be reaffected.
            
  Requirements and setup:
    - numpy:  https://scipy.org/install.html
    - spidev:  https://pypi.python.org/pypi/spidev
    - how to configure SPI on raspberry Pi: https://www.raspberrypi.org/documentation/hardware/raspberrypi/spi/README.md
      Note: I had to $sudo chmod 777 /dev/spide0.0 and reboot the raspberry pi to get access to the SPI device
"""

import struct
from threading import Semaphore, Lock, Thread
from time import time, sleep
import random
import platform
import sys

import numpy as np

STUB_SPI = False
try:
    import spidev
except ImportError:
    STUB_SPI = True
    pass

STUB_GPIO = False
try:
    import RPi.GPIO as GPIO
except:
    STUB_GPIO = True

# eeg data scaling function
# adjusted from (5/Gain)/2^24, where gain is 24
# note: datasheet says 4.5 instead of 5, but this value was determined experimentally
SCALE_TO_UVOLT = 0.0000000121

"""
# conv24bitsToFloat(unpacked)
# @brief utility function that converts signed 24 bits integer to scaled floating point
#        the 24 bits representation needs to be provided as a 3 bytes array MSB first
# @param unpacked (bytes array) 24 bits data point
# @return data scaled to uVolt
# @thanks: https://github.com/OpenBCI/OpenBCI_Python/blob/master/open_bci_ganglion.py
"""


def conv24bitsToFloat(unpacked):
    """ Convert 24bit data coded on 3 bytes to a proper integer """
    if len(unpacked) != 3:
        raise ValueError("Input should be 3 bytes long.")

    # FIXME: quick'n dirty, unpack wants strings later on
    literal_read = struct.pack('3B', unpacked[0], unpacked[1], unpacked[2])

    # 3byte int in 2s compliment
    if (unpacked[0] > 127):
        pre_fix = bytes(bytearray.fromhex('FF'))
    else:
        pre_fix = bytes(bytearray.fromhex('00'))

    literal_read = pre_fix + literal_read;

    # unpack little endian(>) signed integer(i) (makes unpacking platform independent)
    myInt = struct.unpack('>i', literal_read)[0]

    # convert to uVolt
    return myInt * SCALE_TO_UVOLT


"""
DefaultCallback
@brief used as default client callback for tests 
@data byte array of 1xN, where N is the number of channels
"""


def DefaultCallback(data):
    pass
    #print repr(data)


""" ADS1299 PINS """
START_PIN = 22
nRESET_PIN = 23
nPWRDN_PIN = 24
DRDY_PIN = 25

""" ADS1299 registers map """
REG_CONFIG1 = 0x01
REG_CONFIG2 = 0x02
REG_CONFIG3 = 0x03
REG_CHnSET_BASE = 0x05
REG_MISC = 0x15
REG_BIAS_SENSP = 0x0D
REG_BIAS_SENSN = 0x0E

""" ADS1299 Commands """
RDATAC = 0x10
SDATAC = 0x11

MAX_NB_CHANNELS = 8

"""
# ADS1299_API
# @brief Encapsulated API, provides basic functionnalities
#        to configure and control a ADS1299 connected to the SPI port
"""


class ADS1299_API(object):
    # spi port
    spi = None

    # thread processing inputs
    stubThread = None
    APIAlive = True

    # lock over SPI port
    spi_lock = None

    # array of client handles
    clientUpdateHandles = []

    # device configuration
    nb_channels = 8  # {1-8}
    sampling_rate = 500  # {250,500,1000,2000,4000}
    bias_enabled = False  # {True, False}

    # True when a data stream is active
    stream_active = False

    """ PUBLIC
    # Constructor
    # @brief
    """

    def __init__(self):
        if STUB_SPI == False:
            self.spi = spidev.SpiDev()

    """ PUBLIC
    # openDevice
    # @brief open the ADS1299 interface and initialize the chip
    """

    def openDevice(self):

        if STUB_SPI == False and STUB_GPIO == False:

            # open and configure SPI port
            self.spi.open(0, 0)
            self.spi.max_speed_hz = 4000000
            self.spi.mode = 0b01

            # using BCM pin numbering scheme
            GPIO.setmode(GPIO.BCM)

            # setup control pins
            GPIO.setup(START_PIN, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(nRESET_PIN, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(nPWRDN_PIN, GPIO.OUT, initial=GPIO.LOW)

            # setup DRDY callback
            GPIO.setup(DRDY_PIN, GPIO.IN)
            GPIO.add_event_detect(DRDY_PIN, GPIO.FALLING, callback=self.drdy_callback)

        else:

            # setup fake data generator
            print("stubbed mode")
            APIAlive = True
            self.stubThread = Thread(target=self.stubTask)
            self.stubThread.start()

        # spi port mutex
        self.spi_lock = Lock()

        # init the ADS1299
        self.ADS1299StartupSequence()

        return

    """ PUBLIC
    # closeDevice
    # @brief close and clean up the SPI, GPIO and running thread
    """

    def closeDevice(self):
        if STUB_SPI == False and STUB_GPIO == False:
            self.spi.close()
            GPIO.cleanup()

        self.APIAlive = False
        return

    """ PUBLIC
    # startEegStream
    # @brief Init an eeg data stream
    """

    def startEegStream(self):

        # stop any on-going stream
        self.resetOngoingState()

        # setup EEG mode
        self.setupEEGMode()
        self.stream_active = True

        # start the stream
        self.SPI_transmitByte(RDATAC)

    """ PUBLIC
    # startTestStream
    # @brief Init a test data stream
    """

    def startTestStream(self):

        # stop any on-going stream
        self.resetOngoingState()

        # setup test mode
        self.setupTestMode()

        # start the stream
        self.stream_active = True
        self.SPI_transmitByte(RDATAC)

    """ PUBLIC
    # stopStream
    # @brief shut down any active stream
    """

    def stopStream(self):
        # stop any on-going ads stream
        self.SPI_transmitByte(SDATAC)
        self.stream_active = False

    """ PUBLIC
    # registerClient
    # @brief register a client handle to push data
    # @param clientHandle, update handle of the client
    """

    def registerClient(self, clientHandle):
        self.clientUpdateHandles.append(clientHandle)

    """ PUBLIC
    # configure
    # @brief provide the ADS1299 configuration interface, it uses optional parameters
    #        no parameter validation take place, make sure to provide valid value
    #   - nb_channels {1-8}
    #   - sampling_rate {250, 500, 1000, 2000, 4000}
    #   - bias_enabled {True, False}
    """

    def configure(self, nb_channels=None, sampling_rate=None, bias_enabled=None):

        self.stopStream()

        if nb_channels is not None:
            self.nb_channels = nb_channels

        if sampling_rate is not None:
            self.sampling_rate = sampling_rate

        if sampling_rate is not None:
            self.bias_enabled = bias_enabled

    # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    #   ADS1299 control
    # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

    """ PRIVATE
    # ADS1299StartupSequence
    # @brief start-up sequence to init the chip
    """

    def ADS1299StartupSequence(self):

        # pwr and reset goes up
        self.setnReset(True)
        self.setnPWRDN(True)

        # wait
        sleep(1)

        # toggle reset
        self.toggleReset()

        # send SDATAC
        self.resetOngoingState()

        self.setStart(True)
        self.SPI_transmitByte(RDATAC)

    """ PRIVATE
    # setupEEGMode
    # @brief setup EEG mode for data streaming
    """

    def setupEEGMode(self):

        # Write CHnSET 05h (connects test signal)
        # (0) normal operation
        # (110) PGA gain 24
        # (0) SRB2 open
        # (000) Normal operations
        tx_buf = [0] * self.nb_channels
        for i in range(0, self.nb_channels):
            tx_buf[i] = 0x60;
        self.SPI_writeMultipleReg(REG_CHnSET_BASE, tx_buf);

        # set the MUX for SRB1 to be connected to all N pins
        # MISC register (multiple single-ended electrodes)
        self.SPI_writeSingleReg(REG_MISC, 0x20);

        # setup bias
        if self.bias_enabled:
            self.setupBiasDrive()

    """ PRIVATE
    # setupTestMode
    # @brief setup TEST mode for data streaming
    """

    def setupTestMode(self):

        # stop any on-going ads stream
        self.SPI_transmitByte(SDATAC)

        # Write CONFIG2 D0h
        # (110) reserved
        # (1) test signal generated internally
        # (0) reserved
        # (0) signal amplitude: 1 x -(VREFP - VREFN) / 2400
        # (00) test signal pulsed at fCLK / 2^21
        self.SPI_writeSingleReg(REG_CONFIG2, 0xD0)

        # Write CHnSET 05h (connects test signal)
        tx_buf = [0] * self.nb_channels
        for i in range(0, self.nb_channels):
            tx_buf[i] = 0x65
        self.SPI_writeMultipleReg(REG_CHnSET_BASE, tx_buf)

    """ PRIVATE
    # resetOngoingState
    # @brief reset the registers configuration
    """

    def resetOngoingState(self):
        # send SDATAC
        self.SPI_transmitByte(SDATAC)

        # setup CONFIG3 register
        self.SPI_writeSingleReg(REG_CONFIG3, 0xE0)

        # setup CONFIG1 register
        self.setSamplingRate()

        # setup CONFIG2 register
        self.SPI_writeSingleReg(REG_CONFIG2, 0xC0)

        # disable any bias
        self.SPI_writeSingleReg(REG_BIAS_SENSP, 0x00)
        self.SPI_writeSingleReg(REG_BIAS_SENSN, 0x00)

        # setup CHnSET registers
        tx_buf = [0] * MAX_NB_CHANNELS
        for i in range(0, MAX_NB_CHANNELS):
            # input shorted
            tx_buf[i] = 0x01
        self.SPI_writeMultipleReg(REG_CHnSET_BASE, tx_buf)

    """ PRIVATE
    # setSamplingRate
    # @brief set CONFIG1 register, which defines the sampling rate
    """

    def setSamplingRate(self):

        temp_reg_value = 0x90  # base value

        # chip in sampling rate
        if self.sampling_rate == 2000:
            temp_reg_value |= 0x03
        elif self.sampling_rate == 1000:
            temp_reg_value |= 0x04
        elif self.sampling_rate == 500:
            temp_reg_value |= 0x05
        else:
            temp_reg_value |= 0x06

        self.SPI_writeSingleReg(REG_CONFIG1, temp_reg_value)

    """ PRIVATE
    # setupBiasDrive
    # @brief enable the bias drive by configuring the appropriate registers
    # @ref ADS1299 datasheet, see figure 73, p.67
    """

    def setupBiasDrive(self):

        if self.bias_enabled:

            temp_reg_value = 0x00
            for i in range(0, self.nb_channels):
                temp_reg_value |= 0x01 << i
            self.SPI_writeSingleReg(REG_BIAS_SENSP, temp_reg_value)
            self.SPI_writeSingleReg(REG_BIAS_SENSN, temp_reg_value)
            self.SPI_writeSingleReg(REG_CONFIG3, 0xEC)

    """ PRIVATE
    # stubTask
    # @brief activated in stub mode, will generate fake data
    """

    def stubTask(self):
        while self.APIAlive:
            if self.stream_active:
                for handle in self.clientUpdateHandles:
                    handle(np.random.rand(self.nb_channels))
            sleep(1.0 / float(self.sampling_rate))

    # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    #   GPIO Interface
    # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

    """ PRIVATE
    # drdy_callback
    # @brief callback triggered on DRDY falling edge. When this happens, if the stream
             is active, will get all the sample from the ADS1299 and update all
             clients
    # @param state, state of the pin to read (not used)
    """

    def drdy_callback(self, state):

        # on event, read the data from ADS
        # read 24 + n*24 bits or 3+n*3 bytes
        bit_values = self.SPI_readMultipleBytes(3 + self.nb_channels * 3)

        # skip is no stream active
        if self.stream_active == False:
            return

        data_array = np.zeros(self.nb_channels)
        for i in range(0, self.nb_channels):
            data_array[i] = conv24bitsToFloat(bit_values[(i * 3 + 3):((i + 1) * 3 + 3)])

        # broadcast results
        for handle in self.clientUpdateHandles:
            handle(data_array)

    """ PRIVATE
    # setStart
    # @brief control the START pin
    # @param state, state of the pin to set
    """

    def setStart(self, state):
        if STUB_GPIO == False:
            if state:
                GPIO.output(START_PIN, GPIO.HIGH)
            else:
                GPIO.output(START_PIN, GPIO.LOW)

    """ PRIVATE
    # toggleReset
    # @brief toggle the nRESET pin while respecting the timing
    """

    def toggleReset(self):
        # toggle reset
        self.setnReset(False)
        sleep(0.2)
        self.setnReset(True)
        sleep(0.2)

    """ PRIVATE
    # setnReset
    # @brief control the nRESET pin
    # @param state, state of the pin to set
    """

    def setnReset(self, state):
        if STUB_GPIO == False:
            if state:
                GPIO.output(nRESET_PIN, GPIO.HIGH)
            else:
                GPIO.output(nRESET_PIN, GPIO.LOW)

    """ PRIVATE
    # setnPWRDN
    # @brief control the nPWRDN pin
    # @param state, state of the pin to set
    """

    def setnPWRDN(self, state):
        if STUB_GPIO == False:
            if state:
                GPIO.output(nPWRDN_PIN, GPIO.HIGH)
            else:
                GPIO.output(nPWRDN_PIN, GPIO.LOW)

    # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    #   SPI Interface
    # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

    """ PRIVATE
    # SPI_transmitByte
    # @brief push a single byte on the SPI port
    # @param byte, value to push on the port
    """

    def SPI_transmitByte(self, byte):

        if STUB_SPI == False:
            self.spi_lock.acquire()
            self.spi.xfer2([byte])
            self.spi_lock.release()

    """ PRIVATE
    # SPI_writeSingleReg
    # @brief write a value to a single register
    # @param reg, register address to write to
    # @param byte, value to write
    """

    def SPI_writeSingleReg(self, reg, byte):

        if STUB_SPI == False:
            self.spi_lock.acquire()
            self.spi.xfer2([reg | 0x40, 0x00, byte])
            self.spi_lock.release()

    """ PRIVATE
    # SPI_writeMultipleReg
    # @brief write a series of values to a series of adjacent registers
    #        the number of adjacent registers to write is defined by the length
    #        of the value array
    # @param start_reg, base address from where to start writing
    # @param byte_array, array of bytes containing registers values
    """

    def SPI_writeMultipleReg(self, start_reg, byte_array):

        if STUB_SPI == False:
            tmp = [start_reg | 0x40]
            tmp.append(len(byte_array) - 1)
            for i in range(0, len(byte_array)):
                tmp.append(byte_array[i])
            self.spi_lock.acquire()
            self.spi.xfer2(tmp)
            self.spi_lock.release()

    """ PRIVATE
    # SPI_readMultipleBytes
    # @brief read multiple bytes from the SPI port
    # @param nb_bytes, nb of bytes to read
    """

    def SPI_readMultipleBytes(self, nb_bytes):

        r = []

        if STUB_SPI == False:
            self.spi_lock.acquire()
            r = self.spi.xfer2([0x00] * nb_bytes)
            self.spi_lock.release()
            for i in range(0, nb_bytes):
                r[i]

        return r


def _test():
    print("Starting validation sequence")

    # init ads api
    ads = ADS1299_API()

    # init device
    ads.openDevice()
    # attach default callback
    ads.registerClient(DefaultCallback)
    # configure ads
    ads.configure(sampling_rate=1000)

    print("ADS1299 API test stream starting")

    # begin test streaming
    ads.startEegStream()

    # wait
    sleep(10)

    print("ADS1299 API test stream stopping")

    # stop device
    ads.stopStream()
    # clean up
    ads.closeDevice()

    sleep(1)
    print("Test Over")


if __name__ == "__main__":
    _test()
