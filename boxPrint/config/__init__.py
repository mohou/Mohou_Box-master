# coding=utf-8

import json
import os
import threading
import logging

class Singleton(object):
    lock = threading.Lock()
    _instance = None

    @classmethod
    def instance(cls):
        with cls.lock:
            if not cls._instance:
                cls._instance = cls()
                cls._instance.logger.info("Creating new instance of " + cls.__name__)
        return cls._instance

class PrinterProfile(Singleton):
    def __init__(self, path=None):
        if path is None:
            self._profile_path = os.path.join(os.path.dirname(__file__), 'printer_profile.json')
        else:
            self._profile_path = path

        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        self.profile = None
        self.load()
        
    def save(self, profile_data):
        with self.lock:
            try:
                with open(self._profile_path, 'w') as profile_file:
                    self.profile.update(profile_data)
                    json_config = json.dump(self.profile, profile_file, sort_keys = True, indent = 4, separators = (',', ': '))
            except Exception as e:
                self.logger.error("Error writing config to %s: %s." % (self._profile_path, str(e)))
            else:
                pass
        

    def load(self):
        with self.lock:
            try:
                with open(self._profile_path) as profile_file:
                    self.profile = json.load(profile_file)
            except Exception as e:
                self.logger.error("Error reading config from %s: %s." % (self._profile_path, str(e)))
            else:
                return self.profile
    
    def reload(self):
        return self.load()
    
