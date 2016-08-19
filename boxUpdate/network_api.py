# coding=utf-8
import socket
import os
import re
from network_interfaces import InterfacesFile
from exec_cmd import execute_cmd
from tornado.httpclient import HTTPClient
import urllib
import httplib
from tornado.escape import json_decode
import json

APPNAME = "OctoPrint"

#Definition of File name 
CONFIG_FILE_NETWORK_INTERFACE   = "/etc/network/interfaces"
CONFIG_FILE_NETWORK_DNS         = "/etc/resolv.conf"
CONFIG_FILE_NETWORK_WLAN0       = "/etc/wpa_supplicant/wpa_supplicant.conf"



#System Command
COMMAND_SUDO                        = "/usr/bin/sudo"
COMMAND_NETWORK_IFACE_UP            = "/sbin/ifup"
COMMAND_NETWORK_IFACE_DOWN          = "/sbin/ifdown"
COMMAND_NETWORK_DHCLIENT            = COMMAND_SUDO + " /sbin/dhclient "
COMMAND_NETWORK_FIND_WIFI           = "/sbin/iwlist "
COMMAND_NETWORK_WPA_CLI             = "/sbin/wpa_cli "
COMMAND_NETWORK_CHECK_CUR_WIFI      = COMMAND_NETWORK_WPA_CLI + "status"
COMMAND_NETWORK_GET_SSID            = "/sbin/iwgetid wlan0"
COMMAND_NOHUP                       = "/usr/bin/nohup "


#Error Message
PARAMETER_ERR               = "Parameter error."
PARAMETER_ERR_COUNT         = "Incorrect parameter count."
PARAMETER_ERR_LEN           = "Incorrect parameter length."
PARAMETER_ERR_FORMAT_WORD   = "Incorrect parameter format."
PARAMETER_ERR_NOT_ENOUGH    = "Parameter is insufficent."
PARAMETER_ERR_VALUE         = "Incorrect parameter value."

def get_serial_number():
    url = "http://127.0.0.1:5000/profile2"
    cur_client = HTTPClient()
    response = cur_client.fetch(url, request_timeout=10)
    if response.error:
        return None
    res = json_decode(response.body)
    if res["code"] != 0:
        return None
    return res["data"]['boxid']

def set_serial_number(serial_number):
    params=urllib.urlencode({
                              "printer_profile" : '{"boxid": "'+serial_number+'", "box_name": "我的打印机_'+ serial_number[20:24]+'"}'
                            })
    headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Connection": "Keep-Alive"}
    conn = httplib.HTTPConnection('127.0.0.1', port=5000)
    conn.request(method="POST", url="/profile2", body=params, headers=headers)
    response = conn.getresponse()
    response_json = response.read()
    conn.close()
    res = json.loads(response_json)
    if res["code"] == 0:
        os.system("/usr/bin/sudo /bin/sed -i 's@^ssid=.*@ssid=mohou_"+serial_number[20:24]+"@' /etc/hostapd/hostapd.conf > /dev/null 2>&1")
        os.system("/usr/bin/sudo /usr/sbin/service hostapd restart > /dev/null 2>&1")
    return res["code"]

def get_allwifi_info():
    """
    Get valid wifi network info.
    """
    curWifi = getSelectedWifi()
    
    lines = os.popen(COMMAND_NETWORK_FIND_WIFI + "wlan0" + " scanning").readlines()
    wifiInfoList = []
    cellhash = {}
    cell_info_pattern=re.compile("Cell (\\d+) - ")
    essid_pattern = re.compile('ESSID:"(.*)"')
    encryption_pattern = re.compile("Encryption key:(.*)")
    quality_pattern = re.compile(".*Signal level=(\\d+)/.*")
    quality_pattern2 = re.compile(".*Signal level=(-\\d+) dBm")
    
    cell_index = None
    for line in lines:
        line = line.strip()
        match = cell_info_pattern.match(line)
        if match:
            cell_index = match.group(1)
            cellhash[cell_index] = {}
            continue

        match = essid_pattern.match(line)
        if match and cell_index is not None:
            cellhash[cell_index]['ssid'] = match.group(1)
            continue

        match = encryption_pattern.match(line)
        if match and cell_index is not None:
            cellhash[cell_index]['lock'] = match.group(1)
            continue

        match = quality_pattern.match(line)
        if match and cell_index is not None:
            cellhash[cell_index]['signal'] = int(match.group(1))
            continue
        
        match = quality_pattern2.match(line)
        if match and cell_index is not None:
            cellhash[cell_index]['signal'] = min(max(2 * (int(match.group(1)) + 100), 0), 100)
            continue
        
    for k,v in cellhash.iteritems():
        if v['ssid'] != '':
            wifiInfo = []
            wifiInfo.append(v['ssid'])
            #cur_ssid = eval("'"+curWifi["ssid"].replace("'","\\'")+"'")
            if v['ssid'] == curWifi["ssid"]:
                wifiInfo.append(curWifi["wpa_state"])
            else:
                wifiInfo.append("")
            wifiInfo.append(v['lock'])
            wifiInfo.append(v['signal'])
            wifiInfoList.append(wifiInfo)
    wifiInfoList.sort(cmp=compareWifi, reverse=True)
    return wifiInfoList

def compareWifi(wifi1, wifi2):
    if wifi1[1] != "":
        return 1
    if wifi2[1] != "":
        return -1
    
    if wifi1[3] == wifi2[3]:
        return 0
    if wifi1[3] < wifi2[3]:
        return -1
    else:
        return 1
    
def getSSID():
    lines = os.popen(COMMAND_NETWORK_GET_SSID).readlines()
    essid_pattern = re.compile('^.*ESSID:"(.*)".*$')
    ssid = ""
    for line in lines:
        match = essid_pattern.match(line)
        if match:
            ssid = match.group(1)
            break
    return ssid

def getSelectedWifi():
    """
    Get current wifi network info.
    """
    lines = os.popen(COMMAND_NETWORK_CHECK_CUR_WIFI).readlines()
    
    net_state = [
        ["DISCONNECTED", "认证失败"],
        ["SCANNING", "正在搜索"],
        ["AUTHENTICATING", "正在认证"],
        ["ASSOCIATING", "正在连接"],
        ["ASSOCIATED", "连接完成"],
        ["COMPLETED", "已连接"]
    ]

    curwifi = {}
    curwifi["ssid"] = ""
    curwifi["wpa_state"] = net_state[0][1]
    
    for line in lines:
        if line.strip().find("ssid=") == 0:
            curwifi["ssid"] = getSSID()
        if line.strip().find("wpa_state=") == 0:
            for state in net_state:
                if state[0] == line.strip()[len("wpa_state="):]:
                    curwifi["wpa_state"] = state[1]
                    break

    return curwifi

def get_network_info(iface):
    """
    Get network info.
    """

    cfg_file = InterfacesFile(CONFIG_FILE_NETWORK_INTERFACE)
    iface = cfg_file.get_iface(iface)

    dhcp = None
    address = None
    netmask = None
    gateway = None

    if iface.method == 'dhcp':
        dhcp = 1
    else:
        dhcp = 0

    if iface.method == 'static':
        address = iface.address
        netmask = iface.netmask
        gateway = iface.gateway

    networkinfo = {}
    networkinfo["dhcp"] = dhcp
    
    networkinfo["ip"] = ""
    networkinfo["ip_sec1"] = ""
    networkinfo["ip_sec2"] = ""
    networkinfo["ip_sec3"] = ""
    networkinfo["ip_sec4"] = ""
    if address != None:
        networkinfo["ip"] = address
        networkinfo["ip_sec1"] = address.split(".")[0]
        networkinfo["ip_sec2"] = address.split(".")[1]
        networkinfo["ip_sec3"] = address.split(".")[2]
        networkinfo["ip_sec4"] = address.split(".")[3]
    
    networkinfo["mask"] = ""
    networkinfo["mask_sec1"] = ""
    networkinfo["mask_sec2"] = ""
    networkinfo["mask_sec3"] = ""
    networkinfo["mask_sec4"] = ""
    if netmask != None:
        networkinfo["mask"] = netmask
        networkinfo["mask_sec1"] = netmask.split(".")[0]
        networkinfo["mask_sec2"] = netmask.split(".")[1]
        networkinfo["mask_sec3"] = netmask.split(".")[2]
        networkinfo["mask_sec4"] = netmask.split(".")[3]    

    networkinfo["gateway"] = ""
    networkinfo["gateway_sec1"] = ""
    networkinfo["gateway_sec2"] = ""
    networkinfo["gateway_sec3"] = ""
    networkinfo["gateway_sec4"] = ""
    if gateway != None:
        networkinfo["gateway"] = gateway
        networkinfo["gateway_sec1"] = gateway.split(".")[0]
        networkinfo["gateway_sec2"] = gateway.split(".")[1]
        networkinfo["gateway_sec3"] = gateway.split(".")[2]
        networkinfo["gateway_sec4"] = gateway.split(".")[3]
    
    return networkinfo
    
def get_dns_info():
    """
    Get dns info.
    """
    file = open(CONFIG_FILE_NETWORK_DNS, "r")
    lines = []
    try:
        lines = file.readlines()
    finally:
        file.close()
    #Get DNS
    dns_info = {}
    dns_info["dns"] = ""
    dns_info["dns_sec1"] = ""
    dns_info["dns_sec2"] = ""
    dns_info["dns_sec3"] = ""
    dns_info["dns_sec4"] = ""
    for line in lines:
        if "nameserver" in line:
            dns_info["dns"] = line.split()[1].strip()
            dns_info["dns_sec1"] = line.split()[1].strip().split(".")[0]
            dns_info["dns_sec2"] = line.split()[1].strip().split(".")[1]
            dns_info["dns_sec3"] = line.split()[1].strip().split(".")[2]
            dns_info["dns_sec4"] = line.split()[1].strip().split(".")[3]
            break;

    return dns_info

def is_changed_network(iface_name, new_ip_info, new_dns_info):
    org_ip_info = get_network_info(iface_name)
    org_dns_info = get_dns_info()
    
    if org_ip_info["dhcp"] != int(new_ip_info["dhcp"]):
        return True
    if org_ip_info["dhcp"] == 1:
        return False
    if org_ip_info["ip"] != new_ip_info["ip"]:
        return True
    if org_ip_info["mask"] != new_ip_info["netmask"]:
        return True
    if org_ip_info["gateway"] != new_ip_info["gateway"]:
        return True
    if org_dns_info["dns"] != new_dns_info["dns"]:
        return True
    
    return False

def set_network(iface_name, iface_info, dns_info):
    """
    Set network info.
    """
    if is_changed_network(iface_name, iface_info, dns_info) == False:
        print "Network is not changed."
        return 0
    # 1. Update /etc/network/interfaces
    cfg_file = InterfacesFile(CONFIG_FILE_NETWORK_INTERFACE)
    iface = cfg_file.get_iface(iface_name)
    if iface_info["dhcp"] == "1":
        iface.method = "dhcp"
        delattr(iface, "address")
        delattr(iface, "netmask")
        delattr(iface, "gateway")
    else:
        iface.method = "static"
        if iface_info["ip"]:
            iface.address = iface_info["ip"]
        if iface_info["netmask"]:
            iface.netmask = iface_info["netmask"]
        if iface_info["gateway"]:
            iface.gateway =  iface_info["gateway"]
            
    cfg_file.save()
    # 2. Update /etc/resolv.conf
    if dns_info["dns"]:
        lines = "nameserver " + dns_info["dns"] + "\n"
        file = open(CONFIG_FILE_NETWORK_DNS, "w")
        try:
            file.writelines(lines)
        finally:
            file.close()
    
    #3. Iface down wlan0 and iface up wlan0
    execute_cmd("/bin/bash", ["-c", COMMAND_SUDO+ " " + COMMAND_NETWORK_IFACE_DOWN + " " + iface_name +";" + COMMAND_SUDO+ " " + COMMAND_NETWORK_IFACE_UP + " " + iface_name +";"])
    return 0

def set_wifi(wifissid, wifipwd):
    ret = os.system(COMMAND_NETWORK_WPA_CLI + "status")
    if ret != 0:
        ret = os.system(COMMAND_NETWORK_IFACE_UP + " wlan0")

#     ret = os.system(COMMAND_NETWORK_WPA_CLI + "remove_network 0")
#     ret = os.system(COMMAND_NETWORK_WPA_CLI + "add_network")
#     ret = os.system(COMMAND_NETWORK_WPA_CLI + "set_network 0 ssid \\\"" + wifissid + "\\\"")
#     if wifipwd:
#         if (len(wifipwd)<8) or (len(wifipwd)>64):
#             return 1 #password len error
#         ret = os.system(COMMAND_NETWORK_WPA_CLI + "set_network 0 psk \\\"" + wifipwd + "\\\"")
#     else:
#         ret = os.system(COMMAND_NETWORK_WPA_CLI + "set_network 0 key_mgmt NONE")
#     ret = os.system(COMMAND_NETWORK_WPA_CLI + "enable_network 0")
#     ret = os.system(COMMAND_NETWORK_WPA_CLI + "save_config")
#     ret = os.system(COMMAND_NETWORK_DHCLIENT + "-r wlan0")
#     ret = os.system(COMMAND_NETWORK_DHCLIENT + "wlan0")
    lines = "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\nupdate_config=1\n\n"
    if wifipwd:
        if (len(wifipwd)<8) or (len(wifipwd)>64):
            return 1 #password len error
        ssid_passwd = "network={\nssid=\"%s\"\npsk=\"%s\"\n}\n" % (wifissid, wifipwd)
    else:
        ssid_passwd = "network={\nssid=\"%s\"\nkey_mgmt=NONE\n}\n" % wifissid
    file = open(CONFIG_FILE_NETWORK_WLAN0, "w")
    try:
        file.writelines(lines + ssid_passwd)
    finally:
        file.close()
 
    ret = os.system(COMMAND_NETWORK_WPA_CLI + "-i wlan0 reconfigure 1>/dev/null 2>&1")
    ret = os.system(COMMAND_NETWORK_DHCLIENT + "-r wlan0 1>/dev/null 2>&1")
    ret = os.system(COMMAND_NETWORK_DHCLIENT + "wlan0 1>/dev/null 2>&1")
    if ret != 0:
        #LOG
        pass

    return 0

def machine_is_online():
    """
    判断是否联网
    """
    try:
        is_online = socket.gethostbyname("www.mohou.com")
    except:
        is_online = False

    return is_online


if  __name__ == "__main__":
    print __name__
