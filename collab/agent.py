import hat, doctypes, time

class CollabAgent(object):
    def __init__(self, data, auth, model, options):
        self.auth = auth
        self.model = model
        self.options = options
        self.sessionId = hat.hat()
        self.connectTime = time.time()
        self.headers = data['headers']
        self.remoteAddress = data['remoteAddress']

        self.listeners = {}

        self.name = None

    def doAuth(self, actionData, name, userCallback, acceptCallback):
        action = actionData if actionData else {}
        action['name'] = name

        if name == 'connect':
            action['type'] = 'connect'
        elif name == 'create':
            action['type'] = 'create'
        elif name in ['get snapshot', 'get ops', 'open']:
            action['type'] = 'read'
        elif name == 'submit op':
            action['type'] = 'update'
        elif name == 'submit meta':
            action['type'] = 'update'
        elif name == 'delete':
            action['type'] = 'delete'
        else:
            raise Exception("Invalid action name {0}".format(name))

        responded = False

        def _action_reject():
            if responded:
                raise Exception('Multiple accept/reject calls made')
            #responded = True
            userCallback('forbidden', None)
        action['reject'] = _action_reject

        def _action_accept():
            if responded:
                raise Exception('Multiple accept/reject calls made')
            #responded = True
            acceptCallback()
        action['accept'] = _action_accept

        return self.auth(self, action)

    def disconnect(self):
        [self.model.removeListener(docName, self.listeners[docName]) for docName in self.listeners]

    def getOps(self, docName, start, end, callback):
        self.doAuth({'docName':docName, 'start':start, 'end':end}, 'get ops', callback, lambda: self.model.getOps(docName, start, end, callback))

    def getSnapshot(self, docName, callback):
        self.doAuth({'docName':docName}, 'get snapshot', callback, lambda: self.model.getSnapshot(docName, callback))
    
    def create(self, docName, type, meta, callback):
        if isinstance(type, (str, unicode)):
            type = doctypes.types[type]

        meta = {}

        if self.name:
            meta['creator'] = self.name
        meta['ctime'] = meta['mtime'] = time.time()

        self.doAuth({'docName':docName, 'docType':type, 'meta':meta}, 'create', callback, lambda: self.model.create(docName, type, meta, callback))

    def submitOp(self, docName, opData, callback):
        opData['meta']['source'] = self.sessionId
        if 'meta' not in opData or not opData['meta']: opData['meta'] = {}
        dupIfSource = opData['dupIfSource'] if 'dupIfSource' in opData and opData['dupIfSource'] else []

        if 'op' in opData:
            self.doAuth({'docName':docName, 'op':opData['op'], 'v':opData['v'], 'meta':opData['meta'], 'dupIfSource':dupIfSource}, 'submit op', callback, lambda: self.model.applyOp(docName, opData, callback))
        else:
            self.doAuth({'docName':docName, 'meta':opData['meta']}, 'submit meta', callback, lambda: self.model.applyMetaOp(docName, opData, callback))

    def delete(self, docName, callback):
        self.doAuth({'docName':docName}, 'delete', callback, lambda: self.model.delete(docName, callback))
    
    def listen(self, docName, version, listener, callback):
        authOps = (lambda c: self.doAuth({'docName':docName, 'start':version, 'end':None}, 'get ops', callback, c)) if version else (lambda c: c())

        def _do_authops():
            def _do_auth():
                if docName in self.listeners:
                    if callback:
                        return callback('Document is already open')
                    return
                self.listeners[docName] = listener

                def _model_listen(error, v):
                    if error and docName in self.listeners:
                      del self.listeners[docName]

                    if callback:
                        return callback(error, v)
                self.model.listen(docName, version, listener, _model_listen)

            self.doAuth({'docName':docName, 'v':version} if version else {'docName':docName}, 'open', callback, _do_auth)

        authOps(_do_authops)

    def removeListener(self, docName):
        if docName not in self.listeners:
            raise Exception('Document is not open')
        self.model.removeListener(docName, self.listeners[docName])
        del self.listeners[docName]

def createAgent(model, options):
    def _default_auth(agent, action):
        if action['type'] in ['connect', 'read', 'create', 'update']:
            action['accept']()
        else:
            action['reject']()
    auth = options['auth'] if 'auth' in options else _default_auth

    def _returns(data, callback):
        agent = CollabAgent(data, auth, model, options)
        return agent.doAuth(None, 'connect', callback, lambda: callback(None, agent))
    return _returns
