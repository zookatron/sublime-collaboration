import hat, syncQueue, logging

class CollabUserSession(object):
    def __init__(self, connection, model):
        self.connection = connection
        self.model = model

        self.docs = {}
        self.userid = hat.hat()

        if self.connection.ready():
            self.on_session_create()
        else:
            self.connection.on('ok', lambda: self.on_session_create)
        self.connection.on('close', self.on_session_close)
        self.connection.on('message', self.on_session_message)

    def on_session_create(self):
        self.connection.send({'auth':self.userid})

    def on_session_close(self):
        for docname in self.docs:
            if 'listener' in self.docs[docname]:
                self.model.remove_listener(docname, self.docs[docname]['listener'])
        self.docs = None

    def on_session_message(self, query, callback=None):
        error = None
        if 'doc' not in query or not isinstance(query['doc'], (str, unicode)):
            error = 'doc name invalid or missing'
        if 'create' in query and query['create'] is not True:
            error = "'create' must be True or missing"
        if 'create' in query and query['create'] is True and 'type' not in query:
             error = "create:True requires type specified"
        if 'create' not in query and 'type' in query:
            error = "'type' must only be set for create commands"
        if 'open' in query and query['open'] not in [True, False]:
            error = "'open' must be True, False or missing"
        if 'type' in query and not isinstance(query['type'], (str, unicode)):
            error = "'type' invalid"
        if 'v' in query and (not isinstance(query['v'], (int, float)) or query['v'] < 0):
            error = "'v' invalid"

        if error:
            logging.error("Invalid query {0} from {1}: {2}".format(query, self.userid, error))
            self.connection.abort()
            return callback() if callback else None

        if query['doc'] not in self.docs:
            self.docs[query['doc']] = {'queue': syncQueue.syncQueue(self.handle_message)}

        self.docs[query['doc']]['queue'](query)

    def handle_message(self, query, callback):
        if not self.docs:
            return callback()
        
        if 'open' in query and query['open'] == False:
            if 'listener' not in self.docs[query['doc']]:
                self.send({'doc':query['doc'], 'open':False, 'error':'Doc is not open'})
            else:
                self.model.remove_listener(query['doc'], self.docs[query['doc']]['listener'])
                del self.docs[query['doc']]['listener']
                self.send({'doc':query['doc'], 'open':False})
            callback()

        elif 'open' in query or ('snapshot' in query and query['snapshot'] is None) or 'create' in query:
            self.handle_opencreatesnapshot(query, callback)

        elif 'op' in query and 'v' in query:
            def apply_op(error, appliedVersion):
                self.send({'doc':query['doc'], 'v':None, 'error':error} if error else {'doc':query['doc'], 'v':appliedVersion})
                callback()
            self.model.applyOp(query['doc'], {'doc':query['doc'], 'v':query['v'], 'op':query['op'], 'source':self.userid}, apply_op)

        else:
            logging.error("Invalid query {0} from {1}".format(query, self.userid))
            self.connection.abort()
            callback()

    def on_remote_message(self, message, snapshot, oldsnapshot):
        if message['source'] is self.userid: return
        self.send(message)

    def send(self, msg):
        self.connection.send(msg)

    def handle_opencreatesnapshot(self, query, callback):
        def finished(message):
            if 'error' in message:
                if 'create' in query and 'create' not in message: message['create'] = False
                if 'snapshot' in query and 'snapshot' not in message: message['snapshot'] = None
                if 'open' in query and 'open' not in message: message['open'] = False
            self.send(message)
            callback()

        def step1Create(message):
            if 'create' not in query:
                return step2Snapshot(message)

            def model_create(error=None):
                if error == 'Document already exists':
                    message['create'] = False
                    if 'open' not in query:
                        message['error'] = error
                        return finished(message)
                    return step2Snapshot(message)
                elif error:
                    message['create'] = False
                    message['error'] = error
                    return finished(message)
                else:
                    message['create'] = True
                    return step2Snapshot(message)

            self.model.create(query['doc'], query['type'], query.get('snapshot', None), model_create)

        def step2Snapshot(message):
            if 'snapshot' not in query or query['snapshot'] is not None or message['create']:
                return step3Open(message)

            def model_get_data(error, data):
                if error:
                    message['snapshot'] = None
                    message['error'] = error
                    return finished(message)
                message['v'] = data['v']
                message['snapshot'] = data['snapshot']
                return step3Open(message)

            return self.model.get_data(query['doc'], model_get_data)

        def step3Open(message):
            if 'open' not in query:
                return finished(message)

            doc = self.docs[query['doc']]
            if 'listener' in doc:
                message['open'] = True
                return finished(message)
            
            doc['listener'] = self.on_remote_message

            def model_listen(error, v):
                if error:
                    del doc['listener']
                    message['open'] = False
                    message['error'] = error
                message['open'] = True
                if 'v' not in message: message['v'] = v
                return finished(message)
            self.model.listen(query['doc'], doc['listener'], model_listen)

        step1Create({'doc':query['doc']})