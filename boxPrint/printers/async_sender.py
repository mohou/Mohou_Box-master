#Copyright (c) 2015 3D Control Systems LTD

#3DPrinterOS client is free software: you can redistribute it and/or modify
#it under the terms of the GNU Affero General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.

#3DPrinterOS client is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU Affero General Public License for more details.

#You should have received a copy of the GNU Affero General Public License
#along with 3DPrinterOS client.  If not, see <http://www.gnu.org/licenses/>.

# Author: Vladimir Avdeev <another.vic@yandex.ru>

import re
import time
import serial
import string
import logging
import platform
import threading
import subprocess
import collections

from base_sender import BaseSender
import config
import log


class SerialConnection:

    DEFAULT_TIMEOUT = 1
    WRITE_FAIL_WAIT = 0.1
    MAX_LINE_SIZE = 256 #protection against endless line when baudrate mismatch
    WRITE_RETRIES = 4

    def __init__(self, port_name, baudrate, timeout=DEFAULT_TIMEOUT, start_dtr=None, verbose=False):
        self.logger = logging.getLogger("app." + self.__class__.__name__)
        self.port_name = port_name
        self.baudrate = baudrate
        self.timeout = timeout
        self.start_dtr = start_dtr
        self.port_recv_lock = threading.Lock()
        self.port_send_lock = threading.Lock()
        self.verbose = verbose
        self.port = None
        self.connect()

    def connect(self):
        self.control_ttyhup(self.port_name, False)
        try:
            port = serial.Serial(port=self.port_name,
                                 baudrate=self.baudrate,
                                 timeout=self.timeout,
                                 parity=serial.PARITY_ODD)
            port.close()
            port.parity = serial.PARITY_NONE
            if self.start_dtr is not None:
                try:
                    port.setDTR(self.start_dtr)
                except:
                    pass
            port.open()
            self.port = port
        except serial.SerialException as e:
            self.logger.warning("Can't open serial port %s. Error:%s" % (self.port_name, e.message))
        except Exception as e:
            self.logger.warning("Unexpected error while open serial port %s:%s" % (self.port_name, str(e)))
        else:
            self.logger.info("Opened serial port %s at baudrate %d" % (self.port_name, self.baudrate))

    def control_ttyhup(self, port_name, hup_flag):
        if hup_flag:
            hup_command = "hup"
        else:
            hup_command = "-hup"
        if platform.system() == "Linux":
            subprocess.call("stty -F %s %s" % (port_name, hup_command), shell=True)

    def recv(self, size=None):
        with self.port_recv_lock:
            if not self.port:
                self.logger.warning("Can't perform the read - no connection to serial port")
            else:
                try:
                    if size:
                        data = self.port.read(size)
                    else:
                        data = self.port.readline(self.MAX_LINE_SIZE)
                    if self.verbose:
                        self.logger.info("RECV: " + str(data))
                except serial.SerialException as e:
                    self.logger.warning("Can't read serial port %s. Error:%s" % (self.port_name, e.message))
                except Exception as e:
                    self.logger.warning("Unexpected error while reading serial port %s:%s" % (self.port_name, str(e)))
                else:
                    return data

    def prepare_data(self, data):
        return str(data) + "\n"

    def send(self, data):
        with self.port_send_lock:
            if not self.port:
                self.logger.warning("Can't perform the write - no connection to serial port")
            else:
                bytes_send = None
                fails = 0
                data = self.prepare_data(data)
                while not bytes_send:
                    try:
                        bytes_send = self.port.write(data)
                        if self.verbose:
                            self.logger.info("SEND: " + data.strip())
                        if bytes_send != len(data):
                            self.logger.error("Critical error. The data sent to serial port was cut.")
                            return False
                    except serial.SerialException as e:
                        self.logger.warning("Can't write to serial port %s. Error:%s" % (self.port_name, e.message))
                        fails += 1
                        time.sleep(self.WRITE_FAIL_WAIT)
                        if fails > self.WRITE_RETRIES:
                            self.logger.error("Can't send data to serial port")
                            return True
                    else:
                        return bytes_send

    def reset(self):
        with self.port_send_lock:
            with self.port_recv_lock:
                if self.port:
                    self.port.setDTR(1)
                    time.sleep(0.2)
                    self.port.setDTR(0)

    def close(self):
        with self.port_send_lock:
            with self.port_recv_lock:
                if self.port:
                    self.port.close()
                    self.port = None


class Sender(BaseSender):

    positive_acks = ['start', 'Grbl ', 'ok']
    resend_request_prefixes = ['resend', 'rs']
    temperature_acks_signs = ["T:", "T0:", "T1:", "T2:"]
    pause_lift_height = 5
    pause_extrude_length = 7

    CONNECTION_TIMEOUT = 6
    TEMP_REQUEST_PERIOD = 3
    PAUSE_ON_ERROR_READING_PORT = 0.5
    CONNECTION_READ_ATTEMPTS = 10
    CONNECTION_RETRIES_PER_BAUDRATE = 2
    GET_FIRMWARE_VERSION_GCODE = "M115"
    GET_POSITION_GCODE = 'M114'
    GET_TEMP_GCODE = 'M105'
    BOARD_RESET_GCODE = "M999"

    def __init__(self, profile, usb_info, connection_class=SerialConnection, buffer_class=collections.deque):
        BaseSender.__init__(self, profile, usb_info)
        self.define_regexps()
        self.logger = logging.getLogger("app." + self.__class__.__name__)
        self.buffer_class = buffer_class
        self.connection_class = connection_class
        self.operational_flag = False
        self.correct_baudrate = None
        self.send_now_lock = threading.Lock()
        self.homing_lock = threading.Lock()
        self.init()

    def init(self):
        if self.connect():
            self.ready_for_command = True
            self.print_thread = None
            self.read_thread = threading.Thread(target=self.reading, name="Read thread")
            self.read_thread.start()
            self.send_homing_gcodes()
            self.temperature_request_thread = threading.Thread(target=self.temperature_requesting, name="Temperature thread")
            self.temperature_request_thread.start()
            self.in_relative_pos_mode = False
        else:
            raise RuntimeError("Can't connection to printer at baudrates: " + str(self.profile['baudrate']))

    def connect(self):
        if not self.usb_info.get('COM'):
            raise RuntimeError("No serial port detected for serial printer")
        self.logger.info('Baudrates list for %s : %s' % (self.profile['name'], self.profile['baudrate']))
        for baudrate in self.profile['baudrate']:
            if self.correct_baudrate: #FIXME too ugly
                baudrate = self.correct_baudrate
                self.connection.close()
            self.logger.info("Connecting at baudrate %d" % baudrate)
            self.connection = self.connection_class(self.usb_info['COM'], baudrate)
            if self.connection.port:
                retries = 0
                while not self.stop_flag and retries <= self.CONNECTION_RETRIES_PER_BAUDRATE:
                    connection_result =  self.wait_for_online()
                    if connection_result:
                        self.correct_baudrate = baudrate
                        self.logger.info("Successful connection to %s: %s" % (self.profile['alias'], str(self.usb_info)))
                        return True
                    elif connection_result == None:
                        retries += 1
                    else:
                        retries = self.CONNECTION_RETRIES_PER_BAUDRATE + 1
                    self.connection.reset()
                    time.sleep(2)
            self.logger.warning("Error connecting to printer at %d" % baudrate)
            self.connection.close()

    def wait_for_online(self):
        start_time = time.time()
        while time.time() < start_time + self.CONNECTION_TIMEOUT and not self.stop_flag:
            if self.connection.send(self.GET_TEMP_GCODE):
                return self.read_greetings()

    def read_greetings(self):
        line_read_attempts = 0
        while not self.stop_flag and line_read_attempts < self.CONNECTION_READ_ATTEMPTS:
            line = ""
            read_attempts = 0
            while not self.stop_flag and read_attempts <= self.CONNECTION_READ_ATTEMPTS:
                symbol = self.connection.recv(1)
                read_attempts += 1
                if not symbol or symbol == "\n":
                    break
                elif not ord(symbol):
                    time.sleep(0.1)
                elif not symbol in string.printable:
                    return False
                else:
                    read_attempts = 0
                    line += symbol
            if self.BOARD_RESET_GCODE in line:
                self.logger.info("Printer's board requested reset. Resetting...")
                return False
            for ack in self.positive_acks:
                if line.startswith(ack):
                    self.logger.info("Printer is online")
                    return True
            for ack in self.temperature_acks_signs:
                if line.startswith(ack):
                    self.logger.info("Printer is in blocking heating mode. Need to reset...")
                    return False
            line_read_attempts += 1

    def analyze_sent_line(self, line): #TODO FIXME
        self.last_line = line
        if 'M109' in line:
            tool_match = re.match('.+T(\d+)', line)
            if tool_match:
                tool = int(tool_match.group(1)) + 1
            else:
                tool = 1
            temp_match = re.match('.+S([\d\.]+)', line)
            if temp_match:
                if not tool >= len(self.target_temps):
                    self.target_temps[tool] = float(temp_match.group(1))
        elif 'M190' in line:
            temp_match = re.match('.+S([\d\.]+)', line)
            if temp_match:
                self.target_temps[0] = float(temp_match.group(1))
        elif 'G90' in line:
            self.in_relative_pos_mode = False
        elif 'G91' in line:
            self.in_relative_pos_mode = True
        self.in_heating = 'M109' in line or 'M190' in line

    def send_now(self, line):
        with self.send_now_lock:
            if self.print_thread and self.print_thread.is_alive():
                self.print_thread.send_now_buffer.append(line)
            else:
                with self.homing_lock:
                    self.homing_thread.join()
                while not self.ready_for_command:
                    if self.stop_flag:
                        return
                    if not self.operational_flag:
                        return
                    time.sleep(PrintThread.OK_WAITING_STEP)
                self.ready_for_command = False
                if self.connection.send(line):
                    self.analyze_sent_line(line)
                    # we need to wait for processing of current command, to avoid errors in print_thread
                    while not self.ready_for_command:
                        if self.stop_flag:
                            return
                        if not self.operational_flag:
                            return
                        time.sleep(PrintThread.OK_WAITING_STEP)
                else:
                    self.ready_for_command = True
                    config.create_error_report("Unable to write to serial port", 250,
                                               self.usb_info, self.logger, is_blocking=False)

    def send_homing_gcodes(self):
        with self.send_now_lock:
            self.homing_lock.acquire()
            self.logger.info("Sending homing gcodes...")
            #gcodes = [self.GET_FIRMWARE_VERSION_GCODE]
            gcodes = []
            gcodes.extend(self.profile["end_gcodes"])
            self.homing_thread = SendThread(self, gcodes)
            self.homing_thread.start()
            self.logger.info("...done sending homing gcodes")
            self.homing_lock.release()

    def define_regexps(self):
        self.temp_re = re.compile('.*T:([\d\.]+) /([\d\.]+) B:(-?[\d\.]+) /(-?[\d\.]+)')
        self.position_re = re.compile('.*X:(-?[\d\.]+).?Y:(-?[\d\.]+).?Z:(-?[\d\.]+).?E:(-?[\d\.]+).*')
        # self.wait_tool_temp_re = re.compile('T:([\d\.]+) E:(\d+)')
        self.wait_tool_temp_re = re.compile('T:([\d\.]+)')
        self.wait_platform_temp_re = re.compile('.+B:(-?[\d\.]+)')
        self.firmware_re = re.compile(".*(FIRMWARE_NAME:.*$)")
        self.resend_number_re = re.compile("(\d+)")

    @log.log_exception
    def reading(self):
        while not self.stop_flag:
            line = self.connection.recv()
            if line is None:  # None means error reading from printer, but "" is ok
                self.operational_flag = False
                time.sleep(self.PAUSE_ON_ERROR_READING_PORT)
            elif not line or "wait" in line:
                continue
            elif self.is_ok(line):
                self.ready_for_command = True
                self.operational_flag = True
                self.check_temperature_and_position(line)
            elif line.startswith("T"):  # FIXME T is too ambitious
                self.parse_waiting_temperature_updates(line)
                self.operational_flag = True
            elif self.check_for_resend_requests(line):
                self.logger.debug(line)
                self.operational_flag = True
                self.ready_for_command = True
            elif line.startswith('Error'):
                if not ("checksum" in line or
                        "Checksum" in line or
                        "expected line" in line or
                        "Line Number is not Last Line Number+1" in line or
                        "Format error" in line):
                    is_blocking = self.BOARD_RESET_GCODE in line or "disabling all for safety!" in line
                    self.operational_flag = False
                    config.create_error_report(201, line, self.usb_info, self.logger, is_blocking=is_blocking)
                else:
                    self.logger.debug(line)
            elif line.startswith('DEBUG'):
                self.logger.info(line)
            else:
                self.logger.warning("Special message: " + line.strip())

    @log.log_exception
    def temperature_requesting(self):
        STEPS_NUMBER = 100
        sleep_step = self.TEMP_REQUEST_PERIOD / float(STEPS_NUMBER)
        last_line_send = 0
        while not self.stop_flag:
            if self.print_thread and self.print_thread.is_alive():
                if self.print_thread.lines_sent > last_line_send:
                    last_line_send = self.print_thread.lines_sent
                    self.send_now(self.GET_TEMP_GCODE)
            else:
                self.send_now(self.GET_TEMP_GCODE)
            sleep_step_count = STEPS_NUMBER
            while not self.stop_flag and sleep_step_count:
               time.sleep(sleep_step)
               sleep_step_count -= 1

    def parse_temperature(self, line):
        self.logger.debug(line)
        match = self.temp_re.match(line)
        if match:
            tool_temp = float(match.group(1))
            tool_target_temp = float(match.group(2))
            platform_temp = float(match.group(3))
            platform_target_temp = float(match.group(4))
            self.temps = [platform_temp, tool_temp]
            self.target_temps = [platform_target_temp, tool_target_temp]
            return True

    def parse_waiting_temperature_updates(self, line):
        match = self.wait_platform_temp_re.match(line)
        if match:
            self.temps[0] = float(match.group(1))
        match = self.wait_tool_temp_re.match(line)
        if match:
            self.temps[1] = float(match.group(1))

    def check_for_resend_requests(self, line):
        for prefix in self.resend_request_prefixes:
            if line.lower().startswith(prefix):
                match = self.resend_number_re.search(line)
                if match:
                    failed_line_number = int(match.group(1))
                    self.logger.warning("Request to resend line N%d" % failed_line_number)
                    try:
                        self.print_thread.lines_sent = failed_line_number
                    except AttributeError:
                        pass
                    return True
                else:
                    self.logger.warning("Can't parse line number from resent request")

    def is_ok(self, line):
        for ack in self.positive_acks:
            if line.startswith(ack):
                return True

    def check_temperature_and_position(self, line):
        match = self.position_re.match(line)
        if match:
            self.position = [float(match.group(1)), float(match.group(2)), float(match.group(3)), float(match.group(4))]
        match = self.firmware_re.match(line)
        if match:
            firmware_info = match.group(1)
            self.logger.info("Firmware info: " + firmware_info)
            self.profile['firmware_info'] = firmware_info
        for sing in self.temperature_acks_signs:
            if sing in line:
                return self.parse_temperature(line)

    def load_gcodes(self, gcodes):
        if not self.print_thread or not self.print_thread.is_alive():
            with self.homing_lock:
                self.homing_thread.join()
            with self.send_now_lock:
                self.print_thread = PrintThread(self, gcodes)
                self.print_thread.start()
        else:
            return False

    def is_printing(self):
        return self.print_thread and self.print_thread.is_alive()

    def is_paused(self):
        return self.print_thread and self.print_thread.is_alive() and self.print_thread.paused

    def is_operational(self):
        return self.operational_flag

    def pause(self):
        if self.print_thread:
            if not self.print_thread.paused:
                # if self.in_heating:
                #     message = "Can't pause during heating."
                #     config.create_error_report(254, message, self.usb_info, self.logger, is_blocking=False)
                #     return False
                self.print_thread.paused = True
                self.was_in_relative_before_pause = self.in_relative_pos_mode
                if not self.in_relative_pos_mode:
                    self.send_now("G91")
                self.send_now("G1 Z+%d E-%d" % (self.pause_lift_height, self.pause_extrude_length))
                return True
        return False

    def unpause(self):
        if self.print_thread:
            if self.print_thread.paused:
                self.send_now("G1 Z-%d E+%d" % (self.pause_lift_height, self.pause_extrude_length))
                if not self.was_in_relative_before_pause:
                    self.send_now("G90")
                self.print_thread.paused = False
                return True
        return False

    def cancel(self):
        if self.cancel_download():
            return
        self.stop_flag = True
        if self.print_thread:
            self.print_thread.cancel()
            self.print_thread.join()
        self.read_thread.join()
        self.temperature_request_thread.join()
        self.reset()
        self.stop_flag = False
        try:
            self.init()
            self.logger.info("Successful cancel")
        except RuntimeError:
            message = "Can't reconnect to printer after cancel."
            config.create_error_report(255, message, self.usb_info, self.logger, is_blocking=True)

    def reset(self):
        if not self.connection:
            self.logger.warning("No connection to printer to reset")
            return False
        elif self.profile.get('no_DTR'):
            self.logger.warning("DTR reset is forbidden for this printer type. Canceling using gcodes")
            self.connection.send(self.BOARD_RESET_GCODE)
        else:
            self.connection.reset()
            self.logger.info("Successful reset")

    def get_percent(self):
        if self.is_downloading():
            percent = self.downloader.get_percent()
        elif self.print_thread:
            percent = self.print_thread.get_percent()
        else:
            percent = 0
        return percent

    def get_current_line_number(self):
        if self.print_thread:
            return self.print_thread.lines_sent
        else:
            return 0

    def unbuffered_gcodes(self, gcodes):
        self.logger.info("Gcodes for unbuffered execution: " + str(gcodes))
        for gcode in self.preprocess_gcodes(gcodes):
            self.send_now(gcode)
        self.send_now(self.GET_POSITION_GCODE)
        self.logger.info("Gcodes were sent to printer")

    def close(self):
        self.stop_flag = True
        self.read_thread.join()
        if self.print_thread:
            self.print_thread.join()
        if getattr(self, "temperature_request_thread", None):
            self.temperature_request_thread.join()
        #self.connection.reset()
        self.connection.close()
        self.is_running = False
        self.logger.info("Closed")


class PrintThread(threading.Thread):

    OK_WAITING_STEP = 0.0001
    RESUME_WAITING_STEP = 0.1
    GO_TO_LINE_N_GCODE = "M110"

    def __init__(self, sender, gcodes, no_checksums = False):
        self.sender = sender
        self.lines_sent = 0 # need to here for multithreading purposes(lines_sent count be read before load gcodes)
        self.paused = False
        self.buffer = None
        self.gcodes = gcodes
        self.send_now_buffer = collections.deque()
        self.logger = logging.getLogger("app." + self.__class__.__name__)
        self.no_checksums = no_checksums
        super(PrintThread, self).__init__(name=self.__class__.__name__)

    def calc_checksum(self, command):
        return reduce(lambda x, y: x ^ y, map(ord, command))

    def add_line_number_and_checksum(self, line, force_line_number=None):
        if force_line_number:
            line_number = force_line_number
        else:
            line_number = self.lines_sent
        command = "N%d %s" % (line_number, line)
        command = command + "*" + str(self.calc_checksum(command))
        return command

    def load_gcodes(self):
        self.logger.info("Starting gcode loading...")
        if self.gcodes:
            self.gcodes = self.sender.preprocess_gcodes(self.gcodes)
            self.total_gcodes = len(self.gcodes)
            self.lines_sent = 0
            self.buffer = self.sender.buffer_class(self.gcodes)
            self.gcodes = None
        self.logger.info("...done loading gcodes")

    def send(self, line, add_checksum=True, force_line_number=None):
        if add_checksum and not self.no_checksums:
            if not force_line_number is None:
                line = self.add_line_number_and_checksum(line, force_line_number=force_line_number)
            else:
                line = self.add_line_number_and_checksum(line)
        # we need to do this before sending to avoid bugs when resent request change line number before +1
        self.sender.ready_for_command = False
        if add_checksum and not force_line_number:
            self.lines_sent += 1
        if self.sender.connection.send(line):
            self.sender.analyze_sent_line(line)
        else:
            self.sender.ready_for_command = True
            config.create_error_report("Unable to write to serial port", 250,
                                       self.sender.usb_info, self.logger, is_blocking=False)

    @log.log_exception
    def run(self):
        self.load_gcodes()
        if self.buffer:
            self.logger.info("Resetting printer line number")
            while not self.sender.ready_for_command:
                if self.sender.stop_flag:
                    return
            self.send(self.GO_TO_LINE_N_GCODE, force_line_number = -1)
            self.logger.info("...done")
        while not self.sender.stop_flag and self.sender.connection.port:
            while not self.sender.ready_for_command:
                if self.sender.stop_flag:
                    return
                time.sleep(self.OK_WAITING_STEP)
            if self.send_now_buffer:
                line = self.send_now_buffer.popleft()
                self.send(line, add_checksum=False)
            elif self.paused:
                time.sleep(self.RESUME_WAITING_STEP)
            else:
                try:
                    line = self.buffer[self.lines_sent]
                except (IndexError, TypeError):
                    self.logger.info("Print or homing finished.")
                    self.buffer = None
                    return  # TODO: don't break here - last gcode could be corrupted and need to be resent
                except AttributeError:
                    return # mean thread in send thread and there is no buffer except for self.send_now_buffer
                else:
                    self.send(line)

    def pause(self):
        self.paused = True

    def unpause(self):
        self.paused = False

    def cancel(self):
        self.buffer = None

    def get_percent(self):
        if not self.buffer:
            return 0
        else:
            return int(self.lines_sent / float(self.total_gcodes) * 100)


class SendThread(PrintThread):

    def __init__(self, sender, gcodes):
        super(SendThread, self).__init__(sender, None)
        self.send_now_buffer = collections.deque(gcodes)

