import session, model, threading, connection, websocket

# connection should implement the following interface:
#     headers
#     address
#     abort()
#     stop()
#     ready()
#     send(msg)
#     removeListener()
#     on(event, handler) - where event can be 'message' or 'close'

class CollabServer(object):
	def __init__(self, options=None):
		if not options:
			options = {}

		self.options = options
		self.model = model.CollabModel(options)
		self.host = self.options.get('host', '127.0.0.1')
		self.port = self.options.get('port', 6633)

		self.server = websocket.WebSocketServer(self.host, self.port)
		self.server.on('connection', lambda connection: session.CollabUserSession(connection, self.model))

	def run_forever(self):
		threading.Thread(target=self.server.run_forever).start()

	def close(self):
		self.model.close()
		self.server.close()
