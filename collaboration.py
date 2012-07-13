import httplib, socket, time, infinote, sys
from xmpp import *

class InfinoteClient(CommonClient):
	def __init__(self,server,port=5347,typ=None,debug=['always', 'nodebuilder'],domains=None,sasl=0,bind=0,route=0):
		self.Namespace,self.DBG='jabber:client',DBG_CLIENT
		CommonClient.__init__(self,server,port=port,debug=debug)
	def connect(self,server=None,proxy=None,secure=None,use_srv=True):
		if not CommonClient.connect(self,server,proxy,secure,use_srv) or secure<>None and not secure: return self.connected
		transports.TLS().PlugIn(self)
		if not self.Dispatcher.Stream._document_attrs.has_key('version') or not self.Dispatcher.Stream._document_attrs['version']=='1.0': return self.connected
		while not self.Dispatcher.Stream.features and self.Process(1): pass      # If we get version 1.0 stream the features tag MUST BE presented
		if not self.Dispatcher.Stream.features.getTag('starttls'): return self.connected       # TLS not supported by server
		while not self.TLS.starttls and self.Process(1): pass
		if not hasattr(self, 'TLS') or self.TLS.starttls!='success': self.event('tls_failed'); return self.connected
		self.connected='tls'
		return self.connected

	def auth(self,user=None,password=None,resource='',sasl=1):
		""" Authenticate connnection and bind resource. If resource is not provided
			random one or library name used. """
		self._User,self._Password,self._Resource=user,password,resource
		while not self.Dispatcher.Stream._document_attrs and self.Process(1): pass
		if self.Dispatcher.Stream._document_attrs.has_key('version') and self.Dispatcher.Stream._document_attrs['version']=='1.0':
			while not self.Dispatcher.Stream.features and self.Process(1): pass      # If we get version 1.0 stream the features tag MUST BE presented
		if sasl: auth.SASL(user,password).PlugIn(self)
		if not sasl or self.SASL.startsasl=='not-supported':
			if not resource: resource='xmpppy'
			if auth.NonSASL(user,password,resource).PlugIn(self):
				self.connected+='+old_auth'
				return 'old_auth'
			return
		self.SASL.auth()
		while self.SASL.startsasl=='in-process' and self.Process(1): pass
		if self.SASL.startsasl=='success':
			return 'sasl'

cl=InfinoteClient('68.203.13.38', 6523)

con=cl.connect()
if not con:
	print 'could not connect!'
	sys.exit()
print 'connected with'+str(con)

auth = cl.auth()
if not auth:
	print 'could not auth!'
	sys.exit()
print 'authed with'+str(auth)

cl.send('<group publisher="you" name="InfDirectory"><explore-node seq="1" id="0"/></group>')
for x in range(10):
	cl.Process(1)

cl.disconnect()