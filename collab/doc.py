import functools, optransform

class CollabDoc():
    def __init__(self, connection, name, snapshot=None):
        self.connection = connection
        self.name = name
        self.version = 0
        self.snapshot = snapshot
        self.state = 'closed'

        self._events = {}

        self.on('remoteop', self.on_doc_remoteop)

        self.connection.on('closed', lambda data: self.set_state('closed', data))

        self.inflight_op = None
        self.inflight_callbacks = []
        self.pending_op = None
        self.pending_callbacks = []
        self.server_ops = {}

        self._open_callback = None

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
            if self._open_callback: self._open_callback(data if data else "disconnected", None)

        self.emit(state, data)

    def __len__(self):
        return len(self.snapshot)

    def get_text(self):
        return self.snapshot

    def insert(self, pos, text, callback=None):
        op = [{'p':pos, 'i':text}]
        self.submit_op(op, callback)
        return op
    
    def delete(self, pos, length, callback=None):
        op = [{'p':pos, 'd':self.snapshot[pos:(pos+length)]}]
        self.submit_op(op, callback)
        return op

    def on_doc_remoteop(self, op, snapshot):
        for component in op:
            if 'i' in component:
                self.emit('insert', component['p'], component['i'])
            else:
                self.emit('delete', component['p'], component['d'])

    def open(self, callback=None):
        if self.state != 'closed': return

        self.connection.send({'doc': self.name, 'open': True, 'snapshot': self.snapshot, 'create': True})
        self.set_state('opening')

        self._open_callback = callback

    def close(self):
        self.connection.send({'doc':self.name, 'open':False})
        self.set_state('closed', 'closed by local client')

    def submit_op(self, op, callback):
        op = optransform.normalize(op)
        self.snapshot = optransform.apply(self.snapshot, op)

        if self.pending_op is not None:
            self.pending_op = optransform.compose(self.pending_op, op)
        else:
            self.pending_op = op

        if callback:
            self.pending_callbacks.append(callback)

        self.emit('change', op)

        self.flush()

    def flush(self):
        if not (self.connection.state == 'ok' and self.inflight_op is None and self.pending_op is not None):
            return

        self.inflight_op = self.pending_op
        self.inflight_callbacks = self.pending_callbacks

        self.pending_op = None
        self.pending_callbacks = []

        self.connection.send({'doc':self.name, 'op':self.inflight_op, 'v':self.version})

    def apply_op(self, op, is_remote):
        oldSnapshot = self.snapshot
        self.snapshot = optransform.apply(self.snapshot, op)

        self.emit('change', op, oldSnapshot)
        if is_remote:
            self.emit('remoteop', op, oldSnapshot)

    def on_message(self, msg):
        if msg['doc'] != self.name:
            return self.emit('error', "Expected docName '{0}' but got {1}".format(self.name, msg['doc']))

        if 'open' in msg:
            if msg['open'] == True:

                if 'create' in msg and msg['create'] and not self.snapshot:
                    self.snapshot = ''
                else:
                    if 'snapshot' in msg:
                        self.snapshot = msg['snapshot']

                if 'v' in msg:
                    self.version = msg['v']

                self.state = 'open'
                self.emit('open')
                
                if self._open_callback:
                    self._open_callback(None, self)
                    self._open_callback = None
     
            elif msg['open'] == False:
                if 'error' in msg:
                    self.emit('error', msg['error'])
                    if self._open_callback:
                        self._open_callback(msg['error'], None)
                        self._open_callback = None

                self.set_state('closed', 'closed by remote server')
                self.connection.closed(self.name)

        elif 'op' not in msg and 'v' in msg:
            if msg['v'] != self.version:
                return self.emit('error', "Expected version {0} but got {1}".format(self.version, msg['v']))

            oldinflight_op = self.inflight_op
            self.inflight_op = None

            if 'error' in msg:
                error = msg['error']
                undo = optransform.invert(oldinflight_op)
                if self.pending_op:
                    self.pending_op, undo = optransform.transform_x(self.pending_op, undo)
                for callback in self.inflight_callbacks:
                    callback(error, None)
            else:
                self.server_ops[self.version] = oldinflight_op
                self.version += 1
                for callback in self.inflight_callbacks:
                    callback(None, oldinflight_op)

            self.flush()

        elif 'op' in msg and 'v' in msg:
            if msg['v'] != self.version:
                return self.emit('error', "Expected version {0} but got {1}".format(self.version, msg['v']))

            op = msg['op']
            self.server_ops[self.version] = op

            if self.inflight_op is not None:
                self.inflight_op, op = optransform.transform_x(self.inflight_op, op)
            if self.pending_op is not None:
                self.pending_op, op = optransform.transform_x(self.pending_op, op)
                
            self.version += 1
            self.apply_op(op, True)
        else:
            logging.error('Unhandled document message: {0}'.format(msg))
