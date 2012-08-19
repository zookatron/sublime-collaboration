class syncQueue():
    def __init__(self, process):
        self.queue = []
        self.busy = False
        self.process = process
    
    def __call__(self, data, callback=None):
        self.queue.append([data, callback])
        self.flush()

    def flush(self):
        if self.busy or len(self.queue) == 0:
            return

        self.busy = True
        data, callback = self.queue.pop(0)

        def async_done(*args):
            self.busy = False
            if callback: callback(*args)
            self.flush()
        self.process(data, async_done)



