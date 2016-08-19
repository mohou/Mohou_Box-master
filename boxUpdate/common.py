# coding=utf-8
import tornado.web
import uuid
import os.path

class Application():
    def __init__(self):
        self.handlers = []
        self.template = os.path.join(os.path.dirname(__file__), "templates")
        self.static = os.path.join(os.path.dirname(__file__), "static")
        

    def route(self,regex):
        def _route(handler):
            self.handlers.append((regex, handler))
        return _route

    def instance(self):
        return tornado.web.Application(
            handlers=self.handlers,
            template_path=self.template,
            static_path=self.static
        )
