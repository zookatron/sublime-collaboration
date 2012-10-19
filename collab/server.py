import threading, session, model, connection

class CollabServer(object):
	def __init__(self, options=None):
		if not options:
			options = {}

		self.options = options
		self.model = model.CollabModel(options)
		self.host = self.options.get('host', '127.0.0.1')
		self.port = self.options.get('port', 6633)
		self.idtrack = 0

		self.server = connection.SocketServer(self.host, self.port)
		self.server.on('connection', lambda connection: session.CollabSession(connection, self.model, self.new_id()))

	def run_forever(self):
		threading.Thread(target=self.server.run_forever).start()

	def new_id(self):
		self.idtrack += 1
		return self.idtrack

	def close(self):
		self.model.close()
		self.server.close()
