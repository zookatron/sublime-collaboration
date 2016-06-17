import sublime, sublime_plugin, logging

# intitialize logging
logger = logging.getLogger('Sublime Collaboration')
#logger.setLevel(logging.INFO)
logger.setLevel(logging.DEBUG)

loggerhandler = logging.StreamHandler()
loggerhandler.setLevel(logging.NOTSET)

loggerformatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
loggerhandler.setFormatter(loggerformatter)

logger.addHandler(loggerhandler)

try:
    from .collab.client import CollabClient
    from .collab.server import CollabServer
except (ImportError, ValueError):
    from collab.client import CollabClient
    from collab.server import CollabServer

class SublimeListener(sublime_plugin.EventListener):
    _events = {}

    @classmethod
    def on(klass, event, fct):
        if event not in klass._events: klass._events[event] = []
        klass._events[event].append(fct)

    @classmethod
    def removeListener(klass, event, fct):
        if event not in klass._events: return
        klass._events[event].remove(fct)

    def emit(self, event, *args):
        if event not in self._events: return
        for callback in self._events[event]:
            callback(*args)
        return self

    def on_modified(self, view):
        self.emit("modified", view)

    def on_new(self, view):
        self.emit("new", view)

    def on_clone(self, view):
        self.emit("clone", view)

    def on_load(self, view):
        self.emit("load", view)

    def on_close(self, view):
        self.emit("close", view)

    def on_pre_save(self, view):
        self.emit("pre_save", view)

    def on_post_save(self, view):
        self.emit("post_save", view)

    def on_selection_modified(self, view):
        self.emit("selection_modified", view)

    def on_activated(self, view):
        self.emit("activated", view)

    def on_deactivated(self, view):
        self.emit("deactivated", view)



class SublimeEditor(object):
    def __init__(self, view, doc):
        self.doc = None
        self.view = view
        self.doc = doc
        self._events = {}
        self.state = "ok"
        self.in_remoteop = False

        SublimeListener.on("modified", self._on_view_modified)
        SublimeListener.on("close", self._on_view_close)
        SublimeListener.on("post_save", self._on_view_post_save)
        self.doc.on("closed", self.close)
        self.doc.on("remoteop", self._on_doc_remoteop)

        sublime.set_timeout(lambda: self._initialize(self.doc.get_text()), 0)

        logger.info("opened "+doc.name)

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

    def focus(self):
        sublime.set_timeout(lambda: sublime.active_window().focus_view(self.view), 0)

    def close(self, reason=None):
        if self.state != "closed":
            self.state = "closed"
            logger.info("closed "+self.doc.name+(": "+reason if reason else ''))
            self.doc.close()
            SublimeListener.removeListener("modified", self._on_view_modified)
            SublimeListener.removeListener("close", self._on_view_close)
            SublimeListener.removeListener("post_save", self._on_view_post_save)
            self.doc.removeListener("closed", self.close)
            self.doc.removeListener("remoteop", self._on_doc_remoteop)
            self.view = None
            self.doc = None
            self.emit("closed")

    def _on_view_modified(self, view):
        if self.in_remoteop: return
        if self.view == None: return
        if view.id() == self.view.id() and self.doc:
            self._apply_change(self.doc, self.doc.get_text(), self._get_text())

    def _on_view_post_save(self, view):
        if self.view == None: return
        if view.id() == self.view.id() and self.doc:
            view.set_scratch(False)

    def _on_view_close(self, view):
        if self.view == None: return
        if view.id() == self.view.id() and self.doc:
            self.close()

    def _apply_change(self, doc, oldval, newval):
        if oldval == newval:
            return

        commonStart = 0
        while commonStart < len(oldval) and commonStart < len(newval) and oldval[commonStart] == newval[commonStart]:
            commonStart+=1

        commonEnd = 0
        while commonEnd+commonStart < len(oldval) and commonEnd+commonStart < len(newval) and oldval[len(oldval)-1-commonEnd] == newval[len(newval)-1-commonEnd]:
            commonEnd+=1

        if len(oldval) != commonStart+commonEnd:
            doc.delete(commonStart, len(oldval)-commonStart-commonEnd)
        if len(newval) != commonStart+commonEnd:
            doc.insert(commonStart, newval[commonStart:len(newval)-commonEnd])

    def _on_doc_remoteop(self, op, old_snapshot):
        sublime.set_timeout(lambda: self._apply_remoteop(op), 0)

    def _get_text(self):
        return self.view.substr(sublime.Region(0, self.view.size())).replace('\r\n', '\n')

    def _initialize(self, text):
        if self._get_text() == text: return
        self.view.run_command('collab_begin_edit', {'func': 'replace', 'region_start': 0, 'region_end': self.view.size(), 'string': text})

    def _apply_remoteop(self, op):
        self.in_remoteop = True
        for component in op:
            if 'i' in component:
                self.view.run_command('collab_begin_edit', {'func': 'insert', 'point': component['p'], 'string': component['i']})
            else:
                self.view.run_command('collab_begin_edit', {'func': 'erase', 'region_start': component['p'], 'region_end': component['p']+len(component['d'])})
        self.in_remoteop = False



client = None
server = None
editors = {}

class SublimeCollaboration(object):
    def connect(self, host):
        global client
        if client: self.disconnect()
        client = CollabClient(host, 6633)
        client.on('error', lambda error: sublime.error_message("Client error: {0}".format(error)))
        client.on('closed', self.on_close)
        self.set_status()
        logger.info("connected to server")

    def disconnect(self):
        global client
        if not client: return
        client.disconnect()
        self.set_status()

    def on_close(self, reason=None):
        global client
        if not client: return
        client = None
        self.set_status()
        logger.info("disconnected from server")

    def open_get_docs(self, error, items):
        global client
        if not client: return

        if error:
            sublime.error_message("Error retrieving document names: {0}".format(error))
        else:
            if items:
                sublime.set_timeout(lambda: sublime.active_window().show_quick_panel(items, lambda x: None if x < 0 else self.open(items[x])), 0)
            else:
                sublime.error_message("No documents availible to open")

    def open(self, name):
        global client
        if not client: return
        if name in editors:
            logger.info("document "+name+" is already open")
            return editors[name].focus()
        client.open(name, self.open_callback)
        self.set_status()

    def add_current(self, name):
        global client
        if not client: return
        if name in editors:
            logger.info("document "+name+" is already open")
            return editors[name].focus()
        view = sublime.active_window().active_view()
        if view.id() in (editor.view.id() for editor in editors.values()): return
        if view != None:
            client.open(name, lambda error, doc: self.add_callback(view, error, doc), snapshot=view.substr(sublime.Region(0, view.size())))
        self.set_status()

    def open_callback(self, error, doc):
        if error:
            sublime.error_message("Error opening document: {0}".format(error))
        else:
            sublime.set_timeout(lambda: self.create_editor(doc), 0)

    def add_callback(self, view, error, doc):
        if error:
            sublime.error_message("Error adding document: {0}".format(error))
        else:
            sublime.set_timeout(lambda: self.add_editor(view, doc), 0)

    def create_editor(self, doc):
        view = sublime.active_window().new_file()
        view.set_scratch(True)
        view.set_name(doc.name)
        self.add_editor(view, doc)
        self.set_status()

    def add_editor(self, view, doc):
        global editors
        editor = SublimeEditor(view, doc)
        editor.on('closed', lambda: editors.pop(doc.name))
        editors[doc.name] = editor

    def toggle_server(self):
        global server
        if server:
            server.close()
            server = None
            logger.info("server closed")
        else:
            server = CollabServer({'host':'127.0.0.1', 'port':6633})
            server.run_forever()
            logger.info("server started")
        self.set_status()

    def set_status(self):
        global server, client

        if server or client:
            if server:
                server_status = 'running'
            else:
                server_status = 'off'

            if client:
                host = client.socket.host
                state = client.state
                client_status = 'client:%(host)s...%(state)s' % locals()
            else:
                client_status = 'disconnected'

            status_value = "Collab (server:%(server_status)s; %(client_status)s)" % locals()
        else:
            status_value = ''

        def _set_status():
            for window in sublime.windows():
                for view in window.views():
                    view.set_status('collab_server_status', status_value)

        sublime.set_timeout(_set_status, 0)

class CollabConnectToServerCommand(sublime_plugin.ApplicationCommand, SublimeCollaboration):
    def run(self):
        sublime.active_window().show_input_panel("Enter server IP:", "localhost", self.connect, None, None)

class CollabDisconnectFromServerCommand(sublime_plugin.ApplicationCommand, SublimeCollaboration):
    def run(self):
        self.disconnect()
    def is_enabled(self):
        global client
        return bool(client)

class CollabToggleServerCommand(sublime_plugin.ApplicationCommand, SublimeCollaboration):
    def run(self):
        self.toggle_server()

class CollabOpenDocumentCommand(sublime_plugin.ApplicationCommand, SublimeCollaboration):
    def run(self):
        global client
        if not client: return
        client.get_docs(self.open_get_docs)
    def is_enabled(self):
        global client
        return bool(client)

class CollabAddCurrentDocumentCommand(sublime_plugin.ApplicationCommand, SublimeCollaboration):
    def run(self):
        global client, editors
        if not client: return
        if sublime.active_window() == None: return
        view = sublime.active_window().active_view()
        if view == None: return
        if view.id() in (editor.view.id() for editor in editors.values()): return
        sublime.active_window().show_input_panel("Enter new document name:", view.name(), self.add_current, None, None)
    def is_enabled(self):
        global client
        return bool(client)

class CollabEnableDebugCommand(sublime_plugin.ApplicationCommand, SublimeCollaboration):
    def run(self):
        logger.setLevel(logging.DEBUG)



# The new ST3 plugin API sucks
class CollabBeginEditCommand(sublime_plugin.TextCommand):
    def run(self, edit, *args, **kwargs):
        func = kwargs['func']
        if func == 'replace':
            self.view.replace(edit, sublime.Region(kwargs['region_start'], kwargs['region_end']), kwargs['string'])
        elif func == 'insert':
            self.view.insert(edit, kwargs['point'], kwargs['string'])
        elif func == 'erase':
            self.view.erase(edit, sublime.Region(kwargs['region_start'], kwargs['region_end']))

    def is_visible(self):
        return False

    def is_enabled(self):
        return True

    def description(self):
        return
