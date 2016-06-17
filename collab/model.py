import time, re, logging
from .optransform import op_transform, op_apply

logger = logging.getLogger('Sublime Collaboration')

class CollabModel(object):
    def __init__(self, options=None):
        self.options = options if options else {}
        self.options.setdefault('numCachedOps', 20)
        self.options.setdefault('opsBeforeCommit', 20)
        self.options.setdefault('maximumAge', 20)

        self.docs = {}

    def process_queue(self, doc):
        if doc['queuelock'] or len(doc['queue']) == 0:
            return

        doc['queuelock'] = True
        op, callback = doc['queue'].pop(0)
        self.handle_op(doc, op, callback)
        doc['queuelock'] = False

        self.process_queue(doc)

    def handle_op(self, doc, op, callback):
        if 'v' not in op or op['v'] < 0:
            return callback('Version missing', None)
        if op['v'] > doc['v']:
            return callback('Op at future version', None)
        if op['v'] < doc['v'] - self.options['maximumAge']:
            return callback('Op too old', None)
        if op['v'] < 0:
            return callback('Invalid version', None)

        ops = doc['ops'][(len(doc['ops'])+op['v']-doc['v']):]

        if doc['v'] - op['v'] != len(ops):
            logger.error("Could not get old ops in model for document {1}. Expected ops {1} to {2} and got {3} ops".format(doc['name'], op['v'], doc['v'], len(ops)))
            return callback('Internal error', None)

        for oldOp in ops:
            op['op'] = op_transform(op['op'], oldOp['op'], 'left')
            op['v']+=1

        newSnapshot = op_apply(doc['snapshot'], op['op'])

        if op['v'] != doc['v']:
            logger.error("Version mismatch detected in model. File a ticket - this is a bug. Expecting {0} == {1}".format(op['v'], doc['v']))
            return callback('Internal error', None)

        oldSnapshot = doc['snapshot']
        doc['v'] = op['v'] + 1
        doc['snapshot'] = newSnapshot
        for listener in doc['listeners']:
            listener(op, newSnapshot, oldSnapshot)

        def save_op_callback(error=None):
            if error:
                logger.error("Error saving op: {0}".format(error))
                return callback(error, None)
            else:
                return callback(None, op['v'])
        self.save_op(doc['name'], op, save_op_callback)

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

    def get_docs(self, callback):
        callback(None, [self.docs[doc]['name'] for doc in self.docs])

    def add(self, docname, data):
        self.docs[docname] = {
            'name': docname,
            'snapshot': data['snapshot'],
            'v': data['v'],
            'ops': data['ops'],
            'listeners': [],
            'savelock': False,
            'savedversion': 0,
            'queue': [],
            'queuelock': False,
        }

    def load(self, docname, callback):
        try:
            return callback(None, self.docs[docname])
        except KeyError:
            return callback('Document does not exist', None)

        # self.loadingdocs = {}
        # self.loadingdocs.setdefault(docname, []).append(callback)
        # if docname in self.loadingdocs:
        #     for callback in self.loadingdocs[docname]:
        #         callback(None, doc)
        #     del self.loadingdocs[docname]

    def create(self, docname, snapshot=None, callback=None):
        if not re.match("^[A-Za-z0-9._-]*$", docname):
            return callback('Invalid document name') if callback else None
        if self.exists(docname):
            return callback('Document already exists') if callback else None

        data = {
            'snapshot': snapshot if snapshot else '',
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

    def get_snapshot(self, docname, callback):
        self.load(docname, lambda error, doc: callback(error, None if error else doc['snapshot']))

    def get_data(self, docname, callback):
        self.load(docname, lambda error, doc: callback(error, None if error else doc))

    def apply_op(self, docname, op, callback):
        def on_load(error, doc):
            if error:
                callback(error, None)
            else:
                doc['queue'].append((op, callback))
                self.process_queue(doc)
        self.load(docname, on_load)
        
    def flush(self, callback=None):
        return callback() if callback else None

    def close(self):
        self.flush()
