import threading
from .session import CollabSession
from .model import CollabModel
from .connection import SocketServer

class CollabServer(object):
    def __init__(self, options=None):
        if not options:
            options = {}

        self.options = options
        self.model = CollabModel(options)
        self.host = self.options.get('host', '127.0.0.1')
        self.port = self.options.get('port', 6633)
        self.next_user_id = 0

        self.server = SocketServer(self.host, self.port)
        self.server.on('connection', lambda connection: CollabSession(connection, self.model, self.new_user_id()))

    def run_forever(self):
        threading.Thread(target=self.server.run_forever).start()

    def new_user_id(self):
        self.next_user_id += 1
        return self.next_user_id

    def close(self):
        self.model.close()
        self.server.close()
