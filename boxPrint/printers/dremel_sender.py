#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

# Author: Vladimir Avdeev <another.vic@yandex.ru>, Ivan Gaydamakin <megapk@gmail.com>

# Note: this is driver for the worst printer in the world. The worst of the worst, really.

import re
import time
import logging
import threading
from os import path

import log
import config
import pyusb_connection
from base_sender import BaseSender


class FFDConnection(pyusb_connection.PyUSBConnection):

    def __init__(self, profile, usb_info):
        self.file_transfer_endpoint_in = 0x83
        self.file_transfer_endpoint_out = 0x3
        pyusb_connection.PyUSBConnection.__init__(self, profile, usb_info)

    def format_message(self, raw_message):
        return "~" + str(raw_message) + "\r\n"

class Sender(BaseSender):

    INIT_GCODES = ["M115", "M650", "M114", "M105", "M119", "M105", "M104 S0 T0", "M104 S0 T1", "M140 S0"]
    FILE_PACKET_SIZE = 1024*4
    FILE_NAME = "3dprinteros.g3drem"
    STATE_READY = "MachineStatus: READY"

    def __init__(self, profile, usb_info):
        BaseSender.__init__(self, profile, usb_info)
        self.paused = False
        self.monitoring_stop = False
        self.operational_flag = False
        self.printing_flag = False
        self.lines_sent = 0
        self.percent = 0
        self.define_regexps()
        self.connection = FFDConnection(profile, usb_info)
        self.handshake()
        self.connect()
        self.monitoring_thread = None
        self.monitoring_thread_start()

    def handshake(self):
        self.connection.send("M601 S0")

    def define_regexps(self):
        self.temp_re = re.compile('.*T0:([\d\.]+) /([\d\.]+) B:(-?[\d\.]+) /(-?[\d\.]+).*', flags=re.DOTALL)
        self.progress_re = re.compile(".*SD printing byte (\d+)\/(\d+).*", flags=re.DOTALL)

    def connect(self):
        for command in self.INIT_GCODES:
            self.connection.send(command)
        answer = self.readout("ok")
        if not answer:
            raise RuntimeError("Cannot connect to printer and receive \"OK\"")

    def readout(self, wait_for=None):
        retries = 5
        full_answer = ""
        while not self.stop_flag:
            answer = self.connection.recv()
            if answer:
                full_answer += answer
            else:
                if full_answer:
                    if wait_for:
                        return wait_for in full_answer
                    else:
                        return full_answer
                retries -= 1
                if retries == 0:
                    return False

    @log.log_exception
    def monitoring(self):
        self.logger.info("Monitoring thread started")
        while not self.monitoring_stop and not self.stop_flag:
            self.connection.send("M105")
            self.connection.send("M119")
            self.connection.send("M27")
            answer = self.readout()
            if not answer:
                self.operational_flag = False
                message = "Printer not answering in monitoring. Printer lost."
                config.create_error_report(606, message, self.usb_info, self.logger, is_blocking=True)
                break
            self.parse_temperature(answer)
            self.operational_flag = True
            if self.STATE_READY in answer:
                self.printing_flag = False
            else:
                self.printing_flag = True
                progress_match = self.progress_re.match(answer)
                if progress_match:
                    self.lines_sent = int(progress_match.group(1))
                    self.total_gcodes = int(progress_match.group(2))
                    if self.total_gcodes > 0:
                        self.percent = int(self.lines_sent / float(self.total_gcodes) * 100)
            time.sleep(0.1)
        self.logger.info("Monitoring thread stopped")

    def add_g3rem_header(self, gcodes):
        # magic = "g3drem + 1.0"
        # small_snapshot_addr = 0
        # big_snapshot_addr = 0
        # gcode_addr = 0
        # estimated_time = 0
        # filament_diametr = 0
        # flags = 0
        # layer_height = 0
        # infill = 0
        # shell_count = 0
        # speed = 0
        # platform_temp = 0
        # extruder_temps = 0
        # materialTypes = 0
        # small_snapshot_bmp = ""
        # big_snapshot_bmp = ""
        with open(path.join('firmware', 'head_g3drem.bin'), "rb") as f: #header is just a dummy to display something on the print screen
            header = f.read()
        return header + gcodes

    def load_gcodes(self, gcodes):
        if self.operational_flag and not self.is_printing():
            return self.upload_gcodes_and_print(gcodes)
        else:
            config.create_error_report(604, "Printer already printing.", self.usb_info, self.logger, is_blocking=False)
            return False

    def upload_gcodes_and_print(self, gcodes):
        self.monitoring_thread_stop()
        self.percent = 0
        self.lines_sent = 0
        gcodes = self.add_g3rem_header(gcodes)
        file_size = len(gcodes)
        self.connection.send("M28 %d 0:/user/%s" % (file_size, self.FILE_NAME))
        answers = ""
        while not self.stop_flag:
            answer = self.readout()
            if not answer:
                message = "Failed start transfer file"
                config.create_error_report(605, message, self.usb_info, self.logger, is_blocking=True)
                return False
            answers += answer
            if "Writing to file" in answers:
                self.logger.info("Received: Writing to file")
                break
            elif "open failed" in answers:
                message = "Transfer to printer failed"
                config.create_error_report(602, message, self.usb_info, self.logger, is_blocking=True)
                return False
            elif "Disk read error" in answers:
                message = "Transfer to printer failed, error: \"Disk read error\""
                config.create_error_report(608, message, self.usb_info, self.logger, is_blocking=True)
                return False
        timeout = 20000 * file_size / 3000000  #magic timeout
        self.connection.dev.__default_timeout = timeout
        file_endpoint = self.connection.file_transfer_endpoint_out
        chunk_start_index = 0
        counter = 0
        self.logger.info("Start uploading file...")
        while True:
            if self.stop_flag:
                return False
            chunk_end_index = min(chunk_start_index + self.FILE_PACKET_SIZE, file_size)
            chunk = gcodes[chunk_start_index:chunk_end_index]
            if not chunk:
                break
            if self.connection.send(chunk, endpoint=file_endpoint, raw=True, timeout=timeout):
                counter += 1
                if counter > 4:
                    counter = 0
                    self.connection.send("", raw=True)
                    self.readout()
            else:
                config.create_error_report(603, "File transfer interrupted", self.usb_info, self.logger, is_blocking=True)
                return False
            chunk_start_index += self.FILE_PACKET_SIZE
        message = "File transfer interrupted"
        if self.connection.send("M29"):
            if self.connection.send("M23 0:/user/%s" % self.FILE_NAME):
                answers = self.readout()
                if not answers:
                    message = "Printer not answered anything after send M29 and M23"
                elif "Disk read error" in answers:
                    message = "Disk read error"
                elif "File selected" in answers:
                        self.logger.info("File transfer to printer successful")
                        self.printing_flag = True
                        self.monitoring_thread_start()
                        return True
        config.create_error_report(604, message, self.usb_info, self.logger, is_blocking=True)
        return False

    def pause(self):
        if not self.paused:
            if self.connection.send("M25"):
                self.paused = True
            else:
                return False

    def unpause(self):
        if self.paused:
            if self.connection.send("M24"):
                self.paused = False
            else:
                return False

    def cancel(self):
        # TODO: Not working on Cloud, REPORT ME
        message = "Cancel is not supported by BOSCH Dremel"
        config.create_error_report(605, message, self.usb_info, self.logger, is_blocking=False)
        return False

    def is_operational(self):
        return self.operational_flag

    def is_paused(self):
        return self.paused

    def is_printing(self):
        return self.printing_flag

    def unbuffered_gcodes(self, gcodes):
        return False

    def reset(self):
        self.connection.reset()

    def get_percent(self):
        if self.is_downloading():
            percent = self.downloader.get_percent()
        elif self.printing_flag:
            percent = self.percent
        else:
            percent = 0
        return percent

    def get_current_line_number(self):
        if self.printing_flag:
            return self.lines_sent
        else:
            return 0

    def parse_temperature(self, line):
        match = self.temp_re.match(line)
        if match:
            tool_temp = float(match.group(1))
            tool_target_temp = float(match.group(2))
            platform_temp = float(match.group(3))
            platform_target_temp = float(match.group(4))
            self.temps = [platform_temp, tool_temp]
            self.target_temps = [platform_target_temp, tool_target_temp]
            return True

    def close(self):
        self.monitoring_thread_stop()
        self.connection.send("M602")
        self.readout()
        self.stop_flag = True
        self.connection.close()
        self.is_running = False

    def monitoring_thread_start(self):
        self.monitoring_stop = False
        self.monitoring_thread = threading.Thread(target=self.monitoring)
        self.monitoring_thread.start()

    def monitoring_thread_stop(self):
        self.monitoring_stop = True
        if self.monitoring_thread:
            self.monitoring_thread.join()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    your_file_name = "1.gcode" #replace me
    sender = None
    try:
        sender = Sender({}, {"VID": "2a89", "PID": "8889"})
        time.sleep(3)
        print ">>>START PRINTING!!!!"
        with open(your_file_name, "rb") as f:
            your_file_content = f.read()
        sender.load_gcodes(your_file_content)
    except Exception:
        if sender:
            sender.close()
    try:
        time.sleep(10)
    except:
        pass
    if sender:
        sender.close()
