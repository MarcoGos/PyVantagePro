# -*- coding: utf-8 -*-
'''
    pyvantagepro.device
    -------------------

    Allows data query of Davis Vantage Pro2 devices

    :copyright: Copyright 2012 Salem Harrache and contributors, see AUTHORS.
    :license: GNU GPL v3.

'''
from __future__ import division, unicode_literals
import struct
from datetime import datetime, timedelta
from .link import link_from_url, SerialLink

from .logger import LOGGER
from .utils import (cached_property, retry, bytes_to_hex,
                    ListDict, is_bytes)

from .parser import (LoopDataParserRevB, DmpHeaderParser, DmpPageParser,
                     ArchiveDataParserRevB, VantageProCRC, pack_datetime,
                     unpack_datetime, pack_dmp_date_time,
                     HighLowParserRevB)


class NoDeviceException(Exception):
    '''Can not access weather station.'''
    value = __doc__


class BadAckException(Exception):
    '''No valid acknowledgement.'''
    def __str__(self):
        return self.__doc__


class BadCRCException(Exception):
    '''No valid checksum.'''
    def __str__(self):
        return self.__doc__


class BadDataException(Exception):
    '''No valid data.'''
    def __str__(self):
        return self.__doc__


class VantagePro2(object):
    '''Communicates with the station by sending commands, reads the binary
    data and parsing it into usable scalar values.

    :param link: A `PyLink` connection.
    '''

    # device reply commands
    WAKE_STR = '\n'
    WAKE_ACK = '\n\r'
    ACK = '\x06'
    NACK = '\x21'
    DONE = 'DONE\n\r'
    CANCEL = '\x18'
    ESC = '\x1b'
    OK = '\n\rOK\n\r'

    def __init__(self, link):
        self.link = link
        self.link.open()
        self._check_revision()

    @classmethod
    def from_url(cls, url, timeout=10):
        ''' Get device from url.

        :param url: A `PyLink` connection URL.
        :param timeout: Set a read timeout value.
        '''
        link = link_from_url(url)
        link.settimeout(timeout)
        return cls(link)

    @classmethod
    def from_serial(cls, tty, baud, timeout=10):
        ''' Get device from serial port.

        :param url: A `PyLink` connection URL.
        :param timeout: Set a read timeout value.
        '''
        link = SerialLink(tty, baud)
        link.settimeout(timeout)
        return cls(link)

    @retry(tries=3, delay=1)
    def wake_up(self):
        '''Wakeup the station console.'''
        wait_ack = self.WAKE_ACK
        LOGGER.info("try wake up console")
        self.link.write(self.WAKE_STR)
        ack = self.link.read(len(wait_ack))
        if wait_ack == ack:
            LOGGER.info("Check ACK: OK (%s)" % (repr(ack)))
            return True
        #Sometimes we have a 1byte shift from Vantage Pro and that's why wake up doesn't work anymore
        #We just shift another 1byte to be aligned in the serial buffer again.
        self.link.read(1)
        LOGGER.error("Check ACK: BAD (%s != %s)" % (repr(wait_ack), repr(ack)))
        raise NoDeviceException()

    @retry(tries=3, delay=0.5)
    def send(self, data, wait_ack=None, timeout=None):
        '''Sends data to station.

         :param data: Can be a byte array or an ASCII command. If this is
            the case for an ascii command, a <LF> will be added.

         :param wait_ack: If `wait_ack` is not None, the function must check
            that acknowledgement is the one expected.

         :param timeout: Define this timeout when reading ACK from link﻿.
         '''
        if is_bytes(data):
            LOGGER.info("try send : %s" % bytes_to_hex(data))
            self.link.write(data)
        else:
            LOGGER.info("try send : %s" % data)
            self.link.write("%s\n" % data)
        if wait_ack is None:
            return True
        ack = self.link.read(len(wait_ack), timeout=timeout)
        if wait_ack == ack:
            LOGGER.info("Check ACK: OK (%s)" % (repr(ack)))
            return True
        LOGGER.error("Check ACK: BAD (%s != %s)" % (repr(wait_ack), repr(ack)))
        raise BadAckException()

    @retry(tries=3, delay=1)
    def read_from_eeprom(self, hex_address, size):
        '''Reads from EEPROM the `size` number of bytes starting at the
        `hex_address`. Results are given as hex strings.'''
        self.link.write("EEBRD %s %.2d\n" % (hex_address, size))
        ack = self.link.read(len(self.ACK))
        if self.ACK == ack:
            LOGGER.info("Check ACK: OK (%s)" % (repr(ack)))
            data = self.link.read(size + 2, binary=True)  # 2 bytes for CRC
            if VantageProCRC(data).check():
                return data[:-2]
            else:
                raise BadCRCException()
        else:
            msg = "Check ACK: BAD (%s != %s)" % (repr(self.ACK), repr(ack))
            LOGGER.error(msg)
            raise BadAckException()

    def write_to_eeprom(self, hex_address, size, data):
        '''Writes to EEPROM the `size` number of bytes starting at the
        `hex_address` with the given `data`. `data` needs to be bytes. CRC will be automatically added.'''
        self.send("EEBWR %s %.2d\n" % (hex_address, size), self.ACK)
        data_with_crc = VantageProCRC(data).data_with_checksum
        self.send(data_with_crc, self.ACK)

    def gettime(self):
        '''Returns the current datetime of the console.'''
        self.wake_up()
        self.send("GETTIME", self.ACK)
        data = self.link.read(8, binary=True)
        return unpack_datetime(data)

    def settime(self, dtime):
        '''Set the given `dtime` on the station.'''
        self.wake_up()
        self.send("SETTIME", self.ACK)
        self.send(pack_datetime(dtime), self.ACK)

    def get_current_data(self):
        '''Returns the real-time data as a `Dict`.'''
        self.wake_up()
        self.send("LOOP 1", self.ACK)
        current_data = self.link.read(99)
        if self.RevB:
            return LoopDataParserRevB(current_data, datetime.now())
        else:
            raise NotImplementedError('Do not support RevB data format')

    def get_hilows(self):
        '''Returns the hilows data as a `Dict`.'''
        self.wake_up()
        self.send("HILOWS", self.ACK)
        hilows_data = self.link.read(438)
        if self.RevB:
            return HighLowParserRevB(hilows_data, datetime.now())
        else:
            raise NotImplementedError('Do not support RevB data format')

    def get_archives(self, start_date=None, stop_date=None):
        '''Get archive records until `start_date` and `stop_date` as
        ListDict.

        :param start_date: The beginning datetime record.

        :param stop_date: The stopping datetime record.
        '''
        generator = self._get_archives_generator(start_date, stop_date)
        archives = ListDict()
        dates = []
        for item in generator:
            if item['Datetime'] not in dates:
                archives.append(item)
                dates.append(item['Datetime'])
        return archives.sorted_by('Datetime')

    def set_yearly_rain(self, rain_clicks: int) -> None:
        '''Set yearly rain in rain clicks'''
        self.wake_up()
        self.send(f"PUTRAIN {rain_clicks}", self.ACK)

    def set_archive_period(self, archive_period: int) -> None:
        '''Set archive period. WARNING: All stored archive data will be erased!!!'''
        self.wake_up()
        self.send(f"SETPER {archive_period}", self.OK)

    def _get_archives_generator(self, start_date=None, stop_date=None):
        '''Get archive records generator until `start_date` and `stop_date`.'''
        self.wake_up()
        # 2001-01-01 01:01:01
        start_date = start_date or datetime(2001, 1, 1, 1, 1, 1)
        stop_date = stop_date or datetime.now()
        # round start_date, with the archive period to the previous record
        period = self.archive_period
        minutes = (start_date.minute % period)
        start_date = start_date - timedelta(minutes=minutes)
        self.send("DMPAFT", self.ACK)
        # I think that date_time_crc is incorrect...
        self.link.write(pack_dmp_date_time(start_date))
        # timeout must be at least 2 seconds
        ack = self.link.read(len(self.ACK), timeout=2)
        if ack != self.ACK:
            raise BadAckException()
        # Read dump header and get number of pages
        header = DmpHeaderParser(self.link.read(6))
        # Write ACK if crc is good. Else, send cancel.
        if header.crc_error:
            self.link.write(self.CANCEL)
            raise BadCRCException()
        else:
            self.link.write(self.ACK)
        LOGGER.info('Starting download %d dump pages' % header['Pages'])
        finish = False
        r_index = 0
        for i in range(header['Pages']):
            # Read one dump page
            try:
                dump = self._read_dump_page()
            except (BadCRCException, BadDataException) as e:
                LOGGER.error('Error: %s' % e)
                finish = True
                break
            LOGGER.info('Dump page no %d ' % dump['Index'])
            # Get the 5 raw records
            raw_records = dump["Records"]
            # loop through archive records
            offsets = zip(range(0, 260, 52), range(52, 261, 52))
            # offsets = [(0, 52), (52, 104), ... , (156, 208), (208, 260)]
            for offset in offsets:
                raw_record = raw_records[offset[0]:offset[1]]
                if self.RevB:
                    record = ArchiveDataParserRevB(raw_record)
                else:
                    msg = 'Do not support RevA data format'
                    raise NotImplementedError(msg)
                # verify that record has valid data, and store
                r_time = record['Datetime']
                if r_time is None:
                    LOGGER.info('Invalid record detected')
                    finish = True
                    break
                elif r_time <= stop_date:
                    if start_date < r_time:
                        not_in_range = False
                        msg = "Record-%.4d - Datetime : %s" % (r_index, r_time)
                        LOGGER.info(msg)
                        yield record
                    else:
                        not_in_range = True
                        LOGGER.info('The record is not in the datetime range')
                else:
                    LOGGER.info('Invalid record detected')
                    finish = True
                    break
                r_index += 1
            if finish:
                LOGGER.info('Canceling download : Finish')
                self.link.write(self.ESC)
                break
            elif not_in_range:
                msg = 'Page is not in the datetime range'
                LOGGER.info('Canceling download : %s' % msg)
                self.link.write(self.ESC)
                break
            else:
                if header['Pages'] - 1 == i:
                    LOGGER.info('Start downloading next page')
                self.link.write(self.ACK)
        LOGGER.info('Pages Downloading process was finished')

    def newsetup(self) -> None:
        '''Re-initializes the console after making certain configuration changes'''
        self.wake_up()
        self.send("NEWSETUP", self.ACK)

    def get_rain_collector(self) -> int:
        '''Get rainc ollector type. 0x00 = 0.01", 0x10 = 0.2mm, 0x20 = 0.1mm'''
        setup_bits = struct.unpack(b"B", self.read_from_eeprom("2B", 1))[0]  # type: ignore
        rain_type = setup_bits & 0x30
        return rain_type

    def set_rain_collector(self, type) -> None:
        '''Set rain collector type. 0x00 = 0.01", 0x10 = 0.2mm, 0x20 = 0.1mm'''
        setup_bits = struct.unpack(b"B", self.read_from_eeprom("2B", 1))[0]  # type: ignore
        setup_bits = (setup_bits & 0xCF) | type
        data = struct.pack(b'>B', setup_bits)
        self.write_to_eeprom("2B", 1, data)
        self.newsetup()

    @cached_property
    def archive_period(self):
        '''Returns number of minutes in the archive period.'''
        return struct.unpack(b'B', self.read_from_eeprom("2D", 1))[0]

    @cached_property
    def timezone(self):
        '''Returns timezone offset as string.'''
        data = self.read_from_eeprom("14", 3)
        offset, gmt = struct.unpack(b'HB', data)
        if gmt == 1:
            return "GMT+%.2f" % (offset / 100)
        else:
            return "Localtime"

    @cached_property
    def firmware_date(self):
        '''Return the firmware date code'''
        self.wake_up()
        self.send("VER", self.OK)
        data = self.link.read(13)
        return datetime.strptime(data.strip('\n\r'), '%b %d %Y').date()

    @cached_property
    def firmware_version(self):
        '''Returns the firmware version as string'''
        self.wake_up()
        self.send("NVER", self.OK)
        data = self.link.read(6)
        return data.strip('\n\r')

    @cached_property
    def diagnostics(self):
        '''Return the Console Diagnostics report. (RXCHECK command)'''
        self.wake_up()
        self.send("RXCHECK", self.OK)
        data = self.link.read().strip('\n\r').split(' ')
        data = [int(i) for i in data]
        return dict(total_received=data[0], total_missed=data[1],
                    resyn=data[2], max_received=data[3],
                    crc_errors=data[4])

    @retry(tries=3, delay=1)
    def _read_dump_page(self):
        '''Read, parse and check a DmpPage.'''
        raw_dump = self.link.read(267)
        if len(raw_dump) != 267:
            self.link.write(self.NACK)
            raise BadDataException()
        else:
            dump = DmpPageParser(raw_dump)
            if dump.crc_error:
                self.link.write(self.NACK)
                raise BadCRCException()
            return dump

    def _check_revision(self):
        '''Check firmware date and get data format revision.'''
        #Rev "A" firmware, dated before April 24, 2002 uses the old format.
        #Rev "B" firmware dated on or after April 24, 2002
        date = datetime(2002, 4, 24).date()
        self.RevA = self.RevB = True
        if self.firmware_date < date:
            self.RevB = False
        else:
            self.RevA = False
