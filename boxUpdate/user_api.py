# coding=utf-8
import socket
import ConfigParser
import hashlib
import fcntl, struct, uuid
import urllib, httplib
import json
import os

APIHOST="yun.mohou.com"
user_config = '/home/pi/Cura/config/userInfo.ini'
config = ConfigParser.ConfigParser()

def md5(str):
    """
    md5加密
    """
    m = hashlib.md5()
    m.update(str)

    return m.hexdigest()

def get_mac_address():
    """
    获取盒子物理地址
    """
    ifname = "eth0"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl(s.fileno(), 0x8927,  struct.pack('256s', ifname[:15]))
    node = int(''.join(['%02x' % ord(char) for char in info[18:24]]), 16)
    mac = uuid.UUID(int = node).hex[-12:]
    if mac:
        return md5(mac)

    return mac

def get_user_info():
    config.read(user_config)
    return dict(config.items("userInfo"))
    
def set_user_info(user_info):
    config.read(user_config)
    user_dict = dict(config.items("userInfo")) 
    for key,value in user_info.items():
        config.set("userInfo", key, value)
    config.write(open(user_config, "w"))

def bind_box_api(username,password,device_id,device_name,device_type = "box"):
    """绑定box
    @username:用户名
    @password:密码
    @device_id:设备编码
    @device_type:设备类型(box)
    """
    params=urllib.urlencode({
                            "name":username,
                            "password":password,
                            "device_type":device_type,
                            "device_id":device_id,
                            "device_name":device_name
                            })
    headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Connection": "Keep-Alive"}
    conn = httplib.HTTPConnection(APIHOST)
    conn.request(method="POST", url="/api/auth/bind", body=params, headers=headers)
    response = conn.getresponse()
    response_json = response.read()
    conn.close()
    return json.loads(response_json)

def unbind_box_api(token, device_id, device_type = "box"):
    """解除绑定
    @device_type:设备类型(默认为box)
    @token:凭据
    """
    params=urllib.urlencode({
                            "device_type":device_type,
                            "device_id":device_id,
                            "token":token
                            })
    headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Connection": "Keep-Alive"}
    conn = httplib.HTTPConnection(APIHOST)
    conn.request(method="POST", url="/api/auth/unbind", body=params, headers=headers)
    response = conn.getresponse()
    response_json = response.read()
    conn.close()
    return json.loads(response_json)

def init_box_config_info():
    """
    初始化盒子信息
    """
    #device_id = get_mac_address()
    config.read(user_config)
    if not config.get("userInfo", "device_id"):
        #config.set("userInfo", "box_name", "魔猴盒子" + device_id[5:10])        
        #config.set("userInfo", "device_id", device_id)
        config.write(open(user_config, "w"))
        #os.system("/usr/bin/sudo sed -i 's@ssid=mowifi@ssid=mowifi_"+device_id[5:10]+"@' /etc/hostapd/hostapd.conf")
    return 1

if  __name__ == "__main__":
    print __name__