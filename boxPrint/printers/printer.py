import base64
import logging
import collections
import os
import threading
import json
import time
import downloader



class BasePrinter(object):

    def __init__(self, profile, usb_info):
        self.logger = logging.getLogger(__name__)
        self.stop_flag = False
        self.profile = profile
        self.usb_info = usb_info
        self.position = [0, 0, 0, 0]  # X, Y, Z, E
        self.temps = [0,0]
        self.target_temps = [0,0]
        self.total_gcodes = None
        self.buffer = collections.deque()
        self.downloader = None
        self.current_line_number = 0
        self.loading_gcodes_flag = False
        self.cancel_after_loading_flag = False
        self.pause_flag = False
        self.is_running = True
        self.model_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model_files")
        self.printer_state = 1
        self.finished_flag = False
        self.correct_baudrate = None
        self.total_gcodes = None
        self.total_gcodes_part1 = None
        self.total_gcodes_part2 = None
        self.gcode_part_count = None
        
        self.resource_url = "http://api.mohou.com/mohou/"
        self._breakpoint_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".breakpoint")
        self._current_break_info = ['','','','','','','','']
        
        self.breakpoint_index = 0
        self.breakpoint_print_time = 0
        self.breakpoint_total_gcode_len = None
        self.breakpoint_total_time = None
        self.correct_lines = 50
        if self.profile.has_key('correct_lines') and self.profile['correct_lines'] is not None and self.profile['correct_lines'] != "":
            self.correct_lines = int(float(self.profile['correct_lines']))
        self.outage_gcodes = ["M109 S200", "G91", "G1 Z+5 E-7", "G90", "G28 X0 Y0"]
        if self.profile.has_key('outage_gcodes') and self.profile['outage_gcodes'] is not None:
            self.outage_gcodes = self.profile['outage_gcodes']
        self.pause_lift_height = 5
        if self.profile.has_key('pause_lift_height') and self.profile['pause_lift_height'] is not None and self.profile['pause_lift_height'] != "":
            self.pause_lift_height = int(float(self.profile['pause_lift_height']))
        self.pause_extrude_length = 7
        if self.profile.has_key('pause_extrude_length') and self.profile['pause_extrude_length'] is not None and self.profile['pause_extrude_length'] != "":
            self.pause_extrude_length = int(float(self.profile['pause_extrude_length']))
        
            
        self.initBreakInfo() # read break point to set break info.
        
        self._breakpoint = open(self._breakpoint_file, 'w+') # for saveing break point to file.
        self._breakpoint_lock = threading.Lock()
        
        self._metadata = {}
        self._metadataDirty = False
        self._metadataFile = os.path.join(self.model_file_path, "metadata.json")
        self._metadataTempFile = os.path.join(self.model_file_path, "metadata.json.tmp")
        self._metadataFileAccessMutex = threading.Lock()
        
        self.current_print_file = None
        self.total_gcodes_part1 = None
        self.total_gcodes_part2 = None

        self._loadMetadata()
        
    def initBreakPoint(self):
        with self._breakpoint_lock:
            self._current_break_info = ['','','','','','','','']
        self.saveBreakPoint()
        
    def initBreakInfo(self):
        """
        [res_id, slc_id, slc_flag, file_type, gcodes_length, print_time, total_time, line_number]
         0,      1,      2,        3,         4,             5,          6,          7,           8
        
        """
        self._break_info = None
        with open(self._breakpoint_file, "r") as f:
            break_info = f.readline().strip()
            self.logger.info("break info: %s" % str(break_info))
            self._break_info = break_info.split(',')
        if self._break_info is not None and len(self._break_info) == 8:
            for elem in self._break_info:
                if elem is None or elem.strip() == "":
                    return False
            try:
                self.breakpoint_total_gcode_len = int(float(self._break_info[4]))
            except Exception as ex:
                self.logger.warn("Exception: (%s), %s" % (str(self._break_info[4]), ex.message))
                self.breakpoint_total_gcode_len = None

            try:
                self.breakpoint_print_time = float(self._break_info[5])
            except Exception as ex:
                self.logger.warn("Exception: (%s), %s" % (str(self._break_info[5]), ex.message))
                self.breakpoint_print_time = None

            try:
                self.breakpoint_total_time = float(self._break_info[6])
            except Exception as ex:
                self.logger.warn("Exception: (%s), %s" % (str(self._break_info[6]), ex.message))
                self.breakpoint_total_time = None

            try:        
                self.breakpoint_index = int(float(self._break_info[7]))
            except Exception as ex:
                self.logger.warn("Exception: (%s), %s" % (str(self._break_info[7]), ex.message))
                self.breakpoint_index = 0
                
            if self.breakpoint_index > (self.correct_lines + 20):
                self.breakpoint_index = self.breakpoint_index - self.correct_lines
            else:
                self.breakpoint_index = 0
        else:
            return False
        return True

    def setBreakResID(self, res_id):
        with self._breakpoint_lock:
            self._current_break_info[0] = res_id
            
    def setBreakSlcID(self, slc_id):
        with self._breakpoint_lock:
            self._current_break_info[1] = slc_id
            
    def setBreakSlcFlag(self, slc_flag):
        with self._breakpoint_lock:
            self._current_break_info[2] = str(slc_flag)
            
    def setBreakFileType(self, file_type):
        with self._breakpoint_lock:
            self._current_break_info[3] = file_type
            
    def setBreakGcodesLength(self, gcodes_length):
        with self._breakpoint_lock:
            self._current_break_info[4] = str(gcodes_length)
            
    def setBreakPrintTime(self, print_time):
        with self._breakpoint_lock:
            self._current_break_info[5] = str(print_time)
            
    def setBreakTotalTime(self, total_time):
        with self._breakpoint_lock:
            self._current_break_info[6] = str(total_time)
            
    def setBreakLineNumber(self, line_number):
        with self._breakpoint_lock:
            self._current_break_info[7] = str(line_number)
            
    def saveBreakPoint(self):
        info = ""
        with self._breakpoint_lock:
            info = ','.join(self._current_break_info)
        if info != "":
            self._breakpoint.seek(os.SEEK_SET)
            self._breakpoint.write(info+"\n")
            self._breakpoint.flush()
            os.fsync(self._breakpoint.fileno())

#     def getBreakPoint(self):
#         self._breakpoint.seek(os.SEEK_SET)
#         return self._breakpoint.readline().split(',')
    
    def breakStart(self):
        if self._break_info is not None and len(self._break_info) == 8:
            for elem in self._break_info:
                if elem is None or elem == "":
                    return
            if self._break_info[3] == 'gcode':
                self.gcodes(self.resource_url + self._break_info[0], is_link = True, file_type=self._break_info[3], res_id=self._break_info[0])
            else:
                self.gcodes(self.resource_url + self._break_info[0], is_link = True, file_type=self._break_info[3], res_id=self._break_info[0],\
                                 slc_id=self._break_info[1], slc_flag=int(float(self._break_info[2])), slc_lines=int(float(self._break_info[4])), slc_ptime=int(float(self._break_info[6])))
            

    def _loadMetadata(self):
        if os.path.exists(self._metadataFile) and os.path.isfile(self._metadataFile):
            with self._metadataFileAccessMutex:
                with open(self._metadataFile, "r") as f:
                    self._metadata = json.load(f)
        if self._metadata is None:
            self._metadata = {}

    def saveMetadata(self, force=False):
        if not self._metadataDirty and not force:
            return

        with self._metadataFileAccessMutex:
            with open(self._metadataTempFile, "wb") as f:
                json.dump(self._metadata, f, sort_keys = True, indent = 4, separators = (',', ': '))
                self._metadataDirty = False
            os.rename(self._metadataTempFile, self._metadataFile)
            
    def getFileMetadata(self, filename):
        filename = self.getBasicFilename(filename)
        if filename in self._metadata.keys():
            return self._metadata[filename]
        else:
            return {
                "file_name": ""
            }

    def getBasicFilename(self, filename):
        if filename.startswith("/"):
            return os.path.basename(filename)
        else:
            return filename

    def setFileMetadata(self, filename, metadata):
        filename = self.getBasicFilename(filename)
        self._metadata[filename] = metadata
        self._metadataDirty = True
        
    def getFileNameByResID(self, res_id, file_count):
        file_name = None
        file_name2 = None
        if res_id is not None:
            for key in self._metadata:
                if (res_id != "") and (res_id == key):
                    file_name = self._metadata[key]['file_name']
                    if self._metadata[key].has_key('file_name2'):
                        file_name2 = self._metadata[key]['file_name2']
                    break
        
        if file_count == 2:
            if (file_name is None) or (file_name2 is None):
                return (None, None)
            else:
                return (os.path.join(self.model_file_path, file_name), os.path.join(self.model_file_path, file_name2))
        elif file_count == 1:
            if file_name is None:
                return (None, None)
            else:
                return (file_name, None)
        else:
            return (None, None)
    
    def removeFile(self, file_name):
        model_file = self.getBasicFilename(file_name)
        model_file = model_file.split(".")
        model_file = model_file[0].split("_")
        if len(model_file) > 1:
            file = model_file[0] + "_" + model_file[1]
            if (self.current_print_file is None) or (self.current_print_file != file):
                if file in self._metadata.keys():
                    del self._metadata[file]
                    self._metadataDirty = True
                    self.saveMetadata()
                rm_file = os.path.join(self.model_file_path, file_name)
                if os.path.exists(rm_file):
                    os.remove(rm_file)

    def set_total_gcodes(self, length):
        raise NotImplementedError

    def load_gcodes(self, gcodes):
        raise NotImplementedError
    
    def append_gcodes(self, gcodes):
        raise NotImplementedError

    def unbuffered_gcodes(self, gcodes):
        raise NotImplementedError

    def preprocess_gcodes(self, gcodes):
        gcodes = gcodes.replace("\r", "")
        gcodes = gcodes.split("\n")
        gcodes = filter(lambda item: item, gcodes)
#         self.print_total_time = None
#         for gcode in gcodes:
#             if gcode[0] == ';':
#                 if gcode.find(";Print time: ") == 0:
#                     self.logger.info("Find print time: %s" % gcode)
#                     if self.getGcodePrintTotalTime(gcode) != 0:
#                         self.print_total_time = self.getGcodePrintTotalTime(gcode)
#                         break
#                 
        if gcodes:
            while gcodes[-1] in ("\n", "\r\n", "\t", " ", "", None):
                line = gcodes.pop()
                self.logger.info("Removing corrupted line '%s' from gcodes tail" % line)
        self.logger.info('Got %d gcodes to print.' % len(gcodes))
        return gcodes

    def gcodes(self, gcodes_or_link, is_link = False, file_type = "", res_id=None, slc_id=None, slc_flag=None, slc_lines=0, slc_ptime=None):
        #gcodes_or_link = base64.b64decode(gcodes_or_link)
        gcodes_or_link = gcodes_or_link.strip()
        if is_link:
            if self.is_downloading():
                self.logger.error('Download command received while downloading processing. Aborting...')
                return False
            elif gcodes_or_link.startswith("http://"):
                self.total_gcodes = slc_lines
                self.print_total_time = slc_ptime
                self.gcode_part_count = slc_flag
                self.setBreakGcodesLength(slc_lines)
                self.setBreakTotalTime(slc_ptime)
                self.downloader = downloader.Downloader(self, gcodes_or_link, self.model_file_path, file_type = file_type, res_id=res_id, slc_id=slc_id, slc_flag=slc_flag)
                self.downloader.start()
            elif gcodes_or_link.startswith("local://"):
                local_file = os.path.join(self.model_file_path, gcodes_or_link[8:])
                if local_file:
                    with open(local_file, 'rb') as f:
                        self.load_gcodes(f.read())
                        self.logger.info("Local file(%s) gcodes loaded to memory." % local_file)
                
        else:
            self.unbuffered_gcodes(gcodes_or_link)

    def get_position(self):
        return self.position

    def get_temps(self):
        return self.temps

    def get_target_temps(self):
        return self.target_temps

    def cancel_download(self):
        if self.is_downloading():
            self.logger.info("Canceling downloading")
            self.downloader.cancel()
            return True

    def pause(self):
        self.pause_flag = True

    def unpause(self):
        self.pause_flag = False

    def close(self):
        self.stop_flag = True
        self.is_running = False

    def is_paused(self):
        return self.pause_flag

    def is_operational(self):
        return False

    def is_downloading(self):
        return self.downloader and self.downloader.is_alive()
    
    # Utils    
    def getFormattedTimeDelta(self, d):
        if d is None:
            return None
        hours = d.days * 24 + d.seconds // 3600
        minutes = (d.seconds % 3600) // 60
        seconds = d.seconds % 60
        return "%02d:%02d:%02d" % (hours, minutes, seconds)
    
    def getGcodePrintTotalTime(self, line):
        hours = 0
        minutes = 0
        line = line.strip()
        sub_line = line[len(";Print time: "):]
        data = sub_line.split(" ")
        try:
            if len(data) == 4:
                hours = int(data[0])
                minutes = int(data[2])
            elif len(data) == 2:
                hours = 0
                minutes = int(data[0])
            else:
                pass
        except Exception, err:
            raise err    
        return hours * 60 + minutes

    def goHome(self):
        raise NotImplementedError

    def goXYHome(self):
        raise NotImplementedError

    def goZHome(self):
        raise NotImplementedError
    
    def goXPosition(self, pos):
        raise NotImplementedError
        
    def goYPosition(self, pos):
        raise NotImplementedError
    
    def goZPosition(self, pos):
        raise NotImplementedError
        
    def goEOperation(self, e, length):
        raise NotImplementedError

    def setBedTargetTemp(self, temp):
        raise NotImplementedError
    
    def setETargetTemp(self, e, temp):
        raise NotImplementedError
    
    def setSpeedFactor(self, speedfactor):
        raise NotImplementedError
    
    def toOperational(self):
        self.finished_flag = False
        self.printer_state = 3
    
    def createFormData(self, fields, fileinfo=None):
        """
        fields is a dict of (name, value) elements for regular form fields.
        Return (headers, body) ready for httplib.HTTP instance
        """
        BOUNDARY = '----------ThIs_Is_tHe_bouNdaRY_$'
        CRLF = '\r\n'
        L = []
        for (key, value) in fields.items():
            L.append('--' + BOUNDARY)
            L.append('Content-Disposition: form-data; name="%s"' % key)
            L.append('')
            L.append(str(value))
        if fileinfo is not None:
            L.append('--' + BOUNDARY)
            L.append('Content-Disposition: form-data; name="file"; filename="%s"' % str(fileinfo["filename"]))
            L.append('Content-Type: %s' % str(fileinfo["filetype"]))
            L.append('')
            L.append(fileinfo["filecontent"])
    
        L.append('--' + BOUNDARY + '--')
        L.append('')
        body = CRLF.join(L)
        content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
        headers = {'Content-Type' : content_type}
        return headers, body

    def pushMessage2Client(self):
        from tornado.httpclient import HTTPClient, HTTPError
        from tornado.escape import json_decode
        self.logger.info("Print finished.")
        http_client = HTTPClient()
        #data = {"device_id": self.profile['boxid']}
        data = {"device_id": self.profile['boxid']}
        (headers, body) = self.createFormData(data)
        try:
            response = http_client.fetch("http://yun.mohou.com/api/cloud/push-message", method='POST', headers=headers, body=body, request_timeout=10)
            data = json_decode(response.body)
            self.logger.info("Response result: %s." % str(response.body))
            if data['code'] == 0:
                return 0
            else:
                return 1
        except HTTPError as err:
            self.logger.error("HTTPError: " + str(err))
            return 2
        except Exception as ex:
            self.logger.error("Exception: " + str(ex))
            return 2

class BreakPointThread(threading.Thread):

    def __init__(self, printer, name=None):
        self.printer = printer
        if not name:
            name = self.__class__.__name__
        self.logger = logging.getLogger(name)
        super(BreakPointThread, self).__init__(name=name)

    def run(self):
        while not self.printer.stop_flag:
            if not self.printer.is_printing():
                time.sleep(1)
                continue
            time.sleep(1)
            self.printer.saveBreakPoint()

