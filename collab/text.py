

class CollabSystem(object):
    def __init__(self):
        pass

class TextSystemAPI(object):
    provides = {'text':True}

    def getLength(self):
        return len(self.snapshot)

    def getText(self):
        return self.snapshot

    def insert(self, pos, text, callback=None):
        op = [{'p':pos, 'i':text}]
        self.submitOp(op, callback)
        return op
    
    def delete(self, pos, length, callback=None):
        op = [{'p':pos, 'd':self.snapshot[pos:(pos+length)]}]
        self.submitOp(op, callback)
        return op
    
    def _register(self):
        self.on('remoteop', self._on_doc_remoteop)

    def _on_doc_remoteop(self, op, snapshot):
        for component in op:
            if 'i' in component:
                self.emit('insert', component['p'], component['i'])
            else:
                self.emit('delete', component['p'], component['d'])

class TextSystem(CollabSystem):
    name = 'text'
    api = TextSystemAPI()

    def create(self):
        return ''

    def strInject(self, s1, pos, s2):
        return s1[:pos] + s2 + s1[pos:]

    def checkValidComponent(self, c):
        if not isinstance(c, dict): raise ValueError('component must be a normal dict')
        if 'p' not in c: raise ValueError('component missing position field')
        if 'i' not in c and 'd' not in c: raise ValueError('component needs an i or d field')
        if c['p'] < 0: raise ValueError('position cannot be negative')

    def checkValidOp(self, op):
        try:
            [self.checkValidComponent(c) for c in op]
        except Exception as e:
            return False
        return True

    def apply(self, snapshot, op):
        if self.checkValidOp(op):
            for component in op:
                if 'i' in component:
                    snapshot = self.strInject(snapshot, component['p'], component['i'])
                else:
                    deleted = snapshot[component['p']:(component['p'] + len(component['d']))]
                    if(component['d'] != deleted): raise Exception("Delete component '{0}' does not match deleted text '{1}'".format(component['d'], deleted))
                    snapshot = snapshot[:component['p']] + snapshot[(component['p'] + len(component['d'])):]
                return snapshot

    def append(self, newOp, c):
        if 'i' in c and c['i'] == '': return
        if 'd' in c and c['d'] == '': return
        if len(newOp) == 0:
            newOp.append(c)
        else:
            last = newOp[len(newOp) - 1]

            if 'i' in last and 'i' in c and last['p'] <= c['p'] <= (last['p'] + len(last['i'])):
                newOp[len(newOp) - 1] = {'i':self.strInject(last['i'], c['p'] - last['p'], c['i']), 'p':last['p']}
            elif 'd' in last and 'd' in c and c['p'] <= last['p'] <= (c['p'] + len(c['d'])):
                newOp[len(newOp) - 1] = {'d':self.strInject(c['d'], last['p'] - c['p'], last['d']), 'p':c['p']}
            else:
                newOp.append(c)

    def compose(self, op1, op2):
        if self.checkValidOp(op1) and self.checkValidOp(op2):
            newOp = list(op1)
            [self.append(newOp, c) for c in op2]
            return newOp

    def compress(self, op):
        return self.compose([], op)

    def normalize(self, op):
        newOp = []

        if(isinstance(op, dict)): op = [op]

        for c in op:
            if 'p' not in c or not c['p']: c['p'] = 0
            self.append(newOp, c)

        return newOp

    def transformPosition(self, pos, c, insertAfter=False):
        if 'i' in c:
            if c['p'] < pos or (c['p'] == pos and insertAfter):
                return pos + len(c['i'])
            else:
                return pos
        else:
            if pos <= c['p']:
                return pos
            elif pos <= c['p'] + len(c['d']):
                return c['p']
            else:
                return pos - len(c['d'])

    def transformCursor(self, position, op, insertAfter=False):
        for c in op:
            position = self.transformPosition(position, c, insertAfter) 
        return position

    def transformComponent(self, dest, c, otherC, type):
        if self.checkValidOp([c]) and self.checkValidOp([otherC]):
            if 'i' in c:
                self.append(dest, {'i':c['i'], 'p':self.transformPosition(c['p'], otherC, type == 'right')})
            else:
                if 'i' in otherC:
                    s = c['d']
                    if c['p'] < otherC['p']:
                        self.append(dest, {'d':s[:otherC['p'] - c['p']], 'p':c['p']})
                        s = s[(otherC['p'] - c['p']):]
                        pass
                    if s != '':
                        self.append(dest, {'d':s, 'p':c['p'] + len(otherC['i'])})
                else:
                    if c['p'] >= otherC['p'] + len(otherC['d']):
                        self.append(dest, {'d':c['d'], 'p':c['p'] - len(otherC['d'])})
                    elif c['p'] + len(c['d']) <= otherC['p']:
                        self.append(dest, c)
                    else:
                        newC = {'d':'', 'p':c['p']}
                        if c['p'] < otherC['p']:
                            newC['d'] = c['d'][:(otherC['p'] - c['p'])]
                            pass
                        if c['p'] + len(c['d']) > otherC['p'] + len(otherC['d']):
                            newC['d'] += c['d'][(otherC['p'] + len(otherC['d']) - c['p']):]
                            pass

                        intersectStart = max(c['p'], otherC['p'])
                        intersectEnd = min(c['p'] + len(c['d']), otherC['p'] + len(otherC['d']))
                        cIntersect = c['d'][intersectStart - c['p']:intersectEnd - c['p']]
                        otherIntersect = otherC['d'][intersectStart - otherC['p']:intersectEnd - otherC['p']]
                        if cIntersect != otherIntersect:
                            raise Exception('Delete ops delete different text in the same region of the document')

                        if newC['d'] != '':
                            newC['p'] = self.transformPosition(newC['p'], otherC)
                        self.append(dest, newC)

            return dest

    def invertComponent(self, c):
        if 'i' in c:
            return {'d':c['i'], 'p':c['p']}
        else:
            return {'i':c['d'], 'p':c['p']}

    def invert(self, op):
        return [self.invertComponent(c) for c in reversed(op)]

    def transformComponentX(self, left, right, destLeft, destRight):
        self.transformComponent(destLeft, left, right, 'left')
        self.transformComponent(destRight, right, left, 'right')

    def transformX(self, leftOp, rightOp):
        if self.checkValidOp(leftOp) and self.checkValidOp(rightOp):
            newRightOp = []

            for rightComponent in rightOp:
                newLeftOp = []

                k = 0
                while k < len(leftOp):
                    nextC = []
                    self.transformComponentX(leftOp[k], rightComponent, newLeftOp, nextC)
                    k+=1

                    if len(nextC) == 1:
                        rightComponent = nextC[0]
                    elif len(nextC) == 0:
                        [self.append(newLeftOp, l) for l in leftOp[k:]]
                        rightComponent = None
                        break
                    else:
                        l_, r_ = self.transformX(leftOp[k:], nextC)
                        [self.append(newLeftOp, l) for l in l_]
                        [self.append(newRightOp, r) for r in r_]
                        rightComponent = None
                        break
            
                if rightComponent:
                    self.append(newRightOp, rightComponent)
                leftOp = newLeftOp

            return [leftOp, newRightOp]

    def transform(self, op, otherOp, side):
        if side != 'left' and side != 'right':
            raise ValueError("side must be 'left' or 'right'")

        if len(otherOp) == 0:
            return op

        if len(op) == 1 and len(otherOp) == 1:
            return self.transformComponent([], op[0], otherOp[0], side)

        if side == 'left':
            left, _ = self.transformX(op, otherOp)
            return left
        else:
            _, right = self.transformX(otherOp, op)
            return right
