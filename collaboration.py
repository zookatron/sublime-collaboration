import httplib, socket, time, infinote, sys, xmpp, debuggy, sublime, sublime_plugin

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
		if(message.getAttr('name') == "InfDirectory"):
			children = message.getPayload()
			for child in children:
				if(child.getName() == "welcome"):
					self._initialize(child)
				if(child.getName() == "explore-begin"):
					self._get_directory_total = child.getAttr('total')
					self._get_directory_started = True
				if(child.getName() == "add-node"):
					if(not self._get_directory_started): return debuggy.print_debug("unexpected directory node: "+str(child))
					self._get_directory_info.append(InfDirectoryNode(child.getAttr('id'), child.getAttr('parent'), child.getAttr('name'), child.getAttr('type')))
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
		self.time = time
		self.caret = caret
		self.selection = selection
		self.hue = hue

	def __str__(self):
		return "<InfDirectoryNode id="+str(self.id)+" name="+str(self.name)+" status="+str(self.status)+" time="+str(self.time)+" caret="+str(self.caret)+" selection="+str(self.selection)+" hue="+str(self.hue)+">"

class InfTextEditor(object):
	def __init__(self, node, load_callback=None):
		self.status = "unloaded"
		if(node.type != "InfText"): raise ValueError("Node is not a editable file.")
		self.node_id = node.id
		self.name = node.name
		self._request_seq = get_seq()
		self._sync_total = None
		self._sync_data = None
		self._load_callback = load_callback
		self._join_seq = None
		self._join_suffix = None
		self._group = None
		self.users = {}
		self.user_id = None
		self.text = ""
		client.send('<group publisher="you" name="InfDirectory"><subscribe-session seq="'+str(self._request_seq)+'" id="'+str(self.node_id)+'"/></group>')

	def _initialize(self):
		self.status = "loaded"
		if(self._load_callback): self._load_callback(self)

	def is_initialized(self):
		return self.status == "loaded"

	def handle_message(self, message):
		if(message.getAttr('name') == "InfDirectory"):
			children = message.getPayload()
			for child in children:
				if(child.getName() == "subscribe-session"):
					if(child.getAttr('method') != "central"):
						self.state = "error"
						debuggy.print_debug("unsupported method type: "+str(child))
						client.send('<group publisher="you" name="InfDirectory"><subscribe-nack id="'+str(self.node_id)+'"/></group>')
					else:
						self._group = child.getAttr('group')
						client.send('<group publisher="you" name="InfDirectory"><subscribe-ack id="'+str(self.node_id)+'"/></group>')
				if(child.getName() == "request-failed" and str(self._request_seq) in child.getAttr("seq")):
					debuggy.print_debug("error domain "+child.getAttr("domain")+" code "+child.getAttr("code")+": "+child.getData())
					self.status = "error"
		elif(message.getAttr('name') == self._group):
			children = message.getPayload()
			for child in children:
				if(child.getName() == "sync-begin"):
					self._sync_total = child.getAttr('num-messages')
					self._sync_data = ""
					self.status == "syncing"
				if(child.getName() == "sync-user"):
					self.users[child.getAttr("id")] = InfUser(child.getAttr("id"), child.getAttr("name"), child.getAttr("status"), child.getAttr("time"), child.getAttr("caret"), child.getAttr("selection"), child.getAttr("hue"))
				if(child.getName() == "sync-segment"):
					self._sync_data += child.getPayload()[0]
				if(child.getName() == "sync-end"):
					self.text = self._sync_data
					client.send('<group publisher="you" name="'+self._group+'"><sync-ack/></group>')
					self._join_seq = get_seq()
					self._join_suffix = 1
					client.send('<group publisher="you" name="'+self._group+'"><user-join seq="'+str(self._join_seq)+'" name="'+current_user.name+'" status="active" time="" caret="0" hue="'+str(current_user.hue)+'"/></group>')
					self.state = "joining"
				if(child.getName() == "request-failed"):
					if self.state == "joining" and str(self._join_seq) in child.getAttr("seq"):
						if(child.getAttr("domain") == "INF_USER_ERROR"):
							self._join_suffix += 1
							client.send('<group publisher="you" name="'+self._group+'"><user-join seq="'+str(self._join_seq)+'" name="'+current_user.name+' '+str(self._join_suffix)+'" status="active" time="" caret="0" hue="0.71727399999999997"/></group>')
						else:
							debuggy.print_debug("error domain "+child.getAttr("domain")+" code "+child.getAttr("code")+": "+child.getData())
							self.status = "error"
				if(child.getName() == "user-join"):
					self.users[child.getAttr("id")] = InfUser(child.getAttr("id"), child.getAttr("name"), child.getAttr("status"), child.getAttr("time"), child.getAttr("caret"), child.getAttr("selection"), child.getAttr("hue"))
					if self.state == "joining" and str(self._join_seq) in child.getAttr("seq"):
						self.user_id = child.getAttr("id")
						self._initialize()
				if(child.getName() == "user-rejoin"):
					self.users[child.getAttr("id")] = InfUser(child.getAttr("id"), child.getAttr("name"), child.getAttr("status"), child.getAttr("time"), child.getAttr("caret"), child.getAttr("selection"), child.getAttr("hue"))
					if self.state == "joining" and str(self._join_seq) in child.getAttr("seq"):
						self.user_id = child.getAttr("id")
						self._initialize()

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


def sublime_display(x):
	global my_view
	edit = my_view.begin_edit()
	my_view.insert(edit, 0, x.replace("\r", "\n"))
	my_view.end_edit(edit)
	#sys.stdout.write("["+", ".join(str(e) for e in x)+"]")

def display(x):
	sublime.set_timeout(lambda: sublime_display(x), 0)
	#print(x)
	client.disconnect()

def start_directory():
	global directory
	directory = InfDirectory(open_directory)
	client.register(directory)

def open_directory(directory):
	directory.get_directory(lambda x: display(x))

def open_file():
	client.register(InfTextEditor(InfDirectoryNode(2, 0, "cool", "InfText"), lambda x: display(x.text)))

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