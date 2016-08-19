# coding=utf-8

from tornado.options import define, options
import tornado.web
import tornado.httpserver
import tornado.ioloop
import os
import signal
import logging
import time
from threading import Thread
from tornado.escape import json_decode
import psutil
import re

import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "printers"))

from config import PrinterProfile
from print_service import PrintService
from usb_detect import USBDetector
#from docutils.parsers.rst.directives import path

class MainThread(Thread):
    def __init__(self, profileObj, cb_setPrintService):
        super(MainThread, self).__init__(name="MainThread")
        self.profileObj = profileObj
        self.callback = cb_setPrintService
        self.printService = None
        self.stopFlag = False
        self.sleepSecs = 3
        self.connect_status = 1;
        self.retry = 0;
        self.logger = logging.getLogger(__name__)

    def run(self):
        self.logger.info("Start mainThread.")
        while not self.stopFlag:
            self.startPrintService()
            if self.printService is not None:
                if self.printService.serialInfo not in self.serialList:
                    self.logger.info("No longer detected as serial device.")
                    self.printService.disconnectPrinter()
                    self.printService = None
                    self.callback(self.printService)
            if not self.stopFlag:
                time.sleep(self.sleepSecs)
#         self.quit()
            
    def getSerialInfo(self):
        printers = USBDetector().get_printers_list()
        serialList = filter(lambda x: x.get('COM'), printers)
        return serialList
    
    def startPrintService(self):
        self.serialList = self.getSerialInfo()
        profile = self.profileObj.load()
        if profile.has_key('logging') and profile['logging'] is not None and profile['logging'] != "":
            if profile["logging"] == 'debug':
                rootLog = logging.getLogger()
                rootLog.setLevel(logging.DEBUG)
        self.logger.debug(str(self.serialList))
        if len(self.serialList) == 0:
            self.connect_status = 1
            self.retry = 0
        if profile['alias'] == '__AUTO__':
            return
        for serialInfo in self.serialList:
            self.connect_status = 2        
            if profile['port'] == "AUTO":
                if self.printService is None:
                    ps = PrintService(profile, serialInfo)
                    if ps.connectPrinter():
                        self.callback(ps)
                        self.printService = ps
                        break
                        
            else:           
                if serialInfo["COM"] == profile['port']:
                    if self.printService is None:
                        ps = PrintService(profile, serialInfo)
                        if ps.connectPrinter():
                            self.callback(ps)
                            self.printService = ps
                            break
        
        if len(self.serialList) != 0:
            if self.printService is None:
                self.retry = 1
            else:
                self.retry = 0
                    
    
    def stop(self):
        self.stopFlag = True
    
#     def quit(self):
#         pass
#  

class App(tornado.web.Application):
    def __init__(self):
        self.handlers = []
        self.settings = {
                         "autoreload": False,
                         }
#         self.setHandlers()
        
#     def setHandlers(self):
#         self.handlers.append((r'/profile',          PrinterProfileHandler))
#         self.handlers.append((r'/status',           PrinterStatusHandler))
#         self.handlers.append((r'/command',          PrinterCommandHandler))
#         self.handlers.append((r'/test',             PrinterTestHandler))
#         self.handlers.append((r'/snapshot',         MJPGHandler))

    def init(self):
        super(App, self).__init__(self.handlers, **self.settings)
        self.printService = None
        self.profileObj = PrinterProfile.instance()
        self.mainThread = MainThread(self.profileObj, self.setPrintService)
        self.mainThread.start()
        
    def setPrintService(self, service):
        self.printService = service
        
    def addHandler(self, URI):
        def doHandler(handler):
            self.handlers.append((URI, handler))
            return handler
        return doHandler

class Server(object):
    def __init__(self):
        signal.signal(signal.SIGINT, self.intercept_signal)
        signal.signal(signal.SIGTERM, self.intercept_signal)
        
        self.logger = logging.getLogger(__name__)
        define("port", default=5000, help="run on the given port", type=int)
        define("host", default="0.0.0.0", help="run on the given host", type=str)
        self.config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "boxPrint.conf")
        tornado.options.parse_config_file(self.config_file)

        self.host = options.host
        self.port = options.port
        self.app =  App()
        
    def run(self):
        http_server = tornado.httpserver.HTTPServer(self.app)
        http_server.listen(self.port, self.host)
        self.logger.info("Mohou 3d print provider start.")
        tornado.ioloop.IOLoop.current().start()
        
    def intercept_signal(self, signal_code, frame):
        self.logger.info("Mohou 3d print provider stoped.")
        try:
            if self.app.mainThread.printService:
                self.app.mainThread.printService.stop()
        except Exception as ex:
            self.logger.error("Exception: %s." % ex.message)    
        self.app.mainThread.stop()
        tornado.ioloop.IOLoop.current().stop()


server = Server()

@server.app.addHandler(r'/profile')        
class PrinterProfileHandler(tornado.web.RequestHandler):
    def post(self):
        printer_profile = self.get_argument("printer_profile", "")
        token = self.get_argument("token", "")
        code = 0
        msg = "Success"
        data = {}
        if printer_profile != "" and token != "":
            try:
                json_data = json_decode(printer_profile)
                json_data['token'] = token
            except Exception as ex:
                code = 2
                msg = "Exception: %s" % str(ex)
            else:
                self.application.profileObj.save(json_data)
                if self.application.mainThread.printService:
                    self.application.mainThread.printService.stop()
                    self.application.mainThread.printService = None
        else:
            code = 4
            msg = "Parameter error."            
        self.write({"code" : code, "msg" : msg, "data": data})

@server.app.addHandler(r'/profile2')        
class PrinterProfileHandler(tornado.web.RequestHandler):
    def post(self):
        printer_profile = self.get_argument("printer_profile", "")
        code = 0
        msg = "Success"
        data = {}
        if printer_profile != "":
            try:
                json_data = json_decode(printer_profile)
            except Exception as ex:
                code = 2
                msg = "Exception: %s" % str(ex)
            else:
                self.application.profileObj.save(json_data)
                if self.application.mainThread.printService:
                    self.application.mainThread.printService.stop()
                    self.application.mainThread.printService = None
        else:
            code = 4
            msg = "Parameter error."            
        self.write({"code" : code, "msg" : msg, "data": data})

    def get(self):
        code = 0
        msg = "Success"
        data = {}
        data = self.application.profileObj.load()            
        self.write({"code" : code, "msg" : msg, "data": data})

@server.app.addHandler(r'/status')
class PrinterStatusHandler(tornado.web.RequestHandler):
    def get(self):
        code = 0
        if self.application.printService is None:
            profile = self.application.profileObj.load()
            msg = "Printer is disconnected."
            data = {
                "boxid": profile['boxid'],
                "name": profile['box_name'],
                
                "port": "",
                "baudrate": "",
                "pid": "",
                "pname": "",
                "vid": "",
                "vname": "",
                
                "app_ver": "1.0.1",
                #"proto_ver": "1.0.0",
                "bed_temperature": 0,
                "target_bed_temperature": 0,
                "temperature1": 0,
                "target_temperature1": 0,
                "temperature2": 0,
                "target_temperature2": 0,
                "extruder_amount": 1,
                "printer_state": 1,
                "print_progress": 0,
                "print_speed": 0,
                "fan_speed": 0,
                "print_time_escape": "00:00:00",
                "print_time_remain": "00:00:00",
                
                'cpu_usage': 0,
                'disk_size': 0,
                'free_disk_size': 0,
                'mem_size': 0,
                'free_mem_size': 0,
                'loc_ip': "127.0.0.1",
             
            }
            #总内存，单位KB
            phymem = psutil.virtual_memory()
            #剩余内存，单位KB
            data['mem_size'] = phymem.total / 1024
            data['free_mem_size'] = phymem.free / 1024
            #CPU占用率，百分数，60%表示为60
            data['cpu_usage'] = psutil.cpu_percent()
            #内网IP如192.168.1.100
            text = os.popen("ifconfig eth0").read()
            reg_eth0 = re.match(r".*addr:(.*)  Bcast:.*Mask:(.*)", text, re.S)
            text = os.popen("ifconfig wlan0").read()
            reg_wlan0 = re.match(r".*addr:(.*)  Bcast:.*Mask:(.*)", text, re.S)
            if reg_wlan0:
                data['loc_ip'] = reg_wlan0.group(1)
            elif reg_eth0:
                data['loc_ip'] = reg_eth0.group(1)
            else:
                data['loc_ip'] = "127.0.0.1"

            if self.application.mainThread.connect_status == 1:
                data['printer_state'] = self.application.mainThread.connect_status
            elif self.application.mainThread.retry == 0:
                data['printer_state'] = self.application.mainThread.connect_status
            else:
                data['printer_state'] = 0x82
        else:
            msg = "Success"
            data = self.application.printService.getStatus()
            if not data:
                code = 2
                msg = "Get status failed."
            
        self.write({"code" : code, "msg" : msg, 'data': data})

@server.app.addHandler(r'/command')
class PrinterCommandHandler(tornado.web.RequestHandler):
    def post(self):
        type = self.get_argument("type")
        code = 0
        msg = "Success"
        data = {}
        if self.application.printService is None:
            code = 1
            msg = "Printer is disconnected."
            data = {}
        else:
            if type == "start":
                payload_str = self.get_argument("data")
                try:
                    payload = json_decode(payload_str)
                except Exception as ex:
                    code = 2
                    msg = "Exception: %s" % str(ex)
                else:
                    if payload.has_key('filetype') and payload['filetype'] == 'gcode':
                        self.application.printService.startPrint(payload)
                    elif payload.has_key('filetype') and payload.has_key('res_id') and payload.has_key('slc_id') and payload.has_key('slc_flag') \
                            and payload.has_key('slc_lines') \
                            and payload['filetype'] != "" and payload['res_id'] != "" and payload['slc_id'] != "" and payload['slc_flag'] != "" \
                            and payload['slc_lines'] != "":
                        self.application.printService.startPrint(payload)
                    else:
                        code = 4
                        msg = "Parameter error."
                        data['type'] = type
                        data['data'] = payload_str
            elif type == "pause":
                self.application.printService.pausePrint()
            elif type =="continue":
                self.application.printService.unpausePrint()
            elif type == "cancel":
                self.application.printService.cancelPrint()
            elif type == "connect":
                self.application.printService.connectPrinter()
            elif type == "disconnect":
                self.application.printService.disconnectPrinter()
            elif type == "operational":
                self.application.printService.toOperational()
            else:
                code = 1
                msg = "Unknown command type."
            
        self.write({"code" : code, "msg" : msg, 'data': {}})

@server.app.addHandler(r'/test')
class PrinterTestHandler(tornado.web.RequestHandler):
    def post(self):
        code = 0
        msg = "Success"
        data = {}
        type = self.get_argument("type", None)
        data_str = self.get_argument("data", None)
        if self.application.printService is None:
            code = 1
            msg = "Printer is disconnected."
        elif type is None or data_str is None:
            code = 2
            msg = "type or data is None"
        else:
            try:
                json_data = json_decode(data_str)
            except Exception as ex:
                code = 3
                msg = "Exception: %s" % str(ex)
            else:
                if type =="position":
                    if json_data.has_key('orientation') and json_data.has_key('value'):
                        if json_data['orientation'] in [0, "0"]:
                            if json_data['value'] in [0, "0"]:
                                self.application.printService.goXYHome()
                            else:
                                self.application.printService.goXPosition(json_data['value'])
                        if json_data['orientation'] in [1, "1"]:
                            if json_data['value'] in [0, "0"]:
                                self.application.printService.goXYHome()
                            else:
                                self.application.printService.goYPosition(json_data['value'])                        
                        if json_data['orientation'] in [2, "2"]: 
                            if json_data['value'] in [0, "0"]:
                                self.application.printService.goZHome()
                            else:
                                self.application.printService.goZPosition(json_data['value'])
                    else:
                        code = 4
                        msg = "Parameter error."
                        data['type'] = type
                        data['data'] = data_str
                elif type == "nozzle":
                    if json_data.has_key('nozzlenum') and json_data.has_key('direction') and json_data.has_key('value'):
                        self.application.printService.goEOperation(json_data['nozzlenum'], json_data['value'])
                    else:
                        code = 4
                        msg = "Parameter error."
                        data['type'] = type
                        data['data'] = data_str
                elif type == "bedtemp":
                    if json_data.has_key('value'):
                        self.application.printService.setBedTargetTemp(json_data['value'])
                    else:
                        code = 4
                        msg = "Parameter error."
                        data['type'] = type
                        data['data'] = data_str
                elif type == "nozzletemp":
                    if json_data.has_key('nozzlenum') and json_data.has_key('value'):
                        self.application.printService.setETargetTemp(json_data['nozzlenum'], json_data['value'])
                    else:
                        code = 4
                        msg = "Parameter error."
                        data['type'] = type
                        data['data'] = data_str
                elif type == "speedfactor":
                    if json_data.has_key('value'):
                        self.application.printService.setSpeedFactor(json_data['value'])
                    else:
                        code = 4
                        msg = "Parameter error."
                        data['type'] = type
                        data['data'] = data_str
            
        self.write({"code" : code, "msg" : msg, 'data': data})

@server.app.addHandler(r'/snapshot')
class MJPGHandler(tornado.web.RequestHandler):
    def get(self):
        data = {}
        code = 0
        msg = "Success"
        uuid_str = self.get_argument('uuid', '')
        name_str = self.get_argument('name', '')
        if uuid_str == '' and name_str == '':
            code = 4
            msg = "Parameter error."
        elif uuid_str:
            pic_file_name = uuid_str+'.jpg'
            if os.path.exists("/tmp/"+pic_file_name):
                os.remove("/tmp/"+pic_file_name)
            clean_cmd = '/usr/bin/find /tmp -type f -cmin +2 -name "*.jpg" -exec rm {} \;'
            os.system(clean_cmd)
            cmd_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshot", "bin")
            cat_cmd = cmd_path + '/mjpg_streamer -i "' + cmd_path + '/input_uvc.so -r 640x480 -n" -o "' + cmd_path + '/output_file.so -m '+pic_file_name+'" > /dev/null 2>&1'
            os.system(cat_cmd)
            ret_values = {}
            if(os.path.isfile("/tmp/"+pic_file_name) is True):
                data['pic_url'] = "snapshot?name="+pic_file_name
            else:
                data['pic_url'] = "snapshot?name=default_monitor.jpg"

            self.write({"code" : code, "msg" : msg, 'data': data})
        elif name_str:
            pic_path = "/tmp/" + name_str
            default_pic_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshot", "default_monitor.jpg")
            if(os.path.isfile(pic_path) is not True):
                with open(default_pic_path, 'rb') as f:
                    content = f.read()
                size = os.path.getsize(default_pic_path)
            else:
                with open(pic_path, 'rb') as f:
                    content = f.read()
                size = os.path.getsize(pic_path)
            self.set_header("Content-Type", "image/jpg")
            self.set_header("Content-Length", size)
            self.write(content)
        else:
            code = 0xff
            msg = "Unkown error."
            self.write({"code" : code, "msg" : msg, 'data': data})

@server.app.addHandler(r'/execute')
class ExecHandler(tornado.web.RequestHandler):
    def post(self):
        data = {}
        code = 0
        msg = 'Success'
        cmds_str = self.get_argument("cmds", None)
        if self.application.printService is None:
            code = 1
            msg = "Printer is disconnected."
        elif cmds_str is None:
            code = 2
            msg = "cmds is None."
        else:
            try:
                cmds = json_decode(cmds_str)
            except Exception as ex:
                code = 3
                msg = "Exception: %s" % str(ex)
            else:
                if cmds.has_key('cmds'):
                    self.application.printService.executeCommand(cmds['cmds'])
                    data = cmds
                else:
                    code = 4
                    msg = "Parameter error."
        self.write({"code" : code, "msg" : msg, 'data': data})    

@server.app.addHandler(r'/removemodelfiles')
class RemoveModelFilesHandler(tornado.web.RequestHandler):
    def post(self):
        data = {}
        code = 0
        msg = 'Success'
        filelist = self.get_argument("filelist", None)
        if filelist:
            try:
                if filelist[-1:] == ";":
                    files = filelist[0:-1].split(';')
                else:
                    files = filelist.split(';')
                data['file_list'] = filelist
                for f in files:
                    self.application.printService.removeFile(f)
            except Exception as ex:
                code = 1
                msg = ex.message

        self.write({"code" : code, "msg" : msg, 'data': data})    

if __name__ == "__main__":
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    os.chdir("/")
    os.setsid()
    os.umask(0)
    
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    server.app.init()
    server.run()

