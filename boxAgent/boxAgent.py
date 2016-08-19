#!/usr/bin/env python
import sys
# sys.path.append("/home/pi/oprint/lib/python2.7/site-packages/tornado-4.0.1-py2.7-linux-armv7l.egg/")
# sys.path.append("/home/pi/oprint/lib/python2.7/site-packages/backports.ssl_match_hostname-3.4.0.2-py2.7.egg/")

import tornado
import tornado.ioloop
import tornado.options
from tornado.httpclient import AsyncHTTPClient
from tornado.httpclient import HTTPClient, HTTPError
from tornado.httpclient import HTTPRequest
from tornado.escape import json_decode
from tornado.escape import json_encode
from tornado import gen

import ConfigParser
import os
import time
import hashlib
import logging
import datetime
import uuid
import json
import urllib
import urllib2

from common import createFormData
from common import loopTask


TEST=False
BASE_PATH="/home/pi/oprint/lib/python2.7/site-packages/boxAgent-1.0.0-py2.7.egg/"
        
class ClientAgent():
    def __init__(self):

        CLIENT_AGENT_CONFIG_FILE = BASE_PATH + "client.conf"
        DEFAULT_CONFIG_DICT = {
            "protocol"             : "http",
            "config_ver"           : "v1.0",
            "local_host"           : "127.0.0.1",
            "local_port"           : "5000",
            "update_port"          : "8092",
            "server_host"          : "211.103.196.188",
            "server_port"          : 8888,
            "cloud_host"           : "211.103.196.188",
            "cloud_port"           : 8082,
            "heartbeat_interval"   : 10,
            "token"                : "w4hewb"
        }
        self.http_client = AsyncHTTPClient()
        self.sessionID = None
        self.boxID = None

        config = ConfigParser.ConfigParser(DEFAULT_CONFIG_DICT)
        config.readfp(open(CLIENT_AGENT_CONFIG_FILE),"rb")
        self.protocol = config.get("global", "protocol").strip('"') + "://"
        self.config_ver = config.get("global", "config_ver")
        self.localHost = config.get("global", "local_host")
        self.localPort = config.get("global", "local_port")
        self.localHostPort = self.localHost
        if self.localPort:
            self.localHostPort = self.localHost + ":" + self.localPort
        self.updatePort = config.get("global", "update_port")
        self.updateHostPort = self.localHost
        if self.updatePort:
            self.updateHostPort = self.localHost + ":" + self.updatePort
        self.serverHost = config.get("global", "server_host")
        self.serverPort = config.get("global", "server_port")
        self.serverHostPort = self.serverHost
        if self.serverPort:
            self.serverHostPort = self.serverHost + ":" + self.serverPort
        self.cloudHost = config.get("global", "cloud_host")
        self.cloudPort = config.get("global", "cloud_port")
        self.cloudHostPort = self.cloudHost
        if self.cloudPort:
            self.cloudHostPort = self.cloudHost + ":" + self.cloudPort
        self.heartbeatInterval = config.getint("global", "heartbeat_interval")
        self.token = config.get("global", "token").strip('"')
        self.forceUpdate = ""
        if config.has_option("global", "force_update"):
            self.forceUpdate = config.get("global", "force_update")
        self.latest_ver = ""
        if config.has_option("update", "latest_ver"):
            self.latest_ver = config.get("update", "latest_ver")
        self.update_pkg_url = ""
        if config.has_option("update", "pkg_url"):
            self.update_pkg_url = config.get("update", "pkg_url")
        self.update_pkg_md5 = ""
        if config.has_option("update", "pkg_md5"):
            self.update_pkg_md5 = config.get("update", "pkg_md5")
        self.update_pkg_desc = "No new updates."
        if config.has_option("update", "pkg_desc"):
            self.update_pkg_desc = config.get("update", "pkg_desc")

logger = logging.getLogger("__name__")
client = ClientAgent()


@loopTask(delta=client.heartbeatInterval)
@gen.coroutine
def heartbeat():
    logging.debug("heartbeat: Start to heartbeat.")

    curBoxInfo = {}
    curBoxInfo = getCurrentBoxInfo() 
    if not curBoxInfo:
        logging.warn("heartbeat: Failed to get current box info.")
        return

    client.boxID = curBoxInfo["boxid"]
    
    curBoxInfo["sessionID"] = client.sessionID
    curBoxInfo["proto_ver"] = "v1.0"
    curBoxInfo["config_ver"] = client.config_ver
    if client.latest_ver == "":
        lastest_client = ClientAgent()
        client.latest_ver = lastest_client.latest_ver
    if client.latest_ver != "":
        update_info = getUpdateInfo()
        curBoxInfo['update'] = {}
        curBoxInfo['update']["latest_ver"] = client.latest_ver
        curBoxInfo['update']["upd_pkg_name"] = update_info["upd_pkg_name"]
        curBoxInfo['update']["stage"] = update_info["stage"]
        curBoxInfo['update']["progress"] = update_info["progress"]
        curBoxInfo['update']["ret"] = update_info["ret"]
        if curBoxInfo["app_ver"] == client.latest_ver:
            client.latest_ver = ""
        else:
            pass
    else:
        pass

    url = client.protocol + client.serverHostPort + "/heartbeat"
    jdata = json.dumps(curBoxInfo)
    urldata = urllib.urlencode({"jdata":jdata})
    req = urllib2.Request(url, urldata)
    logging.debug("heartbeat: Send heartbeat start...")
    try:
        response = urllib2.urlopen(req, timeout=5)
    except urllib2.URLError, e:
        logging.warn("heartbeat: Failed to send heartbeat. error=%s", e.reason())
        return
    content = response.read()
    logging.debug("heartbeat: Succeed to send heartbeat. response.body=%r", content)
    res = json.loads(content) 
    if res["ret_value"] == 0:
        logging.debug("heartbeat: Succeed to heartbeat. Message=%s", res["message"])
    elif res["ret_value"] == 1:
        #Need to login
        logging.warn("heartbeat: Failed to heartbeat. Reason: Need to login.")
        tornado.ioloop.IOLoop.instance().add_timeout(time.time()+1, login)
    else:
        logging.warn("heartbeat: Failed to heartbeat. Unexpect ret_value=%d", res["ret_value"])

def getCurrentBoxInfo():
    url = client.protocol + client.localHostPort + "/status"
    logging.debug("getCurrentBoxInfo: Start to get current box info. url=%s", url)
    cur_client = HTTPClient()
    response = cur_client.fetch(url, request_timeout=10)
    if response.error:
        logging.warn("getCurrentBoxInfo: Failed to get current box info. error=%s", response.error)
        return None

    logging.debug("getCurrentBoxInfo: Current box info. reponse.body=%r", response.body)
    res = json_decode(response.body)
    if res["code"] != 0:
        logging.warn("getCurrentBoxInfo: Failed to get current box info. ret_value=%d", res["ret_value"])
        return None

    logging.debug("getCurrentBoxInfo: getstate cmd ver. app_ver=%s", res["data"]["app_ver"])

    return res["data"]

def getUpdateInfo():
    url = client.protocol + client.updateHostPort + "/netupdate_ajax?type=meta"
    logging.debug("getUpdateInfo: Start to get update info. url=%s", url)
    cur_client = HTTPClient()
    response = cur_client.fetch(url, request_timeout=10)
    if response.error:
        logging.warn("getUpdateInfo: Failed to get update info. error=%s", response.error)
        return None
    
    logging.debug("getUpdateInfo: Current update info. reponse.body=%r", response.body)
    res = json_decode(response.body)
    return res

def compareVersion(current, latest):
    cur_ver = current.split(".");
    lat_ver = latest.split(".");
    
    if len(cur_ver) != len(lat_ver): 
        return False;
    
    i = 0
    while i < len(cur_ver):
        if latest[i] > current[i]:
            return True
        elif latest[i] == current[i]:
            i += 1
            continue
        else:
            return False;
    
    return False;

@gen.coroutine
def login():
    logging.debug("login: Start to login.")
    client.sessionID = None
    loginInfo = {}
    loginInfo["token1"] = hashlib.md5(client.token).hexdigest()
    loginInfo["token2"] = hashlib.md5(client.boxID).hexdigest()
    loginInfo["boxid"] = client.boxID
    headers, body = createFormData(loginInfo)
    url = client.protocol + client.serverHostPort + "/login"
    login_request = HTTPRequest(url=url, method="POST", headers=headers, body=body)
    
    logging.debug("login: Login info = %s", str(loginInfo))
    response = yield client.http_client.fetch(login_request)
    if response.error:
        logging.error("login: Failed to login. error=%s", response.error)
        return
    else:
        logging.debug("login: Login result. response.body=%r", response.body)
        loginRes = json_decode(response.body) 
        if loginRes["ret_value"] == 0:
            client.sessionID = loginRes["sessionID"]
            logging.info("login: Succeed to login. sessionID=%s", loginRes["sessionID"])
        else:
            logging.error("login: Failed to login. ret_value=%d", loginRes["ret_value"])
        return

@gen.coroutine
def handleOperate(cmd):
    logging.info("handleOperate: Start to handle operate. cmd=%s", str(cmd))

    url = client.protocol + client.localHostPort + "/command"
    command = {"type": cmd['type'],
               "boxid": cmd['boxid'],
               "data": "",
               }
    del cmd['type']
    command['data'] = json.dumps(cmd)
    headers, body = createFormData(command)
    operate_request = HTTPRequest(url=url, method="POST", headers=headers, body=body)
    response = yield client.http_client.fetch(operate_request, request_timeout=60)
    if response.error:
        logging.error("handleOperate: Failed to send operate. error=%s", response.error)
    else:
        logging.info("handleOperate: Operate result. response.body=%r", response.body)
        res = json_decode(response.body)
        if res["ret_value"] != 0:
            #need login
            logging.warn("handleOperate: Failed to execute [%s] operation. ret_val=", res["ret_value"])
    
    logging.info("handleOperate: End to handle operate.")
    
@gen.coroutine
def handleTest(cmd):
    logging.info("handleTest: Start to handle test. cmd=%s", str(cmd))
    url = client.protocol + client.localHostPort + "/test"
    test_comand = { 'type': cmd['type'],
                    'data': "",
                   }
    del cmd['type']
    test_comand['data'] = json.dumps(cmd)
    headers, body = createFormData(test_comand)
    operate_request = HTTPRequest(url=url, method="POST", headers=headers, body=body)
    response = yield client.http_client.fetch(operate_request, request_timeout=60)
    if response.error:
        logging.error("handleTest: Failed to send test. error=%s", response.error)
    else:
        logging.info("handleTest: Test result. response.body=%r", response.body)
        res = json_decode(response.body)
        if res["ret_value"] != 0:
            #need login
            logging.warn("handleTest: Failed to execute [%s] test. ret_val=", res["ret_value"])
    
    logging.info("handleTest: End to handle test.")
    
@gen.coroutine
def handleLogs(cmd):
    logging.info("handleLogs: Start to upload logs. cmd=%s", str(cmd))    
    file_name = client.boxID + ".tgz"
    logs = os.path.join(os.path.abspath(os.path.dirname(__file__)), file_name)
    collect_logs_cmd = os.path.join(os.path.abspath(os.path.dirname(__file__)), "collect_log.sh")
    os.system("sudo /bin/rm -f " + logs )
    os.system("sudo /bin/bash " + collect_logs_cmd + " " + logs)
    with open(logs, 'rb') as logs_file:
        url = client.protocol + client.cloudHostPort + "/api/cloud/logs"
        operateInfo = {}
        operateInfo["token"] = cmd["token"]
        operateInfo["boxid"] = client.boxID
        fileInfo = {}
        fileInfo["filename"] = file_name
        fileInfo["filetype"] = "application/octet-stream"
        fileInfo["filecontent"] = logs_file.read()
        headers, body = createFormData(operateInfo, fileInfo)
        operate_request = HTTPRequest(url=url, method="POST", headers=headers, body=body)
        response = yield client.http_client.fetch(operate_request, request_timeout=60)
        if response.error:
            logging.error("handleLogs: Failed to upload logs. error=%s", response.error)
            return
        res = json_decode(response.body) 
        if res["ret_value"] != 0:
            logging.warn("handleLogs: Failed to upload logs. ret_val=", res["ret_value"])
            return
        logging.info("handleLogs: End to upload logs.")

@gen.coroutine
def handleProfile(cmd):
    logging.info("handleProfile: Start to handle profile. cmd=%s", str(cmd))
    url = client.protocol + client.localHostPort + "/profile"
    profile_data = { 'printer_profile': cmd['profile'],
                     'token': cmd['token'],
                   }
    headers, body = createFormData(profile_data)
    operate_request = HTTPRequest(url=url, method="POST", headers=headers, body=body)
    response = yield client.http_client.fetch(operate_request, request_timeout=60)
    if response.error:
        logging.error("handleProfile: Failed to handle profile. error=%s", response.error)
    else:
        logging.info("handleProfile: handle profile result. response.body=%r", response.body)
        res = json_decode(response.body)
        if res["ret_value"] != 0:
            #need login
            logging.warn("handleProfile: Failed to handle profile. ret_val=%s", res["ret_value"])
    
    logging.info("handleProfile: End to handle profile.")
        
@gen.coroutine
def handleGetPic(cmd):
    logging.info("handleGetPic: Start to handle GetPic. cmd=%s", str(cmd))

    #Send tripping a picture
    url = client.protocol + client.localHostPort + "/snapshot?boxid=local&"
    url += "uuid=" + str(uuid.uuid4())
    response = yield client.http_client.fetch(url, request_timeout=60)
    if response.error:
        logging.error("handleGetPic: Failed to send GetPic. error=%s", response.error)
        return
    
    logging.info("handleGetPic: GetPic result. response.body=%r", response.body)
    res = json_decode(response.body) 
    if res["code"] != 0:
        logging.warn("handleGetPic: Failed to execute operation. ret_val=%d", res["code"])

    #download picture from localhost
    url = client.protocol + client.localHostPort + "/" + res['data']["pic_url"]
    logging.debug("handleGetPic: Start to get picture. url=%s", url)
    response = yield client.http_client.fetch(url, request_timeout=10)
    if response.error:
        logging.warn("handleGetPic: Failed to get picture. error=%s", response.error)
        return

    #upload picture to Server
    url = client.protocol + client.cloudHostPort + "/api/cloud/rtpic"
    #url = URL_HEADER + client.serverHost + ":" + client.serverPort + "/upload"
    operateInfo = {}
    operateInfo["token"] = cmd["token"]
    operateInfo["boxid"] = client.boxID
    fileInfo = {}
    fileInfo["filename"] = "picture.jpg"
    fileInfo["filetype"] = "image/jpg"
    fileInfo["filecontent"] = response.body
    headers, body = createFormData(operateInfo, fileInfo)
    operate_request = HTTPRequest(url=url, method="POST", headers=headers, body=body)
    logging.debug("handleGetPic: Start to upload picture. url=%s", url)
    response = yield client.http_client.fetch(operate_request, request_timeout=60)

    if response.error:
        logging.error("handleGetPic: Failed to upload Pic. error=%s", response.error)
        return
    res = json_decode(response.body) 
    if res["ret_value"] != 0:
        logging.warn("handleGetPic: Failed to upload pic. ret_val=", res["ret_value"])
        return
    logging.debug("handleGetPic: End to upload picture. url=%s", url)

def initUpdateInfo():
    url = client.protocol + client.updateHostPort + "/pre_update"
    logging.debug("initUpdateInfo: Start to init update info. url=%s", url)
    cur_client = HTTPClient()
    response = cur_client.fetch(url, request_timeout=10)
    if response.error:
        logging.warn("initUpdateInfo: Failed to init update info. error=%s", response.error)
        return None

    logging.debug("initUpdateInfo: reponse.body=%r", response.body)
    res = json_decode(response.body)
    return res

@gen.coroutine
def handlePush(cmd):
    logging.info("handlePush: Start to handle push file. cmd=%s", str(cmd))

    #download push file
    url = cmd["file_url"]
    logging.debug("handlePush: Start to get push file. url=%s", url)
    response = yield client.http_client.fetch(url, request_timeout=6)
    logging.debug("handlePush: Finished to get push file.")
    if response.error:
        logging.warn("handlePush: Failed to get push file. error=%s", response.error)
        return
    
    DEFAULT_LOCATION = "/tmp"
    DEFAULT_ATTR = "666"
    DEFAULT_NAME = "temp.txt"
    location = cmd.get("file_location", DEFAULT_LOCATION)
    if location[0] != "/":
         location = os.path.split(os.path.realpath(__file__))[0] + '/' + location;
    attr = cmd.get("file_attr", DEFAULT_ATTR)
    name = cmd.get("file_name", DEFAULT_NAME)
    path = location + "/" + name
    if os.path.exists(path):
        os.rename(path, path+".bk")
    fd = open(path, "w")
    try:
        fd.write(response.body)
        logging.info("handlePush: Succeed to save push file. path=%s", path)
        os.system("sudo chmod " + attr + " " + path)
        logging.info("handlePush: Succeed to change attr. attr=%s", attr)
    except:
        logging.warn("handlePush: Failed to save push file. path=%s", path)
        os.remove(path) 
        os.rename(path+".bk", path)
    finally:
        fd.close()

    if name == "client.conf":
        initUpdateInfo()
    

@gen.coroutine
def handleUpdate(cmd):
    logging.info("handleUpdate: Start to handle update box. cmd=%s", str(cmd))

    update_version = cmd["version"]
    send_data = {
                 'version'   : update_version,
                }
    headers, body = createFormData(send_data)
    url = client.protocol + client.updateHostPort + "/netupdate_ajax"
    update_request = HTTPRequest(url=url, method="POST", headers=headers, body=body)
    
    logging.debug("handleUpdate: Send to update box. version=%s", update_version)
    response = yield client.http_client.fetch(update_request)
    if response.error:
        logging.error("handleUpdate: Failed to send to update. error=%s", response.error)
        return
    else:
        logging.debug("handleUpdate: result. response.body=%r", response.body)
        updateRes = json_decode(response.body) 
        if updateRes == 0:
            logging.info("handleUpdate: Succeed to send.")
        else:
            logging.error("handleUpdate: Failed to send. ret_value=%d", updateRes)
        return


@gen.coroutine
def handleSendExtendInfo(cmd):
    logging.info("handleSendExtendInfo: Start to handle send extend info. cmd=%s", str(cmd))

    url = client.protocol + client.localHostPort + "/stlfiles"
    type = cmd["type"]
    
    if type == '1':
        url = client.protocol + client.localHostPort + "/stlfiles"
    elif type == '2':
        url = client.protocol + client.localHostPort + "/slicerinfo"
    
    cur_client = HTTPClient()
    logging.debug("handleSendExtendInfo: Start to get stl extend info. url=%s, type=%s", url, type)
    response = cur_client.fetch(url, request_timeout=10)
    if response.error:
        logging.error("handleSendExtendInfo: Failed to get stl files. error=%s", response.error)
        return

    logging.info("handleSendExtendInfo: get stl files result. response.body=%r", response.body)
    res = json_decode(response.body) 
    if res["code"] != 0:
        logging.warn("handleSendExtendInfo: Failed to get stl files. ret_val=%d, msg=%s", res["code"], res["msg"])
        return

    extendInfo = {}
    extendInfo["boxid"] = client.boxID
    extendInfo["sessionID"] = client.sessionID
    extendInfo["type"] = type
    extendInfo["data"] = json_encode(res["data"])

    headers, body = createFormData(extendInfo)
    url = client.protocol + client.serverHostPort + "/sendextendinfo"
    heartbeat_request = HTTPRequest(url=url, method="POST", headers=headers, body=body)
    response = yield client.http_client.fetch(heartbeat_request)
    if response.error:
        logging.warn("handleSendExtendInfo: Failed to send extend info. error=%s", response.error)
        return
    else:
        logging.debug("handleSendExtendInfo: Succeed to send extend info. response.body=%r", response.body)
        res = json_decode(response.body) 
        if res["ret_value"] == 0:
            logging.debug("handleSendExtendInfo: Succeed to send extend info.")
        else:
            logging.warn("handleSendExtendInfo: Failed to send extend info. ret_value=%d", res["ret_value"])

@gen.coroutine
def handleFile(cmd):
    logging.info("handleFile: Start to handle operate. cmd=%s", str(cmd))
    url = ""
    if cmd["type"] == "1":
        url = client.protocol + client.localHostPort + "/delete"
    else:
        url = client.protocol + client.localHostPort + "/rename"
    del cmd["type"]
    
    headers, body = createFormData(cmd)
    operate_request = HTTPRequest(url=url, method="POST", headers=headers, body=body)
    response = yield client.http_client.fetch(operate_request, request_timeout=60)
    if response.error:
        logging.error("handleFile: Failed to send operate. error=%s", response.error)
    else:
        logging.info("handleFile: Operate result. response.body=%r", response.body)
        res = json_decode(response.body) 
        if res["ret_value"] != 0:
            #need login
            logging.warn("handleFile: Failed to execute [%s] operation. ret_val=", res["ret_value"])


@gen.coroutine
def handDownloadModelFile(cmd):
    logging.info("handDownloadModelFile: Start to handle Download Model File. cmd=%s", str(cmd))

    filePath = "/home/pi/.octoprint/uploads/" + cmd["filename"]
    if not os.path.exists(filePath):
        logging.warn("handDownloadModelFile: Model file is not exist. file=%s", filePath)
        return

    url=client.protocol + client.cloudHostPort+ "/api/box/file"
    operateInfo = {}
    operateInfo["token"] = cmd["token"]
    fileInfo = {}
    fileInfo["filename"] = str(cmd["filename"])
    fileInfo["filetype"] = "application/octet-stream"
    fd = open(filePath, "rb")
    fileInfo["filecontent"] = fd.read()
    fd.close()
    headers, body = createFormData(operateInfo, fileInfo)
    upload_request = HTTPRequest(url=url, method="POST", headers=headers, body=body)
    logging.debug("handDownloadModelFile: Start to upload model file. url=%s, file=%s", url, filePath)
    response = yield client.http_client.fetch(upload_request, request_timeout=60)

    if response.error:
        logging.error("handDownloadModelFile: Failed to upload model file. error=%s", response.error)
        return
    res = json_decode(response.body) 
    if res["ret_value"] != 0:
        logging.warn("handDownloadModelFile: Failed to upload model file. ret_val=", res["ret_value"])
        return
    logging.debug("handDownloadModelFile: End to upload model file. url=%s", url)


OPERATE_TYPE_OPERATE = 1
OPERATE_TYPE_PUSH = 2
OPERATE_TYPE_GETPIC = 3
OPERATE_TYPE_SENDEXTENDINFO = 4
OPERATE_TYPE_FILE = 5
OPERATE_TYPE_DOWNLOADMODELFILE = 6
OPERATE_TYPE_UPDATE = 7
OPERATE_TYPE_TEST = 8
OPERATE_TYPE_GETLOGS = 9
OPERATE_TYPE_PROFILE = 10

OPERATE_HANDLER_DICT = {
    OPERATE_TYPE_OPERATE               : handleOperate,
    OPERATE_TYPE_PUSH                  : handlePush,
    OPERATE_TYPE_GETPIC                : handleGetPic,
    OPERATE_TYPE_SENDEXTENDINFO        : handleSendExtendInfo,
    OPERATE_TYPE_FILE                  : handleFile,
    OPERATE_TYPE_DOWNLOADMODELFILE     : handDownloadModelFile,
    OPERATE_TYPE_UPDATE                : handleUpdate,
    OPERATE_TYPE_TEST                  : handleTest,
    OPERATE_TYPE_GETLOGS               : handleLogs,
    OPERATE_TYPE_PROFILE               : handleProfile,
}

@gen.coroutine
def keepAlive():
    logging.debug("keepAlive: Start to keep alive.")

    keepAliveInfo = {}
    keepAliveInfo["boxid"] = client.boxID
    keepAliveInfo["sessionID"] = client.sessionID
    headers, body = createFormData(keepAliveInfo)
    url = client.protocol + client.serverHostPort + "/keepalive"
    keepalive_request = HTTPRequest(url=url, method="POST", headers=headers, body=body, request_timeout=120)

    logging.debug("keepAlive: Send keep alive.")
    delta = 1 #next keep alive delta
    try:
        response = yield client.http_client.fetch(keepalive_request)
        if response.error:
            logging.error("keepAlive: Failed to keep alive. error=%s", response.error)
            delta = 1
        else:
            logging.debug("keepAlive: Keep alive result. response.body=%r", response.body)
            res = json_decode(response.body) 
            if res["ret_value"] == 1:
                #need login
                logging.warn("keepAlive: Failed to Keep alive. Reason: need login")
                delta = 1
            elif res["ret_value"] == 0:
                logging.debug("keepAlive: Handle operation. operateType=%d", res["operateType"])
                operateType = res["operateType"]
                del res["ret_value"]
                del res["operateType"]
                if operateType in OPERATE_HANDLER_DICT.keys():
                    OPERATE_HANDLER_DICT[operateType](res)
                else:
                    logging.warn("keepAlive: Unexpect operateType=%d", operateType)
                delta = 1
            else:
                logging.error("keepAlive: Failed to keep alive. ret_value=%d", res["ret_value"])
                delta = 1
    except HTTPError as e:
        # HTTPError is raised for non-200 responses; the response
        # can be found in e.response.
        if e.response is not None:
            logging.error("Failed to keep alive(%s)", native_str(e.response.body))
        else:
            logging.error("Failed to keep alive(%s)", str(e))
    except Exception as e:
        # Other errors are possible, such as IOError.
        logging.error("Failed to keep alive(%s)", str(e))
    finally:
        tornado.ioloop.IOLoop.instance().add_timeout(time.time()+delta, keepAlive)

    return


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

    tornado.options.parse_config_file(BASE_PATH + "clientAgent.conf")
    logger.info("Box client agent start. localHostPort=%s, serverHostPort=%s, serverHostPort=%s, cloudPort=%s, heartbeatInterval=%d, token=%s",
         client.localHostPort, client.updateHostPort, client.serverHostPort, client.cloudHostPort, client.heartbeatInterval, client.token)

    heartbeat()
    keepAlive()
    tornado.ioloop.IOLoop.instance().start() # start the tornado ioloop to
