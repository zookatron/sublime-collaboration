# $Id: __init__.py,v 1.9 2005/03/07 09:34:51 snakeru Exp $

"""
All features of xmpppy library contained within separate modules.
At present there are modules:
simplexml - XML handling routines
protocol - jabber-objects (I.e. JID and different stanzas and sub-stanzas) handling routines.
debug - Jacob Lundquist's debugging module. Very handy if you like colored debug.
auth - Non-SASL and SASL stuff. You will need it to auth as a client or transport.
transports - low level connection handling. TCP and TLS currently. HTTP support planned.
roster - simple roster for use in clients.
dispatcher - decision-making logic. Handles all hooks. The first who takes control over fresh stanzas.
features - different stuff that didn't worths separating into modules
browser - DISCO server framework. Allows to build dynamic disco tree.
filetransfer - Currently contains only IBB stuff. Can be used for bot-to-bot transfers.

Most of the classes that is defined in all these modules is an ancestors of 
class PlugIn so they share a single set of methods allowing you to compile 
a featured XMPP client. For every instance of PlugIn class the 'owner' is the class
in what the plug was plugged. While plugging in such instance usually sets some
methods of owner to it's own ones for easy access. All session specific info stored
either in instance of PlugIn or in owner's instance. This is considered unhandy
and there are plans to port 'Session' class from xmppd.py project for storing all
session-related info. Though if you are not accessing instances variables directly
and use only methods for access all values you should not have any problems.

"""

import simplexml,protocol,debug,auth,transports,roster,dispatcher,features,browser,filetransfer,commands
from client import *
from protocol import *

import threading

class GroupProtocol(Protocol):
    """ A "stanza" object class. Contains methods that are common for presences, iqs and messages. """
    def __init__(self, group_name=None, group_publisher=None, attrs={}, payload=[], xmlns=None, node=None):
        if not attrs: attrs={}
        if group_name: attrs['group_name']=group_name
        if group_publisher: attrs['group_publisher']=grouppublisher
        Protocol.__init__(self, 'group', attrs=attrs, payload=payload, xmlns=xmlns, node=node)
        if self['group_name']: self.set_group_name(self['group_name'])
        if self['group_publisher']: self.set_group_publisher(self['group_publisher'])
    def get_group_name(self):
        return self.getAttr('group_name')
    def get_group_publisher(self):
        return self.getAttr('group_publisher')
    def set_group_name(self,val):
        self.setAttr('group_name', val)
    def set_group_publisher(self,val):
        self.setAttr('group_publisher', val)
        return props

class XMPPHandler(CommonClient):
	def __init__(self,server='',port=5347,typ=None,debug=[],domains=None,sasl=0,bind=0,route=0):
		if(True):
			debug=['always', 'nodebuilder']
		self.Namespace,self.DBG='jabber:client',DBG_CLIENT
		CommonClient.__init__(self,server,port=port,debug=debug)
		self._connect_callback = None
		self._disconnect_callback = None
		self._data_callback = None

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

	def auth(self,user,password=None,resource='',sasl=1):
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

	def DisconnectHandler(self):
		self._disconnect_callback()

	def MessageHandler(self, conn, node):
		self._data_callback(node)

	def run(self, server, port):
		con=self.connect((server, port))
		if not con:
			print('could not connect!')
			return
		print('connected with '+str(con))

		auth = self.auth('Username')
		if not auth:
			print('could not auth!')
			return
		print('authed with '+str(auth))
		
		self.RegisterProtocol('group', GroupProtocol)
		self.RegisterHandler('group', self.MessageHandler)

		self._connect_callback()

		while self.Process():
			pass

	def start(self, server, port, data_callback, connect_callback, disconnect_callback):
		self._connect_callback = connect_callback
		self._disconnect_callback = disconnect_callback
		self._data_callback = data_callback
		thread = threading.Thread(target=self.run, args=(server, port))
		thread.start()
