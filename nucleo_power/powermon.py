import serial
import serial.tools.list_ports as ports
import logging
from enum import Enum

logger = logging.getLogger(__name__)

class ParseState(Enum):
    IDLE = 0,
    START = 1

class Metadata(object):
    ERROR = 0xF1
    INFO = 0xF2
    TIMESTAMP = 0xF3
    ACQ_END = 0xF4
    OVERCURRENT = 0xF5
    POWERDOWN = 0xF6
    VOLTAGE_GET = 0xF7
    TEMPERATURE = 0xF8
    POWER_GET = 0xF9

    def __init__(self, mdType):
        self._mdType = mdType

class ErrorMd(Metadata):

    def __init__(self, mdType, buf):
        super().__init__(mdType)
        self.error = str(buf, 'ascii')

class InfoMd(Metadata):

    def __init__(self, mdType, buf):
        super().__init__(mdType)
        self.info = str(buf, 'ascii')

class Timestamp(Metadata):

    def __init__(self, mdType, buf):
        super().__init__(mdType)

        self.timestamp = int.from_bytes(buf[:4], 'big', signed = False)
        self.loadPct = int(buf[4])

class AcqEndMd(Metadata):

    def __init__(self, mdType, buf):
        super().__init__(mdType)

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

    def _parse_md(self, metadataType = None):
        collected = False
        if (metadataType is None):
            mdType = int(self._dev.read(1)[0])
        else:
            mdType = metadataType
        logger.debug("Parsing MD of type {}".format(hex(mdType)))
        mdBuf = bytearray()
        while(not collected):
            data = self._dev.read(1)

            if (data[0] == 0xFF):
                secondByte = self._dev.read(1)
                if (secondByte[0] == 0xFF):
                    collected = True
                    break
                else:
                    logger.error("Expected 0xFF in MD detection")

            mdBuf.append(data[0])

        logger.debug("Detected MD type: {} value {}".format(hex(mdType), mdBuf.hex()))

        md = None

        if (mdType == Metadata.ERROR):
            md = ErrorMd(mdType, mdBuf)
            logger.error("Caught MD error: {}".format(md.error))
        elif (mdType == Metadata.INFO):
            md = InfoMd(mdType, mdBuf)
            logger.info("Received MD info: {}".format(md.info))
        elif (mdType == Metadata.TIMESTAMP):
            md = Timestamp(mdType, mdBuf)
            logger.info("Received TS: {} {}".format(md.timestamp, md.loadPct))
        elif (mdType == Metadata.ACQ_END):
            md = AcqEndMd(mdType, mdBuf)
            logger.info("End of ACQ")
        elif (mdType == Metadata.OVERCURRENT):
            logger.error("Overcurrent error")
        return md

    def _parse_data(self):
        state = ParseState.IDLE
        collectedData = bytearray()
        readBytes = 1
        while(True):
            data = self._dev.read(readBytes)

            #we first need to wait for the first metadata message before we can start collection
            if (state == ParseState.IDLE):
                if (data[0] == 0xF0):
                    md = self._parse_md()
                    state = ParseState.START
                    readBytes = 2
            elif (state == ParseState.START):
                if (data[0] == 0xF0):
                    md = self._parse_md(data[1])
                    if (isinstance(md, AcqEndMd)):
                        logger.info("Finished acquisition")
                        break
                else:
                    pass
                    #logger.debug("Collected value: {}".format(self._convert_reading(data)))

    def _convert_reading(self, reading):
        power = (reading[0] & 0xF0) >> 4
        value = int.from_bytes(reading, 'big', signed = False) & 0x0FFF
        return value * (16 ** -power)

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



