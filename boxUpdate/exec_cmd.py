# coding=utf-8
import logging
import os
import subprocess
import threading

logger = logging.getLogger(__name__)
def run(call_args, call_back, call_back_args):
	(cwd, ignored) = os.path.split(call_args[0])
	try:
		logger.info("Running %r in %s." % (call_args, cwd))
		subprocess.check_call(call_args, cwd=cwd)
	except subprocess.CalledProcessError as (e):
		logger.warn("Could not execute cmd : %s, got return code %r." % (call_args[0], e.returncode))
		tmp_list = list(call_back_args)
		tmp_list.append(e.returncode)
		call_back_args = tuple(tmp_list)
	if call_back and hasattr(call_back, '__call__'):
		call_back(*call_back_args)

def execute_cmd(cmd_path, cmd_args, call_back=None, *call_back_args):
	if cmd_args:
		call_args = [cmd_path]
		call_args.extend(cmd_args)
	else:
		call_args = [cmd_path]
	thread = threading.Thread(target=run, args=(call_args, call_back, call_back_args))
	thread.start()
	return 0

if __name__ == "__main__":
	logging.basicConfig(level=logging.INFO)
	logger = logging.getLogger(__name__)
	def test(*args):
		print len(args)
		print repr(args)
	import time
	execute_cmd("/bin/ls", ["-l", "/home"], test, "test")
	time.sleep(2)
	execute_cmd("/bin/ls", ["-l", "/error"], test, "test")
	time.sleep(2)
	execute_cmd("/bin/ls", ["-l", "/home/pi"], test)
	time.sleep(2)
	execute_cmd("/bin/ls", ["-l", "~"])
	time.sleep(2)
