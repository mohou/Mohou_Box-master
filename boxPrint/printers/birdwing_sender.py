# Copyright (c) 2015 3D Control Systems LTD

# 3DPrinterOS client is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# 3DPrinterOS client is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with 3DPrinterOS client.  If not, see <http://www.gnu.org/licenses/>.

# Author: Ivan Gaydamakin <megapk@gmail.com>, Vladimir Avdeev <another.vic@yandex.ru>

import httplib
import logging
import os
import threading
import time
import config
import paths
from base_sender import BaseSender
from makerbotapi import Makerbot


class BirdwingNetworkConnection(Makerbot):
    def __init__(self, ip, auth_code=None, auto_connect=True, verbose=False, auth_timeout=120):
        Makerbot.__init__(self, ip, auth_code, auto_connect)
        self.debug_http = verbose
        self.debug_jsonrpc = verbose
        self.debug_fcgi = verbose
        self.auth_timeout = auth_timeout

    def put_file(self, gcode_file, remote_path):
        token = self.get_access_token(context='put')
        if not token:
            raise Exception("No access token for PUT file")
        put_token = str(token)
        host = "%s:%i" % (self.host, 80)
        con = httplib.HTTPConnection(host)
        remote_path = "%s?token=%s" % (remote_path, put_token)
        if self.debug_http:
            self._debug_print('HTTP', 'REQUEST', "PUT FILE:  %s%s" % (host, remote_path))
        con.request("PUT", remote_path, gcode_file)
        resp = con.getresponse()
        status_code = resp.status
        if self.debug_http:
            self._debug_print('HTTP', 'RESPONSE', "PUT FILE: status code: %s" % status_code)
        if status_code == 200:
            msg = resp.read()
            if self.debug_http:
                self._debug_print('HTTP', 'RESPONSE', 'Received http code %d, message\n%s' % (status_code, msg))
                # raise httplib.HTTPException(errcode)
        return status_code == 200

    def start_printing_file(self, file):
        if self.rpc_request_response_with_try("print", {"filepath": os.path.basename(file)}):
            return self.rpc_request_response_with_try("process_method", {"params": {}, "method": "build_plate_cleared"})

    def cancel_print(self):
        return self.rpc_request_response_with_try("cancel", {})

    def pause_print(self):
        return self.rpc_request_response_with_try("process_method", {"params": {}, "method": "suspend"})

    def unpause_print(self):
        return self.rpc_request_response_with_try("process_method", {"params": {}, "method": "resume"})

    def rpc_request_response_with_try(self, method, params):
        try:
            return self.rpc_request_response(method, params)
        except AssertionError:
            return

    def authenticate_to_printer(self):
        try:
            self.authenticate_json_rpc()
            return True
        except:
            pass


class Sender(BaseSender):
    REMOTE_URL_PATH_FILE = "/current_thing/3dprinteros.makerbot"
    STEP_PRINTING_NAME = "printing"

    def __init__(self, profile, usb_info):
        BaseSender.__init__(self, profile, usb_info)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.operational_flag = False
        self.printing_flag = False
        self.pairing_needed = False
        self.percent = 0
        self.ip = usb_info['IP']
        self.available_methods = []
        self.serial_number = usb_info['SNR']
        self.path_to_file_with_auth_code = os.path.join(
            paths.CURRENT_SETTINGS_FOLDER,
            "%s_%s.auth_code" % (self.ip.replace(".", "-"), self.serial_number)
        )
        self.timeout = profile["operational_timeout"]
        self.auth_and_monitoring_thread = threading.Thread(target=self.auth_and_monitoring)
        self.auth_and_monitoring_thread.start()
        #  TODO: Develop report to server info about this printer (in botstate)

    def auth_and_monitoring(self):
        self.logger.info("Connecting to BirdWing printer...")
        try:
            self.makerbot = BirdwingNetworkConnection(self.ip, self.read_auth_code(), auth_timeout=self.timeout)
        except Exception as e:
            message = "Cannot connect to printer, error message: %s" % e.message
            config.create_error_report(708, message,
                                       self.usb_info, self.logger, is_blocking=True)
            return
        if not self.makerbot.authenticate_to_printer():
            self.pairing_needed = True
            self.logger.debug("Press the flashing action button on your printer now")
            try:
                self.makerbot.authenticate_fcgi()
            except Exception as e:
                message = "Birdwing module failed in pairing your printer, error message: %s" % e.message
                config.create_error_report(707, message,
                                           self.usb_info, self.logger, is_blocking=True)
                return
            self.logger.debug("Authenticated with code: %s" % self.makerbot.auth_code)
            self.write_auth_code(self.makerbot.auth_code)
            if not self.makerbot.authenticate_to_printer():
                message = "Birdwing module can't authenticate printer after pairing."
                config.create_error_report(706, message,
                                           self.usb_info, self.logger, is_blocking=True)
                return
        self.pairing_needed = False
        self.logger.info("...connected!")
        while not self.stop_flag:
            printer_state = None
            try:
                printer_state = self.makerbot.get_system_information()
            except AssertionError:
                time.sleep(0.5)
                continue
            except Exception as e:
                config.create_error_report(700, "Crash BirdWing module, exception: %s" % e,
                                           self.usb_info, self.logger, is_blocking=True)
                break
            finally:
                self.operational_flag = bool(printer_state)
            if printer_state:
                # print self.makerbot.firmware_version
                # print self.makerbot.iserial
                # print self.makerbot.machine_name
                # print self.makerbot.machine_type
                # print self.makerbot.vid
                # print self.makerbot.pid
                # print self.makerbot.bot_type
                toolhead = printer_state.toolheads[0]
                self.temps[1] = toolhead.current_temperature
                self.target_temps[1] = toolhead.target_temperature
                process = printer_state.current_process
                self.printing_flag = bool(process)
                if process:
                    self.available_methods = process.methods
                    if process.step == self.STEP_PRINTING_NAME and process.progress:
                        # Dirty hack, because this printer can answer on first step "printing" 98%!
                        if self.percent != 0 or process.progress < 50:
                            self.percent = process.progress
            time.sleep(0.5)

    def load_gcodes(self, gcode_file):
        if not self.printing_flag:
            if not self.makerbot.put_file(gcode_file, self.REMOTE_URL_PATH_FILE):
                config.create_error_report(701, "Cannot upload file to printer",
                                           self.usb_info, self.logger, is_blocking=True)
                return
            if not self.makerbot.start_printing_file(self.REMOTE_URL_PATH_FILE):
                config.create_error_report(702, "Cannot start print",
                                           self.usb_info, self.logger, is_blocking=True)
                return
            self.logger.info("Success start print")
        else:
            return False

    def is_printing(self):
        return self.printing_flag

    def is_paused(self):
        return self.pause_flag

    def is_operational(self):
        return self.operational_flag

    def pause(self):
        # FIXME: Its ugly, need move to BirdwingConnector or better MakerBotAPI
        if not self.pause_flag and "suspend" in self.available_methods:
            self.makerbot.pause_print()
            self.pause_flag = True
        else:
            config.create_error_report(703, "For now, cannot use command pause.",
                                       self.usb_info, self.logger, is_blocking=False)
            return False

    def unpause(self):
        # FIXME: Its ugly, need move to BirdwingConnector or better MakerBotAPI
        if self.pause_flag and "resume" in self.available_methods:
            self.makerbot.unpause_print()
            self.pause_flag = False
        else:
            config.create_error_report(704, "For now, cannot use command resume.",
                                       self.usb_info, self.logger, is_blocking=False)
            return False

    def cancel(self):
        if self.cancel_download():
            return
        if self.printing_flag:
            self.logger.info("Cancel print")
            self.makerbot.cancel_print()

    def get_percent(self):
        return self.percent

    def set_total_gcodes(self, length):
        pass

    def get_current_line_number(self):
        return 0

    def unbuffered_gcodes(self, gcodes):
        # TODO: Add report for not support this
        config.create_error_report(705, "This printer don't support Gcodes",
                                   self.usb_info, self.logger, is_blocking=False)
        return None

    def close(self):
        self.logger.info("Closing BirdWingSender module...")
        self.stop_flag = True
        if self.auth_and_monitoring_thread and self.auth_and_monitoring_thread.is_alive():
            self.auth_and_monitoring_thread.join()
        self.is_running = False
        self.logger.info("...closed")

    def read_auth_code(self):
        try:
            self.logger.info("Birdwing reading auth code from file: %s" % self.path_to_file_with_auth_code)
            file = open(self.path_to_file_with_auth_code, "r")
            auth_code = file.read()
            file.close()
            self.logger.info("Birdwing read auth code: %s" % auth_code)
            return auth_code
        except Exception as e:
            self.logger.info(
                "Cannot read from file: %s, have exception: %s" % (self.path_to_file_with_auth_code, e.message))

    def write_auth_code(self, auth_code):
        try:
            self.logger.info(
                "Birdwing writing auth code: %s to file: %s" % (auth_code, self.path_to_file_with_auth_code))
            file = open(self.path_to_file_with_auth_code, "w")
            file.write(auth_code)
            file.close()
        except Exception as e:
            self.logger.info(
                "Cannot write to file: %s, have exception: %s" % (self.path_to_file_with_auth_code, e.message))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    your_file_name = "1.makerbot"
    sender = None
    try:
        sender = Sender(
            {},
            {
                "IP": "192.168.10.45",
                "SNR": "TOSTER_PRINTER112",
            }
        )
        time.sleep(3)
        print ">>>START PRINTING!!!!"
        # with open(your_file_name, "rb") as f:
        #     your_file_content = f.read()
        # sender.load_gcodes(your_file_content)
        # sender.cancel()
    except KeyboardInterrupt:
        if sender:
            sender.close()
        exit()

    while True:
        try:
            print "STATUS PRINTER: %s" % sender.is_operational()
            time.sleep(3)
        except KeyboardInterrupt:
            if sender:
                sender.close()
            break
