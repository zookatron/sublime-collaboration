mad_hatter = 0

def hat():
	global mad_hatter
	mad_hatter+=1
	return mad_hatter

def rack():
	return lambda: hat()