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

import re
import time
import raw_usb_sender

class Sender(raw_usb_sender.Sender):
    def __init__(self, profile, usb_info):
        self.define_regexps()
        raw_usb_sender.Sender.__init__(self, profile, usb_info)

    def define_regexps(self):
        self.temp_re = re.compile('.*ok T:([\d\.]+) /([\d\.]+) .* B:(-?[\d\.]+) /(-?[\d\.]+) .*')
        self.position_re = re.compile('Position X: ([\d\.]+), Y: ([\d\.]+), Z: ([\d\.]+)')
        self.get_temp_bed_re = re.compile('bed temp: ([\d\.]+)/([\d\.]+) @')
        self.get_temp_hotend_re = re.compile('hotend temp: ([\d\.]+)/([\d\.]+) @')
        self.bed_heating_re = re.compile('M190 S([\d\.]+)')
        self.tool_heating_re = re.compile('M109 T0 S([\d\.]+)')

    def parse_response(self, ret):
        if ret == 'ok':
            self.oks += 1
        elif ret.startswith('ok T:'):
            self.temp_request_counter -= 1
            match = self.match_temps(ret)
            if match:
                self.logger.info('TEMP UPDATE')
        elif ret.startswith('Position X:'):
            match = self.position_re.match(ret)
            if match:
                self.get_pos_counter -= 1
                self.pos_x = match.group(1)
                self.pos_y = match.group(2)
                self.pos_z = match.group(3)
                self.lift_extruder()
            else:
                self.logger.warning('Got position answer, but it does not match! Response: %s' % ret)
        else:
            self.logger.debug('Got unpredictable answer from printer: %s' % ret.decode())

    # M105 based matching. Redefine if needed.
    def match_temps(self, request):
        match = self.temp_re.match(request)
        if match:
            tool_temp = float(match.group(1))
            tool_target_temp = float(match.group(2))
            platform_temp = float(match.group(3))
            platform_target_temp = float(match.group(4))
            self.temps = [platform_temp, tool_temp]
            self.target_temps = [platform_target_temp, tool_target_temp]
            #self.logger.info('Got temps: T %s/%s B %s/%s' % (tool_temp, tool_target_temp, platform_temp, platform_target_temp))
            return True
        return False

    def pause(self):
        if not self.pause_flag:
            self.logger.info("Pausing...")
            self.pause_flag = True
            self.get_pos_counter += 1
            with self.write_lock:
                self.write('get pos')

    def prepare_heating(self):
        self.logger.info('Preparing heating...')
        with self.buffer_lock:
            for gcode in self.buffer:
                if gcode.startswith('G0') or gcode.startswith('G1'):
                    break
                match = self.bed_heating_re.match(gcode)
                if match:
                    self.heating_gcodes.append(gcode)
                    continue
                match = self.tool_heating_re.match(gcode)
                if match:
                    self.heating_gcodes.append(gcode)
            self.logger.info('Got heating gcodes: %s' % str(self.heating_gcodes))
            for gcode in self.heating_gcodes:
                self.buffer.remove(gcode)

    def heat_printer(self):
        self.logger.info('Heating printer!')
        self.heating_flag = True
        for gcode in self.heating_gcodes:
            self.logger.info('Writing heating gcode: %s' % gcode)
            with self.write_lock:
                self.write(gcode)
            self.sent_gcodes += 1
            if self.bed_heating_re.match(gcode):
                self.logger.info('Heating bed')
                while not self.temps[0] or not self.target_temps[0]:
                    time.sleep(0.05)
                self.logger.info('Waiting heating bed')
                while self.temps[0] < self.target_temps[0]:
                    time.sleep(0.05)
                self.logger.info('Bed heated!')
            elif self.tool_heating_re.match(gcode):
                self.logger.info('Heating tool')
                while not self.temps[1] or not self.target_temps[1]:
                    time.sleep(0.05)
                self.logger.info('Waiting heating tool')
                while self.temps[1] < self.target_temps[1]:
                    time.sleep(0.05)
                self.logger.info('Tool heated!')
            else:
                self.logger.warning('Heating gcode cannot be matched! Printer most likely will hang on heating.\nGcode: %s' % gcode)
        self.logger.info('Finished heating!')
        self.heating_flag = False

    def temp_request(self):
        while not self.stop_flag:
            time.sleep(2)
            if self.heating_flag:
                time.sleep(5)  # For not bothering ZMorph printer too much while heating, otherwise it could hang up.
            with self.write_lock:
                self.write(self.TEMP_REQUEST_GCODE)