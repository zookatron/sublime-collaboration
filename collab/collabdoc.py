import doctypes, functools

class CollabDoc():
    def __init__(self, connection, name, doctype, snapshot=None):
        self.connection = connection
        self.name = name
        self.version = 0
        self.snapshot = snapshot
        self.state = 'closed'

        self._events = {}

        self.doctype = doctype()
        if hasattr(doctype, 'api'):
            for var in self.doctype.api.__class__.__dict__:
                try:
                    self.__dict__[var] = functools.partial(self.doctype.api.__class__.__dict__[var], self)
                except:
                    self.__dict__[var] = self.doctype.api.__class__.__dict__[var]
            if hasattr(self, '_register'):
                self._register()

        self.connection.on('closed', lambda data: self.set_state('closed', data))

        self.inflightOp = None
        self.inflightCallbacks = []
        self.pendingOp = None
        self.pendingCallbacks = []
        self.serverOps = {}

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

    def set_state(self, state, data=None):
        if self.state is state: return
        self.state = state

        if state is 'closed':
            if self._openCallback: self._openCallback(data, None)

        self.emit(state, data)
    
    def open(self, callback=None):
        if self.state != 'closed': return

        self.connection.send({'doc': self.name, 'open': True, 'snapshot': self.snapshot, 'type': self.doctype.name, 'create': True})
        self.set_state('opening')

        self._openCallback = callback

    def close(self):
        self.connection.send({'doc':self.name, 'open':False})
        self.set_state('closed', 'closed by local client')

    def submitOp(self, op, callback):
        op = self.doctype.normalize(op)

        self.snapshot = self.doctype.apply(self.snapshot, op)

        if self.pendingOp is not None:
            self.pendingOp = self.doctype.compose(self.pendingOp, op)
        else:
            self.pendingOp = op

        if callback:
            self.pendingCallbacks.append(callback)

        self.emit('change', op)

        self.flush()

    def flush(self):
        if not (self.connection.state == 'ok' and self.inflightOp is None and self.pendingOp is not None):
            return

        self.inflightOp = self.pendingOp
        self.inflightCallbacks = self.pendingCallbacks

        self.pendingOp = None
        self.pendingCallbacks = []

        self.connection.send({'doc':self.name, 'op':self.inflightOp, 'v':self.version})

    def on_message(self, msg):
        if msg['doc'] != self.name:
            return self.emit('error', "Expected docName '{0}' but got {1}".format(self.name, msg['doc']))

        def _otApply(docOp, isRemote):
            oldSnapshot = self.snapshot
            self.snapshot = self.doctype.apply(self.snapshot, docOp)

            self.emit('change', docOp, oldSnapshot)
            if isRemote:
                self.emit('remoteop', docOp, oldSnapshot)

        if 'open' in msg:
            if msg['open'] == True:

                if 'create' in msg and msg['create'] and not self.snapshot:
                    self.snapshot = self.doctype.create()
                else:
                    if 'snapshot' in msg:
                        self.snapshot = msg['snapshot']

                if 'v' in msg:
                    self.version = msg['v']

                self.state = 'open'
                self.emit('open')
                
                if self._openCallback:
                    self._openCallback(None, self)
                    self._openCallback = None
     
            elif msg['open'] == False:
                if 'error' in msg:
                    self.emit('error', msg['error'])
                    if self._openCallback:
                        self._openCallback(msg['error'], None)
                        self._openCallback = None

                self.set_state('closed', 'closed by remote server')
                self.connection.closed(self.name)

        elif 'op' not in msg and 'v' in msg:
            if msg['v'] != self.version:
                return self.emit('error', "Expected version {0} but got {1}".format(self.version, msg['v']))
                
            oldInflightOp = self.inflightOp
            self.inflightOp = None

            if 'error' in msg:
                error = msg['error']
                undo = self.doctype.invert(oldInflightOp)
                if self.pendingOp:
                    self.pendingOp, undo = self.doctype.transformX(self.pendingOp, undo)
                _otApply(undo, True)

                for callback in self.inflightCallbacks:
                    callback(error, None)
            else:
                self.serverOps[self.version] = oldInflightOp
                self.version += 1
                for callback in self.inflightCallbacks:
                    callback(None, oldInflightOp)

            self.flush()

        elif 'op' in msg and 'v' in msg:
            if msg['v'] != self.version:
                return self.emit('error', "Expected version {0} but got {1}".format(self.version, msg['v']))

            op = msg['op']
            self.serverOps[self.version] = op

            if self.inflightOp is not None:
                [self.inflightOp, op] = self.doctype.transformX(self.inflightOp, op)
            if self.pendingOp is not None:
                [self.pendingOp, op] = self.doctype.transformX(self.pendingOp, op)
                
            self.version += 1
            _otApply(op, True)

        else:
            logging.error('Unhandled document message: {0}'.format(msg))
