#!/usr/bin/env python
# -*- coding:utf-8 -*-  
import sys
reload(sys)
sys.setdefaultencoding('utf8')
#sys.path.append("/home/pi/oprint/lib/python2.7/site-packages/tornado-4.0.1-py2.7-linux-armv7l.egg/")
#sys.path.append("/home/pi/oprint/lib/python2.7/site-packages/backports.ssl_match_hostname-3.4.0.2-py2.7.egg/")


import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import uuid
import hashlib
import time
import logging
import os
import urllib
import httplib
import json
import md5

from tornado.httpclient import HTTPClient
from tornado.escape import json_decode
from tornado.options import define, options
from common import Application

from network_api import get_allwifi_info, get_network_info, get_dns_info, set_wifi, set_network, machine_is_online, get_serial_number, set_serial_number
from user_api import md5, get_user_info, set_user_info, bind_box_api, unbind_box_api, init_box_config_info
from update_api import getLatestVer, getCurrentVer, getUpdateMeta, netUpdate, initUpdateInfo, clearUpdateInfoBegin, getUpdatePkgDesc
import settings as WebConfig
from machine_api import update_machine_config, update_setting_gcode, update_preferences_file_info, get_current_activity_print_machine, get_active_machine_print_info, \
                        get_default_machine_print_info, write_print_info, restart_web_service


define("host", default="*", help="run on the given host")
define("port", default=8092,  help="run on the given port", type=int)

app = Application()
WebConfig.settings(True);

logger = logging.getLogger("__name__")
bind_messages = ["绑定成功".encode("utf8"),
            "绑定失败，请重试".encode("utf8"), 
            "数据读取失败,配置文件丢失".encode("utf8"), 
            "连接认证服务器网络失败".encode("utf8")]
unbind_messages = ["解除绑定成功".encode("utf8"),
            "解除绑定失败，请重试".encode("utf8"), 
            "数据读取失败,配置文件丢失".encode("utf8"), 
            "连接认证服务器网络失败".encode("utf8")]
machine_config_messages = ["设定成功".encode("utf8"),
            "设定失败".encode("utf8")]


@app.route(r"/bind")
class bind(tornado.web.RequestHandler):
    def post(self):
        username = self.get_argument("username")
        password = md5(self.get_argument("password"))
        result = None
        is_on_line = machine_is_online()
        if is_on_line:
            user_info = get_user_info()
            if user_info["device_id"]:
                response = bind_box_api(username, password, user_info["device_id"], user_info["box_name"])
                if response and response["code"] in [1, 81]:
                    user_info["username"] = username
                    user_info["password"] = password
                    user_info["user_token"] = response["data"]["token"]
                    user_info["remember_information"] = 1
                    user_info["binding_mohou"] = 1
                    user_info["is_login"] = 1
                    set_user_info(user_info);
                    result = 0
                else:
                    result = 1
            else:
                result = 2
        else:
            result = 3
        return self.write({"result" : result, "msg" : bind_messages[result]})

@app.route(r"/unbind")
class unbind(tornado.web.RequestHandler):
    def post(self):
        result = None
        is_on_line = machine_is_online()
        if is_on_line:
            user_info = get_user_info()
            if user_info and user_info["user_token"] and user_info["device_id"]:
                response = unbind_box_api(user_info["user_token"], user_info["device_id"])
                if response and response["code"] == 1:
                    user_info_default = {
                                         "username" : "",
                                         "password" : "",
                                         "user_token" : "",
                                         "remember_information" : 0,
                                         "binding_mohou" : 0,
                                         "is_login" : 0
                                         }
                    set_user_info(user_info_default);
                    result = 0
                else:
                    result = 1
            else:
                result = 2
        else:
            result = 3
        return self.write({"result" : result, "msg" : unbind_messages[result]})
    

@app.route(r"/update")
class update(tornado.web.RequestHandler):
    def get(self):
        clearUpdateInfoBegin()
        initUpdateInfo()
        return self.render(
            "update.jinja2",
            update_mode=self.get_argument("mode"),
            latest_ver=getLatestVer(),
            current_ver=getCurrentVer(),
             update_desc=getUpdatePkgDesc(),
            update_meta=getUpdateMeta()
        )
 		
@app.route(r"/pre_update")
class pre_update(tornado.web.RequestHandler):
    def get(self):
        result = "0"
        clearUpdateInfoBegin()
        initUpdateInfo()
        return self.write(result)
         
@app.route(r"/netupdate_ajax")
class netupdate_ajax(tornado.web.RequestHandler):
    def post(self):
        result = "0"
        clearUpdateInfoBegin()
        initUpdateInfo()
        netUpdate()
        return self.write(result)

    def get(self):
        type = self.get_argument("type", default="meta")
        retContent = {}
        if type == "meta":
            retContent=getUpdateMeta()
        elif type == "cur_ver":
            retContent = {"current_ver" : getCurrentVer()}
        #retContent = {"current_ver" : "1.1"}
        else:
            pass
        return self.write(retContent)

@app.route(r"/")
class moWifi(tornado.web.RequestHandler):
    def get(self):
        wifi_info = get_network_info("wlan0")
        wire_info = get_network_info("eth0")
        dns_info = get_dns_info()
        serial_number = get_serial_number()
        #user_info = get_user_info()
        #print_info = get_active_machine_print_info()
        return self.render(
        	"mowifi.jinja2",
        	wifi_info = wifi_info,
            wire_info = wire_info,
        	dns_info = dns_info,
            sn=serial_number
            #user_info = user_info,
            #print_info = print_info
        )
        
@app.route(r"/setserialnumber")
class SerialNumber(tornado.web.RequestHandler):
    def post(self):
        serial_number = self.get_argument("sn", None)
        if serial_number:
            if set_serial_number(serial_number) == 0:
                return self.write("0")
        return self.write("1")
    

@app.route(r"/wifi")
class WifiSetting(tornado.web.RequestHandler):
    def get(self):
        wifissid = self.get_argument("ssid", None)
        wifi_list = get_allwifi_info()
        if wifissid:
           wifi_list =  filter(lambda x: x[0]==wifissid and x or False , wifi_list)
           if wifi_list:
               return self.write({'code': 0, 'msg': 'Success', 'data': {'ssid': wifi_list[0][0], 'state': wifi_list[0][1], 'lock': wifi_list[0][2], 'signal': wifi_list[0][3]}})
           else:
               return self.write({'code': 1, 'msg': 'SSID error.', 'data': {'wifi_list': []}})
        else:
            return self.write({'code': 0, 'msg': 'Success', 'data': {'wifi_list': wifi_list}})
    def post(self):
        wifissid = self.get_argument("ssid")
        wifipwd = self.get_argument("pwd")
        set_wifi(wifissid, wifipwd)
        return self.write({'code': 0, 'msg': 'Success', 'data': {}})

@app.route(r"/isaccesscloud")
class AccessCloud(tornado.web.RequestHandler):
    def get(self):
        is_on_line = machine_is_online()
        
        cur_client = HTTPClient()
        response = cur_client.fetch("http://127.0.0.1:5000/status", request_timeout=10)
        if response.error:
            logger.warn("Failed to get current box info. error=%s", response.error)
            is_on_line = False
        res = json_decode(response.body)
        if res["code"] != 0:
            logger.warn("Failed to get current box info. ret_value=%d", res["ret_value"])
            is_on_line = False
        
        if is_on_line:
            boxid = res["data"]["boxid"]
            params=urllib.urlencode({
                        "token": "box_setting",
                        "boxid": boxid,
                        "progress": 2
                        })
            headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Connection": "Keep-Alive"}
            conn = httplib.HTTPConnection("yun.mohou.com")
            conn.request(method="POST", url="/api/box/init-setting", body=params, headers=headers)
            response = conn.getresponse()
            response_json = response.read()
            conn.close()
            logger.info("Box setting result: " + str(response_json))
            is_access_cloud = True
        else:
            is_access_cloud = False
        return self.write({'code': 0, 'msg': 'Success', 'data': {'is_access_cloud': is_access_cloud}})

@app.route(r"/mowifiinfoajax")
class moWifiAjax(tornado.web.RequestHandler):
    def get(self):
        return self.render(
            "wifiinfo.jinja2",
            wifi_list=get_allwifi_info()
        )
	
    def post(self):
        result = "0"
        type = int(self.get_argument("type"))
        if type == 1:
            #connect wifi
            wifissid = self.get_argument("wifissid")
            wifipwd = self.get_argument("wifipwd")
            set_wifi(wifissid, wifipwd)
            return self.write(result)
        elif (type == 2) or (type == 3):
            #set ip address
            if type == 2:
                iface_name = "wlan0"
            else:
                iface_name = "eth0"
            
            result = "0"
            iface_info = {}
            dns_info = {}
            
            iface_info["dhcp"] = self.get_argument("dhcp")
            iface_info["ip"] = ""
            iface_info["netmask"] = ""
            iface_info["gateway"] = ""
            dns_info["dns"] = ""
            if iface_info["dhcp"] == "0":
                iface_info["ip"] = self.get_argument("ip")
                iface_info["netmask"] = self.get_argument("mask")
                iface_info["gateway"] = self.get_argument("gateway")
                dns_info["dns"] = self.get_argument("dns")
            set_network(iface_name, iface_info, dns_info)
            return self.write(result)
        else:
            #Log incorrect type
            pass
        

@app.route(r"/settings/machines")
class MachineDefaultConfig(tornado.web.RequestHandler):
    def post(self):
        json_strings = self.request.body
        data = json.loads(json_strings)
        alter_machine_info = get_default_machine_print_info(data["machine_name"], data["machine_type"])    
        return self.write({"result" : 0, "msg" : machine_config_messages[0],"data": alter_machine_info})

@app.route(r"/settings/machines/edit")
class MachineConfig(tornado.web.RequestHandler):
    def post(self):
        json_strings = self.request.body
        data = json.loads(json_strings)
        set_user_info({ "box_name": data["add_machine_data"]["box_name"] })
        del data["add_machine_data"]["box_name"]
        if data["machine_type_changed"] == "1":
            write_print_info(data["add_machine_data"]["machine_name"], data["add_machine_data"]["machine_type"])
        web_config = WebConfig.settings()
        #保存打印机信息和切片参数 
        write_result_update=update_machine_config(data["machine_type_name"],data)
        if write_result_update == 0:
            return self.write({"result" : 1, "msg" : machine_config_messages[1]})
        #如果是活动打印机的话还得更新CuraConfig.ini中的信息
        current_activity_print_machine = get_current_activity_print_machine()
        if current_activity_print_machine:
            if data["machine_type_name"]:
                if current_activity_print_machine==data["machine_type_name"]:
                    #如果是激活的打印机则更新CuraConfig
                    update_setting_gcode(current_activity_print_machine)
        
        #更新preferences.ini中的machine_n节点信息
        write_results=update_preferences_file_info(data["add_machine_data"])
        if write_results==0:
            return self.write({"result" : 1, "msg" : machine_config_messages[1]})

#          
#         if "api" in data.keys():
#             if "enabled" in data["api"].keys(): web_config.set(["api", "enabled"], data["api"]["enabled"])
#             if "key" in data["api"].keys(): web_config.set(["api", "key"], data["api"]["key"], True)
#             
#         if "appearance" in data.keys():
#             if "name" in data["appearance"].keys(): web_config.set(["appearance", "name"], data["appearance"]["name"])
#             if "color" in data["appearance"].keys(): web_config.set(["appearance", "color"], data["appearance"]["color"])
#             
#         if "printer" in data.keys():
#             if "movementSpeedX" in data["printer"].keys(): web_config.setInt(["printerParameters", "movementSpeed", "x"], data["printer"]["movementSpeedX"])
#             if "movementSpeedY" in data["printer"].keys(): web_config.setInt(["printerParameters", "movementSpeed", "y"], data["printer"]["movementSpeedY"])
#             if "movementSpeedZ" in data["printer"].keys(): web_config.setInt(["printerParameters", "movementSpeed", "z"], data["printer"]["movementSpeedZ"])
#             if "movementSpeedE" in data["printer"].keys(): web_config.setInt(["printerParameters", "movementSpeed", "e"], data["printer"]["movementSpeedE"])
#             if "invertAxes" in data["printer"].keys(): web_config.set(["printerParameters", "invertAxes"], data["printer"]["invertAxes"])
#         
#         if "webcam" in data.keys():
#             if "streamUrl" in data["webcam"].keys(): web_config.set(["webcam", "stream"], data["webcam"]["streamUrl"])
#             if "snapshotUrl" in data["webcam"].keys(): web_config.set(["webcam", "snapshot"], data["webcam"]["snapshotUrl"])
#             if "ffmpegPath" in data["webcam"].keys(): web_config.set(["webcam", "ffmpeg"], data["webcam"]["ffmpegPath"])
#             if "bitrate" in data["webcam"].keys(): web_config.set(["webcam", "bitrate"], data["webcam"]["bitrate"])
#             if "watermark" in data["webcam"].keys(): web_config.setBoolean(["webcam", "watermark"], data["webcam"]["watermark"])
#             if "flipH" in data["webcam"].keys(): web_config.setBoolean(["webcam", "flipH"], data["webcam"]["flipH"])
#             if "flipV" in data["webcam"].keys(): web_config.setBoolean(["webcam", "flipV"], data["webcam"]["flipV"])
#         
#         if "feature" in data.keys():
#             if "gcodeViewer" in data["feature"].keys(): web_config.setBoolean(["feature", "gCodeVisualizer"], data["feature"]["gcodeViewer"])
#             if "temperatureGraph" in data["feature"].keys(): web_config.setBoolean(["feature", "temperatureGraph"], data["feature"]["temperatureGraph"])
#             if "waitForStart" in data["feature"].keys(): web_config.setBoolean(["feature", "waitForStartOnConnect"], data["feature"]["waitForStart"])
#             if "alwaysSendChecksum" in data["feature"].keys(): web_config.setBoolean(["feature", "alwaysSendChecksum"], data["feature"]["alwaysSendChecksum"])
#             if "sdSupport" in data["feature"].keys(): web_config.setBoolean(["feature", "sdSupport"], data["feature"]["sdSupport"])
#             if "sdAlwaysAvailable" in data["feature"].keys(): web_config.setBoolean(["feature", "sdAlwaysAvailable"], data["feature"]["sdAlwaysAvailable"])
#             if "swallowOkAfterResend" in data["feature"].keys(): web_config.setBoolean(["feature", "swallowOkAfterResend"], data["feature"]["swallowOkAfterResend"])
        
        if "serial" in data.keys():
#             if "autoconnect" in data["serial"].keys(): web_config.setBoolean(["serial", "autoconnect"], data["serial"]["autoconnect"])
            if "port" in data["serial"].keys(): web_config.set(["serial", "port"], data["serial"]["port"])
            if "baudrate" in data["serial"].keys(): 
                if data["serial"]["baudrate"] == "AUTO":
                    web_config.set(["serial", "baudrate"], "AUTO")
                else:
                    web_config.setInt(["serial", "baudrate"], data["serial"]["baudrate"])
            else:
                web_config.set(["serial", "baudrate"], "AUTO")
                
#             if "timeoutConnection" in data["serial"].keys(): web_config.setFloat(["serial", "timeout", "connection"], data["serial"]["timeoutConnection"])
#             if "timeoutDetection" in data["serial"].keys(): web_config.setFloat(["serial", "timeout", "detection"], data["serial"]["timeoutDetection"])
#             if "timeoutCommunication" in data["serial"].keys(): web_config.setFloat(["serial", "timeout", "communication"], data["serial"]["timeoutCommunication"])
# 
#             oldLog = web_config.getBoolean(["serial", "log"])
#             if "log" in data["serial"].keys(): web_config.setBoolean(["serial", "log"], data["serial"]["log"])
#             if oldLog and not web_config.getBoolean(["serial", "log"]):
#                 # disable debug logging to serial.log
#                 logging.getLogger("SERIAL").debug("Disabling serial logging")
#                 logging.getLogger("SERIAL").setLevel(logging.CRITICAL)
#             elif not oldLog and web_config.getBoolean(["serial", "log"]):
#                 # enable debug logging to serial.log
#                 logging.getLogger("SERIAL").setLevel(logging.DEBUG)
#                 logging.getLogger("SERIAL").debug("Enabling serial logging")
        
#         if "folder" in data.keys():
#             if "uploads" in data["folder"].keys(): web_config.setBaseFolder("uploads", data["folder"]["uploads"])
#             if "timelapse" in data["folder"].keys(): web_config.setBaseFolder("timelapse", data["folder"]["timelapse"])
#             if "timelapseTmp" in data["folder"].keys(): web_config.setBaseFolder("timelapse_tmp", data["folder"]["timelapseTmp"])
#             if "logs" in data["folder"].keys(): web_config.setBaseFolder("logs", data["folder"]["logs"])
# 
#         if "temperature" in data.keys():
#             if "profiles" in data["temperature"].keys(): web_config.set(["temperature", "profiles"], data["temperature"]["profiles"])
# 
#         if "terminalFilters" in data.keys():
#             web_config.set(["terminalFilters"], data["terminalFilters"])
        
#         cura = data.get("cura", None)
#         if cura:
#             path = cura.get("path")
#             if path:
#                 web_config.set(["cura", "path"], path)
# 
#             config = cura.get("config")
#             if config:
#                 web_config.set(["cura", "config"], config)
# 
#             # Enabled is a boolean so we cannot check that we have a result
#             enabled = cura.get("enabled")
#             web_config.setBoolean(["cura", "enabled"], enabled)
            
        web_config.save()
        restart_web_service()
        return self.write({"result" : 0, "msg" : machine_config_messages[0]})
        

#~~ startup code
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
                  
    tornado.options.parse_command_line()
    logger.info("Box management server start.")
    app = app.instance()
    server = tornado.httpserver.HTTPServer(app)
    server.listen(options.port, options.host)
    tornado.ioloop.IOLoop.instance().start() # start the tornado ioloop to
