import collab, sublime, sublime_plugin

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

        print("opened "+doc.name)

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
            print("closed "+self.doc.name+(": "+reason if reason else ''))
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
        edit = self.view.begin_edit()
        self.view.replace(edit, sublime.Region(0, self.view.size()), text)
        self.view.end_edit(edit)

    def _apply_remoteop(self, op):
        self.in_remoteop = True
        edit = self.view.begin_edit()
        for component in op:
            if 'i' in component:
                self.view.insert(edit, component['p'], component['i'])
            else:
                self.view.erase(edit, sublime.Region(component['p'], component['p']+len(component['d'])))
        self.view.end_edit(edit)
        self.in_remoteop = False



client = None
server = None
editors = {}

class SublimeCollaboration(object):
    def connect(self, host):
        global client
        if client: self.disconnect()
        client = collab.client.CollabClient(host, 6633)
        client.on('error', lambda error: sublime.error_message("Client error: {0}".format(error)))
        client.on('closed', self.on_close)
        print("connected")

    def disconnect(self):
        global client
        if not client: return
        client.disconnect()

    def on_close(self, reason=None):
        global client
        if not client: return
        client = None
        print("disconnected")

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
            print(name+" is already open")
            return editors[name].focus()
        client.open(name, self.open_callback)

    def add_current(self, name):
        global client
        if not client: return
        if name in editors:
            print(name+" is already open")
            return editors[name].focus()
        view = sublime.active_window().active_view()
        if view.id() in (editor.view.id() for editor in editors.values()): return
        if view != None:
            client.open(name, lambda error, doc: self.add_callback(view, error, doc), snapshot=view.substr(sublime.Region(0, view.size())))

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
            print("server closed")
            sublime.active_window().active_view().set_status('Collab','Collab server OFF');
        else:
            server = collab.server.CollabServer({'host':'127.0.0.1', 'port':6633})
            server.run_forever()
            print("server started")
            sublime.active_window().active_view().set_status('Collab','Collab server ON');

class CollabConnectToServerCommand(sublime_plugin.ApplicationCommand, SublimeCollaboration):
    def run(self):
        sublime.active_window().show_input_panel("Enter server IP:", "localhost", self.connect, None, None)

class CollabDisconnectFromServerCommand(sublime_plugin.ApplicationCommand, SublimeCollaboration):
    def run(self):
        self.disconnect()
    def is_enabled(self):
        global client
        return client

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
        return client

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
        return client

class CollabToggleDebugCommand(sublime_plugin.ApplicationCommand, SublimeCollaboration):
    def run(self):
        collab.connection.debug = not collab.connection.debug
