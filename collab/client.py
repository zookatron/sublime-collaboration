import logging, doc, connection

class CollabClient:
    def __init__(self, host, port):
        self.docs = {}
        self.state = 'connecting'

        self.waiting_for_docs = []

        self.connected = False
        self.id = None

        self.socket = connection.ClientSocket(host, port)
        self.socket.on('message', self.socket_message)
        self.socket.on('error', self.socket_error)
        self.socket.on('open', self.socket_open)
        self.socket.on('close', self.socket_close)
        self.socket.start()

        self._events = {}

    def on(self, event, fct):
        if event not in self._events: self._events[event] = []
        self._events[event].append(fct)
        return self

    def removeListener(self, event, fct):
        if event not in self._events: return self
        self._events[event].remove(fct)
        return self

    def emit(self, event, *args):
        if event not in self._events: return self
        for callback in self._events[event]:
            callback(*args)
        return self

    def socket_open(self):
        self.set_state('handshaking')

    def socket_close(self, reason=''):
        self.set_state('closed', reason)
        self.socket = None

    def socket_error(self, error):
        self.emit('error', error)

    def socket_message(self, msg):
        if 'auth' in msg:
            if msg['auth'] is None or msg['auth'] == '':
                logging.warning('Authentication failed: {0}'.format(msg['error']))
                self.disconnect()
            else:
                self.id = msg['auth']
                self.set_state('ok')
            return

        if 'docs' in msg:
            if 'error' in msg:
                for callback in self.waiting_for_docs:
                    callback(msg['error'], None)
            else:
                for callback in self.waiting_for_docs:
                    callback(None, msg['docs'])
            self.waiting_for_docs = []
            return

        if 'doc' in msg and msg['doc'] in self.docs:
            self.docs[msg['doc']].on_message(msg)
        else:
            logging.error('Unhandled message {0}'.format(msg))

    def set_state(self, state, data=None):
        if self.state is state: return
        self.state = state

        if state is 'closed':
            self.id = None
        self.emit(state, data)

    def send(self, data):
        if self.state is not "closed":
            self.socket.send(data)

    def disconnect(self):
        if self.state is not "closed":
            self.socket.close()

    def get_docs(self, callback):
        if self.state is 'closed':
            return callback('connection closed', None)

        if self.state is 'connecting':
            return self.on('ok', lambda x: self.get_docs(callback))

        if not self.waiting_for_docs:
            self.send({"docs":None})
        self.waiting_for_docs.append(callback)

    def open(self, name, callback, **kwargs):
        if self.state is 'closed':
            return callback('connection closed', None)

        if self.state is 'connecting':
            return self.on('ok', lambda x: self.open(name, callback))

        if name in self.docs:
            return callback("doc {0} already open".format(name), None)

        newdoc = doc.CollabDoc(self, name, kwargs.get('snapshot', None))
        self.docs[name] = newdoc

        newdoc.open(lambda error, doc: callback(error, doc if not error else None))

    def closed(self, name):
        del self.docs[name]

