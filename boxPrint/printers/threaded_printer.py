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
import string
import logging
import threading
import collections
import datetime

from printer import BasePrinter
from printer import BreakPointThread
from serial_connection import SerialConnection
# import config
# import log

class Printer(BasePrinter):

    positive_acks = ['start', 'Grbl ', 'ok']
    resend_request_prefixes = ['resend', 'rs']
    temperature_acks_signs = ["T:", "T0:", "T1:", "T2:"]

    CONNECTION_TIMEOUT = 60
    TEMP_REQUEST_PERIOD = 3
    PAUSE_ON_ERROR_READING_PORT = 0.5
    CONNECTION_RETRIES_PER_BAUDRATE = 2
    CONNECTION_LINE_READ_ATTEMPTS = 2
    CONNECTION_READ_ATTEMPTS = 10
    CONNECTION_GREATINGS_READ_TIMEOUT = 20
    GET_FIRMWARE_VERSION_GCODE = "M115"
    GET_POSITION_GCODE = 'M114'
    GET_TEMP_GCODE = 'M105'
    BOARD_RESET_GCODE = "M999"
    PRINT_JOIN_TIMEOUT = 6

    OK_TIMEOUT = 60

    ok_re = re.compile(".ok")

    def __init__(self, profile, usb_info, connection_class=SerialConnection, buffer_class=collections.deque):
        BasePrinter.__init__(self, profile, usb_info)
        self.define_regexps()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.buffer_class = buffer_class
        self.connection_class = connection_class
        self.operational_flag = False
#         self.finished_flag = False
#         self.correct_baudrate = None
        
        self.start_time = None
        self.print_time_escape = "00:00:00"
        self.print_time_remain = "00:00:00"
        self.printer_state = 1
        self.print_speed = 100
        self.fan_speed = 100
        self.serial_verbose = False
        self.thread_start_lock = threading.Lock()
        self.ready_for_command = threading.Event()
        self.init()

    def init(self):
        if self.connect():
            self.ready_for_command.set()
            #self.logger.info("ready_for_command set.")
            self.in_relative_pos_mode = False
            self.in_heating = False
            self.last_gcode_was_blocking_heating = False
            self.print_thread = None
            self.start_time = None
            self.finished_flag = False
            self.print_time_escape = "00:00:00"
            self.print_time_remain = "00:00:00"
            self.read_thread = threading.Thread(target=self.reading, name="Read thread")
            self.breakpoint_thread = BreakPointThread(self, name="breakpoint_thread")
            self.breakpoint_thread.start()
            self.read_thread.start()
            self.send_homing_gcodes()
            self.start_temp_requesting()
        else:
            self.printer_state = 130
            raise RuntimeError("Can't connection to printer at baudrates: " + str(self.profile['baudrate']))

    def connect(self):
        if not self.usb_info.get('COM'):
            raise RuntimeError("No serial port detected for serial printer")
        self.logger.info('Baudrates list for %s : %s' % (self.profile['name'], self.profile['baudrate']))
        self.printer_state = 2
        for baudrate in self.profile['baudrate']:
            if self.correct_baudrate: #FIXME too ugly
                baudrate = self.correct_baudrate
                self.connection.close()
            self.logger.info("Connecting at baudrate %d" % baudrate)
            if self.profile.has_key('serial_verbose') and self.profile['serial_verbose'] is not None and self.profile['serial_verbose'] != "":
                self.serial_verbose = self.profile['serial_verbose']
            self.connection = self.connection_class(self.usb_info['COM'], baudrate, verbose=self.serial_verbose)
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
        empty_count = 15
        empty_lines = 0
        self.connection.send(self.GET_TEMP_GCODE)
        start_time = time.time()
        while time.time() < start_time + self.CONNECTION_TIMEOUT and not self.stop_flag:
            line = self.connection.recv()
            if line is None:
                break
            if not line:
                empty_lines += 1
            if empty_lines == empty_count:
                break
            if line.startswith(tuple(self.positive_acks)) or 'ok' in line or "T:" in line:
                return True
        return False
# 
#     def read_greetings(self, line):
#         if self.BOARD_RESET_GCODE in line:
#             self.logger.info("Printer's board requested reset. Resetting...")
#             return False
#         for ack in self.positive_acks:
#             if line.startswith(ack):
#                 self.logger.info("Printer is online")
#                 return True
#         for ack in self.temperature_acks_signs:
#             if line.startswith(ack):
#                 self.logger.info("Printer is in blocking heating mode. Need to reset...")
#                 return False

    def analyze_sent_line(self, line):
        self.last_line_sent = line
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
        elif 'M220' in line:
            speed_factor = re.match('.+S([\d\.]+)', line)
            if speed_factor:
                self.print_speed = int(speed_factor.group(1))
        elif 'M106' in line:
            fan_speed = re.match('.+S([\d\.]+)', line)
            if fan_speed:
                self.fan_speed = int(float(fan_speed.group(1)) * 100 / 255)
        elif 'M107' in line:
            self.fan_speed = 0
        self.last_gcode_was_blocking_heating = self.in_heating
        self.in_heating = 'M109' in line or 'M190' in line

    def send_now(self, line_or_lines_list):
        with self.thread_start_lock:
            if not self.print_thread or not self.print_thread.is_alive():
                self.print_thread = PrintThread(self, name="SendNowThread")
                self.add_lines_to_send_now_buffer(line_or_lines_list)
                self.print_thread.start()
            else:
                self.add_lines_to_send_now_buffer(line_or_lines_list)

    def add_lines_to_send_now_buffer(self, line_or_lines_list):
        if type(line_or_lines_list) == str:
            self.print_thread.send_now_buffer.append(line_or_lines_list)
        else:
            self.print_thread.send_now_buffer.extend(line_or_lines_list)

    def send_homing_gcodes(self):
        with self.thread_start_lock:
            self.logger.info("Starting homing thread")
            gcodes = []
            if self.breakpoint_index > 0:
                gcodes.extend(self.outage_gcodes)
                self.printer_state = 10
            else:
                gcodes.extend(self.profile["end_gcodes"])
            gcodes.append(self.GET_FIRMWARE_VERSION_GCODE)
            self.print_thread = PrintThread(self, name="HomingThread")
            self.print_thread.send_now_buffer.extend(gcodes)
            self.print_thread.start()

    def define_regexps(self):
        self.temp_re = re.compile('.*T:([\d\.]+) /([\d\.]+) B:(-?[\d\.]+) /(-?[\d\.]+)')
        '''
                                   ok T:29.1 /0.0 T0:29.1 /0.0 @:0 B@:0
                                   ok T:27.2 /0.0 B:0.0 /0.0 T0:27.2 /0.0 @:0 B@:0
                                   T:69.1 E:0 W:?
        '''
        self.temp_re2 = re.compile("([TB]\d*):([-+]?\d*\.?\d*)(?: ?\/)?([-+]?\d*\.?\d*)")
        self.position_re = re.compile('.*X:(-?[\d\.]+).?Y:(-?[\d\.]+).?Z:(-?[\d\.]+).?E:(-?[\d\.]+).*')
        # self.wait_tool_temp_re = re.compile('T:([\d\.]+) E:(\d+)')
        self.wait_tool_temp_re = re.compile('T:([\d\.]+)')
        self.wait_platform_temp_re = re.compile('.+B:(-?[\d\.]+)')
        self.firmware_re = re.compile(".*(FIRMWARE_NAME:.*$)")
        self.resend_number_re = re.compile("(\d+)")

    #@log.log_exception
    def reading(self):
        last_ok_time = time.time()
        while not self.stop_flag:
            line = self.connection.recv()
            if self.parse_printer_answers(line):
                last_ok_time = time.time()
                if self.last_gcode_was_blocking_heating and not self.in_heating: # dropping in_heating flag
                    self.last_gcode_was_blocking_heating = False                 # after ok on next gcode
            elif not self.in_heating:
                self.in_heating = self.last_gcode_was_blocking_heating # assuming last ok was for blocking heating
                if last_ok_time > time.time() + self.OK_TIMEOUT:
                    message = "Warning! Timeout while waiting for ok. Must be printer error."
                    #config.create_error_report(251, message, self.usb_info, self.logger, is_blocking=False)
                    self.logger.error(message)
                    last_ok_time = time.time()

    def parse_printer_answers(self, line):
        if line is None:  # None means error reading from printer, but "" is ok
            self.operational_flag = False
            time.sleep(self.PAUSE_ON_ERROR_READING_PORT)
        elif not line or "wait" in line:
            return
        elif self.is_ok(line):
            first_message = True
            while self.ready_for_command.is_set() and not self.stop_flag:
                if first_message:
                    message = "Warning! Double ok received! Waiting for sending to complete."
                    #config.create_error_report(251, message, self.usb_info, self.logger, is_blocking=False)
                    self.logger.warn(message)
                    self.logger.info("Last_line: " + self.last_line_sent)
                    first_message = False
                time.sleep(0.01)
            self.ready_for_command.set()
            #self.logger.info("ready_for_command set.")
            self.operational_flag = True
            self.check_temperature_and_position(line)
            return True
        elif line[0] == "T" or line[1] == "T":
            self.parse_waiting_temperature_updates(line)
            self.operational_flag = True
        elif self.check_for_resend_requests(line):
            self.logger.debug(line)
            self.logger.info("Last_line: " + self.last_line_sent)
            self.operational_flag = True
            self.ready_for_command.set()
            #self.logger.info("ready_for_command set.")
        elif line.startswith('Error'):
            self.logger.debug(line)
            self.logger.info("Last_line: " + self.last_line_sent)
            if not ("checksum" in line or
                    "Checksum" in line or
                    "expected line" in line or
                    "Line Number is not Last Line Number+1" in line or
                    "Format error" in line):
                is_blocking = self.BOARD_RESET_GCODE in line or "disabling all for safety!" in line
                self.operational_flag = False
                #config.create_error_report(201, line, self.usb_info, self.logger, is_blocking=is_blocking)
        elif line.startswith('DEBUG'):
            self.logger.info(line)
        else:
            self.log_strange_acks(line)

    def log_strange_acks(self, line):
        self.logger.warning("Received: " + line.strip())

    def start_temp_requesting(self):
        self.stop_temp_requesting_flag = False
        self.temperature_request_thread = threading.Thread(target=self.temperature_requesting, name="TemperatureThread")
        self.temperature_request_thread.start()

    #@log.log_exception
    def temperature_requesting(self):
        STEPS_NUMBER = 100
        sleep_step = self.TEMP_REQUEST_PERIOD / float(STEPS_NUMBER)
        #lines_sent = 0
        while not self.stop_flag and not self.stop_temp_requesting_flag:
            # if self.print_thread and self.print_thread.is_alive():
            #     if self.print_thread.lines_sent > lines_sent:
            #         lines_sent = self.print_thread.lines_sent
            #         if not self.in_heating:
            #             self.send_now(self.GET_TEMP_GCODE)
            # else:
            #     self.send_now(self.GET_TEMP_GCODE)
            if not self.in_heating:
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

    def parse_temperature2(self, line):
        matches = self.temp_re2.findall(line)
        temps = dict((m[0], (m[1], m[2])) for m in matches)

        if "T0" in temps and temps["T0"][0]: tool_temp = float(temps["T0"][0])
        elif "T" in temps and temps["T"][0]: tool_temp = float(temps["T"][0])
        else: tool_temp = 0
        
        if "T0" in temps and temps["T0"][1]: tool_target_temp = float(temps["T0"][1])
        elif "T" in temps and temps["T"][1]: tool_target_temp = float(temps["T"][1])
        else: tool_target_temp = 0
        
        platform_temp = float(temps["B"][0]) if "B" in temps and temps["B"][0] else None
        if platform_temp is not None:
            platform_target_temp = temps["B"][1]
            if platform_target_temp:
                platform_target_temp = float(platform_target_temp)
            else:
                platform_target_temp = 0
        else:
            platform_temp = 0
            platform_target_temp = 0

        self.temps = [platform_temp, tool_temp]
        self.target_temps = [platform_target_temp, tool_target_temp]

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
                    self.logger.info("Request to resend line N%d" % failed_line_number)
                    self.print_thread.lines_sent = failed_line_number
                    return True
                else:
                    self.logger.warning("Can't parse line number from resent request")

    def is_ok(self, line):
        for ack in self.positive_acks:
            if line.startswith(ack):
                return True
        return self.ok_re.match(line)

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
                return self.parse_temperature2(line)

    def load_gcodes(self, gcodes):
        self.logger.info("Loading gcodes in ThreadedSender")
        if gcodes is None or gcodes == "":
            self.logger.info("load_gcodes(): Empty gcodes.")
            return False
        if self.printer_state == 0x87:
            self.logger.info("load_gcodes(): previous print failed.")
            return False
        with self.thread_start_lock:
            if (self.print_thread and self.print_thread.is_alive()):
                self.logger.info("Joining printing thread...")
                self.print_thread.join(timeout=self.PRINT_JOIN_TIMEOUT)
                if self.print_thread.is_alive():
                    message = "Can't start print cause already printing"
                    #config.create_error_report(260, message, self.usb_info, self.logger, is_blocking=False)
                    self.logger.warn(message)
                    return False
            self.start_time = None
            self.print_time_escape = "00:00:00"
            self.print_time_remain = "00:00:00"

            if (self.breakpoint_thread and self.breakpoint_thread.is_alive()):
                pass
            else:
                self.breakpoint_thread = BreakPointThread(self, name="breakpoint_thread")
                self.breakpoint_thread.start()
                
            self.print_thread = PrintThread(self, name="PrintTask")
            self.print_thread.load_gcodes(gcodes)
            self.print_thread.start()
            self.logger.info("Print thread started")
            return True

    def append_gcodes(self, gcodes):
        if gcodes is None or gcodes == "":
            self.logger.info("append_gcodes(): Empty gcodes.")
            return False
        if self.printer_state == 0x87:
            self.logger.info("append_gcodes(): previous print failed.")
            return False
        self.print_thread.append_gcodes(gcodes)
        return True
    def is_printing(self):
        return self.print_thread and self.print_thread.is_alive() and self.print_thread.buffer

    def is_paused(self):
        return self.print_thread and self.print_thread.is_alive() and self.print_thread.paused

    def is_operational(self):
        return self.operational_flag

    def pause(self):
        if self.print_thread:
            if not self.print_thread.paused:
                if self.in_heating:
                    message = "Can't pause during heating."
                    #config.create_error_report(254, message, self.usb_info, self.logger, is_blocking=False)
                    self.logger.warn(message)
                    return False
                self.print_thread.paused = True
                self.was_in_relative_before_pause = self.in_relative_pos_mode
                if not self.in_relative_pos_mode:
                    self.send_now("G91")
                self.send_now("G1 Z+%d E-%d" % (self.pause_lift_height, self.pause_extrude_length))
                return True
        return False

    def unpause(self):
        if self.breakpoint_index > 0:
            self.breakStart()
            self.printer_state = 7
        elif self.print_thread:
            if self.print_thread.paused:
                self.send_now("G1 Z-%d E+%d" % (self.pause_lift_height, self.pause_extrude_length))
                if not self.was_in_relative_before_pause:
                    self.send_now("G90")
                self.print_thread.paused = False
                return True
        return False

    def cancel(self):
        if not self.cancel_download():
            if self.profile.get('no_DTR') and self.in_heating:
                message = "This printer model can't cancel during heating."
                #config.create_error_report(257, message, self.usb_info, self.logger, is_blocking=False)
                self.logger.warn(message)
                return False
            else:
                self.stop_flag = True
                if self.print_thread:
                    self.print_thread.cancel()
                self.print_thread.join()
                self.read_thread.join()
                self.temperature_request_thread.join()
                if self.breakpoint_thread and self.breakpoint_thread.is_alive():
                    self.breakpoint_thread.join()
                self.reset()
                self.stop_flag = False
                try:
                    self.init()
                    self.logger.info("Successful cancel")
                except RuntimeError:
                    message = "Can't reconnect to printer after cancel."
                    #config.create_error_report(255, message, self.usb_info, self.logger, is_blocking=True)
                    self.logger.error(message)

    def reset(self):
        if not self.connection:
            self.logger.warning("No connection to printer to reset")
            return False
        elif self.profile.get('no_DTR'):
            self.logger.warning("DTR reset is forbidden for this printer type. Canceling using gcodes")
            self.connection.send(self.BOARD_RESET_GCODE)
            time.sleep(2)
        else:
            self.connection.reset()
            self.logger.info("Successful reset")

    def get_percent(self):
#         if self.is_downloading():
#             return self.downloader.get_percent()
#         elif self.print_thread:
        if self.print_thread:
            return self.print_thread.get_percent()
        else:
            return 0

    def get_current_line_number(self):
        if self.print_thread:
            return self.print_thread.lines_sent
        else:
            return 0

    def unbuffered_gcodes(self, gcodes):
        self.logger.info("Gcodes to send now: " + str(gcodes))
        gcodes = self.preprocess_gcodes(gcodes)
        gcodes.append(self.GET_POSITION_GCODE)
        self.send_now(gcodes)
        self.logger.info("Gcodes were sent to printer")

    def close(self):
        self.stop_flag = True
        self.logger.debug("Joining reading thread...")
        self.read_thread.join()
        self.logger.debug("...done")
        with self.thread_start_lock:
            if self.print_thread:
                self.logger.debug("Joining printing thread...")
                self.print_thread.join()
                self.logger.debug("...done")
            if self.breakpoint_thread and self.breakpoint_thread.is_alive():
                self.logger.debug("Joining breakpoint thread...")
                self.breakpoint_thread.join()
                self.logger.debug("...done")
        if hasattr(self, "temperature_request_thread"):
            self.logger.debug("Joining temperature thread...")
            self.temperature_request_thread.join()
            self.logger.debug("...done")
        #self.connection.reset()
        self.connection.close()
        
        self.current_print_file = None
        self.initBreakPoint()
        self.breakpoint_index = 0
        self.breakpoint_print_time = 0
        
        self.is_running = False
        self.logger.info("Threaded printer is closed")
        
    def read_state(self):
        if self.printer_state == 10: #pause(outage)
            pass
        elif self.printer_state > 0x80:
            pass
        elif self.is_paused():
            self.printer_state = 8
        elif self.is_printing():
            self.printer_state = 7
        elif self.is_operational():
            self.printer_state = 3

        self.print_progress = round(self.get_percent(), 2)
        if self.print_progress > 1:
            self.logger.error("Print progress error: print_progress == %s" % str(self.print_progress))
            self.print_progress = 0
        self.extruder_amount = 1
        if self.finished_flag:
            self.printer_state = 9
            self.print_progress = 1
            self.print_time_remain = "00:00:00"
            return 
        if self.printer_state == 7:
            if self.start_time is not None:
                print_time = time.time() - self.start_time + self.breakpoint_print_time
#                 if (self.total_gcodes_part1 is not None) and (self.total_gcodes_part2 is not None):
#                     self.total_gcodes = self.total_gcodes_part1 + self.total_gcodes_part2
                percent = self.get_percent()
                if print_time > 0 and percent > 0 and percent < 1:
                    self.print_time_escape = self.getFormattedTimeDelta(datetime.timedelta(seconds=print_time))
                    time_left  = print_time / percent - print_time
                    self.print_time_remain = self.getFormattedTimeDelta(datetime.timedelta(seconds=time_left))
                    if self.print_total_time:
                        time_left2 = self.print_total_time - print_time
                        if time_left2 > 0 and time_left2 < time_left:
                            self.print_time_remain = self.getFormattedTimeDelta(datetime.timedelta(seconds=time_left2))
            else:
                if self.print_total_time:
                    self.print_time_escape = "00:00:00"
                    self.print_time_remain = self.getFormattedTimeDelta(datetime.timedelta(seconds=self.print_total_time))
                
        elif self.printer_state == 3:
            self.print_time_escape = "00:00:00"
            self.print_time_remain = "00:00:00"
        elif self.printer_state == 10:
            if self.breakpoint_total_gcode_len and self.breakpoint_index:
                self.print_progress = round(1.0 * self.breakpoint_index / self.breakpoint_total_gcode_len, 2)
            if self.breakpoint_print_time:
                self.print_time_escape = self.getFormattedTimeDelta(datetime.timedelta(seconds=self.breakpoint_print_time))
                if self.breakpoint_total_time:
                    self.print_time_remain = self.getFormattedTimeDelta(datetime.timedelta(seconds=(self.breakpoint_total_time - self.breakpoint_print_time)))
        else:
            pass

    def goHome(self):
        gcodes = "G28 X0 Y0 Z0"
        self.unbuffered_gcodes(gcodes)

    def goXYHome(self):
        gcodes = "G28 X0 Y0"
        self.unbuffered_gcodes(gcodes)

    def goZHome(self):
        gcodes = "G28 Z0"
        self.unbuffered_gcodes(gcodes)
    
    def goXPosition(self, pos):
        movementSpeedX = 1000
        gcodes = "G91\nG1 X%s F%d\nG90" % (pos, movementSpeedX)
        self.unbuffered_gcodes(gcodes)
        
    def goYPosition(self, pos):
        movementSpeedY = 1000
        gcodes = "G91\nG1 Y%s F%d\nG90" % (pos, movementSpeedY)
        self.unbuffered_gcodes(gcodes)
    
    def goZPosition(self, pos):
        movementSpeedZ = 200
        gcodes = "G91\nG1 Z%s F%d\nG90" % (pos, movementSpeedZ)
        self.unbuffered_gcodes(gcodes)
        
    def goEOperation(self, e, length):
        movementSpeedE = 300
        gcodes = "G91\nT%s G1 E%s F%d\nG90" % (e, length, movementSpeedE)
        self.unbuffered_gcodes(gcodes)

    def setBedTargetTemp(self, temp):
        gcodes = "M140 S%s T0" % temp
        self.unbuffered_gcodes(gcodes)
    
    def setETargetTemp(self, e, temp):
        gcodes = "M104 S%s T%s" % (temp, e)
        self.unbuffered_gcodes(gcodes)
        
    def setSpeedFactor(self, speedfactor):
        gcodes = "M220 S%s" % (speedfactor)
        self.unbuffered_gcodes(gcodes)
        
    def toOperational(self):
        self.finished_flag = False
        if self.print_thread.buffer and len(self.print_thread.buffer) != 0:
            with self.print_thread.buffer_lock:
                self.print_thread.buffer.clear()
        if self.printer_state == 0x87:
            self.unbuffered_gcodes("\n".join(self.profile['end_gcodes']))
        self.printer_state = 3
        



class PrintThread(threading.Thread):

    RESUME_WAITING_STEP = 0.1
    GO_TO_LINE_N_GCODE = "M110"
    IDLE_WAITING_STEP = 0.1
    IDLE_WAITING_DOWNLOAD = 2

    def __init__(self, printer, name=None):
        self.printer = printer
        self.lines_sent = 0 # need to here for multithreading purposes(lines_sent count be read before load gcodes)
        self.paused = False
        self.canceled = False
        self.buffer = None
        self.buffer_lock = threading.Lock()
        self.send_now_buffer = collections.deque()
        if not name:
            name = self.__class__.__name__
        self.logger = logging.getLogger(name)
        super(PrintThread, self).__init__(name=name)

    def calc_checksum(self, command):
        return reduce(lambda x, y: x ^ y, map(ord, command))

    def load_gcodes(self, gcodes):
        self.logger.info("Starting gcodes loading...")
        gcode_new = self.remove_comments(gcodes)
        if self.printer.breakpoint_index > 0:
            self.lines_sent = self.printer.breakpoint_index - 6
        else:
            self.lines_sent = 0
        gcode_new.insert(0, self.GO_TO_LINE_N_GCODE + " N" + str(self.lines_sent))
        self.printer.total_gcodes += 1
        self.printer.total_gcodes_part1 = len(gcode_new)
        self.logger.info("printer.total_gcodes_part1: " + str(self.printer.total_gcodes_part1))
        with self.buffer_lock:
            self.buffer = self.printer.buffer_class(gcode_new)
        self.logger.info("...done loading gcodes")

    def append_gcodes(self, gcodes):
        gcode_new = self.remove_comments(gcodes)
        self.printer.total_gcodes_part2 = len(gcode_new)
        self.printer.setBreakGcodesLength(self.printer.total_gcodes_part1 + self.printer.total_gcodes_part2)
        self.logger.info("printer.total_gcodes_part2: " + str(self.printer.total_gcodes_part2))
        with self.buffer_lock:
            for code in gcode_new:
                self.buffer.append(code)

    def remove_comments(self, gcodes):
        gcodes = self.printer.preprocess_gcodes(gcodes)
        gcode_new = []
        #remove comments start
        for gcode in gcodes:
            if ";" in gcode:
                line = gcode[0:gcode.find(";")]
                line = line.strip()
                if (len(line) != 0) and (("M" in gcode) or ("G" in gcode)):
                    gcode_new.append(line)
                line2 = gcode[gcode.find(";"):]
                if line2.find(";Print time: ") == 0:
                    if self.printer.print_total_time is None:
                        print_time = self.printer.getGcodePrintTotalTime(line2);
                        if print_time > 0:
                            self.printer.print_total_time = print_time
            elif ("M" in gcode) or ("G" in gcode):
                gcode_new.append(gcode)
        #end
        return gcode_new
    
    def add_line_number_and_checksum(self, line):
        command = "N%d %s" % (self.lines_sent, line)
        command = command + "*" + str(self.calc_checksum(command))
        return command

    def send(self, line, add_checksum=True):
        if add_checksum:
            line = self.add_line_number_and_checksum(line)
        # we need to do this before sending to avoid bugs when resent request change line number before +1
        self.printer.ready_for_command.clear()
        #self.logger.info("ready_for_command clear.")
        #self.logger.info("self.lines_sent: %d" % self.lines_sent)
        #self.logger.info("Send Line to serial %s" % line)
        if self.printer.connection.send(line):
            if add_checksum:
                self.lines_sent += 1
                if self.printer.start_time is None:
                    self.printer.setBreakPrintTime(0)
                else:
                    self.printer.setBreakPrintTime(time.time() - self.printer.start_time)
                self.printer.setBreakLineNumber(self.lines_sent)
            self.printer.analyze_sent_line(line)
        else:
            self.printer.ready_for_command.set()
            #self.logger.info("ready_for_command set.")
            #config.create_error_report(250, "Unable to write to serial port",
            #                           self.printer.usb_info, self.logger, is_blocking=False)
            self.logger.error("Unable to write to serial port.")

    #@log.log_exception
    def run(self):
        index = 0
        e_offset = 0
        z_offset = 0
        line=""
        while not self.printer.stop_flag and self.printer.connection.port:
            if self.printer.printer_state == 0x87:
                self.printer.current_print_file = None
                self.printer.initBreakPoint()
                self.printer.breakpoint_index = 0
                self.printer.breakpoint_print_time = 0
                return
            while not self.printer.ready_for_command.wait(1):
                #self.logger.info("Wait command (%s)." % str(line))
                #self.logger.info("Wait command to be finished.")
                if self.printer.stop_flag:
                    return
            if self.printer.start_time is None:
                if self.lines_sent > 10: 
                    self.printer.start_time = time.time()
            if self.send_now_buffer:
                line = self.send_now_buffer.popleft()
                self.send(line, add_checksum=False)
            elif self.paused:
                time.sleep(self.RESUME_WAITING_STEP)
            else:
                try:
                    #line = self.buffer[self.lines_sent]
                    if not self.buffer_lock.acquire(False):
                        raise RuntimeError
                    line = self.buffer.popleft()
                    #self.logger.info("Breakpoint index: %d" % self.printer.breakpoint_index)
                    if self.printer.breakpoint_index > 0:
                        z_offset_match = re.match('.+Z([\d\.]+)', line)
                        if z_offset_match:
                            z_offset = z_offset_match.group(1)
                        e_offset_match = re.match('.+E([\d\.]+)', line)
                        if e_offset_match:
                            e_offset = e_offset_match.group(1)
                        if 'M109' in line or 'M190' in line:
                            self.printer.send_now(line)
                        if (index + 1) == self.printer.breakpoint_index:
                            self.logger.info("Z_OFFSET: %s, E_OFFSET: %s" % (str(z_offset), str(e_offset)))
                            self.buffer.appendleft("G92 Z%s E%s" % (str(z_offset), str(e_offset)))
                            #"G91", "G1 Z-5 E+7", "G90",
                            self.buffer.appendleft("G90")
                            self.buffer.appendleft("G1 Z-%d E+%d" % (self.printer.pause_lift_height, self.printer.pause_extrude_length))
                            self.buffer.appendleft("G91")
                            self.buffer.appendleft("G28 X0 Y0")
                            self.buffer.appendleft("M110 N%s" % str(self.printer.breakpoint_index - 6))
                        if index < self.printer.breakpoint_index:
                            #self.logger.info("Index: %d" % index)
                            #self.logger.info("Skip line: %s" % line)
                            self.buffer_lock.release()
                            index = index + 1
                            self.printer.ready_for_command.set()
                            #self.logger.info("ready_for_command set.")
                            continue
                        else:
                            self.printer.breakpoint_index = 0
                            self.logger.info("Break line: %s" % line)
                except RuntimeError:
                    time.sleep(self.IDLE_WAITING_STEP)
                except (IndexError, AttributeError):
                    self.buffer_lock.release()
                    self.logger.debug(threading.currentThread().getName() + " is finished.")
                    if threading.currentThread().getName() == "PrintTask":
                        if not self.canceled:
                            if ((self.printer.gcode_part_count == 1) and (self.printer.total_gcodes_part1 is not None)) or ((self.printer.gcode_part_count == 2) and (self.printer.total_gcodes_part2 is not None)):
                                self.printer.current_print_file = None
                                self.printer.initBreakPoint()
                                self.printer.breakpoint_index = 0
                                self.printer.breakpoint_print_time = 0
                                self.printer.finished_flag = True
                                self.printer.gcode_part_count = None
                                self.printer.total_gcodes_part1 = None
                                self.printer.total_gcodes_part2 = None
                                self.printer.pushMessage2Client()
                            elif (self.printer.gcode_part_count == 2) and (self.printer.total_gcodes_part2 is None):
                                continue
                            else:
                                if self.printer.printer_state == 0x87:
                                    self.printer.current_print_file = None
                                    self.printer.initBreakPoint()
                                    self.printer.breakpoint_index = 0
                                    self.printer.breakpoint_print_time = 0
                        else:
                            self.printer.current_print_file = None
                            self.printer.initBreakPoint()
                            self.printer.breakpoint_index = 0
                            self.printer.breakpoint_print_time = 0

                    if self.buffer:
                        with self.buffer_lock:
                            self.buffer.clear()
                        self.buffer = None
                    return
                else:
                    self.buffer_lock.release()
                    self.send(line)

    def pause(self):
        self.paused = True

    def unpause(self):
        self.paused = False

    def cancel(self):
        with self.buffer_lock:
            if self.buffer:
                self.buffer.clear()
            self.buffer = None
        self.canceled = True
        self.printer.current_print_file = None
        self.printer.initBreakPoint()
        self.printer.breakpoint_index = 0
        self.printer.breakpoint_print_time = 0

    def get_percent(self):
        if not self.lines_sent:
            return 0
        else:
            return self.lines_sent * 1.0 / self.printer.total_gcodes
