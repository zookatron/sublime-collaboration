import json, threading, socket, base64, hashlib



def unicode_to_str(obj):
    return dict((str(x) if isinstance(x, unicode) else x, str(y) if isinstance(y, unicode) else y) for x, y in obj.iteritems())

class ClientSocket(threading.Thread):
    def __init__(self, host, port):
        threading.Thread.__init__(self)

        self.host = host
        self.port = port
        self.sock = None

        self.keep_running = True

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

    def send(self, data):
        #print('Sending:{0}'.format(data))
        self.sock.send(data)

    def close(self):
        self.keep_running = False
        if self.sock:
            self.sock.shutdown(socket.SHUT_RDWR)

    def run(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.emit('open')
        while self.keep_running:
            data = self.sock.recv(1024)
            if data is None or data == "":
                break
            #print('Recieved:{0}'.format(data))
            self.emit('message', json.loads(data, object_hook=unicode_to_str))

        self.sock.close()
        self.emit('close')
        self.sock = None



class ServerSocket(threading.Thread):
    def __init__(self, sock, addr):
        threading.Thread.__init__(self)

        self.sock = sock
        sock.settimeout(None)

        self.address = addr
        self.headers = None

        self._ready = False
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

    def run(self):
        self._ready = True

        while self._ready:
            data = self.sock.recv(1024)
            if not data or data == "":
                break
            #print('Recieved from {0}:{1}'.format(self.address, data))
            self.emit('message', json.loads(data, object_hook=unicode_to_str))

        self._ready = False
        self.emit('close')
        self.close()

    def close(self):
        self._ready = False
        self.sock.shutdown(socket.SHUT_RDWR)

    def send(self, msg):
        if not self._ready:
            return
        msg = json.dumps(msg)
        #print('Sending to {0}:{1}'.format(self.address, msg))
        self.sock.send(msg)

    def ready(self):
        return self._ready

    def abort(self):
        self.close()

    def stop(self):
        self.close()



class SocketServer:
    def __init__(self, host='127.0.0.1', port=6633):
        self.host = host
        self.port = port
        self.sock = None
        self.keep_running = True
        self.closed = False
        self.connections = []
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

    def run_forever(self):
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(0.1)
        self.sock.bind(('', self.port))
        self.sock.listen(1)

        while self.keep_running:
            try:
                conn, addr = self.sock.accept()
            except socket.timeout:
                continue
            #print('Connected by {0}'.format(addr))
            connection = ServerSocket(conn, addr)
            self.connections.append(connection)
            def on_close():
                #print('Disconnected by {0}'.format(addr))
                if connection in self.connections:
                    self.connections.remove(connection)
            connection.on('close', on_close)
            connection.start()
            self.emit('connection', connection)

        self.closed = True

    def close(self):
        self.keep_running = False
        for connection in self.connections:
            connection.close()
        self.sock.close()
        while not self.closed: pass
