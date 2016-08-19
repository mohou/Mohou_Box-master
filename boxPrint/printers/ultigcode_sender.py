import re
import time

import config
import threaded_sender


# TODO: Need implement validate Firmware Version
class SDCardPrintThread(threaded_sender.PrintThread):
    START_WRITE_FILE_GCODE = "M28 1.gco"
    END_WRITE_FILE_GCODE = "M29 1.gco"
    START_PRINT_FROM_FILE = "M623 1.gco"

    def __init__(self, sender, gcodes):
        super(SDCardPrintThread, self).__init__(sender, None)
        self.gcodes = self.sender.preprocess_gcodes(gcodes)
        self.total_gcodes = len(gcodes)
        self.print_thread_flag = True

    def run(self):
        self.logger.info("Start print from SD Card")
        self.sender.stop_temp_requesting_flag = True
        self.sender.temperature_request_thread.join()
        self.send(self.START_WRITE_FILE_GCODE, add_checksum=False)
        self.sender.ready_for_command.set()
        while not self.sender.ready_for_command.wait(1):
            if self.sender.stop_flag or not self.sender.operational_flag:
                return
        self.logger.info("Starting upload gcodes...")
        for line in self.gcodes:
            if self.sender.stop_flag:
                return
            self.sender.connection.send(line)
        for gcode in [self.END_WRITE_FILE_GCODE, self.START_PRINT_FROM_FILE]:
            self.send(gcode, add_checksum=False)
            self.sender.ready_for_command.set()
            while not self.sender.ready_for_command.wait(1):
                if self.sender.stop_flag or not self.sender.operational_flag:
                    return
        self.logger.info("done")
        next_send_request = 0
        self.logger.info("Starting monitoring...")
        while self.print_thread_flag:
            time_now = time.time()
            if time_now >= next_send_request:
                next_send_request = time_now + 15
                self.send("M27", add_checksum=False)
                self.send("M105", add_checksum=False)
            if self.sender.stop_flag:
                return
            time.sleep(0.1)
        self.logger.info("done")
        self.sender.start_temp_requesting()

    def get_percent(self):
        if self.lines_sent < 0:
            return 0
        else:
            return int(self.lines_sent / float(self.total_gcodes) * 100)

class Sender(threaded_sender.Sender):
    def load_gcodes(self, gcodes):
        if self.print_thread and self.print_thread.is_alive():
            self.logger.warning("PrintThread already alive")
            return False
        else:
            with self.homing_lock:
                self.homing_thread.join()
            self.logger.info("Starting PrintThread")
            self.print_thread = SDCardPrintThread(self, gcodes)
            self.print_thread.start()


    def define_regexps(self):
        threaded_sender.Sender.define_regexps(self)
        self.progress_re = re.compile(".*SD printing byte (\d+)\/(\d+).*", flags=re.DOTALL)

    def pause(self):
        # if self.print_thread:
        #     if not self.print_thread.paused:
        #         self.print_thread.send("M25", add_checksum=False)
        #         self.print_thread.paused = True
        #         return True
        message = "This feature do not supported"
        config.create_error_report(902, message, self.usb_info, self.logger, is_blocking=False)
        return False

    def unpause(self):
        # if self.print_thread:
        #     if self.print_thread.paused:
        #         self.print_thread.send("M24", add_checksum=False)
        #         self.print_thread.paused = False
        #         return True
        message = "This feature do not supported"
        config.create_error_report(901, message, self.usb_info, self.logger, is_blocking=False)
        return False

    def log_strange_acks(self, line):
        if self.print_thread:
            if "Done printing file" in line:
                self.print_thread.print_thread_flag = False
                self.print_thread.lines_sent = self.print_thread.total_gcodes
            elif "SD printing" in line:
                progress_match = self.progress_re.match(line)
                if progress_match:
                    self.print_thread.lines_sent = int(progress_match.group(1))
                    self.print_thread.total_gcodes = int(progress_match.group(2))
                    if self.print_thread.total_gcodes > 0:
                        if self.print_thread.lines_sent >= self.print_thread.total_gcodes:
                            self.print_thread.print_thread_flag = False
        elif "error" in line or "failed" in line:
            self.operational_flag = False
            config.create_error_report(900, line, self.usb_info, self.logger, is_blocking=True)
        else:
            self.logger.warning("Received strange answer: " + line.strip())


if __name__ == "__main__":
    import log

    log.create_logger("", "debug_log.txt")
    usb_info = {'COM': "COM18"}
    profile = {
        'baudrate': [115200],
        "name": "Test",
        "alias": "Test",
        "no_DTR": False,
        "end_gcodes": [
            "M104 S0",
            "M140 S0",
            "G28 X0 Y0",
            "M84"
        ]
    }
    with open("test_gcodes.gco", "r") as f:
        your_file_content = f.read()
    sender = Sender(profile, usb_info)
    sender.connection.verbose = True
    time.sleep(4)
    print "start print"
    sender.load_gcodes(your_file_content)
    time.sleep(3)
    try:
        while True:
            write = raw_input(">: ").strip()
            sender.connection.send(write)
    except:
        pass
