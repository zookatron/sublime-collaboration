import hat, syncQueue

class sessionHandler(object):
    def __init__(self, session, createAgent):
        self.session = session
        self.data = {'headers': self.session.headers, 'remoteAddress': self.session.address}
        self.agent = None

        self.lastSentDoc = None
        self.lastReceivedDoc = None

        self.docState = {}

        self.buffer = []
        self.bufferMsg = lambda msg: self.buffer.append(msg)
        self.session.on('message', self.bufferMsg)

        createAgent(self.data, self._agent_message)

        self.session.on('close', self._on_session_close)

    def _agent_message(self, error, agent_):
        if error:
            self.session.send({'auth':None, 'error':error})
            self.session.stop()
        else:
            self.agent = agent_
            self.session.send({'auth':self.agent.sessionId})

            self.session.removeListener('message', self.bufferMsg)
            [self.handleMessage(msg) for msg in self.buffer]
            self.buffer = None
            self.session.on('message', self.handleMessage)

    def _on_session_close(self):
        if not self.agent:
            return
        for docName in self.docState:
            if 'listener' in self.docState[docName] and self.docState[docName]['listener']:
                self.agent.removeListener(docName)
        self.docState = None

    def handleMessage(self, query, callback=None):
        error = None
        if not (('doc' in query and query['doc'] is None) or ('doc' in query and isinstance(query['doc'], (str, unicode))) or ('doc' not in query and self.lastReceivedDoc)):
            error = 'Invalid docName'
        if 'create' in query and query['create'] is not True:
            error = "'create' must be True or missing"
        if 'open' in query and query['open'] not in [True, False]:
            error = "'open' must be True, False or missing"
        if 'snapshot' in query and query['snapshot'] is not None:
            error = "'snapshot' must be None or missing"
        if 'type' in query and not isinstance(query['type'], (str, unicode)):
            error = "'type' invalid"
        if 'v' in query and (not isinstance(query['v'], (int, float)) or query['v'] < 0):
            error = "'v' invalid"

        if error:
            print("Invalid query {0} from {1}: {2}".format(query, self.agent.sessionId, error))
            self.session.abort()
            if callback:
              return callback()
            else:
              return

        if 'doc' in query:
            if query['doc'] is None:
                query['doc'] = self.lastReceivedDoc = hat.hat()
            else:
                self.lastReceivedDoc = query['doc']
        else:
            if not self.lastReceivedDoc:
                print("msg.doc missing in query {0} from {1}".format(query, self.agent.sessionId))
                return self.session.abort()
            query['doc'] = self.lastReceivedDoc

        if query['doc'] not in self.docState:
            self.docState[query['doc']] = {}

        if 'queue' not in self.docState[query['doc']]:
            def _queue_func(query, callback):
                if not self.docState:
                    return callback()

                if 'open' in query and query['open'] == False:
                    self.handleClose(query, callback)
                elif 'open' in query or ('snapshot' in query and query['snapshot'] is None) or 'create' in query:
                    self.handleOpenCreateSnapshot(query, callback)
                elif 'op' in query or ('meta' in query and 'path' in query['meta']):
                    self.handleOp(query, callback)
                else:
                    print("Invalid query {0} from {1}".format(json.dumps(query), self.agent.sessionId))
                    self.session.abort()
                    callback()

            self.docState[query['doc']]['queue'] = syncQueue.syncQueue(_queue_func)

        self.docState[query['doc']]['queue'](query)

    def send(self, response):
        if response['doc'] is self.lastSentDoc:
            del response['doc']
        else:
            self.lastSentDoc = response['doc']

        if self.session.ready():
            self.session.send(response)

    def open(self, docName, version, callback):
        if not self.docState:
            return callback('Session closed')
        if docName not in self.docState:
            self.docState[docName] = {'queue':None, 'listener':None}
        if 'listener' in self.docState[docName]:
            return callback('Document already open')

        def _doc_listener(opData, snapshot, oldsnapshot):
            if 'source' in opData['meta'] and opData['meta']['source'] is self.agent.sessionId:
                return
            opMsg = {'doc': docName, 'op': opData['op'], 'v': opData['v'], 'meta': opData['meta']}
            self.send(opMsg)

        self.docState[docName]['listener'] = _doc_listener 

        def _listen(error, v):
            if error:
                self.docState[docName]['listener'] = None
            callback(error, v)
        self.agent.listen(docName, version, self.docState[docName]['listener'], _listen)

    def close(self, docName, callback):
        if not self.docState:
            return callback('Session closed')
        if docName not in self.docState:
            return callback('Doc does not exist')

        listener = self.docState[docName]['listener']
        if not listener:
            return callback('Doc already closed')

        self.agent.removeListener(docName)
        self.docState[docName]['listener'] = None
        return callback()

    def handleOpenCreateSnapshot(self, query, finished):
        docName = query['doc']
        msg = {'doc':docName}

        def callback(error=None):
            if error:
                if 'open' in msg and msg['open'] == True:
                    self.close(docName)
                if 'open' in query and query['open'] == True:
                    msg['open'] = False
                if 'snapshot' in query:
                    msg['snapshot'] = None
                if 'create' in msg:
                    del msg['create']

                msg['error'] = error

            self.send(msg)
            finished()

        if 'doc' not in query:
            return callback('No docName specified')

        if 'create' in query and query['create'] == True:
            if 'type' not in query or not isinstance(query['type'], (str, unicode)):
                return callback('create:True requires type specified')

        if 'meta' in query:
            if not isinstance(query['meta'], dict):
                return callback('meta must be a dict')

        self.docData = None

        def step1Create():
            if 'create' not in query or query['create'] != True:
                return step2Snapshot()

            if self.docData:
                msg['create'] = False
                return step2Snapshot()
            else:
                def _agent_create(error=None):
                    if error == 'Document already exists':
                        def _agent_get_snapshot(error, data):
                            if error:
                                return callback(error)
                            self.docData = data
                            msg['create'] = False
                            return step2Snapshot()
                        self.agent.getSnapshot(docName, _agent_get_snapshot)
                    elif error:
                        return callback(error)
                    else:
                        msg['create'] = True
                        return step2Snapshot()
                return self.agent.create(docName, query['type'] if 'type' in query else None, query['meta'] if 'meta' in query else {}, _agent_create)

        def step2Snapshot():
            if 'snapshot' not in query or query['snapshot'] != None or ('create' in msg and msg['create'] == True):
                return step3Open()

            if self.docData:
                msg['v'] = self.docData['v']
                if not 'type' in query or query['type'] != self.docData['type'].name:
                    msg['type'] = self.docData['type'].name
                msg['snapshot'] = self.docData['snapshot']
            else:
                return callback('Document does not exist')

            return step3Open()

        def step3Open():
            if 'open' not in query or query['open'] != True:
                return callback()

            if 'type' in query and self.docData and query['type'] != self.docData['type'].name:
                return callback('Type mismatch')

            def _open_doc(error, version):
                if error:
                    return callback(error)
                msg['open'] = True
                msg['v'] = version
                return callback()
            return self.open(docName, query['v'] if 'v' in query else None, _open_doc)

        def _agent_get_snapshot(error, data):
              if error and error != 'Document does not exist':
                  return callback(error)
              self.docData = data
              return step1Create()

        if query['snapshot'] == None or query['open'] == True:
            return self.agent.getSnapshot(query['doc'], _agent_get_snapshot)
        else:
            return step1Create()

    def handleClose(self, query, callback):
        def _close_doc(error=None):
            if error:
                self.send({'doc':query['doc'], 'open':False, 'error':error})
            else:
                self.send({'doc':query['doc'], 'open':False})
            callback()
        self.close(query['doc'], _close_doc)

    def handleOp(self, query, callback):
        if 'v' not in query:
            raise Exception('No version specified')

        opData = {'v':query['v'], 'op':query['op'], 'meta':query['meta'] if 'meta' in query else {}, 'dupIfSource':query['dupIfSource'] if 'dupIfSource' in query else None}

        def _agent_submitop(error, appliedVersion):
            self.send({'doc':query['doc'], 'v':None, 'error':error} if error else{'doc':query['doc'], 'v':appliedVersion})
            callback()
        self.agent.submitOp(query['doc'], opData, callback if ('op' not in opData and 'meta' in opData and 'path' in opData['meta']) else _agent_submitop)
