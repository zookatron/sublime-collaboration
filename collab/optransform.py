def op_inject(s1, pos, s2):
    return s1[:pos] + s2 + s1[pos:]

def op_apply(snapshot, op):
    for component in op:
        if 'i' in component:
            snapshot = op_inject(snapshot, component['p'], component['i'])
        else:
            deleted = snapshot[component['p']:(component['p'] + len(component['d']))]
            if(component['d'] != deleted): raise Exception("Delete component '{0}' does not match deleted text '{1}'".format(component['d'], deleted))
            snapshot = snapshot[:component['p']] + snapshot[(component['p'] + len(component['d'])):]
    return snapshot

def op_append(newOp, c):
    if 'i' in c and c['i'] == '': return
    if 'd' in c and c['d'] == '': return
    if len(newOp) == 0:
        newOp.append(c)
    else:
        last = newOp[len(newOp) - 1]

        if 'i' in last and 'i' in c and last['p'] <= c['p'] <= (last['p'] + len(last['i'])):
            newOp[len(newOp) - 1] = {'i':op_inject(last['i'], c['p'] - last['p'], c['i']), 'p':last['p']}
        elif 'd' in last and 'd' in c and c['p'] <= last['p'] <= (c['p'] + len(c['d'])):
            newOp[len(newOp) - 1] = {'d':op_inject(c['d'], last['p'] - c['p'], last['d']), 'p':c['p']}
        else:
            newOp.append(c)

def op_compose(op1, op2):
    newOp = list(op1)
    [op_append(newOp, c) for c in op2]
    return newOp

def op_compress(op):
    return op_compose([], op)

def op_normalize(op):
    newOp = []

    if(isinstance(op, dict)): op = [op]

    for c in op:
        if 'p' not in c or not c['p']: c['p'] = 0
        op_append(newOp, c)

    return newOp

def op_invert_component(c):
    if 'i' in c:
        return {'d':c['i'], 'p':c['p']}
    else:
        return {'i':c['d'], 'p':c['p']}

def op_invert(op):
    return [op_invert_component(c) for c in reversed(op)]

def op_transform_position(pos, c, insertAfter=False):
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

def op_transform_cursor(position, op, insertAfter=False):
    for c in op:
        position = op_transform_position(position, c, insertAfter)
    return position

def op_transform_component(dest, c, otherC, type):
    if 'i' in c:
        op_append(dest, {'i':c['i'], 'p':op_transform_position(c['p'], otherC, type == 'right')})
    else:
        if 'i' in otherC:
            s = c['d']
            if c['p'] < otherC['p']:
                op_append(dest, {'d':s[:otherC['p'] - c['p']], 'p':c['p']})
                s = s[(otherC['p'] - c['p']):]
                pass
            if s != '':
                op_append(dest, {'d':s, 'p':c['p'] + len(otherC['i'])})
        else:
            if c['p'] >= otherC['p'] + len(otherC['d']):
                op_append(dest, {'d':c['d'], 'p':c['p'] - len(otherC['d'])})
            elif c['p'] + len(c['d']) <= otherC['p']:
                op_append(dest, c)
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
                    newC['p'] = op_transform_position(newC['p'], otherC)
                op_append(dest, newC)

    return dest

def op_transform_component_x(left, right, destLeft, destRight):
    op_transform_component(destLeft, left, right, 'left')
    op_transform_component(destRight, right, left, 'right')

def op_transform_x(leftOp, rightOp):
    newRightOp = []

    for rightComponent in rightOp:
        newLeftOp = []

        k = 0
        while k < len(leftOp):
            nextC = []
            op_transform_component_x(leftOp[k], rightComponent, newLeftOp, nextC)
            k+=1

            if len(nextC) == 1:
                rightComponent = nextC[0]
            elif len(nextC) == 0:
                [op_append(newLeftOp, l) for l in leftOp[k:]]
                rightComponent = None
                break
            else:
                l_, r_ = op_transform_x(leftOp[k:], nextC)
                [op_append(newLeftOp, l) for l in l_]
                [op_append(newRightOp, r) for r in r_]
                rightComponent = None
                break

        if rightComponent:
            op_append(newRightOp, rightComponent)
        leftOp = newLeftOp

    return [leftOp, newRightOp]

def op_transform(op, otherOp, side):
    if side != 'left' and side != 'right':
        raise ValueError("side must be 'left' or 'right'")

    if len(otherOp) == 0:
        return op

    if len(op) == 1 and len(otherOp) == 1:
        return op_transform_component([], op[0], otherOp[0], side)

    if side == 'left':
        left, _ = op_transform_x(op, otherOp)
        return left
    else:
        _, right = op_transform_x(otherOp, op)
        return right
