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

        SublimeListener.on("modified", self._on_view_modified)
        SublimeListener.on("close", self._on_view_close)
        SublimeListener.on("post_save", self._on_view_post_save)

        self.prevvalue = self.doc.getText()
        sublime.set_timeout(lambda: self._replaceText(self.prevvalue), 0)
        self.doc.on('insert', self._on_doc_insert)
        self.doc.on('delete', self._on_doc_delete)

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

    def _on_view_modified(self, view):
        if not self.view: return
        if view.id() == self.view.id() and self.doc:
            self.prevvalue = self._getText()
            self._applyChange(self.doc, self.doc.getText(), self.prevvalue)

    def _on_view_post_save(self, view):
        if not self.view: return
        if view.id() == self.view.id() and self.doc:
            view.set_scratch(False)

    def _on_view_close(self, view):
        if not self.view: return
        if view.id() == self.view.id() and self.doc:
            print("closed "+self.doc.name)
            self.doc.close()
            SublimeListener.removeListener("modified", self._on_view_modified)
            SublimeListener.removeListener("close", self._on_view_close)
            self.doc.removeListener('insert', self._on_doc_insert)
            self.doc.removeListener('delete', self._on_doc_delete)
            self.view = None
            self.doc = None
            self.emit("close")

    def _applyChange(self, doc, oldval, newval):
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

    def _on_doc_insert(self, pos, text):
        sublime.set_timeout(lambda: self._insertText(pos, text), 0)

    def _on_doc_delete(self, pos, text):
        sublime.set_timeout(lambda: self._deleteText(pos, text), 0)
    
    def _getText(self):
        return self.view.substr(sublime.Region(0, self.view.size())).replace('\r\n', '\n')

    def _replaceText(self, text):
        if self._getText() == text: return
        edit = self.view.begin_edit()
        self.view.replace(edit, sublime.Region(0, self.view.size()), text)
        self.view.end_edit(edit)

    def _insertText(self, pos, text):
        edit = self.view.begin_edit()
        self.view.insert(edit, pos, text)
        self.view.end_edit(edit)

    def _deleteText(self, pos, text):
        edit = self.view.begin_edit()
        self.view.erase(edit, sublime.Region(pos, pos+len(text)))
        self.view.end_edit(edit)



client = None
server = None
editors = {}

class SublimeCollaboration(object):
    def connect(self, host):
        global client
        if client: self.disconnect()
        client = collab.client.CollabClient(host, 6633)
        print("connected")

    def disconnect(self):
        global client
        if not client: return
        client.disconnect()
        client = None
        print("disconnected")

    def open(self, name):
        global client
        if not client: return
        if name in editors:
            return editors[name].focus()
        client.open(name, 'text', self.open_callback)

    def add_current(self, name):
        global client
        if not client: return
        if name in editors:
            return editors[name].focus()
        view = sublime.active_window().active_view()
        client.open(name, 'text', lambda error, doc: self.add_callback(view, error, doc), snapshot=view.substr(sublime.Region(0, view.size())))

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
        editor.on('close', lambda: editors.pop(doc.name))
        editors[doc.name] = editor

    def toggle_server(self):
        global server
        if server:
            server.close()
            server = None
            print("server closed")
        else:
            server = collab.server.CollabServer({'host':'127.0.0.1', 'port':6633})
            server.run_forever()
            print("server started")

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
        sublime.active_window().show_input_panel("Enter document name:", "blag", self.open, None, None)
    def is_enabled(self):
        global client
        return client

class CollabAddCurrentDocumentCommand(sublime_plugin.ApplicationCommand, SublimeCollaboration):
    def run(self):
        global client
        if not client: return
        sublime.active_window().show_input_panel("Enter document name:", "blag", self.add_current, None, None)
    def is_enabled(self):
        global client
        return client