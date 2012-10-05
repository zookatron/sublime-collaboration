import doctypes, syncQueue, time, re, logging

class CollabModel(object):
    def __init__(self, options=None):
        self.options = options if options else {}
        self.options.setdefault('numCachedOps', 20)
        self.options.setdefault('opsBeforeCommit', 20)
        self.options.setdefault('maximumAge', 20)

        self.docs = {}

    def make_op_queue(self, docname, doc):

        def queue_process(opData, callback):
            if 'v' not in opData or opData['v'] < 0:
                return callback('Version missing', None)
            if opData['v'] > doc['v']:
                return callback('Op at future version', None)
            if opData['v'] < doc['v'] - self.options['maximumAge']:
                return callback('Op too old', None)
            if opData['v'] < 0:
                return callback('Invalid version', None)

            ops = doc['ops'][(len(doc['ops'])+opData['v']-doc['v']):]

            if doc['v'] - opData['v'] != len(ops):
                logging.error("Could not get old ops in model for document {1}. Expected ops {1} to {2} and got {3} ops".format(docname, opData['v'], doc['v'], len(ops)))
                return callback('Internal error', None)

            for oldOp in ops:
                opData['op'] = doc['type'].transform(opData['op'], oldOp['op'], 'left')
                opData['v']+=1

            newSnapshot = doc['type'].apply(doc['snapshot'], opData['op'])

            if opData['v'] != doc['v']:
                logging.error("Version mismatch detected in model. File a ticket - this is a bug. Expecting {0} == {1}".format(opData['v'], doc['v']))
                return callback('Internal error', None)

            oldSnapshot = doc['snapshot']
            doc['v'] = opData['v'] + 1
            doc['snapshot'] = newSnapshot
            for listener in doc['listeners']:
                listener(opData, newSnapshot, oldSnapshot)

            def save_op_callback(error=None):
                if error:
                    logging.error("Error saving op: {0}".format(error))
                    return callback(error, None)
                else:
                    callback(None, opData['v'])
            self.save_op(docname, opData, save_op_callback)

        return syncQueue.syncQueue(queue_process)

    def save_op(self, docname, op, callback):
        doc = self.docs[docname]
        doc['ops'].append(op)
        if len(doc['ops']) > self.options['numCachedOps']:
            doc['ops'].pop(0)
        if not doc['savelock'] and doc['savedversion'] + self.options['opsBeforeCommit'] <= doc['v']:
            pass
        callback(None)

    def exists(self, docname):
        return docname in self.docs

    def add(self, docname, data):
        doc = {
            'snapshot': data['snapshot'],
            'v': data['v'],
            'type': data['type'],
            'ops': data['ops'],
            'listeners': [],
            'savelock': False,
            'savedversion': 0,
        }
        
        doc['opQueue'] = self.make_op_queue(docname, doc)

        self.docs[docname] = doc

    def load(self, docname, callback):
        # try:
        return callback(None, self.docs[docname])
        # except KeyError:
        #     return callback('Document does not exist', None)

        # self.loadingdocs = {}
        # self.loadingdocs.setdefault(docname, []).append(callback)
        # if docname in self.loadingdocs:
        #     for callback in self.loadingdocs[docname]:
        #         callback(None, doc)
        #     del self.loadingdocs[docname]

    def create(self, docname, doctype, snapshot=None, callback=None):
        if not re.match("^[A-Za-z0-9._-]*$", docname):
            return callback('Invalid document name') if callback else None
        if self.exists(docname):
            return callback('Document already exists') if callback else None

        if isinstance(doctype, (str, unicode)):
            doctype = doctypes.types.get(doctype, None)
        if not doctype:
            return callback('Invalid document type') if callback else None

        doctype = doctype()
        data = {
            'snapshot': snapshot if snapshot else doctype.create(),
            'type': doctype,
            'v': 0,
            'ops': []
        }
        self.add(docname, data)

        return callback(None) if callback else None

    def delete(self, docname, callback=None):
        if docname not in self.docs: raise Exception('delete called but document does not exist')
        del self.docs[docname]
        return callback(None) if callback else None

    def listen(self, docname, listener, callback=None):
        def done(error, doc):
            if error: return callback(error, None) if callback else None
            doc['listeners'].append(listener)
            return callback(None, doc['v']) if callback else None
        self.load(docname, done)

    def remove_listener(self, docname, listener):
        if docname not in self.docs: raise Exception('remove_listener called but document not loaded')
        self.docs[docname]['listeners'].remove(listener)

    def get_version(self, docname, callback):
        self.load(docname, lambda error, doc: callback(error, None if error else doc['v']))

    def get_doctype(self, docname, callback):
        self.load(docname, lambda error, doc: callback(error, None if error else doc['type']))

    def get_snapshot(self, docname, callback):
        self.load(docname, lambda error, doc: callback(error, None if error else doc['snapshot']))

    def get_data(self, docname, callback):
        self.load(docname, lambda error, doc: callback(error, None if error else doc))

    # Ops are queued before being applied so that the following code applies op C before op B:
    # model.applyOp 'doc', OPA, -> model.applyOp 'doc', OPB
    # model.applyOp 'doc', OPC
    def applyOp(self, docname, op, callback):
        self.load(docname, lambda error, doc: callback(error, None) if error else doc['opQueue'](op, callback))
        
    def flush(self, callback=None):
        return callback() if callback else None

    def close(self):
        self.flush()
