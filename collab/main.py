import BaseHTTPServer, SimpleHTTPServer, server, threading

threading.Thread(target=lambda: BaseHTTPServer.HTTPServer(('127.0.0.1', 8080), SimpleHTTPServer.SimpleHTTPRequestHandler).serve_forever()).start()
server.CollabServer({'host':'127.0.0.1', 'port':6633}).run_forever()