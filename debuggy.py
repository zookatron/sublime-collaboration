DEBUG = 1
def print_debug(message, level=1):
	if DEBUG and level >= DEBUG:
		print(message)
def get_debug():
	return DEBUG