# coding=utf-8
import traceback
import os
import glob
import ConfigParser
import settings as WebConfig
from user_api import get_user_info


def restart_web_service():
    os.system("/usr/bin/sudo service octoprint restart")
    
def get_serial_list():
    baselist=[]
    baselist = baselist \
               + glob.glob("/dev/ttyUSB*") \
               + glob.glob("/dev/ttyACM*") \
               + glob.glob("/dev/tty.usb*") \
               + glob.glob("/dev/cu.*") \
               + glob.glob("/dev/rfcomm*")

    additionalPorts = WebConfig.settings().get(["serial", "additionalPorts"])
    for additional in additionalPorts:
        baselist += glob.glob(additional)

    if "AUTO" not in baselist:
        baselist.insert(0, "AUTO")
    prev = WebConfig.settings().get(["serial", "port"])
    if prev in baselist:
        baselist.remove(prev)
        baselist.insert(0, prev)
    if WebConfig.settings().getBoolean(["devel", "virtualPrinter", "enabled"]):
        baselist.append("VIRTUAL")
    return baselist

def get_baudrate_list():
    ret = [115200, 250000, 230400, 57600, 38400, 19200, 9600]
    prev = WebConfig.settings().get(["serial", "baudrate"])
    if prev == "AUTO":
        ret.insert(0, "AUTO")
    elif prev in ret:        
        ret.remove(prev)
        ret.insert(0, prev)
    else:
        pass

    return ret

def get_machine_type_list():
    type_list = read_default_config_file_name("/home/pi/Cura/config/default_type_config")
    return sorted(type_list)
    
def update_preferences_file_info(data):
    """
    更新preferences配置文件信息   更新时需要在 machine_config下的对应文件和preferences.ini中都要更新
    """
    machine_name = data["machine_name"]
    if machine_name:
        preferences_file = '/home/pi/.cura/dev/preferences.ini'
        config = ConfigParser.ConfigParser()
        config.read(preferences_file)
        sections_list = config.sections()
        # print sections_list , type(sections_list)
        #读取打印机名称列表
        machine_list = sections_list[1:]
        # print machine_list
        section_name = ''
        for machine in  machine_list:
            machine_n = config.get(machine, "machine_name")
            # print machine_n
            if machine_n == machine_name:
                section_name = machine
                break

        if section_name:
            for d in data:
                config.set(section_name, d, data[d])
        else:
            num = len(machine_list)
            add_section_name = "%s%s" % ("machine_", num)
            config.add_section(add_section_name)
            for d in data:
                config.set(add_section_name, d, data[d])

        config.write(open(preferences_file, "w"))

        return 1
    else:
        return 0

def read_cura_config_gcode_info(machine_type_name):
    """
    读取对应打印机配置里面的gcode
    """
#     profile_config_file = '%s%s%s' % ('/home/pi/Cura/config/profileConfig/', machine_type_name, '.ini')
    profile_config_file = '%s%s%s' % ('/home/pi/Cura/config/machine_config/', machine_type_name, '.ini')
    profile_config = ConfigParser.ConfigParser()
    profile_config.read(profile_config_file)
    if profile_config.has_section("alterations"):
        gcode_dict = profile_config.items("alterations")
        return gcode_dict
        
    
def read_cura_config_profile_item(machine_type_name):
    """读取对应打印机配置里的profile
    @machine_type_name:打印机名称
    """   
    profile_config_file = '%s%s%s' % ('/home/pi/Cura/config/machine_config/', machine_type_name, '.ini')
    profile_config = ConfigParser.ConfigParser()
    profile_config.read(profile_config_file)
    if profile_config.has_section("profile"):
        profile_dict = profile_config.items("profile")
        return profile_dict
    
def update_setting_gcode(machine_type_name):
    """
    更新CuraConfig.ini中的gcode和profile
    """
    # 读取对应打印机配置里面的gcode
    gcode_dict = dict(read_cura_config_gcode_info(machine_type_name))
    profile_dict=dict(read_cura_config_profile_item(machine_type_name))

    # 读取CuraConfig.ini
    cura_config_file = '/home/pi/Cura/config/CuraConfig.ini'
    cura_config = ConfigParser.ConfigParser()
    cura_config.read(cura_config_file)

    # 写入文件
    for k,v in gcode_dict.items():
        cura_config.set("alterations", k, v)
        
    for s,m in profile_dict.items():
        cura_config.set("profile", s, m)

    cura_config.write(open(cura_config_file, "w"))
    return 1

def get_current_activity_print_machine():
    """
    获取当前活动打印机
    """
    # 读取活动机配置信息的文件 preferences.ini
    preferences = '/home/pi/.cura/dev/preferences.ini'
    config = ConfigParser.ConfigParser()
    config.read(preferences)
    #active_machine = 0
    number = config.get("preference", "active_machine")
    if not number:
        machine_name = ''
        return machine_name
    
    machine_number = "%s_%s" % ("machine", number)
    machine_name = config.get(machine_number, "machine_name")
    return machine_name

def get_profileitem_bymaterials(material_name):
    """根据打印材料获取对应的profile节点
    @material_name 1:PLA,2:ABS
    """
    material_config="/home/pi/Cura/config/quickprint/materials/"
    material_dict={1:"1_pla.ini",2:"2_abs.ini",3:"3_pet.ini"}
    material_type=None
    result={}
    if material_name:
        material_type=material_dict.get(int(material_name))
        if material_type:
            config=ConfigParser.ConfigParser()
            file_path="%s%s" %(material_config,material_type)
            config.read(file_path)
            if config.has_section("profile"):
                result=dict(config.items("profile"))
    return result
                
def get_profileitem_byprinttype(print_type_num):
    """根据打印类型获取对应的信息 profile节点
    @print_type_num:打印类型 1.高质量打印， 2.正常效果打印， 3.快速低质量打印 , 4.Ulti print
    """
    fast_config="/home/pi/Cura/config/quickprint/profiles/"
    fast_dict={1:"3_high.ini",2:"2_normal.ini",3:"1_low.ini",4:"4_ulti.ini"}
    type_name=None
    result={}
    if print_type_num:
        type_name=fast_dict.get(int(print_type_num))
        if type_name:
            config=ConfigParser.ConfigParser()
            file_path="%s%s" %(fast_config,type_name)
            config.read(file_path)
            if config.has_section("profile"):
                result=dict(config.items("profile"))
    return result

def read_default_config_file_name(default_config_dir):
    """
    读取所有默认配置文件名(不包含后缀)
    """
    all_default_config_file_names = []
    # # 服务器路劲
    # default_config_dir = '/home/pi/Cura/config/machineConfig/'

    for dir_path, dir_names, file_names in os.walk(default_config_dir):
        # print 'Directory', dir_path  # Directory D:\p_working\trunk\printBox\Cura\config
        # print file_names
        if file_names:
            for file_name in file_names:
                if '.ini' in file_name:
                    file_name = file_name[:-4]
                    all_default_config_file_names.append(file_name)

    return all_default_config_file_names

def update_machine_config(machine_name,machine_data):
    '''更新打印机的配置信息
    @machine_name:打印机的名称
    @machine_data:要更新的数据 包含machine和profile两个节点
    ''' 
    try:
        config_path="/home/pi/Cura/config/machine_config/"  
        default_value_path="/home/pi/Cura/config/default_mahcine_value/default_machine.ini"
        
        has_config_name_list = read_default_config_file_name(default_config_dir=config_path)
        if machine_name in has_config_name_list:
            config=ConfigParser.ConfigParser()
            config_default=ConfigParser.ConfigParser()
            read_path="%s%s%s" %(config_path,machine_name,'.ini')
            config.read(read_path)
            config_default.read(default_value_path)
            
            # 打印机参数
            update_machinedata=machine_data["add_machine_data"]
            # 切片参数
            update_printdata=machine_data["data_add"]

            if update_machinedata:
                if update_machinedata["machine_name"]:
                    for d in update_machinedata:
                        config.set("machine", d, update_machinedata[d])
                        
            # 专业打印
            if machine_data["data_add"]["print_mode"] == 2:
                if update_printdata:       
                    config.set("profile", "print_mode", '2')
                    for up in update_printdata:
                        config.set("profile", up, update_printdata[up])

            # 根据打印类型和材料替换某些参数
            # 快速打印类型 
            if machine_data["data_add"]["print_mode"] == 1:
                # 1.高质量打印， 2.正常效果打印， 3.快速低质量打印 , 4.Ulti print
                #print_mode print_type print_material print_other
                
                #1首先从 默认配置中获取切片参数
                default_profile=dict(config_default.items("profile"))
                if default_profile:
                    for key,value in default_profile.items():
                        config.set("profile", key, value)
                config.set("profile", "print_mode", '1')

                print_type=machine_data["data_add"]["print_info"]["print_type"]
                config.set("profile", "print_type", print_type)
                
                result_type=get_profileitem_byprinttype(print_type)
                if result_type:
                    for fs in result_type:
                        config.set("profile", fs, result_type[fs])

                # 材料类型 PLA=1   ABS=2
                print_material=machine_data["data_add"]['print_info']['print_material']
                config.set("profile", "print_material", print_material)
                
                mt_result=get_profileitem_bymaterials(print_material)
                if mt_result:
                    for mt in mt_result:
                        config.set("profile", mt, mt_result[mt])
                        
                # 打印支撑结构
                print_other=machine_data["data_add"]['print_info']['print_other']
                if print_other=="1":
                    config.set("profile", "support", "Everywhere") 
                    config.set("profile", "print_other", "True")
                else:
                    config.set("profile", "support", "None")
                    config.set("profile", "print_other", "False")
                
            config.write(open("%s%s%s" % (config_path, machine_name, ".ini"), "w"))
            return 1
        
    except Exception,e:
        print traceback.format_exc()
        return 0

def read_config_profile_by_file_name(config_profile_name):
    """
    根据配置文件名读取默认配置文件（打印机的打印配置） 
    """
    profile_dict = {} 
    config_dir='%s%s%s' %('/home/pi/Cura/config/machine_config/',config_profile_name,'.ini')
    config=ConfigParser.ConfigParser()
    config.read(config_dir)
    if config.has_section("profile"): 
        profile_dict = dict(config.items("profile"))
    return profile_dict

def read_config_file_by_file_name(config_file_name):
    """
    根据配置文件名读取默认配置文件（打印机的配置）
    """
    machine_dict = {}
    config=ConfigParser.ConfigParser()
    config_dir='%s%s%s' %('/home/pi/Cura/config/machine_config/',config_file_name,'.ini')
    config.read(config_dir)
    if config.has_section("machine"):
        machine_dict = dict(config.items("machine"))
    
    return machine_dict

def get_active_machine_print_info():
    current_activity_print_machine = get_current_activity_print_machine()
    machine_dict = read_config_file_by_file_name(config_file_name=current_activity_print_machine)
    profile_dict = read_config_profile_by_file_name(config_profile_name=current_activity_print_machine)
    machine_type_list = get_machine_type_list()
    machine_shape_list = ["Square", "Circular"]
    extruder_list = [1, 2]
    serial_list = get_serial_list()
    baudrate_list = get_baudrate_list()
    user_info = get_user_info()
        
    active_machine = {
                """
                    Machine parameters.
                """
                "box_name": "",
                "machine_type": machine_type_list,
                "machine_width": 0,
                "machine_depth": 0,
                "machine_height": 0,
                "machine_center_is_zero": "False",
                "has_heated_bed": "False",
                "machine_shape": machine_shape_list,
                "extruder_amount": extruder_list,
                "extruder_offset_x2": 0,
                "extruder_offset_y2": 0,
                "serial_port": serial_list,
                "serial_baud": baudrate_list,
                "extruder_head_size_min_x": 0,
                "extruder_head_size_min_y": 0,
                "extruder_head_size_max_x": 0,
                "extruder_head_size_max_y": 0,
                "extruder_head_size_height": 0,
                "nozzle_size": 0,
                """
                    Profile parameters.
                """
                "layer_height": 0.1,
                "wall_thickness": 0.8,
                "bottom_thickness": 0.3,
                "layer0_width_factor": 100,
                "object_sink": 0.0,
                "overlap_dual": 0.15,
                "retraction_enable": "True",
                "retraction_min_travel": 1.5,
                "retraction_combing": ["Off", "All", "No Skin"],
                "retraction_minimal_extrusion": 0.02,
                "retraction_hop": 0.0,
                "retraction_speed": 40.0,
                "retraction_amount": 4.5,
                "solid_layer_thickness": 0.6,
                "fill_density": 20,
                "solid_top": "True",
                "solid_bottom": "True",
                "fill_overlap": 15,
                "print_speed": 50,
                "print_temperature": 200,
                "print_temperature2": 0,
                "print_bed_temperature": 70,
                "travel_speed": 150,
                "bottom_layer_speed": 20,
                "infill_speed": 0.0,
                "solidarea_speed": 0.0,
                "inset0_speed": 0.0,
                "insetx_speed": 0.0,
                "support": ["None", "Touching buildplate", "Everywhere"],
                "support_type": ["Grid", "Lines"],
                "support_angle": 60,
                "support_fill_rate": 20,
                "support_xy_distance": 0.7,
                "support_z_distance": 0.15,
                "platform_adhesion": ["None", "Brim", "Raft"],
                "skirt_line_count": 1,
                "skirt_gap": 3,
                "skirt_minimal_length": 150,
                "brim_line_count": 20,
                "raft_margin": 5,
                "raft_line_spacing": 3,
                "raft_base_thickness": 0.3,
                "raft_base_linewidth": 1.0,
                "raft_interface_thickness": 0.27,
                "raft_interface_linewidth": 0.4,
                "raft_airgap_all": 0.0,
                "raft_airgap": 0.22,
                "raft_surface_layers": 2,
                "raft_surface_thickness": 0.27,
                "raft_surface_linewidth": 0.4,
                "cool_min_layer_time": 5,
                "fan_enabled": "True",
                "fan_full_height": 0.5,
                "fan_speed": 100,
                "fan_speed_max": 100,
                "cool_min_feedrate": 10,
                "cool_head_lift": "False",
                "filament_diameter": 0,
                "filament_diameter2": 0,
                "filament_flow": 100,           
    }

    if user_info.has_key("box_name") and user_info["box_name"]:
        active_machine["box_name"] = user_info["box_name"]
    
    for (key, value) in machine_dict.items():
        if key in ["machine_type", "machine_shape", "extruder_amount", "serial_port", "serial_baud"]:
            pass
        else:
            active_machine[key] = value
            
    for (key, value) in profile_dict.items():
        if key in ["machine_type", "machine_shape", "extruder_amount", "serial_port", "serial_baud", "retraction_combing", "support", "support_type", "platform_adhesion"]:
            pass
        else:
            active_machine[key] = value

    if machine_dict.has_key("machine_type") and machine_dict["machine_type"]:
        current_machine_type = machine_dict["machine_type"]
        if current_machine_type in machine_type_list:
            machine_type_list.remove(current_machine_type)
            machine_type_list.insert(0, current_machine_type)
            active_machine["machine_type"] = machine_type_list

    if machine_dict.has_key("machine_shape") and machine_dict["machine_shape"]:
        current_machine_shape = machine_dict["machine_shape"]
        if current_machine_shape in machine_shape_list:
            machine_shape_list.remove(current_machine_shape)
            machine_shape_list.insert(0, current_machine_shape)
            active_machine["machine_shape"] = machine_shape_list

    if machine_dict.has_key("extruder_amount") and machine_dict["extruder_amount"]:    
        current_extruder_amount = machine_dict["extruder_amount"]
        if current_extruder_amount in extruder_list:
            extruder_list.remove(current_extruder_amount)
            extruder_list.insert(0, current_extruder_amount)
            active_machine["extruder_amount"] = extruder_list

    if machine_dict.has_key("serial_port") and machine_dict["serial_port"]:
        current_serial_port = machine_dict["serial_port"]
        if current_serial_port in serial_list:
            serial_list.remove(current_serial_port)
            serial_list.insert(0, current_serial_port)
            active_machine["serial_port"] = serial_list

    if profile_dict.has_key("retraction_combing") and profile_dict["retraction_combing"]:
        current_retraction_combing = profile_dict["retraction_combing"]
        if current_retraction_combing in active_machine["retraction_combing"]:
            active_machine["retraction_combing"].remove(current_retraction_combing)
            active_machine["retraction_combing"].insert(0, current_retraction_combing)

    if profile_dict.has_key("support") and profile_dict["support"]:
        current_support = profile_dict["support"]
        if current_support in active_machine["support"]:
            active_machine["support"].remove(current_support)
            active_machine["support"].insert(0, current_support)

    if profile_dict.has_key("support_type") and profile_dict["support_type"]:
        current_support_type = profile_dict["support_type"]
        if current_support_type in active_machine["support_type"]:
            active_machine["support_type"].remove(current_support_type)
            active_machine["support_type"].insert(0, current_support_type)

    if profile_dict.has_key("platform_adhesion") and profile_dict["platform_adhesion"]:
        current_platform_adhesion = profile_dict["platform_adhesion"]
        if current_platform_adhesion in active_machine["platform_adhesion"]:
            active_machine["platform_adhesion"].remove(current_platform_adhesion)
            active_machine["platform_adhesion"].insert(0, current_platform_adhesion)

    if machine_dict.has_key("serial_baud") and machine_dict["serial_baud"]:
        baudrate = machine_dict["serial_baud"]
        if baudrate == "AUTO":
            if baudrate in baudrate_list:
                baudrate_list.remove(baudrate)
                baudrate_list.insert(0, baudrate)
                active_machine["serial_baud"] = baudrate_list
        else:
            baudrate_num = int(baudrate)
            if baudrate_num in baudrate_list:
                baudrate_list.remove(baudrate_num)
                baudrate_list.insert(0, baudrate_num)
                if "AUTO" not in baudrate_list:
                    baudrate_list.insert(1, "AUTO")
                active_machine["serial_baud"] = baudrate_list
    

    return active_machine

def get_default_machine_print_info(machine_name, machine_type):
    config_default_value=ConfigParser.ConfigParser()
    config_default=ConfigParser.ConfigParser()
    current_config=ConfigParser.ConfigParser()
    
    default_value_path="/home/pi/Cura/config/default_mahcine_value/default_machine.ini" 
    default_config_path="%s%s%s"  %('/home/pi/Cura/config/default_type_config/',machine_type,'.ini')
    current_config_path="%s%s%s"  %('/home/pi/Cura/config/machine_config/',machine_name,'.ini')

    config_default_value.read(default_value_path)
    config_default.read(default_config_path)
    current_config.read(current_config_path)

    default_machines=dict(config_default_value.items("machine"))
    default_profiles=dict(config_default_value.items("profile"))
     
    machines=dict(config_default.items("machine"))
    profiles=dict(config_default.items("profile"))
    
    current_machines=dict(current_config.items("machine"))
    current_profiles=dict(current_config.items("profile"))

    if current_machines["machine_type"] == machine_type:
        machine_width = current_machines["machine_width"]
        machine_depth = current_machines["machine_depth"]
        machine_height = current_machines["machine_height"]
        machine_center_is_zero = current_machines["machine_center_is_zero"]
        has_heated_bed = current_machines["has_heated_bed"]
        machine_shape = current_machines["machine_shape"]
        extruder_amount = current_machines["extruder_amount"]
        extruder_offset_x2 = current_machines["extruder_offset_x2"]
        extruder_offset_y2 = current_machines["extruder_offset_y2"]
        extruder_head_size_min_x = current_machines["extruder_head_size_min_x"]
        extruder_head_size_min_y = current_machines["extruder_head_size_min_y"]
        extruder_head_size_max_x = current_machines["extruder_head_size_max_x"]
        extruder_head_size_max_y = current_machines["extruder_head_size_max_y"]
        extruder_head_size_height = current_machines["extruder_head_size_height"]
        filament_diameter = current_profiles["filament_diameter"]
        filament_diameter2 = current_profiles["filament_diameter2"]
        nozzle_size = current_profiles["nozzle_size"]
        
        layer_height = current_profiles["layer_height"]
        wall_thickness = current_profiles["wall_thickness"]
        bottom_thickness = current_profiles["bottom_thickness"]
        layer0_width_factor = current_profiles["layer0_width_factor"]
        object_sink = current_profiles["object_sink"]
        overlap_dual = current_profiles["overlap_dual"]
        retraction_enable = current_profiles["retraction_enable"]
        retraction_min_travel = current_profiles["retraction_min_travel"]
        retraction_combing = current_profiles["retraction_combing"]
        retraction_minimal_extrusion = current_profiles["retraction_minimal_extrusion"]
        retraction_hop = current_profiles["retraction_hop"]
        retraction_speed = current_profiles["retraction_speed"]
        retraction_amount = current_profiles["retraction_amount"]
        
        solid_layer_thickness = current_profiles["solid_layer_thickness"]
        fill_density = current_profiles["fill_density"]
        solid_top = current_profiles["solid_top"]
        solid_bottom = current_profiles["solid_bottom"]
        fill_overlap = current_profiles["fill_overlap"]
        
        print_speed = current_profiles["print_speed"]
        print_temperature = current_profiles["print_temperature"]
        print_temperature2 = current_profiles["print_temperature2"]
        print_bed_temperature = current_profiles["print_bed_temperature"]
        travel_speed = current_profiles["travel_speed"]
        bottom_layer_speed = current_profiles["bottom_layer_speed"]
        infill_speed = current_profiles["infill_speed"]
        solidarea_speed = current_profiles["solidarea_speed"]
        inset0_speed = current_profiles["inset0_speed"]
        insetx_speed = current_profiles["insetx_speed"]
        
        support = current_profiles["support"]
        support_type = current_profiles["support_type"]
        support_angle = current_profiles["support_angle"]
        support_fill_rate = current_profiles["support_fill_rate"]
        support_xy_distance = current_profiles["support_xy_distance"]
        support_z_distance = current_profiles["support_z_distance"]
        platform_adhesion = current_profiles["platform_adhesion"]
        skirt_line_count = current_profiles["skirt_line_count"]
        skirt_gap = current_profiles["skirt_gap"]
        skirt_minimal_length = current_profiles["skirt_minimal_length"]
        brim_line_count = current_profiles["brim_line_count"]
        raft_margin = current_profiles["raft_margin"]
        raft_line_spacing = current_profiles["raft_line_spacing"]
        raft_base_thickness = current_profiles["raft_base_thickness"]
        raft_base_linewidth = current_profiles["raft_base_linewidth"]
        raft_interface_thickness = current_profiles["raft_interface_thickness"]
        raft_interface_linewidth = current_profiles["raft_interface_linewidth"]
        raft_airgap_all = current_profiles["raft_airgap_all"]
        raft_airgap = current_profiles["raft_airgap"]
        raft_surface_layers = current_profiles["raft_surface_layers"]
        raft_surface_thickness = current_profiles["raft_surface_thickness"]
        raft_surface_linewidth = current_profiles["raft_surface_linewidth"]
        
        cool_min_layer_time = current_profiles["cool_min_layer_time"]
        fan_enabled = current_profiles["fan_enabled"]
        fan_full_height = current_profiles["fan_full_height"]
        fan_speed = current_profiles["fan_speed"]
        fan_speed_max = current_profiles["fan_speed_max"]
        cool_min_feedrate = current_profiles["cool_min_feedrate"]
        cool_head_lift = current_profiles["cool_head_lift"]
           
    else:    
        machine_width = machines["machine_width"] if machines.has_key("machine_width")and machines["machine_width"] else default_machines["machine_width"]
        machine_depth = machines["machine_depth"] if machines.has_key("machine_depth") and machines["machine_depth"]else default_machines["machine_depth"]
        machine_height = machines["machine_height"] if machines.has_key("machine_height") and machines["machine_height"] else default_machines["machine_height"]
        machine_center_is_zero = machines["machine_center_is_zero"] if machines.has_key("machine_center_is_zero") and machines["machine_center_is_zero"] else default_machines["machine_center_is_zero"]
        has_heated_bed = machines["has_heated_bed"] if machines.has_key("has_heated_bed") and machines["has_heated_bed"] else default_machines["has_heated_bed"]
        machine_shape = machines["machine_shape"] if machines.has_key("machine_shape") and machines["machine_shape"] else default_machines["machine_shape"]
        extruder_amount = machines["extruder_amount"] if machines.has_key("extruder_amount") and machines["extruder_amount"] else default_machines["extruder_amount"]
        extruder_offset_x2 = machines["extruder_offset_x2"] if machines.has_key("extruder_offset_x2") and machines["extruder_offset_x2"] else default_machines["extruder_offset_x2"]
        extruder_offset_y2 = machines["extruder_offset_y2"] if machines.has_key("extruder_offset_y2") and machines["extruder_offset_y2"] else default_machines["extruder_offset_y2"]
        extruder_head_size_min_x = machines["extruder_head_size_min_x"] if machines.has_key("extruder_head_size_min_x") and machines["extruder_head_size_min_x"] else default_machines["extruder_head_size_min_x"]
        extruder_head_size_min_y = machines["extruder_head_size_min_y"] if machines.has_key("extruder_head_size_min_y") and machines["extruder_head_size_min_y"] else default_machines["extruder_head_size_min_y"]
        extruder_head_size_max_x = machines["extruder_head_size_max_x"] if machines.has_key("extruder_head_size_max_x") and machines["extruder_head_size_max_x"] else default_machines["extruder_head_size_max_x"]
        extruder_head_size_max_y = machines["extruder_head_size_max_y"] if machines.has_key("extruder_head_size_max_y") else default_machines["extruder_head_size_max_y"]
        extruder_head_size_height = machines["extruder_head_size_height"] if machines.has_key("extruder_head_size_height") and machines["extruder_head_size_height"] else default_machines["extruder_head_size_height"]
        
        filament_diameter = profiles["filament_diameter"] if profiles.has_key("filament_diameter") and profiles["filament_diameter"] else default_profiles["filament_diameter"]
        filament_diameter2 = profiles["filament_diameter2"] if profiles.has_key("filament_diameter2") and profiles["filament_diameter2"] else default_profiles["filament_diameter2"]
        nozzle_size = profiles["nozzle_size"] if profiles.has_key("nozzle_size") and profiles["nozzle_size"] else default_profiles["nozzle_size"]
        
        layer_height = profiles["layer_height"] if profiles.has_key("layer_height") and profiles["layer_height"] else default_profiles["layer_height"]
        wall_thickness = profiles["wall_thickness"] if profiles.has_key("wall_thickness") and profiles["wall_thickness"] else default_profiles["wall_thickness"]
        bottom_thickness = profiles["bottom_thickness"] if profiles.has_key("bottom_thickness") and profiles["bottom_thickness"] else default_profiles["bottom_thickness"]
        layer0_width_factor = profiles["layer0_width_factor"] if profiles.has_key("layer0_width_factor") and profiles["layer0_width_factor"] else default_profiles["layer0_width_factor"]
        object_sink = profiles["object_sink"] if profiles.has_key("object_sink") and profiles["object_sink"] else default_profiles["object_sink"]
        overlap_dual = profiles["overlap_dual"] if profiles.has_key("overlap_dual") and profiles["overlap_dual"] else default_profiles["overlap_dual"]
        retraction_enable = profiles["retraction_enable"] if profiles.has_key("retraction_enable") and profiles["retraction_enable"] else default_profiles["retraction_enable"]
        retraction_min_travel = profiles["retraction_min_travel"] if profiles.has_key("retraction_min_travel") and profiles["retraction_min_travel"] else default_profiles["retraction_min_travel"]
        retraction_combing = profiles["retraction_combing"] if profiles.has_key("retraction_combing") and profiles["retraction_combing"] else default_profiles["retraction_combing"]
        retraction_minimal_extrusion = profiles["retraction_minimal_extrusion"] if profiles.has_key("retraction_minimal_extrusion") and profiles["retraction_minimal_extrusion"] else default_profiles["retraction_minimal_extrusion"]
        retraction_hop = profiles["retraction_hop"] if profiles.has_key("retraction_hop") and profiles["retraction_hop"] else default_profiles["retraction_hop"]
        retraction_speed = profiles["retraction_speed"] if profiles.has_key("retraction_speed") and profiles["retraction_speed"] else default_profiles["retraction_speed"]
        retraction_amount = profiles["retraction_amount"] if profiles.has_key("retraction_amount") and profiles["retraction_amount"] else default_profiles["retraction_amount"]
        
        solid_layer_thickness = profiles["solid_layer_thickness"] if profiles.has_key("solid_layer_thickness") and profiles["solid_layer_thickness"] else default_profiles["solid_layer_thickness"]
        fill_density = profiles["fill_density"] if profiles.has_key("fill_density") and profiles["fill_density"] else default_profiles["fill_density"]
        solid_top = profiles["solid_top"] if profiles.has_key("solid_top") and profiles["solid_top"] else default_profiles["solid_top"]
        solid_bottom = profiles["solid_bottom"] if profiles.has_key("solid_bottom") and profiles["solid_bottom"] else default_profiles["solid_bottom"]
        fill_overlap = profiles["fill_overlap"] if profiles.has_key("fill_overlap") and profiles["fill_overlap"] else default_profiles["fill_overlap"]
        
        print_speed = profiles["print_speed"] if profiles.has_key("print_speed") and profiles["print_speed"] else default_profiles["print_speed"]
        print_temperature = profiles["print_temperature"] if profiles.has_key("print_temperature") and profiles["print_temperature"] else default_profiles["print_temperature"]
        print_temperature2 = profiles["print_temperature2"] if profiles.has_key("print_temperature2") and profiles["print_temperature2"] else default_profiles["print_temperature2"]
        print_bed_temperature = profiles["print_bed_temperature"] if profiles.has_key("print_bed_temperature") and profiles["print_bed_temperature"] else default_profiles["print_bed_temperature"]
        travel_speed = profiles["travel_speed"] if profiles.has_key("travel_speed") and profiles["travel_speed"] else default_profiles["travel_speed"]
        bottom_layer_speed = profiles["bottom_layer_speed"] if profiles.has_key("bottom_layer_speed") and profiles["bottom_layer_speed"] else default_profiles["bottom_layer_speed"]
        infill_speed = profiles["infill_speed"] if profiles.has_key("infill_speed") and profiles["infill_speed"] else default_profiles["infill_speed"]
        solidarea_speed = profiles["solidarea_speed"] if profiles.has_key("solidarea_speed") and profiles["solidarea_speed"] else default_profiles["solidarea_speed"]
        inset0_speed = profiles["inset0_speed"] if profiles.has_key("inset0_speed") and profiles["inset0_speed"] else default_profiles["inset0_speed"]
        insetx_speed = profiles["insetx_speed"] if profiles.has_key("insetx_speed") and profiles["insetx_speed"] else default_profiles["insetx_speed"]
        
        support = profiles["support"] if profiles.has_key("support") and profiles["support"] else default_profiles["support"]
        support_type = profiles["support_type"] if profiles.has_key("support_type") and profiles["support_type"] else default_profiles["support_type"]
        support_angle = profiles["support_angle"] if profiles.has_key("support_angle") and profiles["support_angle"] else default_profiles["support_angle"]
        support_fill_rate = profiles["support_fill_rate"] if profiles.has_key("support_fill_rate") and profiles["support_fill_rate"] else default_profiles["support_fill_rate"]
        support_xy_distance = profiles["support_xy_distance"] if profiles.has_key("support_xy_distance") and profiles["support_xy_distance"] else default_profiles["support_xy_distance"]
        support_z_distance = profiles["support_z_distance"] if profiles.has_key("support_z_distance") and profiles["support_z_distance"] else default_profiles["support_z_distance"]
        platform_adhesion = profiles["platform_adhesion"] if profiles.has_key("platform_adhesion") and profiles["platform_adhesion"] else default_profiles["platform_adhesion"]
        skirt_line_count = profiles["skirt_line_count"] if profiles.has_key("skirt_line_count") and profiles["skirt_line_count"] else default_profiles["skirt_line_count"]
        skirt_gap = profiles["skirt_gap"] if profiles.has_key("skirt_gap") and profiles["skirt_gap"] else default_profiles["skirt_gap"]
        skirt_minimal_length = profiles["skirt_minimal_length"] if profiles.has_key("skirt_minimal_length") and profiles["skirt_minimal_length"] else default_profiles["skirt_minimal_length"]
        brim_line_count = profiles["brim_line_count"] if profiles.has_key("brim_line_count") and profiles["brim_line_count"] else default_profiles["brim_line_count"]
        raft_margin = profiles["raft_margin"] if profiles.has_key("raft_margin") and profiles["raft_margin"] else default_profiles["raft_margin"]
        raft_line_spacing = profiles["raft_line_spacing"] if profiles.has_key("raft_line_spacing") and profiles["raft_line_spacing"] else default_profiles["raft_line_spacing"]
        raft_base_thickness = profiles["raft_base_thickness"] if profiles.has_key("raft_base_thickness") and profiles["raft_base_thickness"] else default_profiles["raft_base_thickness"]
        raft_base_linewidth = profiles["raft_base_linewidth"] if profiles.has_key("raft_base_linewidth") and profiles["raft_base_linewidth"] else default_profiles["raft_base_linewidth"]
        raft_interface_thickness = profiles["raft_interface_thickness"] if profiles.has_key("raft_interface_thickness") and profiles["raft_interface_thickness"] else default_profiles["raft_interface_thickness"]
        raft_interface_linewidth = profiles["raft_interface_linewidth"] if profiles.has_key("raft_interface_linewidth") and profiles["raft_interface_linewidth"] else default_profiles["raft_interface_linewidth"]
        raft_airgap_all = profiles["raft_airgap_all"] if profiles.has_key("raft_airgap_all") and profiles["raft_airgap_all"] else default_profiles["raft_airgap_all"]
        raft_airgap = profiles["raft_airgap"] if profiles.has_key("raft_airgap") and profiles["raft_airgap"] else default_profiles["raft_airgap"]
        raft_surface_layers = profiles["raft_surface_layers"] if profiles.has_key("raft_surface_layers") and profiles["raft_surface_layers"] else default_profiles["raft_surface_layers"]
        raft_surface_thickness = profiles["raft_surface_thickness"] if profiles.has_key("raft_surface_thickness") and profiles["raft_surface_thickness"] else default_profiles["raft_surface_thickness"]
        raft_surface_linewidth = profiles["raft_surface_linewidth"] if profiles.has_key("raft_surface_linewidth") and profiles["raft_surface_linewidth"] else default_profiles["raft_surface_linewidth"]
        
        cool_min_layer_time = profiles["cool_min_layer_time"] if profiles.has_key("cool_min_layer_time") and profiles["cool_min_layer_time"] else default_profiles["cool_min_layer_time"]
        fan_enabled = profiles["fan_enabled"] if profiles.has_key("fan_enabled") and profiles["fan_enabled"] else default_profiles["fan_enabled"]
        fan_full_height = profiles["fan_full_height"] if profiles.has_key("fan_full_height") and profiles["fan_full_height"] else default_profiles["fan_full_height"]
        fan_speed = profiles["fan_speed"] if profiles.has_key("fan_speed") and profiles["fan_speed"] else default_profiles["fan_speed"]
        fan_speed_max = profiles["fan_speed_max"] if profiles.has_key("fan_speed_max") and profiles["fan_speed_max"] else default_profiles["fan_speed_max"]
        cool_min_feedrate = profiles["cool_min_feedrate"] if profiles.has_key("cool_min_feedrate") and profiles["cool_min_feedrate"] else default_profiles["cool_min_feedrate"]
        cool_head_lift = profiles["cool_head_lift"] if profiles.has_key("cool_head_lift") and profiles["cool_head_lift"] else default_profiles["cool_head_lift"]
        

    machine_shape_list = ["Square", "Circular"]
    if machine_shape in machine_shape_list:
        machine_shape_list.remove(machine_shape)
        machine_shape_list.insert(0, machine_shape)
        
    extruder_amount_list = ["1", "2"]
    if extruder_amount in extruder_amount_list:
        extruder_amount_list.remove(extruder_amount)
        extruder_amount_list.insert(0, extruder_amount)
        
    retraction_combing_list = ["Off", "All", "No Skin"]
    if retraction_combing in retraction_combing_list:
        retraction_combing_list.remove(retraction_combing)
        retraction_combing_list.insert(0, retraction_combing)
        
    support_list = ["None", "Touching buildplate", "Everywhere"]
    if support in support_list:
        support_list.remove(support)
        support_list.insert(0, support)

    support_type_list = ["Grid", "Lines"]
    if support_type in support_type_list:
        support_type_list.remove(support_type)
        support_type_list.insert(0, support_type)
        
    platform_adhesion_list = ["None", "Brim", "Raft"]
    if platform_adhesion in platform_adhesion_list:
        platform_adhesion_list.remove(platform_adhesion)
        platform_adhesion_list.insert(0, platform_adhesion)

    alter_machine_info = {
            "machine_width": machine_width,
            "machine_depth": machine_depth,
            "machine_height": machine_height,
            "machine_center_is_zero": machine_center_is_zero,
            "has_heated_bed": has_heated_bed,
            "machine_shape": machine_shape_list,
            "extruder_amount": extruder_amount_list,
            "extruder_offset_x2": extruder_offset_x2,
            "extruder_offset_y2": extruder_offset_y2,
            "extruder_head_size_min_x": extruder_head_size_min_x,
            "extruder_head_size_min_y": extruder_head_size_min_y,
            "extruder_head_size_max_x": extruder_head_size_max_x,
            "extruder_head_size_max_y": extruder_head_size_max_y,
            "extruder_head_size_height": extruder_head_size_height,
            "filament_diameter": filament_diameter,
            "filament_diameter2": filament_diameter2,
            "nozzle_size": nozzle_size,

            "layer_height": layer_height,
            "wall_thickness": wall_thickness,
            "bottom_thickness": bottom_thickness,
            "layer0_width_factor": layer0_width_factor,
            "object_sink": object_sink,
            "overlap_dual": overlap_dual,
            "retraction_enable": retraction_enable,
            "retraction_min_travel": retraction_min_travel,
            "retraction_combing": retraction_combing_list,
            "retraction_minimal_extrusion": retraction_minimal_extrusion,
            "retraction_hop": retraction_hop,
            "retraction_speed": retraction_speed,
            "retraction_amount": retraction_amount,
            
            "solid_layer_thickness": solid_layer_thickness,
            "fill_density": fill_density,
            "solid_top": solid_top,
            "solid_bottom": solid_bottom,
            "fill_overlap": fill_overlap,
            
            "print_speed": print_speed,
            "print_temperature": print_temperature,
            "print_temperature2": print_temperature2,
            "print_bed_temperature": print_bed_temperature,
            "travel_speed": travel_speed,
            "bottom_layer_speed": bottom_layer_speed,
            "infill_speed": infill_speed,
            "solidarea_speed": solidarea_speed,
            "inset0_speed": inset0_speed,
            "insetx_speed": insetx_speed,
            
            "support": support_list,
            "support_type": support_type_list,
            "support_angle": support_angle,
            "support_fill_rate": support_fill_rate,
            "support_xy_distance": support_xy_distance,
            "support_z_distance": support_z_distance,
            "platform_adhesion": platform_adhesion_list,
            "skirt_line_count": skirt_line_count,
            "skirt_gap": skirt_gap,
            "skirt_minimal_length": skirt_minimal_length,
            "brim_line_count": brim_line_count,
            "raft_margin": raft_margin,
            "raft_line_spacing": raft_line_spacing,
            "raft_base_thickness": raft_base_thickness,
            "raft_base_linewidth": raft_base_linewidth,
            "raft_interface_thickness": raft_interface_thickness,
            "raft_interface_linewidth": raft_interface_linewidth,
            "raft_airgap_all": raft_airgap_all,
            "raft_airgap": raft_airgap,
            "raft_surface_layers": raft_surface_layers,
            "raft_surface_thickness": raft_surface_thickness,
            "raft_surface_linewidth": raft_surface_linewidth,
            
            "cool_min_layer_time": cool_min_layer_time,
            "fan_enabled": fan_enabled,
            "fan_full_height": fan_full_height,
            "fan_speed": fan_speed,
            "fan_speed_max": fan_speed_max,
            "cool_min_feedrate": cool_min_feedrate,
            "cool_head_lift": cool_head_lift,
            

    }
    return alter_machine_info

def write_print_info(printer_name,printer_type):
    """读取默认类型的打印机配置添加到machine_config文件夹中
    @printer_name:打印机名称
    @printer_type:打印机类型
    """
    try:
        config_default_value=ConfigParser.ConfigParser()
        config_default=ConfigParser.ConfigParser()
        config_add=ConfigParser.ConfigParser()
        
        default_value_path="/home/pi/Cura/config/default_mahcine_value/default_machine.ini" 
        default_config_path="%s%s%s"  %('/home/pi/Cura/config/default_type_config/',printer_type,'.ini')
        add_config_path="%s%s%s"  %('/home/pi/Cura/config/machine_config/',printer_name,'.ini')
        config_default.read(default_config_path)
        config_default_value.read(default_value_path)

        config_add.add_section("machine")
        config_add.add_section("profile")
        config_add.add_section("alterations")
        
        default_machines=dict(config_default_value.items("machine"))
        default_profiles=dict(config_default_value.items("profile"))
        default_alteration=dict(config_default_value.items("alterations"))

        machines=dict(config_default.items("machine"))
        profiles=dict(config_default.items("profile"))
        
        alter=None
        if config_default.has_section("alterations") and config_default.has_option("alterations", "start.gcode"):
            alter=config_default.items("alterations")
        alteration={}
        if alter:
            alteration=dict(alter)  
    
        if default_machines:
            for df_k in default_machines:
                config_add.set("machine", df_k, default_machines[df_k])
        if default_profiles:
            for dt_pf in default_profiles:
                config_add.set("profile", dt_pf,default_profiles[dt_pf])
        if default_alteration:
            for df_al in default_alteration:
                config_add.set("alterations", df_al, default_alteration[df_al])
    
        if machines:
            for keys,values in machines.items():
                config_add.set("machine", keys, values)

        config_add.set("machine", "machine_name", printer_name)

        if profiles:
            for pro,provalue in profiles.items():
                config_add.set("profile", pro,provalue)

        if alteration:
            for gc,gcvalue in alteration.items():
                config_add.set("alterations", gc, gcvalue)  

        config_add.write(open(add_config_path, "w"))

        cfg=ConfigParser.ConfigParser()
        cfg.read(add_config_path)

        machines_item=dict(cfg.items("machine"))
        update_preferences_file_info(machines_item)
        return 1
            
    except Exception,e:
        print e.message
        return 0

if __name__ == '__main__':
    pass
