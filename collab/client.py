import collabdoc, json, doctypes, connection, websocket

class CollabClient:
    def __init__(self, host, port):
        self.docs = {}
        self.state = 'connecting'
        self.lastError = None

        self.connected = False
        self.id = None


        def _socket_onopen(reason=''):
            self.setState('disconnected', reason)
            if reason in ['Closed', 'Stopped by server']:
                self.setState('stopped', self.lastError or reason)

        def _socket_onopen():
            self.lastError = self.lastReceivedDoc = self.lastSentDoc = None
            self.setState('handshaking')

        self.socket = websocket.ClientWebSocket(host, port)
        self.socket.on('message', self._socket_message)
        self.socket.on('error', lambda e: self.emit('error', e))
        self.socket.on('connecting', lambda: self.setState('connecting'))
        self.socket.on('open', _socket_onopen)
        self.socket.on('close', _socket_onopen)
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

    def _socket_message(self, msg):
        if 'auth' in msg:
            if msg['auth'] == '':
                self.lastError = msg['error']
                self.disconnect()
                return self.emit('connect failed', msg.error)
            else:
                self.id = msg['auth']
                self.setState('ok')
                return

        if 'doc' in msg:
            docName = msg['doc']
            self.lastReceivedDoc = docName
        else:
            msg['doc'] = docName = self.lastReceivedDoc

        if docName in self.docs:
            self.docs[docName]._onMessage(msg)
        else:
            print('Unhandled message {1}'.format(msg))

    def setState(self, state, data=None):
        if self.state is state:
          return
        self.state = state

        if state is 'disconnected':
            self.id = None
        self.emit(state, data)

        for docName in self.docs:
            self.docs[docName]._connectionStateChanged(state, data)

    def send(self, data):
        docName = data['doc']

        if docName is self.lastSentDoc:
            del data['doc']
        else:
            self.lastSentDoc = docName

        self.socket.send(json.dumps(data))

    def disconnect(self):
        self.socket.close()
 
    def makeDoc(self, name, data, callback):
        if name in self.docs:
            raise Exception("Doc {1} already open".format(name))

        doc = collabdoc.CollabDoc(self, name, data)
        self.docs[name] = doc

        def _doc_open(error):
            if error:
                del self.docs[name]
            callback(error, doc if not error else None)
        doc.open(_doc_open)

    def openExisting(self, docName, callback):
        if self.state is 'stopped':
            return callback('connection closed')
        if docName in self.docs:
            return callback(None, self.docs[docName])
        self.makeDoc(docName, {}, callback)

    def open(self, docName, type, callback):
        if self.state is 'stopped':
            return callback('connection closed', None)

        if self.state is 'connecting':
            self.on('handshaking', lambda x: self.open(docName, type, callback))
            return

        if isinstance(type, (str, unicode)):
            type = doctypes.types.get(type, None)

        if not type:
            return callback("OT code for document type missing", None)

        if not docName:
            raise Exception('Server-generated random doc names are not currently supported')

        if docName in self.docs:
            doc = self.docs[docName]
            if doc.type.name == type.name:
                callback(None, doc)
            else:
                callback('Type mismatch', doc)
            return

        self.makeDoc(docName, {'create':True, 'type':type.name}, callback)