import serial
import serial.tools.list_ports as ports
import logging
from enum import Enum

logger = logging.getLogger(__name__)

class ParseState(Enum):
    IDLE,
    START,
    METADATA,
    METADATA_ENDING,
    TIMESTAMP,
    DATA


class PowerMon(object):

    PRODUCT_ID = 0x5740

    def __init__(self, port = None):

        #detect port
        if (port == None):
            ports_list = ports.comports()

            for p in ports_list:
                if (p.pid == PowerMon.PRODUCT_ID):
                    logger.info("Power monitor detected: {}".format(p.device))
                    port = p.device
                    break

            if (port == None):
                #TODO make a real exception for this
                raise Exception("PowerMon could not be detected")

            self._dev = serial.Serial(port, 3864000,
                                     timeout=1, write_timeout=3)

            self._open()

    def _helloworld(self):
        self._send('lcd 1 "Hello World"\n'.encode())
        self._wait_for_data()
        logger.info("Hello World should be on LCD")

    def start(self, voltage = 3000, freq = 100000, duration = 0):
        '''Starts sampling.

        voltage (in mV)
        freq in hz
        duration in seconds. 0 means infinite
        '''

        self._set_format()
        self._set_freq(freq)
        self._set_voltage(voltage)
        self._set_duration(duration)

        logger.info("Starting capture")
        self._start_capture()
        self._parse_data()

    def _parse_data(self):
        state = ParseState.START

        timeStamp = bytearray()

        while(True):
            data = self._dev.read(1)

            if state == ParseState.IDLE:
                if (data[0] == 0xF0):
                    state = ParseState.START
            elif state == ParseState.START:
                if (data[1] == 0xF3):
                    logger.debug("Detecting timestamp")
                    state = ParseState.TIMESTAMP
                    timeStamp = bytearray()
                else:
                    logger.debug("Detecting metadata")
                    state = ParseState.METADATA
            elif state == ParseState.METADATA:
                if (data[0] == 0xFF):
                    state = ParseState.METADATA_ENDING
            elif state == ParseState.METADATA_ENDING:
                if (data[0] == 0xFF):
                    state = ParseState.START.
            elif state == ParseState.TIMESTAMP:

                timeStamp.append(data)

                if (len(timeStamp) == 8):
                    state = ParseState.DATA
            elif state == ParseState.DATA:

            if (len(data) == 0):
                break

            logger.info("RCV: raw {} hex {}".format(data, data.hex()))



    def stop(self):
        #TODO
        pass

    def _start_capture(self):
        self._send('start\n'.encode())
        self._wait_for_data()

    def _set_freq(self, freq):
        freq_cmd = 'freq {}\n'.format(freq)
        self._send(freq_cmd.encode())
        self._wait_for_data()

    def _set_voltage(self, voltage):
        volt_cmd = 'volt {}m\n'.format(str(voltage))
        self._send(volt_cmd.encode())
        self._wait_for_data()

    def _set_duration(self, duration):
        acqtime_cmd = 'acqtime {}\n'.format(str(duration))
        self._send(acqtime_cmd.encode())
        self._wait_for_data()

    def _set_format(self):
        #only supports hex
        format_cmd = 'format bin_hexa\n'
        self._send(format_cmd.encode())
        self._wait_for_data()

    def _send(self, cmd):
        logger.debug("$ {}".format(cmd.decode().strip()))
        self._dev.write(cmd)

    def _wait_for_data(self, lines = 1):
        #TODO this needs a timeout
        while(lines > 0):
            data = self._dev.readline()
            if (len(data.decode().strip()) != 0):
                logger.debug("Line: {}".format(data.decode().strip()))
                lines = lines - 1
            else:
                logger.debug("Empty line")


    def _reset(self):
        logger.info("Resetting board, please wait")
        self._send('psrst\n'.encode())

        #may be too long
        time.sleep(10)

    def _open(self):
        logger.debug('Opening connection')
        self._send('htc\n'.encode())
        self._wait_for_data()

    def close(self):
        self._send('hrc\n'.encode())
        self._wait_for_data()
        logger.debug('Done, exiting')



