import json, threading, socket, base64, hashlib, logging, sys

logger = logging.getLogger('Sublime Collaboration')

#A pretty terrible hacky framing system, I'll need to come up with a better one soon
def send_msg(sock, msg):
    if sys.version_info[0] < 3:
        sock.send(unicode("0")*(10-len(unicode(len(msg))))+unicode(len(msg))+msg)
    else:
        sock.send(bytes("0"*(10-len(str(len(msg))))+str(len(msg))+msg, 'UTF-8'))

class ClientSocket(threading.Thread):
    def __init__(self, host, port):
        threading.Thread.__init__(self)

        self.host = host
        self.port = port
        self.sock = None

        self.saved_data = ''
        self.target_size = None

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
        logger.debug('Client sending: <{0}>'.format(data))

        msg = json.dumps(data)

        try:
            send_msg(self.sock, msg)
        except:
            self.close()

    def close(self):
        self.keep_running = False
        if self.sock:
            self.sock.shutdown(socket.SHUT_RDWR)

    def run(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.host, self.port))
        except:
            self.emit('error', 'could not connect to server')
            self.emit('close')
            self.sock = None
            return
        self.emit('open')
        while self.keep_running:
            try:
                data = self.sock.recv(self.target_size if self.target_size else 10)
            except:
                break
            if data is None or data == b'':
                break

            logger.debug('Client recieved: <{0}>'.format(data))

            if self.target_size:
                self.saved_data += data.decode("utf-8")
                if len(self.saved_data) == self.target_size:
                    self.emit('message', json.loads(self.saved_data, "utf-8"))
                    self.saved_data = ''
                    self.target_size = None
            else:
                self.target_size = int(data)

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

        self.saved_data = ''
        self.target_size = None

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
        self.emit('ok')

        while self._ready:
            try:
                data = self.sock.recv(self.target_size if self.target_size else 10)
            except:
                break
            if data is None or data == b'':
                break

            logger.debug('Server recieved from {0}: <{1}>'.format(self.address, data))

            if self.target_size:
                self.saved_data += data.decode("utf-8")
                if len(self.saved_data) == self.target_size:
                    self.emit('message', json.loads(self.saved_data, "utf-8"))
                    self.saved_data = ''
                    self.target_size = None
            else:
                self.target_size = int(data)

        self._ready = False
        self.emit('close')
        self.close()

    def close(self):
        self._ready = False
        self.sock.shutdown(socket.SHUT_RDWR)

    def send(self, data):
        if not self._ready: return

        logger.debug('Server sending to {0}: <{1}>'.format(self.address, data))

        msg = json.dumps(data)

        try:
            send_msg(self.sock, msg)
        except:
            self.close()

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
            except OSError:
                break
            logger.debug('Server was connected by {0}'.format(addr))
            connection = ServerSocket(conn, addr)
            self.connections.append(connection)
            def on_close():
                logger.debug('Server was disconnected by {0}'.format(addr))
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
