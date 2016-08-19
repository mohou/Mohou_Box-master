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
import logging
import threading
import os
# import makerbot_driver
# import serial
# import serial.serialutil
import datetime
# X = [0][0] | 0.1 = 8
# Y = [0][1] | 0.1 = 8
# Z = [0][2] | 0.1 = 4
# E = [0][3]
#import log
from printer import BasePrinter
from printer import BreakPointThread
import gpx
import Queue
#import config
class Printer(BasePrinter):

    PAUSE_STEP_TIME = 0.5
    BUFFER_OVERFLOW_WAIT = 0.01
    IDLE_WAITING_STEP = 0.1
    TEMP_UPDATE_PERIOD = 5
    GODES_BETWEEN_READ_STATE = 100
    BUFFER_OVERFLOWS_BETWEEN_STATE_UPDATE = 20
    MAX_RETRY_BEFORE_ERROR = 100

    def __init__(self, profile, usb_info):
        BasePrinter.__init__(self, profile, usb_info)
        self.logger = logging.getLogger(__name__)
        self.logger.info('Makerbot printer created')
        
        self.gpx_logfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "gpx.log")
        self.gpx_profile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "gpx_profiles", profile['type']+'.ini')
        self.gpx_verbose = profile['gpx_verbose']
                 
#         self.init_target_temp_regexps()
        self.execution_lock = threading.Lock()
        self.buffer_lock = threading.Lock()
        self.parser = None
        #self.finished_flag = False
        #self.correct_baudrate = None
        retries = 5
        self.sending_thread = None
        self.monitor_thread = None
        self.monitor2_thread = None
        self.breakpoint_thread = None
        self.response_queue = Queue.Queue()
        
        self.connect_flag = False
        self.reinit_flag = False
        self.printer_state = 1
        self.start_time = None
        self.print_time_escape = "00:00:00"
        self.print_time_remain = "00:00:00"
        self.print_total_time = None
        
        
        self.current_tool = None
        self.temp = {}
        self.bed_temp = None
        
        self.init()

    def init(self):
        if not self.usb_info.get('COM'):
            raise RuntimeError("No serial port detected for serial printer")
        
        for baudrate in self.profile['baudrate']:
            while not self.sending_thread:
                try:
                    self.printer_state = 2
                    connect_result = gpx.connect(self.usb_info.get('COM'), baudrate, self.gpx_profile, self.gpx_logfile, self.gpx_verbose)
                    self.logger.info("connect result: " + str(connect_result))
                    if 'start' in connect_result:
                        time.sleep(0.1)
                        start_result = gpx.start()
                        self.logger.info("connect result: " + str(start_result))
                        self.correct_baudrate = baudrate
                    else:
                        break
                except Exception as e:
                    if retries > 0:
                        retries -= 1
                        self.logger.warning("Error connecting to printer %s\n%s" % (str(profile), str(e)))
                        time.sleep(1)
                    else:
                        break
                else:
                    self.stop_flag = False
                    self.pause_flag = False
                    self.printing_flag = False
                    self.cancel_flag = False
                    self.current_tool = gpx.get_current_tool()
                    self.sending_thread = threading.Thread(target=self.send_gcodes,  name="send_gcodes")
                    self.monitor_thread = threading.Thread(target=self.monitor,  name="monitor")
                    self.monitor2_thread = threading.Thread(target=self.monitor2,  name="monitor2")
                    self.breakpoint_thread = BreakPointThread(self, name="breakpoint_thread")
                    self.sending_thread.start()
                    self.monitor_thread.start()
                    self.monitor2_thread.start()
                    self.breakpoint_thread.start()

                    if self.sending_thread.is_alive():
                         self.breakpoint_index = 0 # 不支持断电续打
                         if self.breakpoint_index > 0:
                            self.unbuffered_gcodes("\n".join(self.outage_gcodes))
                            self.printer_state = 10
                         else:
                            self.unbuffered_gcodes("\n".join(self.profile["end_gcodes"]))

                    break

            if self.sending_thread:
                break
            
        if not self.sending_thread:
            self.printer_state = 130
            raise RuntimeError("Error connecting to printer %s\n%s" % (str(profile), str(e)))
        
    def reinit(self):
        self.reinit_flag = True
        gpx.disconnect()
        time.sleep(0.2)
        connect_res = gpx.connect(self.usb_info.get('COM'), self.correct_baudrate, self.gpx_profile, self.gpx_logfile, self.gpx_verbose)
        self.reinit_flag = False
        time.sleep(0.5)
        start_res = gpx.start()
        self.logger.info("reinit: connect result %s, start result %s" % (str(connect_res), str(start_res)));

        self.start_time = None
        self.print_time_escape = "00:00:00"
        self.print_time_remain = "00:00:00"
        
        self.stop_flag = False
        self.pause_flag = False
        self.printing_flag = False
        self.cancel_flag = False
        self.current_tool = gpx.get_current_tool()
        
        self.current_print_file = None
        self.initBreakPoint()
        self.breakpoint_index = 0
        self.breakpoint_print_time = 0

    def append_position_and_lift_extruder(self):
        position = gpx.get_current_position()
        if position:
            with self.buffer_lock:
                self.buffer.appendleft('G1 Z' + str(position["z"]))
            z = min(160, position["z"] + 30)
            self.write('G1  Z' + str(z))

    def _append(self, s):
        if (s is not None and s != ''):
            if '\n' in s:
                for item in s.split('\n'):
                    self.response_queue.put(item)
            else:
                self.response_queue.put(s)
    # length argument is used for unification with Printrun. DON'T REMOVE IT!
    def set_total_gcodes(self, length):
        #self.reinit()
        self.total_gcodes = length
        self.write('(@build "Mohou3D")')
        self.write("M136 (Mohou3D)")
        self.current_line_number = 0
        self.logger.info('Begin of GCodes')
        self.printing_flag = False
        #self.execute(lambda: self.parser.s3g.set_RGB_LED(255, 255, 255, 0))

    def load_gcodes(self, gcodes):
        if gcodes is None or gcodes == "":
            self.logger.info("load_gcodes(): Empty gcodes.")
            return False
        if self.printer_state == 0x87:
            self.logger.info("load_gcodes(): previous print failed.")
            return False
        gcode_new = self.remove_comments(gcodes)
        self.logger.info("printer.total_gcodes: " + str(self.total_gcodes))
        self.total_gcodes_part1 = len(gcode_new)
        #self.total_gcodes += 99
        self.set_total_gcodes(self.total_gcodes)
        if self.breakpoint_index > 0:
            self.current_line_number = self.breakpoint_index - 11
        else:
            self.current_line_number = 0
        with self.buffer_lock:
            for code in gcode_new:
                self.buffer.append(code)

        self.printing_flag = True
        self.start_time = None
        self.print_time_escape = "00:00:00"
        self.print_time_remain = "00:00:00"
        return True

    def append_gcodes(self, gcodes):
        if gcodes is None or gcodes == "":
            self.logger.info("append_gcodes(): Empty gcodes.")
            return False
        if self.printer_state == 0x87:
            self.logger.info("load_gcodes(): previous print failed.")
            return False
        gcode_new = self.remove_comments(gcodes)
        self.total_gcodes_part2 = len(gcode_new)
        self.total_gcodes = self.total_gcodes_part1 + self.total_gcodes_part2
        with self.buffer_lock:
            for code in gcode_new:
                self.buffer.append(code)
                
        return True
                
                
    def remove_comments(self, gcodes):
        gcodes = self.preprocess_gcodes(gcodes)
        gcode_new = []
        #remove comments start
        for gcode in gcodes:
            if ";" in gcode:
                line = gcode[0:gcode.find(";")]
                line = line.strip()
                if (len(line) != 0):
                    gcode_new.append(line)
                line2 = gcode[gcode.find(";"):]
                if line2.find(";Print time: ") == 0:
                    if self.print_total_time is None:
                        print_time = self.getGcodePrintTotalTime(line2);
                        if print_time > 0:
                            self.print_total_time = print_time
            else:
                gcode_new.append(gcode)
        #end
        return gcode_new

    def cancel(self, go_home=True):
        if self.cancel_download():
            return
        try:
            gpx.abort()
        except Exception as ex:
            self.logger.error("gpx.abort() Exception: %s." % ex.message)

        self.pause_flag = False
        self.cancel_flag = True
        self.printing_flag = False

        with self.buffer_lock:
            self.buffer.clear()

        time.sleep(1)            
        self.reinit()
 
        #gpx.disconnect()
        #self.init()
    
    def canceled(self):
        with self.buffer_lock:
            self.buffer.clear()
        self.pause_flag = False
        self.cancel_flag = True
        self.printing_flag = False
        self.start_time = None
        self.print_time_escape = "00:00:00"
        self.print_time_remain = "00:00:00"
        
        self.current_print_file = None
        self.initBreakPoint()
        self.breakpoint_index = 0
        self.breakpoint_print_time = 0

    def pause(self):
        if not self.pause_flag and not self.cancel_flag:
            self.pause_flag = True
            time.sleep(0.1)
            self.append_position_and_lift_extruder()
            return True
        else:
            return False

    def unpause(self):
        if self.breakpoint_index > 0:
            self.breakStart()
            self.printer_state = 7
        elif self.pause_flag and not self.cancel_flag:
            self.pause_flag = False
            return True
        else:
            return False

    def emergency_stop(self):
        self.cancel(False)
        self.current_print_file = None

#     def immediate_pause(self):
#         gpx.pause_resume()

    def close(self):
        self.logger.info("Makerbot printer is closing...")
        self.stop_flag = True
        if threading.current_thread() != self.sending_thread:
            self.sending_thread.join(10)
            if self.sending_thread.isAlive():
                self.logger.error("Failed to join sending thread in makerbot_printer.")
            self.monitor_thread.join(10)
            if self.monitor_thread.isAlive():
                self.logger.error("Failed to join monitor thread in makerbot_printer.")
            self.monitor2_thread.join(10)
            if self.monitor2_thread.isAlive():
                self.logger.error("Failed to join monitor2 thread in makerbot_printer.")
            self.breakpoint_thread.join(10)
            if self.breakpoint_thread.isAlive():
                self.logger.error("Failed to join break thread in makerbot_printer.")
        self.sending_thread = None
        self.monitor_thread = None
        self.monitor2_thread = None
        self.breakpoint_thread = None
        #gpx.stop()
        try:
            gpx.disconnect()
        except Exception as ex:
            pass
        
        self.pause_flag = False
        self.printing_flag = False
        self.cancel_flag = False
        self.printer_state = 1
        self.current_print_file = None
        self.initBreakPoint()
        self.breakpoint_index = 0
        self.breakpoint_print_time = 0
        self.logger.info("...done closing makerbot printer.")

    def unbuffered_gcodes(self, gcodes): 
        self.logger.info("Gcodes for unbuffered execution: " + str(gcodes))
        if self.printing_flag or self.pause_flag:
            self.logger.warning("Can't execute gcodes - wrong mode")
            return False
        else:
#             if not self.parser.state.values.get("build_name"):
#                 self.parser.state.values["build_name"] = 'Mohou3D'
            for gcode in self.preprocess_gcodes(gcodes):
                result = self.write(gcode)
                if result:
                    #self.request_position_from_printer()
                    self.logger.info("Printers answer: " + result)
            self.logger.info("Gcodes were sent to printer")
            return True

    def write(self, command):
        res = None
        try:
            command = command.strip()
            try:
                #reprapSave = gpx.reprap_flavor(True)
                timeout_retries = 0
                bo_retries = 0
                while not self.stop_flag:
                    if self.cancel_flag or self.reinit_flag:
                        #self.cancel_flag = False
                        break
                    try:
                        #self.printing_flag = True
                        #self.execution_lock.acquire()
                        res = gpx.write("%s" % command)
                    except gpx.BufferOverflow:
                        #self.execution_lock.release()
                        bo_retries += 1
                        try:
                            if gpx.build_paused():
                                if bo_retries == 1:
                                    time.sleep(1) # 1 sec
                            elif bo_retries == 1:
                                self.logger.info('Makerbot BufferOverflow on ' + command)
                        except IOError:
                            pass
                        if self.start_time is None:
                            self.setBreakPrintTime(0)
                        else:
                            self.setBreakPrintTime(time.time() - self.start_time)
                        self.setBreakLineNumber(self.current_line_number + 1)
                        time.sleep(self.BUFFER_OVERFLOW_WAIT) # 100 ms
                    except gpx.Timeout:
                        #self.execution_lock.release()
                        time.sleep(1)
                        timeout_retries += 1
                        if (timeout_retries >= 5):
                            raise
                    else:
                        #self.execution_lock.release()
                        break
            finally:
                #gpx.reprap_flavor(reprapSave)
                pass
        except gpx.CancelBuild:
            self.canceled()
            self.logger.info("Write: print is canceled.")
        return res

    def read_state(self):
        if self.is_operational():
            try:
                platform_temp           = self.bed_temp[0]
            except Exception as ex:
                platform_temp           = 0
            try:
                platform_ttemp          = self.bed_temp[1]
            except Exception as ex:
                platform_ttemp          = 0
            try:
                head_temp1              = self.temp[0][0]
            except Exception as ex:
                head_temp1              = 0
            try:
                head_ttemp1             = self.temp[0][1]
            except Exception as ex:
                head_ttemp1             = 0
            try:
                head_temp2              = self.temp[1][0]
            except Exception as ex:
                head_temp2              = 0
            try:
                head_ttemp2             = self.temp[1][1]
            except Exception as ex:
                head_ttemp2             = 0

        else:
            platform_temp           = 0
            platform_ttemp          = 0
            head_temp1              = 0
            head_temp2              = 0
            head_ttemp1             = 0
            head_ttemp2             = 0
        self.temps              = [platform_temp, head_temp1, head_temp2]
        self.target_temps       = [platform_ttemp, head_ttemp1, head_ttemp2]
        
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


        self.print_progress = self.get_percent()
        self.fan_speed = 0
        self.print_speed = 100
        self.extruder_amount = 2
        if self.finished_flag:
            self.printer_state = 9
            self.print_progress = 1
            self.print_time_remain = "00:00:00"
            return 
        if self.printer_state == 7:
            if self.start_time is None:
                if self.print_total_time:
                    self.print_time_escape = "00:00:00"
                    self.print_time_remain = self.getFormattedTimeDelta(datetime.timedelta(seconds=self.print_total_time))
                if gpx.is_extruder_ready(self.current_tool):
                    self.start_time = time.time()
            else:
                print_time = time.time() - self.start_time
                if print_time > 0:
                    self.print_time_escape = self.getFormattedTimeDelta(datetime.timedelta(seconds=print_time))
                    progress = self.current_line_number * 1.0 / self.total_gcodes
                    time_left  = print_time / progress - print_time
                    self.print_time_remain = self.getFormattedTimeDelta(datetime.timedelta(seconds=time_left))
                    if self.print_total_time:
                        time_left2 = self.print_total_time - print_time
                        if time_left2 > 0 and time_left2 < time_left:
                            self.print_time_remain = self.getFormattedTimeDelta(datetime.timedelta(seconds=time_left2))
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

    def is_paused(self):
        return self.pause_flag

    def is_operational(self):
        return self.sending_thread.is_alive() and self.monitor_thread.is_alive() and self.monitor2_thread.is_alive()

    #@log.log_exception
    def send_gcodes(self):
#         last_time = time.time()
#         counter = 0
        index = 0
        e_offset = 0
        z_offset = 0
        command=""
        while not self.stop_flag:
            if self.printer_state == 0x87:
                self.current_print_file = None
                self.initBreakPoint()
                self.breakpoint_index = 0
                self.breakpoint_print_time = 0
                continue
#             counter += 1
#             current_time = time.time()
#             if (counter >= self.GODES_BETWEEN_READ_STATE) or (current_time - last_time > self.TEMP_UPDATE_PERIOD):
#                 counter = 0
#                 last_time = current_time
#                 self._append(self.write("M105"))
            if self.pause_flag:
                self.printing_flag = False
                time.sleep(self.PAUSE_STEP_TIME)
                continue
            try:
                if not self.buffer_lock.acquire(False):
                    raise RuntimeError
                command = self.buffer.popleft()
                if self.breakpoint_index > 0:
                    z_offset_match = re.match('.+Z([\d\.]+)', command)
                    if z_offset_match:
                        z_offset = z_offset_match.group(1)
                    e_offset_match = re.match('.+E([\d\.]+)', command)
                    if e_offset_match:
                        e_offset = e_offset_match.group(1)
                    else:
                        e_offset_match = re.match('.+A([\d\.]+)', command)
                        if e_offset_match:
                            e_offset = e_offset_match.group(1)
                        else:
                            e_offset_match = re.match('.+B([\d\.]+)', command)
                            if e_offset_match:
                                e_offset = e_offset_match.group(1)
                    if "M133" in command or "M130" in command or command.startswith("T") or 'M135' in command or 'M104' in command or 'M109' in command or 'M190' in command:
                        self._append(self.write(command))
                    if (index + 1) == self.breakpoint_index:
                        self.logger.info("Z_OFFSET: %s, E_OFFSET: %s" % (str(z_offset), str(e_offset)))
                        #self.buffer.appendleft("G1 X0 Y0 Z%s" % str(z_offset))
                        #"G91", "G1 Z-5 E+7", "G90",
                        #self.buffer.appendleft("M132 X Y Z A B")
                        '''
                        G162 X Y F2000(home XY axes maximum)
                        G161 Z F900(home Z axis minimum)
                        G92 X0 Y0 Z-5 A0 B0 (set Z to -5)
                        G1 Z0.0 F900(move Z to '0')
                        G161 Z F100(home Z axis minimum)
                        M132 X Y Z A B (Recall stored home offsets for XYZAB axis)
                        '''
#                       self.buffer.appendleft("G92 X0 Y0 Z%s" % (str(z_offset)))
                        self.buffer.appendleft("G92 Z%s E%s" % (str(z_offset), str(e_offset)))
                        self.buffer.appendleft("G0 X-90 Y-73 Z%s F2000" % str(z_offset))
                        self.buffer.appendleft("M132 X Y Z A B")
                        self.buffer.appendleft("G161 Z F900")
                        self.buffer.appendleft("G1 Z0.0 F900")
                        self.buffer.appendleft("G92 X0 Y0 Z-5 A0 B0")
                        self.buffer.appendleft("G161 Z F900")
                        self.buffer.appendleft("G162 X Y F2000")
                        self.buffer.appendleft("G90")
                        self.buffer.appendleft("G1 Z-%d E+%d" % (self.pause_lift_height, self.pause_extrude_length))
                        self.buffer.appendleft("G91")
                        #self.buffer.appendleft("M110 N%s" % str(self.printer.breakpoint_index - 6))
                    if index < self.breakpoint_index:
                        #self.logger.info("Index: %d" % index)
                        #self.logger.info("Skip line: %s" % line)
                        self.buffer_lock.release()
                        index = index + 1
                        continue
                    else:
                        self.breakpoint_index = 0
                        self.logger.info("Break line: %s" % command)
            except RuntimeError:
                time.sleep(self.IDLE_WAITING_STEP)
            except IndexError:
                #self.logger.info("buffer is empty.")
                self.buffer_lock.release()
                if self.printing_flag and (not self.cancel_flag):
                    if ((self.gcode_part_count == 1) and (self.total_gcodes_part1 is not None)) or ((self.gcode_part_count == 2) and (self.total_gcodes_part2 is not None)):
                        if gpx.is_ready():
                            self.logger.info("print is finished.")
                            self.finished_flag = True
                            self.current_print_file = None
                            self.pushMessage2Client()
                            self.gcode_part_count = None
                            self.total_gcodes_part1 = None
                            self.total_gcodes_part2 = None
                            self.printing_flag = False
                    elif (self.gcode_part_count == 2) and (self.total_gcodes_part2 is None):
                        pass
                time.sleep(self.IDLE_WAITING_STEP)
            else:
                self.buffer_lock.release()
                self.printing_flag = True
                #self.logger.info("write command %s." % command)
                self._append(self.write(command))
                self.current_line_number += 1
        self.printing_flag = False
        self.pause_flag = False
        self.cancel_flag = False
        with self.buffer_lock:
            self.buffer.clear()
        self.logger.info("Makerbot printer: sender thread ends.")

    #@log.log_exception
    def monitor(self):
        response = ""
        while not self.stop_flag:
            try:
                try:
                    if self.reinit_flag:
                        response = self.response_queue.get()
                    else:                                            
                        if gpx.waiting():
                            response = self.response_queue.get(timeout=2)
                        else:
                            response = self.response_queue.get(timeout=10)
                except Queue.Empty:
                    if not self.reinit_flag:
                        response = gpx.readnext()
                    #self.logger.info("Response Queue is empty.")
            except gpx.CancelBuild:
                self.canceled()
                self.logger.info("Monitor: print is canceled.")
            #self.logger.info("Monitor response: %s" % response)
            self.parse_response(response)
            
        self.logger.info("Makerbot printer: monitor thread ends.")
        
    def monitor2(self):
        while not self.stop_flag:
            if self.printing_flag:
                time.sleep(2)
                continue
            time.sleep(5)
            #self.logger.info("monitor2: M105")
            self._append(self.write("M105"))
            
        self.logger.info("Makerbot printer: monitor2 thread ends.")
        
    def parse_response(self, response):
        if response is None:
            return
        line = response.strip()
        if line is "":
            return
#         ##~~ debugging output handling
#         if line.startswith("//"):
#             pass
        
        if ' T:' in line or line.startswith('T:') or ' T0:' in line or line.startswith('T0:') or ' B:' in line or line.startswith('B:'):
            self.parse_temperatures(line)


    def parse_temperatures(self, line):
        current_tool = self.current_tool
        maxToolNum, parsedTemps = self.parse_temperature_line(line, current_tool)

        if "T0" in parsedTemps.keys():
            for n in range(maxToolNum + 1):
                tool = "T%d" % n
                if not tool in parsedTemps.keys():
                    continue

                actual, target = parsedTemps[tool]
                if target is not None:
                    self.temp[n] = (actual, target)
                elif n in self.temp and self.temp[n] is not None and isinstance(self.temp[n], tuple):
                    (oldActual, oldTarget) = self.temp[n]
                    self.temp[n] = (actual, oldTarget)
                else:
                    self.temp[n] = (actual, 0)

        # bed temperature
        if "B" in parsedTemps.keys():
            actual, target = parsedTemps["B"]
            if target is not None:
                self.bed_temp = (actual, target)
            elif self.bed_temp is not None and isinstance(self.bed_temp, tuple):
                (oldActual, oldTarget) = self.bed_temp
                self.bed_temp = (actual, oldTarget)
            else:
                self.bed_temp = (actual, 0)
                
    def parse_temperature_line(self, line, current):   
        result = {}
        maxToolNum = 0
        
        regex_float_pattern = "[-+]?[0-9]*\.?[0-9]+"
        regex_positive_float_pattern = "[+]?[0-9]*\.?[0-9]+"
        regex_temp = re.compile("(?P<tool>B|T(?P<toolnum>\d*)):\s*(?P<actual>%s)(\s*\/?\s*(?P<target>%s))?" % (regex_positive_float_pattern, regex_positive_float_pattern))
        
        for match in re.finditer(regex_temp, line):
            values = match.groupdict()
            tool = values["tool"]
            toolnum = values.get("toolnum", None)
            toolNumber = int(toolnum) if toolnum is not None and len(toolnum) else None
            if toolNumber > maxToolNum:
                maxToolNum = toolNumber
    
            try:
                actual = float(match.group(3))
                target = None
                if match.group(4) and match.group(5):
                    target = float(match.group(5))
    
                result[tool] = (actual, target)
            except ValueError:
                # catch conversion issues, we'll rather just not get the temperature update instead of killing the connection
                pass
    
        return max(maxToolNum, current), self.canonicalize_temperatures(result, current)

    def canonicalize_temperatures(self, parsed, current): 
        reported_extruders = filter(lambda x: x.startswith("T"), parsed.keys())
        if not "T" in reported_extruders:
            return parsed
    
        current_tool_key = "T%d" % current
        result = dict(parsed)
    
        if len(reported_extruders) > 1:
            if "T0" in reported_extruders:
                # Both T and T0 are present, so T contains the current
                # extruder's temperature, e.g. for current_tool == 1:
                #
                #     T:<T1> T0:<T0> T2:<T2> ... B:<B>
                #
                # becomes
                #
                #     T0:<T1> T1:<T1> T2:<T2> ... B:<B>
                #
                # Same goes if Tc is already present, it will be overwritten:
                #
                #     T:<T1> T0:<T0> T1:<T1> T2:<T2> ... B:<B>
                #
                # becomes
                #
                #     T0:<T0> T1:<T1> T2:<T2> ... B:<B>
                result[current_tool_key] = result["T"]
                del result["T"]
            else:
                # So T is there, but T0 isn't. That looks like Smoothieware which
                # always reports the first extruder T0 as T:
                #
                #     T:<T0> T1:<T1> T2:<T2> ... B:<B>
                #
                # becomes
                #
                #     T0:<T0> T1:<T1> T2:<T2> ... B:<B>
                result["T0"] = result["T"]
                del result["T"]
    
        else:
            # We only have T. That can mean two things:
            #
            #   * we only have one extruder at all, or
            #   * we are currently parsing a response to M109/M190, which on
            #     some firmwares doesn't report the full M105 output while
            #     waiting for the target temperature to be reached but only
            #     reports the current tool and bed
            #
            # In both cases it is however safe to just move our T over
            # to T<current> in the parsed data, current should always stay
            # 0 for single extruder printers. E.g. for current_tool == 1:
            #
            #     T:<T1>
            #
            # becomes
            #
            #     T1:<T1>
    
            result[current_tool_key] = result["T"]
            del result["T"]
    
        return result

    def is_printing(self):
        return self.printing_flag

    def get_percent(self):
        if not self.reinit_flag:    
            self.percent_bak = gpx.get_percentage()
            percent = self.percent_bak
            if percent > 0 and percent <= 100:
                percent = round(percent * 1.0 / 100, 2)
            else:
                percent = 0
        else:
            percent = self.percent_bak
        return percent

    def get_current_line_number(self):
        return self.current_line_number

    def goHome(self):
        gcodes = "M135 T0\nG162 X Y F2000\nG161 Z F900\nG92 X0 Y0 Z-5 A0 B0\nG1 Z0.0 F900\nG161 Z F100\nM132 X Y Z A B"
        self.unbuffered_gcodes(gcodes)

    def goXYHome(self):
        gcodes = "M135 T0\nG162 X Y F2000\nG92 X0 Y0 Z0 A0 B0\nM132 X Y A B"
        self.unbuffered_gcodes(gcodes)

    def goZHome(self):
        gcodes = "M135 T0\nG161 Z F900\nG92 X0 Y0 Z-5 A0 B0\nG1 Z0.0 F900\nG161 Z F100\nM132 Z A B"
        self.unbuffered_gcodes(gcodes)
    
    def goXPosition(self, pos):
        gcodes = "M135 T0\nG92 X0 Y0 Z0 A0 B0\nG1 X%s F900" % pos
        self.unbuffered_gcodes(gcodes)
        
    def goYPosition(self, pos):
        gcodes = "M135 T0\nG92 X0 Y0 Z0 A0 B0\nG1 Y%s F900" % pos
        self.unbuffered_gcodes(gcodes)
    
    def goZPosition(self, pos):
        gcodes = "M135 T0\nG92 X0 Y0 Z0 A0 B0\nG1 Z%s F900" % pos
        self.unbuffered_gcodes(gcodes)
        
    def goEOperation(self, e, length):
        gcodes = "M135 T%s\nG92 X0 Y0 Z0 A0 B0\nG1 E%s" % (e, length)
        self.unbuffered_gcodes(gcodes)

    def setBedTargetTemp(self, temp):
        gcodes = "M109 S%s" % temp
        self.unbuffered_gcodes(gcodes)
    
    def setETargetTemp(self, e, temp):
        gcodes = "M135 T%s\nM104 S%s T%s" % (e, temp, e)
        self.unbuffered_gcodes(gcodes)

    def setSpeedFactor(self, speedfactor):
        gcodes = "M220 S%s" % (speedfactor)
        self.unbuffered_gcodes(gcodes)
        #self.logger.info("gcodes: %s is not supported." % gcodes)
    
    def toOperational(self):
        self.finished_flag = False
        self.printer_state = 3
        if self.buffer and len(self.buffer) != 0:
            with self.buffer_lock:
                self.buffer.clear()
                
        self.unbuffered_gcodes("\n".join(self.profile['end_gcodes']))
            
    
    
    