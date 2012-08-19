import doctypes, functools

class CollabDoc():
    def __init__(self, connection, name, openData):
        self.connection = connection
        self.name = name

        self._events = {}

        if not openData: openData = {}
        self.version = openData.get('v', 0)
        self.snapshot = openData.get('snaphot', None)
        self.type = None
        if 'type' in openData:
            self._setType(openData['type'])

        self.state = 'closed'
        self.created = None
        self.autoOpen = False
        self._create = openData['create'] if 'create' in openData else False
        self.inflightOp = None
        self.inflightCallbacks = []
        self.inflightSubmittedIds = []
        self.pendingOp = None
        self.pendingCallbacks = []
        self.serverOps = {}

        self._closeCallback = None
        self._openCallback = None

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

    def _xf(self, client, server):
        if hasattr(self.type, 'transformX'):
            self.type.transformX(client, server)
        else:
            client_ = self.type.transform(client, server, 'left')
            server_ = self.type.transform(server, client, 'right')
            return [client_, server_]
    
    def _otApply(self, docOp, isRemote):
        oldSnapshot = self.snapshot
        self.snapshot = self.type.apply(self.snapshot, docOp)

        self.emit('change', docOp, oldSnapshot)
        if isRemote:
            self.emit('remoteop', docOp, oldSnapshot)

    def _connectionStateChanged(self, state, data):
        if state == 'disconnected':
            self.state = 'closed'
            if self.inflightOp:
                self.inflightSubmittedIds.append(self.connection.id)
            self.emit('closed')
        elif state == 'ok':
            if self.autoOpen:
                self.open()
        elif state == 'stopped':
            if self._openCallback:
                self._openCallback(data)
        self.emit(state, data)

    def _setType(self, type):
        if isinstance(type, (str, unicode)):
            type = doctypes.types[type]

        if type and not hasattr(type, 'compose'):
            raise Exception('Support for types without compose() is not implemented')

        self.type = type()
        if hasattr(type, 'api'):
            for var in type.api.__class__.__dict__:
                try:
                    self.__dict__[var] = functools.partial(type.api.__class__.__dict__[var], self)
                except:
                    self.__dict__[var] = type.api.__class__.__dict__[var]
            if hasattr(self, '_register'):
                self._register()

    def _onMessage(self, msg):
        if 'open' in msg:
            if msg['open'] == True:
                self.state = 'open'
                self._create = False
                if not self.created:
                    self.created = msg['create'] if 'create' in msg else False

                if 'type' in msg:
                    self._setType(msg['type'])
                if 'create' in msg and msg['create']:
                    self.created = True
                    self.snapshot = self.type.create()
                else:
                    if self.created != True:
                        self.created = False
                    if 'snapshot' in msg:
                        self.snapshot = msg['snapshot']

                if 'v' in msg:
                    self.version = msg['v']

                if self.inflightOp:
                    response = {'doc': self.name, 'op': self.inflightOp, 'v': self.version}
                    if len(self.inflightSubmittedIds):
                        response.dupIfSource = self.inflightSubmittedIds
                    self.connection.send(response)
                else:
                    self.flush()

                self.emit('open')
                
                if self._openCallback:
                    self._openCallback(None)
     
            elif msg['open'] == False:
                if 'error' in msg:
                    self.emit('error', msg['error'])
                    if self._openCallback:
                        self._openCallback(msg['error'])

                self.state = 'closed'
                self.emit('closed')

                if self._closeCallback:
                    self._closeCallback()
                self._closeCallback = None

        elif 'op' in msg and msg['op'] is None and msg['error'] == 'Op already submitted':
            pass

        elif ('op' not in msg and 'v' in msg) or ('op' in msg and 'meta' in msg and 'source' in msg['meta'] and msg['meta']['source'] in self.inflightSubmittedIds):
            oldInflightOp = self.inflightOp
            self.inflightOp = None
            self.inflightSubmittedIds = []

            if 'error' in msg:
                error = msg['error']
                if self.type.invert:
                    undo = self.type.invert(oldInflightOp)
                    if self.pendingOp:
                        self.pendingOp, undo = self._xf(self.pendingOp, undo)
                    self._otApply(undo, True)
                else:
                    self.emit('error', "Op apply failed ({0}) and the op could not be reverted".format(error))

                for callback in self.inflightCallbacks:
                    callback(error)
            else:
                if not msg['v'] == self.version:
                    raise Exception('Invalid version from server')

                self.serverOps[self.version] = oldInflightOp
                self.version+=1
                for callback in self.inflightCallbacks:
                    callback(None, oldInflightOp)

            self.flush()

        elif 'op' in msg:
            if msg['v'] < self.version:
                return

            if msg['doc'] != self.name:
                return self.emit('error', "Expected docName '{0}' but got {1}".format(self.name, msg['doc']))
            if msg['v'] != self.version:
                return self.emit('error', "Expected version {0} but got {1}".format(self.version, msg['v']))

            op = msg['op']
            self.serverOps[self.version] = op

            docOp = op
            if self.inflightOp is not None:
                [self.inflightOp, docOp] = self._xf(self.inflightOp, docOp)
            if self.pendingOp is not None:
                [self.pendingOp, docOp] = self._xf(self.pendingOp, docOp)
                
            self.version+=1
            self._otApply(docOp, True)

        elif 'meta' in msg:
            path = msg['meta']['path']
            value = msg['meta']['value']

            if path:
                if path[0] == 'shout':
                    return self.emit('shout', value)
                else:
                    print('Unhandled meta op: {0}'.format(msg))

        else:
            print('Unhandled document message: {0}'.format(msg))

    def flush(self):
        if not (self.connection.state == 'ok' and self.inflightOp is None and self.pendingOp is not None):
            return

        self.inflightOp = self.pendingOp
        self.inflightCallbacks = self.pendingCallbacks

        self.pendingOp = None
        self.pendingCallbacks = []

        self.connection.send({'doc':self.name, 'op':self.inflightOp, 'v':self.version})

    def submitOp(self, op, callback):
        if self.type.normalize:
            op = self.type.normalize(op)

        self.snapshot = self.type.apply(self.snapshot, op)

        if self.pendingOp is not None:
            self.pendingOp = self.type.compose(self.pendingOp, op)
        else:
            self.pendingOp = op

        if callback:
            self.pendingCallbacks.append(callback)

        self.emit('change', op)

        self.flush() #setTimeout(self.flush, 0) -- A timeout is used so if the user sends multiple ops at the same time, they'll be composed & sent together.
    
    def shout(self, msg):
        self.connection.send({'doc':self.name, 'meta':{'path':['shout'], 'value':msg}})

    def open(self, callback=None):
        self.autoOpen = True
        if self.state != 'closed':
            return

        message = {'doc': self.name, 'open': True}

        if not self.snapshot:
            message['snapshot'] = None
        if self.type:
            message['type'] = self.type.name
        if self.version:
            message['v'] = self.version
        if self._create:
            message['create'] = True

        self.connection.send(message)

        self.state = 'opening'

        def tempOpenCallback(error):
            self._openCallback = None
            if callback:
                callback(error)
        self._openCallback = tempOpenCallback

    def close(self, callback=None):
        self.autoOpen = False
        if self.state is 'closed':
            return callback() if callback else None

        self.connection.send({'doc':self.name, 'open':False})

        self.state = 'closed'

        self.emit('closing')
        self._closeCallback = callback

