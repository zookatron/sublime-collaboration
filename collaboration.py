import httplib, socket, xmpp, time, infinote, sys

# conn = httplib.HTTPConnection('localhost:6523')
# conn.request("GET", "/index.html")
# r1 = conn.getresponse()
# print r1.status, r1.reason

cl=xmpp.Client('localhost', 6523)

con=cl.connect()
if not con:
    print 'could not connect!'
    sys.exit()
print 'connected with',con

#cl.SendInitPresence(requestRoster=0)   # you may need to uncomment this for old server
id=cl.send(xmpp.protocol.Message("","hi"))
print 'sent message with id',id

time.sleep(1)   # some older servers will not send the message if you disconnect immediately after sending

cl.disconnect()