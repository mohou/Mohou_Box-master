# coding=utf-8
import sys
#sys.path.append("/home/pi/oprint/lib/python2.7/site-packages/tornado-3.0.2-py2.7.egg/")

from tornado.httpclient import AsyncHTTPClient
from tornado.httpclient import HTTPClient
from tornado.httpclient import HTTPRequest
from tornado.escape import json_decode
from tornado.escape import json_encode

import logging
import os
import ConfigParser
import urllib
import commands
import threading


#Definition of File name 

#System Command
COMMAND_SUDO                        = "/usr/bin/sudo "
UPDATE_METADATA_DIR = "/home/pi/.update/updatePkg/"
UPDATE_METADATA_FILE = UPDATE_METADATA_DIR + "updateMeta.conf"
UPDATE_EXECUTE_FILE = "update.sh"

UPDATE_STAGE_INIT = "init"
UPDATE_STAGE_FINISHED = "finished"

UPDATE_RET_NORMAL = 0
UPDATE_RET_ERR_MD5 = 1
UPDATE_RET_ERR_UNCOMPRESS = 2
UPDATE_RET_ERR_UPDATE = 3
UPDATE_RET_ERR_UNKNOWN = 10

class ClientAgent():
    def __init__(self):
        BASE_PATH="/home/pi/oprint/lib/python2.7/site-packages/boxAgent-1.0.0-py2.7.egg/"
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
#        self.http_client = AsyncHTTPClient()
        config = ConfigParser.ConfigParser(DEFAULT_CONFIG_DICT)
        config.readfp(open(CLIENT_AGENT_CONFIG_FILE),"rb")

        self.protocol = config.get("global", "protocol") + "://"
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
        self.token = config.get("global", "token").strip('\"')
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


def getCurrentBoxInfo():
    """
    Get current box info.
    """
    boxInfo = {}
    url = client.protocol + client.localHostPort + "/getstate"
    logging.debug("getCurrentBoxInfo: Start to get current box info. url=%s", url)
    cur_client = HTTPClient()
    response = cur_client.fetch(url, request_timeout=10)
    if response.error:
        logging.warn("getCurrentBoxInfo: Failed to get current box info. error=%s", response.error)
        return None

    logging.debug("getCurrentBoxInfo: Current box info. reponse.body=%r", response.body)
    res = json_decode(response.body)
    if res["ret_value"] != 0:
        logging.warn("getCurrentBoxInfo: Failed to get current box info. ret_value=%d", res["ret_value"])
        return None

    logging.debug("getCurrentBoxInfo: getstate cmd ver. cmd_ver=%s", res["cmd_ver"])

    boxInfo["id"] = res.get("id")
    boxInfo["name"] = res.get("name")
    boxInfo["app_ver"] = res.get("app_ver")
    boxInfo["isactive"] = res.get("isactive")
    boxInfo["user_name"] = res.get("user_name")
    boxInfo["disk_size"] = res.get("disk_size")
    boxInfo["free_disk_size"] = res.get("free_disk_size")
    boxInfo["mem_size"] = res.get("mem_size")
    boxInfo["free_mem_size"] = res.get("free_mem_size")
    boxInfo["cpu_usage"] = res.get("cpu_usage")
    boxInfo["loc_ip"] = res.get("loc_ip")
    boxInfo["printer_name"] = res.get("printer_name")
    boxInfo["printer_state"] = res.get("printer_state")
    boxInfo["printer_length"] = res.get("printer_length", 0)
    boxInfo["printer_width"] = res.get("printer_width", 0)
    boxInfo["printer_height"] = res.get("printer_height", 0)
    boxInfo["model_file"] = res.get("model_file",)
    boxInfo["model_type"] = res.get("model_type")
    boxInfo["print_time_all"] = res.get("print_time_all", 0)
    boxInfo["print_time_escape"] = res.get("print_time_escape", 0)
    boxInfo["print_time_remain"] = res.get("print_time_remain", 0)
    boxInfo["print_progress"] = res.get("print_progress", 0)

    return boxInfo


def getLatestVer():
    if client.latest_ver == "":
        client.latest_ver = getCurrentVer()
    return client.latest_ver

def getUpdatePkgUrl():
    return client.update_pkg_url

def getUpdatePkgDesc():
    return client.update_pkg_desc

def getCurrentVer():
    app_ver = None
    boxinfo = getCurrentBoxInfo()
    if boxinfo:
        app_ver = boxinfo["app_ver"]
    return app_ver

def clearUpdateInfoBegin():
    file = UPDATE_METADATA_FILE
    if os.path.exists(file):
        os.remove(file)

def initUpdateInfo():
    global client
    client = ClientAgent()
    
    #Initialize net update info
    fileDir = UPDATE_METADATA_DIR
    if os.path.isfile(fileDir):
        os.remove(fileDir)
    if not os.path.exists(fileDir):
        os.makedirs(fileDir)
    
    file = UPDATE_METADATA_FILE
    config = ConfigParser.ConfigParser()
    if not os.path.exists(file):
        config.add_section("meta")
        config.set("meta", "upd_pkg_name", "")
        config.set("meta", "stage", UPDATE_STAGE_INIT)
        config.set("meta", "progress", 0)
        config.set("meta", "ret", UPDATE_RET_NORMAL)
        config.write(open(file, 'w'))
        return
    
    config.readfp(open(file),"rb")
    if config.get("meta", "stage") == UPDATE_STAGE_FINISHED:
        config.set("meta", "upd_pkg_name", "")
        config.set("meta", "stage", "init")
        config.set("meta", "progress", 0)
        config.set("meta", "ret", UPDATE_RET_NORMAL)
        config.write(open(file, 'w'))
        return

def getUpdateMeta():
    file = UPDATE_METADATA_FILE
    if not os.path.exists(file):
        initUpdateInfo()
        
    config = ConfigParser.ConfigParser()
    config.readfp(open(file),"rb")
    
    metaInfo = {}
    metaInfo["upd_pkg_name"] = config.get("meta", "upd_pkg_name")
    metaInfo["stage"] = config.get("meta", "stage")
    metaInfo["progress"] = config.getint("meta", "progress")
    metaInfo["ret"] = config.getint("meta", "ret")
   
    return metaInfo
    
def setUpdateMeta(key, value):
    file = UPDATE_METADATA_FILE
    config = ConfigParser.ConfigParser()
    config.read(file)
    config.set("meta", key, value)
    config.write(open(file, 'w'))
    
def clearUpdateInfoEnd():
    config = ConfigParser.ConfigParser()
    config.read(CLIENT_AGENT_CONFIG_FILE)
    config.remove_section("update")
    config.write(open(CLIENT_AGENT_CONFIG_FILE, "w"))
      
def update_BG():
    pkg_url = getUpdatePkgUrl()
    fileName = 'upd_pkg_' + client.latest_ver + '.tgz'
    fileDir = UPDATE_METADATA_DIR
    filePath = fileDir + fileName
    setUpdateMeta("stage", "downloading")
    setUpdateMeta("progress", 0)
    setUpdateMeta("upd_pkg_name", fileName)

    def netReporthook(count, block_size, total_size):
        progress = (50 * count * block_size/ total_size)
        if progress > 50:
            progress = 50
        setUpdateMeta("progress", progress)

        #if client.update_flag == "download_update":
        #    exeUpdatePkg()
    try:  
        urllib.urlretrieve(pkg_url, filePath, netReporthook)
    except Exception,ex:
        logging.warn("update_BG: Failed to download update package. " + str(ex))
        setUpdateMeta("stage", UPDATE_STAGE_FINISHED)
        setUpdateMeta("ret", UPDATE_RET_ERR_UNKNOWN)
        return
    
    #check download file
    md5sum = commands.getoutput("md5sum " + filePath + " | awk '{print $1}'")
    if md5sum != client.update_pkg_md5:
        logging.warn("update_BG: Failed to download update package. md5sum is incorrect.")
        setUpdateMeta("stage", UPDATE_STAGE_FINISHED)
        setUpdateMeta("ret", UPDATE_RET_ERR_MD5)
        return
            
    #uncompress update Pkg        
    setUpdateMeta("stage", "uncompressing")
    uncompress_cmd = "tar -xvf " + filePath + " -C " + fileDir
    ret = commands.getstatusoutput(uncompress_cmd)
    if ret[0] != 0:
        logging.warn("update_BG: Failed to uncompress package. cmd=%s. ret=%d. output=%s", uncompress_cmd, ret[0], ret[1])
        setUpdateMeta("stage", UPDATE_STAGE_FINISHED)
        setUpdateMeta("ret", UPDATE_RET_ERR_UNCOMPRESS)
        return
        
    #execute update Pkg        
    setUpdateMeta("stage", "updating")
    tar_path = os.path.splitext(fileName)[0]
    update_cmd = fileDir + tar_path + "/" + UPDATE_EXECUTE_FILE
    print "begin" + update_cmd
    ret = commands.getstatusoutput(update_cmd)
    print "end" + update_cmd
    if ret[0] != 0:
        logging.warn("update_BG: Failed to execute update package. cmd=%s. ret=%d. output=%s", update_cmd, ret[0], ret[1])
        setUpdateMeta("stage", UPDATE_STAGE_FINISHED)
        setUpdateMeta("ret", 10+ret[0])
        return
    
    
    setUpdateMeta("stage", UPDATE_STAGE_FINISHED)
    setUpdateMeta("ret", UPDATE_RET_NORMAL)
    
    #delete updateinfo
    clearUpdateInfoEnd()
    
    return
    
    
def netUpdate():
    thread = threading.Thread(target=update_BG)
    thread.setDaemon(True)
    thread.start()
    return


if  __name__ == "__main__":
    print test