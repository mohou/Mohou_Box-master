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

# Author: Alexey Slynko <alex_ey@i.ua>

import logging
import threading
import usb.core
import usb.util
import usb.backend.libusb1
import paths
import collections
import time
import base_sender
import sys
paths.init_path_to_libs()

import config

TEMP_REQUEST_WAIT = 5
PAUSE_LIFT_HEIGHT = 5

class Sender(base_sender.BaseSender):

    TEMP_REQUEST_GCODE = 'M105'

    def __init__(self, profile, usb_info):
        base_sender.BaseSender.__init__(self, profile, usb_info)
        self.logger = logging.getLogger(__name__)
        self.logger.info('Raw USB Sender started!')
        self.int_vid = int(usb_info['VID'], 16)
        self.int_pid = int(usb_info['PID'], 16)
        self.end_gcodes = profile['end_gcodes']

        self.pause_flag = False
        self.printing_flag = False
        self.percent = None
        self.heating_flag = None
        self.pos_x = None
        self.pos_y = None
        self.pos_z = None

        self.heating_gcodes = []

        self.buffer = collections.deque()
        self.buffer_lock = threading.Lock()
        self.write_lock = threading.Lock()
        self.read_lock = threading.Lock()
        self.gcode_lines = None
        self.sent_gcodes = 0
        self.oks = 0
        self.temp_request_counter = 0
        self.get_pos_counter = 0

        self.dev = None
        self.define_endpoints()

        connect = self.connect()
        time.sleep(2)  # Important!
        if connect:
            self.prepare_printer()
            self.handshake()
            self.read_thread = threading.Thread(target=self.reading)
            self.read_thread.start()
            self.temp_request_thread = threading.Thread(target=self.temp_request)
            self.temp_request_thread.start()
            self.sending_thread = threading.Thread(target=self.sending)
            self.sending_thread.start()
        else:
            raise Exception('Cannot connect to USB device.')

    # Override if needed
    def define_endpoints(self):
        self.endpoint_in = None
        self.endpoint_out = None

    def set_total_gcodes(self, length):
        self.total_gcodes = len(self.buffer)
        self.current_line_number = 0

    def handshake(self):
        pass

    def connect(self):
        backend_from_our_directory = usb.backend.libusb1.get_backend(find_library=paths.get_libusb_path)
        self.dev = usb.core.find(idVendor=self.int_vid, idProduct=self.int_pid, backend=backend_from_our_directory)
        if sys.platform.startswith('linux'):  # TODO: test at mac this too
            # Checking and claiming interface 0 - interrupt interface for command sending
            # Zmorph also has interface 1 - bulk interface, assuming for file upload.
            if self.dev.is_kernel_driver_active(0) is True:
                self.logger.info('Interface is kernel active. Detaching...')
                claim_attempts = 5
                for _ in range(claim_attempts):
                    try:
                        self.dev.detach_kernel_driver(0)
                        #time.sleep(0.1)
                        self.dev.set_configuration()
                        usb.util.claim_interface(self.dev, 0)
                        #time.sleep(0.1)
                    except Exception as e:
                        logging.warning('Exception while detaching : %s' % e.message)
                    else:
                        if self.dev.is_kernel_driver_active(0) is True:
                            self.logger.info('Can\'t detach USB device. Attempting once more...')
                        else:
                            self.logger.info('Detached and claimed!')
                            break
            else:
                self.logger.info('Interface is free. Connecting...')
            if self.dev.is_kernel_driver_active(0) is True:
                self.logger.warning('Cannot claim USB device. Aborting.')
                return False
        elif sys.platform.startswith('win'):
            self.dev.set_configuration()
        elif sys.platform.startswith('darwin'):
            self.logger.info('Mac os is not currently supported')
            return False
        #self.dev.set_configuration()
        #cfg = self.dev.get_active_configuration()
        if not self.endpoint_in and not self.endpoint_out:
            cfg = self.dev.get_active_configuration()
            # TODO: endpoint sequence can vary in different printer. Ensure IN endpoint is actually IN etc.
            self.endpoint_in = cfg[(0, 0)][0]
            self.endpoint_out = cfg[(0, 0)][1]
            self.logger.info('Setting endpoints from device config')
            # casting endpoints to str may cause exception if cfg is actually wrong
            #self.logger.info('IN endpoint:\n' % str(self.endpoint_in))
            #self.logger.info('OUT endpoint:\n' % str(self.endpoint_out))
        return True

    def write(self, gcode):
        try:
            self.endpoint_out.write(gcode + '\n', 2000)
        except Exception as e:
            self.logger.warning('Error while writing gcode "%s"\nError: %s' % (gcode, e.message))
        else:
            self.logger.info('SENT: %s' % gcode)

    def get_percent(self):
        if self.is_downloading():
            percent = self.downloader.get_percent()
        else:
            percent = self.percent
        return percent

    def is_printing(self):
        return self.printing_flag

    def parse_response(self, resp):
        raise NotImplementedError

    def reading(self):
        with self.read_lock:
            self.read()  # Clearing printer output buffer
        while not self.stop_flag:
            data = True
            if not self.printing_flag:
                time.sleep(0.1)
            while data:
                with self.read_lock:
                    data = self.read()
                if data:
                    sret = ''.join([chr(x) for x in data])
                    if sret:
                        spret = sret.split('\n')
                        for ret in spret:
                            ret = ret.replace('\n', '')
                            ret = ret.replace('\r', '')
                            if ret:
                                self.parse_response(ret)
                    else:
                        time.sleep(0.001)
                        continue
                else:
                    time.sleep(0.001)
                    continue
            time.sleep(0.001)

    def unbuffered_gcodes(self, gcodes):
        #TODO implement it some day
        return False

    def read(self):
        try:
            data = self.dev.read(self.endpoint_in.bEndpointAddress, self.endpoint_in.wMaxPacketSize, 2000)
        except usb.core.USBError as e:
            self.logger.info('USBError : %s' % str(e))
            # TODO: parse ERRNO 110 here to separate timeout exceptions | [Errno 110] Operation timed out
            return None
        except Exception as e:  # TODO: make not operational
            self.logger.warning('Error while reading gcode: %s' % str(e))
            return None
        else:
            return data

    def is_operational(self):
        return self.printing_flag or \
                self.pause_flag or   \
               (self.read_thread.is_alive() and self.temp_request_thread.is_alive())

    def cancel(self):
        if self.is_downloading():
            self.cancel_download()
        else:
            self.pause_flag = False
            self.printing_flag = False
            with self.write_lock:
                for gcode in self.end_gcodes:
                    self.write(gcode)
                    time.sleep(0.1)
            with self.write_lock:
                self.buffer.clear()
            self.logger.info('Cancelled!')

    def lift_extruder(self):
        gcode = 'G1 Z' + str(float(self.pos_z) + PAUSE_LIFT_HEIGHT)
        with self.write_lock:
            self.write(gcode)
        self.sent_gcodes += 1
        self.logger.info("Paused successfully")

    # Might have firmware-dependable logic
    def pause(self):
        raise NotImplementedError

    def unpause(self):
        if self.pause_flag:
            self.logger.info('Unpausing')
            gcode = 'G1 Z' + str(self.pos_z)
            with self.write_lock:
                self.write(gcode)
            self.sent_gcodes += 1
            self.pause_flag = False
            self.logger.info("Unpaused successfully")

    def temp_request(self):
        self.temp_request_counter = 0
        no_answer_counter = 0
        no_answer_cap = 5
        while not self.stop_flag:
            time.sleep(1)
            if self.heating_flag:
                time.sleep(5)
            if self.temp_request_counter:
                time.sleep(1.5)
                no_answer_counter += 1
                if no_answer_counter >= no_answer_cap and self.temp_request_counter > 0:
                    self.temp_request_counter -= 1
            else:
                no_answer_counter = 0
                self.temp_request_counter += 1
                with self.write_lock:
                    self.write(self.TEMP_REQUEST_GCODE)

    def get_current_line_number(self):
        return self.oks

    # For printer dependable functionality like beevery firmware flushing
    def prepare_printer(self):
        pass

    def sending(self):
        self.logger.info('Sending thread started!')
        #self.handshake()
        while not self.stop_flag:
            if not self.printing_flag:
                time.sleep(0.1)
                continue
            self.logger.info('Sending started!')
            with self.read_lock:
                self.read()  # Clear buffer from previous printing or cancel command
            self.init_sending_values()
            self.prepare_heating()
            self.heat_printer()  # Blocking
            self.sending_loop()
            self.logger.info('All gcodes are sent to printer. Waiting for finish')
            self.wait_for_sending_end()
            self.logger.info('Printer has finished printing!')
            with self.write_lock:
                self.buffer.clear()
            self.percent = 100
            self.printing_flag = False

    # Might have firmware-dependable logic
    def prepare_heating(self):
        pass
        #raise NotImplementedError  # Not always needed

    # Might have firmware-dependable logic
    def heat_printer(self):
        pass
        #raise NotImplementedError  # Not always needed

    def wait_for_sending_end(self):
        wait_cap = 30
        wait_counter = 0
        start_oks = self.oks
        start_sent_gcodes = self.sent_gcodes
        while self.oks < self.sent_gcodes:
            if not self.stop_flag:
                self.logger.info('Waiting... %s/%s' % (self.oks, self.sent_gcodes))
                time.sleep(1)
                wait_counter += 1
                if wait_counter >= wait_cap:
                    self.logger.info('Waiting too long...')
                    if start_oks == self.oks and start_sent_gcodes == self.sent_gcodes:
                        self.logger.info('...and no progress in received oks')
                    self.logger.info('Skipping wait for finish...')
                    break

    def sending_loop(self):
        while self.printing_flag and self.buffer:
            gcode = None
            if self.pause_flag:
                time.sleep(0.1)
            elif self.heating_flag:
                time.sleep(0.05)
            elif self.sent_gcodes == self.oks:
                with self.buffer_lock:
                    try:
                        gcode = self.buffer.popleft()
                    except IndexError:
                        self.logger.info('Buffer is empty!')
                if gcode is not None:  # TODO: add gcode processing. Now it is for empty gcode which is counting in self.gcode_lines
                    with self.write_lock:
                        self.write(gcode)
                    self.sent_gcodes += 1
                    self.logger.info('Progress: %s/%s' % (self.oks, self.sent_gcodes))
                    self.percent = self.sent_gcodes / self.percent_step
            else:
                time.sleep(0.001)

    def init_sending_values(self):
            self.gcode_lines = len(self.buffer)
            self.percent_step = self.gcode_lines / 100
            if self.percent_step == 0:
                self.percent_step = 1
            self.heating_gcodes = []
            self.temps[0] = 0
            self.temps[1] = 0
            self.target_temps[0] = 0
            self.target_temps[1] = 0
            self.printing_flag = True
            self.percent = 0
            self.sent_gcodes = 0
            self.oks = 0
            self.temp_request_counter = 0
            self.logger.info('Start sending!')

    def load_gcodes(self, gcodes):
        if self.printing_flag or self.pause_flag:
            self.logger.warning('Got gcodes command while job is not finished. Skipping.')
            return False
        gcodes = gcodes.split('\n')
        self.set_total_gcodes(len(gcodes))
        with self.buffer_lock:
            for line in gcodes:
                line = line.replace('\n', '')
                line = line.replace('\r', '')
                if line:
                    self.buffer.append(line)
            self.logger.info('Loaded gcodes: %d' % len(self.buffer))
            self.printing_flag = True
            return True

    def close(self):
        self.stop_flag = True
        self.logger.info('Raw USB sender is closing')
        if self.temp_request_thread:
            self.logger.debug('(Joining temp request thread...')
            self.temp_request_thread.join(10)
            if self.temp_request_thread.isAlive():
                config.create_error_report(202, "Error stopping temperature request thread!", self.usb_info, self.logger, is_blocking=True)
            else:
                self.logger.debug('...done)')
        if self.read_thread:
            self.logger.debug('(Joining read thread...')
            self.read_thread.join(10)
            if self.read_thread.isAlive():
                config.create_error_report(203, "Error stopping read thread!", self.usb_info, self.logger, is_blocking=True)
            else:
                self.logger.debug('...done)')
        if self.sending_thread:
            self.logger.debug('(Joining sending thread...')
            self.read_thread.join(10)
            if self.read_thread.isAlive():
                config.create_error_report(204, "Error stopping sending thread!", self.usb_info, self.logger, is_blocking=True)
            else:
                self.logger.debug('...done)')
        self.is_running = False
        self.logger.info('...closed')

if __name__ == '__main__':
    pass