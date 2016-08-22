
import threaded_printer

class Printer(threaded_printer.Printer):

    def __init__(self, profile, usb_info):
        threaded_printer.Printer.__init__(self, profile, usb_info)
