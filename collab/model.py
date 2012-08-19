import doctypes, syncQueue, time, re

class EventEmitter(object):
    def __init__(self):
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

    def listeners(self, event):
        return self._events.get(event, [])

class CollabModel(object):
    def __init__(self, db, options=None):
        self.options = options
        self.db = db

        if not self.options:
            options = {}

        self.docs = {}
        self._events = {}

        self.awaitingGetSnapshot = {}

        if 'numCachedOps' not in self.options:
            self.options['numCachedOps'] = 20

        if 'opsBeforeCommit' not in self.options:
            self.options['opsBeforeCommit'] = 20

        if 'maximumAge' not in self.options:
            self.options['maximumAge'] = 20

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

    def makeOpQueue(self, docName, doc):

        def _queue_process(opData, callback):
            if 'v' not in opData or opData['v'] < 0:
                return callback('Version missing')
            if opData['v'] > doc['v']:
                return callback('Op at future version')
            if opData['v'] < doc['v'] - self.options['maximumAge']:
                return callback('Op too old')

            if 'meta' not in opData or not opData['meta']:
                opData['meta'] = {}
            opData['meta']['ts'] = time.time()

            def _get_ops(error, ops=None):
                if error:
                    return callback(error)

                if doc['v'] - opData['v'] != len(ops):
                    print("Could not get old ops in model for document {0}".format(docName))
                    print("Expected ops {0} to {1} and got {2} ops".format(opData['v'], doc['v'], len(ops)))
                    return callback('Internal error')

                if len(ops) > 0:
                    try:
                        for oldOp in ops:
                            if 'meta' in oldOp and 'source' in oldOp['meta'] and 'dupIfSource' in opData and oldOp['meta']['source'] in opData['dupIfSource']:
                                return callback('Op already submitted')

                            opData['op'] = doc['type'].transform(opData['op'], oldOp['op'], 'left')
                            opData['v']+=1
                    except Exception as error:
                        print(error)
                        return callback(str(error))

                try:
                    snapshot = doc['type'].apply(doc['snapshot'], opData['op'])
                except Exception as error:
                    print(error)
                    return callback(error)

                if opData['v'] != doc['v']:
                    print("Version mismatch detected in model. File a ticket - this is a bug.")
                    print("Expecting {0} == {1}".format(opData['v'], doc['v']))
                    return callback('Internal error')

                writeOp = self.db.writeOp if self.db and 'writeOp' in self.db else lambda docName, newOpData, callback: callback()

                def _writeop_callback(error=None):
                    if error:
                        print("Error writing ops to database: {0}".format(error))
                        return callback(error)

                    if 'stats' in self.options and 'writeOp' in self.options['stats']:
                        self.options['stats']['writeOp']()

                    oldSnapshot = doc['snapshot']

                    doc['v'] = opData['v'] + 1
                    doc['snapshot'] = snapshot

                    doc['ops'].append(opData)
                    if self.db and len(doc['ops']) > self.options['numCachedOps']:
                        doc['ops'].pop(0)

                    self.emit('applyOp', docName, opData, snapshot, oldSnapshot)
                    doc['eventEmitter'].emit('op', opData, snapshot, oldSnapshot)

                    callback(None, opData['v'])
            
                    # I need a decent strategy here for deciding whether or not to save the snapshot.
                    #
                    # The 'right' strategy looks something like "Store the snapshot whenever the snapshot
                    # is smaller than the accumulated op data". For now, I'll just store it every 20
                    # ops or something. (Configurable with doc.committedVersion)
                    if not doc['snapshotWriteLock'] and doc['committedVersion'] + self.options['opsBeforeCommit'] <= doc['v']:
                        def write_snappy_error(error=None):
                            if error:
                                print("Error writing snapshot {0}. This is nonfatal".format(error))
                        self.tryWriteSnapshot(docName, write_snappy_error)
                writeOp(docName, opData, _writeop_callback)

            self.getOps(docName, opData['v'], doc['v'], _get_ops)

        return syncQueue.syncQueue(_queue_process)

    def add(self, docName, error, data, committedVersion, ops, dbMeta):
        callbacks = None
        if docName in self.awaitingGetSnapshot:
            callbacks = self.awaitingGetSnapshot[docName]
            del self.awaitingGetSnapshot[docName]

        if not error and docName in self.docs:
            error = "doc already exists"

        if error:
            if callbacks:
                for callback in callbacks:
                    callback(error)
        else:
            doc = {
                'snapshot': data['snapshot'],
                'v': data['v'],
                'type': data['type'],
                'meta': data['meta'],
                'ops': ops if ops else [],
                'eventEmitter': EventEmitter(),
                'committedVersion': committedVersion if committedVersion else data['v'],
                'snapshotWriteLock': False,
                'dbMeta': dbMeta
            }

            self.docs[docName] = doc

            doc['opQueue'] = self.makeOpQueue(docName, doc)
            
            self.emit('add', docName, data)
            if callbacks:
                for callback in callbacks:
                    callback(None, doc)

        return doc



    def getOpsInternal(self, docName, start, end, callback):
        if not self.db:
            return callback('Document does not exist')

        def _getops(error, ops):
            if error:
                if callback:
                    return callback(error)
                return

            v = start
            for op in ops:
                v+=1
            op['v'] = v

            if callback:
                callback(None, ops)

        self.db.getOps(docName, start, end, _getops)



    def load(self, docName, callback):
        if docName in self.docs:
            if 'stats' in self.options and 'cacheHit' in self.options['stats']:
                self.options['stats']['cacheHit']('getSnapshot')
            return callback(None, self.docs[docName])

        if not self.db:
            return callback('Document does not exist')

        callbacks = self.awaitingGetSnapshot[docName]

        if callbacks:
            return callbacks.append(callback)

        if 'stats' in self.options and 'cacheMiss' in self.options['stats']:
            self.options['stats']['cacheMiss']('getSnapshot')

        self.awaitingGetSnapshot[docName] = callbacks

        def _get_snappy(error, data, dbMeta):
            if error:
                return self.add(docName, error)

            type = doctypes.types[data['type']]
            if not type:
                print("Type '{0}' missing".format(data.type))
                return callback("Type not found")
            data['type'] = type

            committedVersion = data['v']

            def _get_ops_internal(error, ops):
                if error:
                    return callback(error)

                if len(ops) > 0:
                    print("Catchup {0} {1} -> {2}".format(docName, data['v'], data['v'] + len(ops))) # not an error?

                    try:
                        for op in ops:
                            data['snapshot'] = type.apply(data['snapshot'], op['op'])
                            data['v']+=1
                    except Exception as e:
                        print("Op data invalid for {0}: {1}".format(docName, e))
                        return callback('Op data invalid')

                self.emit('load', docName, data)
                self.add(docName, error, data, committedVersion, ops, dbMeta)
            self.getOpsInternal(docName, data['v'], None, _get_ops_internal)
        self.db.getSnapshot(docName, _get_snappy)



    def tryWriteSnapshot(self, docName, callback):
        if not self.db or not docName in self.docs:
            return callback() if callback else None

        doc = self.docs[docName]

        if not doc:
            return callback() if callback else None

        if doc['committedVersion'] is doc['v']:
            return callback() if callback else None

        if doc['snapshotWriteLock']:
            return callback('Another snapshot write is in progress') if callback else None

        doc['snapshotWriteLock'] = True

        if 'stats' in self.options and 'writeSnapshot' in self.options['stats']:
            self.options['stats']['writeSnapshot']()

        writeSnapshot = self.db.writeSnapshot if self.db else lambda docName, docData, dbMeta, callback: callback()

        data = {
            'v': doc['v'],
            'meta': doc['meta'],
            'snapshot': doc['snapshot'],
            'type': doc['type'].name
        }

        def _write_snappy(error, dbMeta):
            doc['snapshotWriteLock'] = False
            doc['committedVersion'] = data['v']
            doc['dbMeta'] = dbMeta
            return callback(error) if callback else None

        self.writeSnapshot(docName, data, doc['dbMeta'], _write_snappy)



    def create(self, docName, type, meta, callback=None):
        if callable(meta):
            callback = meta
            meta = {}

        if not re.match("^[A-Za-z0-9._-]*$", docName):
            return callback('Invalid document name') if callback else None
        if docName in self.docs:
            return callback('Document already exists') if callback else None

        if isinstance(type, (str, unicode)):
            type = doctypes.types.get(type, None)

        if not type:
            return callback('Type not found') if callback else None

        data = {
            'snapshot': type().create(),
            'type': type.name,
            'meta': meta if meta else {},
            'v': 0
        }

        def done(error=None, dbMeta=None):
            if error:
                return callback(error) if callback else None

            data['type'] = type()
            self.add(docName, None, data, 0, [], dbMeta)
            self.emit('create', docName, data)
            return callback() if callback else None

        if self.db:
            self.db.create(docName, data, done)
        else:
            done()



    def delete(self, docName, callback):
        doc = None
        if docName in self.docs:
            doc = self.docs[docName]
            del self.docs[docName]

        def done(error=None):
            if not error:
                model.emit('delete', docName)
            return callback(error) if callback else None

        if self.db:
            return self.db.delete(docName, doc['dbMeta'] if doc else None, done)
        else:
            return done() if doc else done('Document does not exist')



    def getOps(self, docName, start, end, callback):
        if not start >= 0:
            raise Exception('start must be 0+')

        if callable(end):
            end, callback = None, end

        ops = None
        if docName in self.docs:
            ops = self.docs[docName]['ops']

            version = self.docs[docName]['v']

            if not end:
                end = version
            start = min(start, end)

            if start == end:
                return callback(None, [])

            base = version - len(ops)

            if not self.db or start >= base:
                if 'stats' in self.options and 'cacheHit' in self.options['stats']:
                    self.options['stats']['cacheHit']('getOps')

                return callback(None, ops[(start - base):(end - base)])

        if 'stats' in self.options and 'cacheMiss' in self.options['stats']:
            self.options['stats']['cacheMiss']('getOps')

        return self.getOpsInternal(docName, start, end, callback)



    def getSnapshot(self, docName, callback):
        self.load(docName, lambda error, doc=None: callback(error, {'v':doc['v'], 'type':doc['type'], 'snapshot':doc['snapshot'], 'meta':doc['meta']} if doc else None))



    def getVersion(self, docName, callback):
        self.load(docName, lambda error, doc=None: callback(error, doc['v'] if doc else None))



    # Ops are queued before being applied so that the following code applies op C before op B:
    # model.applyOp 'doc', OPA, -> model.applyOp 'doc', OPB
    # model.applyOp 'doc', OPC
    def applyOp(self, docName, opData, callback=None):
        def _load(error, doc):
            if error: return callback(error) if callback else None
            doc['opQueue'](opData, lambda error, newVersion=None: callback(error, newVersion) if callback else None)
        self.load(docName, _load)



    def applyMetaOp(self, docName, metaOpData, callback):
        path = metaOpData['meta']['path']
        value = metaOpData['meta']['value']

        def _load(error, doc):
            if error:
                return callback(error) if callback else None
            else:
                applied = False
                if path[0] == 'shout':
                    doc['eventEmitter'].emit('op', metaOpData)
                    applied = True

                if applied:
                    model.emit('applyMetaOp', docName, path, value)
                return callback(None, doc['v']) if callback else None
        self.load(docName, _load)



    def listen(self, docName, version=None, listener=None, callback=None):
        if callable(version):
            version, listener, callback = None, version, listener

        def _load(error, doc):
            if error:
                return callback(error) if callback else None

            if version:
                def _getops(error, data):
                    if error:
                        return callback(error) if callback else None

                    doc['eventEmitter'].on('op', listener)
                    if callback:
                        callback(None, version)

                    for op in data:
                        listener(op)
                        if not listener in doc['eventEmitter'].listeners('op'):
                            break

                self.getOps(docName, version, None, _getops)

            else:
                doc['eventEmitter'].on('op', listener)
                return callback(None, doc['v']) if callback else None
        self.load(docName, _load)



    def removeListener(self, docName, listener):
        if docName not in self.docs:
            raise Exception('removeListener called but document not loaded')
        self.docs[docName]['eventEmitter'].removeListener('op', listener)



    def flush(self, callback):
        if not self.db:
            return callback() if callback else None

        global pendingWrites
        pendingWrites = 0

        for docName in self.docs:
            doc = self.docs[docName]
            if doc['committedVersion'] < doc['v']:
                pendingWrites+=1

                def _write_it_snappy_like():
                    global pendingWrites
                    pendingWrites-=1
                    if pendingWrites == 0 and callback:
                        callback()
                    callback = None
                self.tryWriteSnapshot(docName, _write_it_snappy_like)

        if pendingWrites == 0 and callback:
            callback()



    def closeDb(self):
        if self.db:
            self.db.close()
        self.db = None
