# coding=utf-8
import tornado.ioloop
import time


def createFormData(fields, fileinfo=None):
    """
    fields is a dict of (name, value) elements for regular form fields.
    Return (headers, body) ready for httplib.HTTP instance
    """
    BOUNDARY = '----------ThIs_Is_tHe_bouNdaRY_$'
    CRLF = '\r\n'
    L = []
    for (key, value) in fields.items():
        L.append('--' + BOUNDARY)
        L.append('Content-Disposition: form-data; name="%s"' % key)
        L.append('')
        L.append(str(value))
    if fileinfo is not None:
        L.append('--' + BOUNDARY)
        L.append('Content-Disposition: form-data; name="file"; filename="%s"' % str(fileinfo["filename"]))
        L.append('Content-Type: %s' % str(fileinfo["filetype"]))
        L.append('')
        L.append(fileinfo["filecontent"])

    L.append('--' + BOUNDARY + '--')
    L.append('')
    body = CRLF.join(L)
    content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
    headers = {'Content-Type' : content_type}
    return headers, body




def loopTask(delta=10):
    def wrap_loop(task):
        def wrapTask():
            task()
            tornado.ioloop.IOLoop.instance().add_timeout(time.time()+delta, wrapTask)
        return wrapTask
    return wrap_loop

