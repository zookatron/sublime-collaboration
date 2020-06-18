import httplib, socket, time, infinote, sys, xmpp, debuggy, infinote, sublime, sublime_plugin

class InfinoteClient(object):
	def __init__(self):
		self.xmpp_handler = xmpp.XMPPHandler()
		self._connected = False
		self.handlers = []
		self._connected_callback = None

	def is_connected(self):
		return self._connected

	def connect(self, server, port=5347, callback=None):
		self.xmpp_handler.start(server, port, self.recv, self.connected, self.disconnected)
		self._connected_callback = callback

	def connected(self):
		self._connected = True
		if self._connected_callback:
			self._connected_callback()
			self._connected_callback = None

	def disconnect(self):
		self.xmpp_handler.disconnect()

	def disconnected(self):
		self._connected = False

	def register(self, handler):
		self.handlers.append(handler)

	def unregister(self, handler):
		self.handlers.remove(handler)

	def recv(self, data):
		for handler in self.handlers:
			handler.handle_message(data)

	def send(self, data):
		if self.is_connected():
			self.xmpp_handler.send(data)

class InfDirectoryNode(object):
	def __init__(self, id, parent, name, type):
		self.id = id
		self.parent = parent
		self.name = name
		self.type = type
		self.children = []

	def __str__(self):
		return "<InfDirectoryNode id="+str(self.id)+" parent="+str(self.parent)+" name="+str(self.name)+" type="+str(self.type)+" children="+str(self.children)+">"

class InfDirectory(object):
	def __init__(self, load_callback=None):
		self._initialized = False
		self._get_directory_callback = None
		self._get_directory_seq = None
		self._get_directory_info = None
		self._get_directory_total = None
		self._get_directory_started = False
		self._load_callback = load_callback

	def _initialize(self, welcome):
		self._initialized = True
		if(self._load_callback): self._load_callback(self)

	def is_initialized(self):
		return self._initialized

	def handle_message(self, message):
		if(str(message.getAttr('name')) == "InfDirectory"):
			children = message.getPayload()
			for child in children:
				if(child.getName() == "welcome"):
					self._initialize(child)
				if(child.getName() == "explore-begin"):
					self._get_directory_total = int(child.getAttr('total'))
					self._get_directory_started = True
				if(child.getName() == "add-node"):
					if(not self._get_directory_started): return debuggy.print_debug("unexpected directory node: "+str(child))
					self._get_directory_info.append(InfDirectoryNode(int(child.getAttr('id')), int(child.getAttr('parent')), str(child.getAttr('name')), str(child.getAttr('type'))))
				if(child.getName() == "explore-end"):
					if(not self._get_directory_started): return debuggy.print_debug("unexpected directory end: "+str(child))
					self._get_directory_callback(self._get_directory_info)
					self._get_directory_callback = None
					self._get_directory_seq = None
					self._get_directory_info = None
					self._get_directory_total = None
					self._get_directory_started = False

	def get_directory(self, callback, directory=None):
		if(not self._initialized): return False
		dir_id = 0
		if directory:
			if(directory.type != "InfDirectory"): raise ValueError("Node is not a directory.")
			dir_id = directory.id
		self._get_directory_seq = get_seq()
		self._get_directory_callback = callback
		self._get_directory_info = []
		client.send('<group publisher="you" name="InfDirectory"><explore-node seq="'+str(self._get_directory_seq)+'" id="'+str(dir_id)+'"/></group>')

class InfUser(object):
	def __init__(self, id, name, status="active", time=0, caret=0, selection=0, hue=.5):
		self.id = id
		self.name = name
		self.status = status
		self.time = infinote.Vector(time)
		self.caret = caret
		self.selection = selection
		self.hue = hue

	def __str__(self):
		return "<InfUser id="+str(self.id)+" name="+str(self.name)+" status="+str(self.status)+" time="+str(self.time.toString())+" caret="+str(self.caret)+" selection="+str(self.selection)+" hue="+str(self.hue)+">"

class InfTextEditor(object):
	def __init__(self, node, load_callback=None):
		self.status = "unloaded"
		if(node.type != "InfText"): raise ValueError("Node is not a editable file.")
		self.node_id = node.id
		self.name = node.name
		self._request_seq = get_seq()
		self._sync_total = None
		self._sync_buffer = None
		self._sync_vector = None
		#self._sync_data = None
		self._load_callback = load_callback
		self._join_seq = None
		self._join_suffix = None
		self._group = None
		self.users = {}
		self.user_id = None
		#self.text = ""
		client.send('<group publisher="you" name="InfDirectory"><subscribe-session seq="'+str(self._request_seq)+'" id="'+str(self.node_id)+'"/></group>')

		self.log = []
		self._state = None #infinote.State()

	def add_to_log(self, executedRequest):
		print("THING CALLED")
		self.log.append(executedRequest)
		sublime_sync(self)

	def try_insert(self, params):
		#user, text
		print("insert trying:"+str(params))
		segment = infinote.Segment(params[0], params[3])
		buffer = infinote.Buffer([segment])
		#position, buffer
		operation = infinote.Insert(int(params[2]), buffer)
		#user, vector
		request = infinote.DoRequest(params[0], infinote.Vector(params[1]), operation)
		self._state.queue(request)
		self._state.executeAll()
		print(self.get_state())

	def try_delete(self, params):
		print("delete trying:"+str(params))
		operation = infinote.Delete(params[2], params[3])
		#user, vector, operation
		request = infinote.DoRequest(params[0], infinote.Vector(params[1]), operation)
		self._state.queue(request)
		self._state.executeAll()
		print(self.get_state())

	def try_undo(self, params):
		request = infinote.UndoRequest(params[0], self._state.vector)
		self._state.queue(request)
		self._state.executeAll()
		print(self.get_state())
		
	def get_state(self):
		return (self._state.vector.toString(), self._state.buffer.toString()) 
		
	def get_text(self):
		return self._state.buffer.toString()

	def _initialize(self):
		self.status = "loaded"
		if(self._load_callback): self._load_callback(self)

	def is_initialized(self):
		return self.status == "loaded"

	def handle_message(self, message):
		if(str(message.getAttr('name')) == "InfDirectory"):
			children = message.getPayload()
			for child in children:
				if(child.getName() == "subscribe-session"):
					if(str(child.getAttr('method')) != "central"):
						self.state = "error"
						debuggy.print_debug("unsupported method type: "+str(child))
						client.send('<group publisher="you" name="InfDirectory"><subscribe-nack id="'+str(self.node_id)+'"/></group>')
					else:
						self._group = str(child.getAttr('group'))
						client.send('<group publisher="you" name="InfDirectory"><subscribe-ack id="'+str(self.node_id)+'"/></group>')
				elif(child.getName() == "request-failed" and str(self._request_seq) in str(child.getAttr("seq"))):
					debuggy.print_debug("error domain "+child.getAttr("domain")+" code "+child.getAttr("code")+": "+child.getData())
					self.status = "error"
		elif(str(message.getAttr('name')) == self._group):
			children = message.getPayload()
			for child in children:
				if(child.getName() == "sync-begin"):
					self._sync_total = child.getAttr('num-messages')
					self._sync_buffer = infinote.Buffer()
					self._sync_vector = infinote.Vector()
					self._sync_log = []
					self.status = "syncing"
				elif(child.getName() == "sync-user"):
					self.users[int(child.getAttr("id"))] = InfUser(int(child.getAttr("id")), str(child.getAttr("name")), str(child.getAttr("status")), str(child.getAttr("time")), int(child.getAttr("caret")), int(child.getAttr("selection")), float(child.getAttr("hue")))
				elif(child.getName() == "sync-segment"):
					segment_user = int(child.getAttr("author"))
					segment_text = child.getPayload()[0]
					self._sync_buffer.segments.append(infinote.Segment(segment_user, segment_text))
				elif(child.getName() == "sync-request"):
					if(self.status == "syncing"):
						request_user = int(child.getAttr("user"))
						request_time = infinote.Vector(str(child.getAttr("time")))
						for request in child.getPayload():
							if(request.getName() == "insert" or request.getName() == "insert-caret"):
								request_position = int(request.getAttr("pos"))
								request_text = request.getData()
								self._sync_vector = self._sync_vector.overwrite(request_time)
								self._sync_log.append(infinote.DoRequest(request_user, request_time, infinote.Insert(int(request_position), infinote.Buffer([infinote.Segment(request_user, request_text)]))))
							if(request.getName() == "delete" or request.getName() == "delete-caret"):
								request_position = int(request.getAttr("pos"))
								request_length = int(request.getAttr("len")) if request.getAttr("len") else 1
								self._sync_vector = self._sync_vector.overwrite(request_time)
								self._sync_log.append(None)
								#TODO: handle delete sync :(
							if(request.getName() == "undo" or request.getName() == "undo-caret"):
								self._sync_vector = self._sync_vector.overwrite(request_time)
								self._sync_log.append(None)
								#TODO: handle undo sync :(
				elif(child.getName() == "sync-end"):
					self._sync_vector = self._sync_vector.all_incr()
					current_user.time = infinote.Vector(self._sync_vector)
					self._state = infinote.State(self._sync_buffer, self._sync_vector, self._sync_log)
					self._state.onexecute = self.add_to_log
					self._sync_buffer = None
					client.send('<group publisher="you" name="'+self._group+'"><sync-ack/></group>')
					self._join_seq = get_seq()
					self._join_suffix = 1
					client.send('<group publisher="you" name="'+self._group+'"><user-join seq="'+str(self._join_seq)+'" name="'+current_user.name+'" status="active" time="'+current_user.time.toString()+'" caret="0" hue="'+str(current_user.hue)+'"/></group>')
					self.state = "joining"
				elif(child.getName() == "request-failed"):
					if self.state == "joining" and str(self._join_seq) in str(child.getAttr("seq")):
						if(child.getAttr("domain") == "INF_USER_ERROR"):
							self._join_suffix += 1
							client.send('<group publisher="you" name="'+self._group+'"><user-join seq="'+str(self._join_seq)+'" name="'+current_user.name+' '+str(self._join_suffix)+'" status="active" time="'+current_user.time.toString()+'" caret="0" hue="0.71727399999999997"/></group>')
						else:
							debuggy.print_debug("error domain "+child.getAttr("domain")+" code "+child.getAttr("code")+": "+child.getData())
							self.status = "error"
				elif(child.getName() == "user-join"):
					self.users[int(child.getAttr("id"))] = InfUser(int(child.getAttr("id")), str(child.getAttr("name")), str(child.getAttr("status")), str(child.getAttr("time")), int(child.getAttr("caret")), int(child.getAttr("selection")), float(child.getAttr("hue")))
					if self.state == "joining" and str(self._join_seq) in child.getAttr("seq"):
						self.user_id = int(child.getAttr("id"))
						self._initialize()
				elif(child.getName() == "user-rejoin"):
					self.users[int(child.getAttr("id"))] = InfUser(int(child.getAttr("id")), str(child.getAttr("name")), str(child.getAttr("status")), str(child.getAttr("time")), int(child.getAttr("caret")), int(child.getAttr("selection")), float(child.getAttr("hue")))
					if self.state == "joining" and str(self._join_seq) in child.getAttr("seq"):
						self.user_id = int(child.getAttr("id"))
						self._initialize()
				elif(child.getName() == "request"):
					if(self.status == "loaded"):
						request_user = int(child.getAttr("user"))
						user = self.users[request_user]
						user.time = user.time.add(infinote.Vector(str(child.getAttr("time"))))
						request_time = user.time.toString()
						for request in child.getPayload():
							if(request.getName() == "move"):
								self.users[request_user].caret = int(request.getAttr("caret"))
								self.users[request_user].sel = int(request.getAttr("selection"))
							if(request.getName() == "insert" or request.getName() == "insert-caret"):
								user.time = user.time.incr(request_user)
								current_user.time = current_user.time.incr(request_user)
								request_position = int(request.getAttr("pos"))
								request_text = request.getData()
								self.try_insert([request_user, request_time, request_position, request_text])
								if(request.getName() == "insert-caret"):
									self.users[request_user].caret = request_position
									self.users[request_user].sel = 0
							if(request.getName() == "delete" or request.getName() == "delete-caret"):
								user.time = user.time.incr(request_user)
								current_user.time = current_user.time.incr(request_user)
								request_position = int(request.getAttr("pos"))
								request_length = int(request.getAttr("len")) if request.getAttr("len") else 1
								self.try_delete([request_user, request_time, request_position, request_length])
								if(request.getName() == "delete-caret"):
									self.users[request_user].caret = request_position
									self.users[request_user].sel = 0
							if(request.getName() == "undo" or request.getName() == "undo-caret"):
								user.time = user.time.incr(request_user)
								current_user.time = current_user.time.incr(request_user)
								self.try_undo([request_user, request_time])
								# if(request.getName() == "undo-caret"):
								# 	self.users[request_user].caret = request_position
								# 	self.users[request_user].sel = 0


	def __str__(self):
		return "<InfTextEditor id="+str(self.id)+" name="+str(self.name)+">"



#global state, yuck
my_view = None
client = None
directory = None
current_user = InfUser(0, "Derp")
seq = 0
def get_seq():
	global seq
	seq += 1
	return seq


def sublime_display(text):
	global my_view
	edit = my_view.begin_edit()
	my_view.replace(edit, sublime.Region(0, my_view.size()), text.replace("\r", "\n"))
	my_view.end_edit(edit)

def sublime_sync(editor):
	sublime.set_timeout(lambda: sublime_display(editor.get_text()), 0)

def display(text):
	sublime.set_timeout(lambda: sublime_display(text), 0)




def start_directory():
	global directory
	directory = InfDirectory(open_directory)
	client.register(directory)

def open_directory(directory):
	directory.get_directory(lambda x: display(x))

def open_file():
	client.register(InfTextEditor(InfDirectoryNode(2, 0, "cool", "InfText"), lambda x: sublime_sync(x)))




def start_client():
	global client
	client = InfinoteClient()
	client.connect('68.203.13.38', 6523, open_file)

def console_input():
	while not client.is_connected(): pass

	import msvcrt
	while client.is_connected():
		time.sleep(.2)
		if msvcrt.kbhit():
			c = msvcrt.getch()
			if(c == "s"):
				open_file()
			if(c == "q"):
				print("exiting")
				client.disconnect()

class ConnectToInfinoteServerCommand(sublime_plugin.ApplicationCommand):
	def run(self):
		global my_view
		my_view = sublime.active_window().new_file()
		my_view.set_scratch(True)
		start_client()

class DisconnectFromInfinoteServerCommand(sublime_plugin.ApplicationCommand):
	def run(self):
		if client and client.is_connected():
			client.disconnect()
			print("disconnected")
		else:
			print("already disconnected")