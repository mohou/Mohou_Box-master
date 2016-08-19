# coding=utf-8

#from threading import Thread
import Queue
import sys
import time
import logging
import re
import os
import psutil

class PrintService(object):
    def __init__(self, profile, serialInfo):
#         super(PrintService, self).__init__(name="PrintService")
        self.profile = profile
        self.serialInfo = serialInfo
        self.printer = None
        self.logger = logging.getLogger(__name__)
#         self.stopFlag = False
     
#         self.command_queue = Queue.PriorityQueue()
    
#     def run(self):
#         while True:
#             if self.stopFlag:
#                 break
#             (command, payload) = self.command_queue.get(True)
#             print "command: %s" % str(command)
#             print "payload: %s" % str(payload)
#             method = getattr(self, command, None)
#             if not method:
#                 print "Unkown command: %s!" % command
#                 continue
#             try:
#                 method(payload)
#             except Exception as e:
#                 print "Exception: %s." % e.message
#             else:
#                 pass
# 
#     # Stop print service.    
    def stop(self):
#         self.stopFlag = True
        self.disconnectPrinter()
# 
#     # Send command to queue.
#     def connect(self, payload=None):
#         self.command_queue.put(("connectPrinter", payload), 0)
#     
#     def disconnect(self, payload=None):
#         self.command_queue.put(("disconnectPrinter", payload), 0)
#     
#     def start(self, payload=None):
#         self.command_queue.put(("startPrint", payload), 0)
#     
#     def pause(self, payload=None):
#         self.command_queue.put(("pausePrint", payload), 0)
#     
#     def unpause(self, payload=None):
#         self.command_queue.put(("unpausePrint", payload), 0)
#  
#     def cancel(self, payload=None):
#         self.command_queue.put(("cancelPrint", payload), 0)
#         
#     def execute(self, payload):
#         self.command_queue.put(("executeCommand", payload), 0)

    # Execute printer command.
    def connectPrinter(self, playload=None):
        ret = False
        if (self.profile['driver'] is not None) and (self.serialInfo['COM'] is not None):
            if self.printer is not None:
                self.disconnectPrinter()
                time.sleep(0.1)
            try:
                printer_class = __import__(self.profile['driver'])
            except ImportError as ie:
                self.logger.error("Printer type %s not supported." % self.profile['driver'])
                self.logger.error("Import error: %s" % ie.message)
            else:
                try:
                    self.printer = printer_class.Printer(self.profile, self.serialInfo)
                except RuntimeError as e:
                    message = "Can't connect to printer %s %s\nReason: %s" % (self.profile['name'], str(self.serialInfo), e.message)
                    self.logger.error(message)
                except Exception:
                    message = "Unexpected error while connecting to %s: %s" % (self.profile['name'], sys.exc_info()[1])
                    self.logger.error(message)
                else:
                    message = "Successful connection to %s!" % (self.profile['name'])
                    self.logger.info(message)
                    ret = True
        return ret

    def disconnectPrinter(self, playload=None):
        if self.printer is None:
            return
        #if self.printer.is_operational():
        self.printer.close()
        self.printer = None
        
    def startPrint(self, payload):
        if self.printer is None:
            return
        if payload['filetype'] == 'gcode':
            self.printer.gcodes(self.printer.resource_url + payload['res_id'], is_link = True, file_type=payload['filetype'], res_id=payload['res_id'])
        else:
            self.printer.gcodes(self.printer.resource_url + payload['res_id'], is_link = True, file_type=payload['filetype'], res_id=payload['res_id'],\
                             slc_id=payload['slc_id'], slc_flag=int(payload['slc_flag']), slc_lines=int(payload['slc_lines']), slc_ptime=int(payload['slc_ptime']))
        
    def pausePrint(self, payload=None):
        if self.printer is None:
            return
        self.printer.pause()

    def unpausePrint(self, payload=None):
        if self.printer is None:
            return
        self.printer.unpause()

    def cancelPrint(self, payload=None):
        if self.printer is None:
            return
        self.printer.cancel()
        
    def executeCommand(self, payload):
        if self.printer is None:
            return
        self.printer.unbuffered_gcodes(payload)
        
    def removeFile(self, payload):
        if self.printer is None:
            return
        self.printer.removeFile(payload)
        
    def toOperational(self, payload=None):
        if self.printer is None:
            return
        self.printer.toOperational()

    def getStatus(self):
        data = {
                "boxid": self.profile['boxid'],
                "name": self.profile['box_name'],
                
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
        if self.printer is None:
            data["printer_state"] = 1
        else:
            self.printer.read_state()
            try:
                data["bed_temperature"]           = self.printer.temps[0]
                data["target_bed_temperature"]    = self.printer.target_temps[0]
                data["temperature1"]              = self.printer.temps[1]
                data["target_temperature1"]       = self.printer.target_temps[1]
                data["temperature2"]              = self.printer.temps[2]
                data["target_temperature2"]       = self.printer.target_temps[2]
            except Exception as ex:
                pass
            data["extruder_amount"]           = self.printer.extruder_amount
            data["printer_state"]             = self.printer.printer_state
            data["print_progress"]            = self.printer.print_progress
            data["print_speed"]               = self.printer.print_speed
            data["fan_speed"]                 = self.printer.fan_speed
            if hasattr(self.printer, "print_time_escape"):
                data["print_time_escape"]     = self.printer.print_time_escape
            if hasattr(self.printer, "print_time_remain"):
                data["print_time_remain"]     = self.printer.print_time_remain

            hddinfo = os.statvfs(self.printer.model_file_path)
            data['disk_size'] = hddinfo.f_frsize * hddinfo.f_blocks / 1024
            #剩余存储空间，单位为KB
            data['free_disk_size'] = hddinfo.f_frsize * hddinfo.f_bavail / 1024
            #总内存，单位KB
            phymem = psutil.virtual_memory()
            #剩余内存，单位KB
            data['mem_size'] = phymem.total / 1024
            data['free_mem_size'] = phymem.free / 1024
            #CPU占用率，百分数，60%表示为60
            data['port'] = self.serialInfo["COM"]
            data['baudrate'] = self.printer.correct_baudrate
            data['cpu_usage'] = psutil.cpu_percent()
            data['pid'] = self.serialInfo["PID"]
            data['vid'] = self.serialInfo["VID"]
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
        return data
    
    def goHome(self):
        if self.printer is None:
            return
        self.printer.goHome()

    def goXYHome(self):
        if self.printer is None:
            return
        self.printer.goXYHome()

    def goZHome(self):
        if self.printer is None:
            return
        self.printer.goZHome()
    
    def goXPosition(self, pos):
        if self.printer is None:
            return
        self.printer.goXPosition(pos)
        
    def goYPosition(self, pos):
        if self.printer is None:
            return
        self.printer.goYPosition(pos)
    
    def goZPosition(self, pos):
        if self.printer is None:
            return
        self.printer.goZPosition(pos)
        
    def goEOperation(self, e, length):
        if self.printer is None:
            return
        self.printer.goEOperation(e, length)

    def setBedTargetTemp(self, temp):
        if self.printer is None:
            return
        self.printer.setBedTargetTemp(temp)
        
    def setETargetTemp(self, e, temp):
        if self.printer is None:
            return
        self.printer.setETargetTemp(e, temp)
    
    def setSpeedFactor(self, speedfactor):
        if self.printer is None:
            return
        self.printer.setSpeedFactor(speedfactor)
    
    
