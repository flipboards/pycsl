""" Types used in IR.
"""

from collections import namedtuple


class Pointer(namedtuple('Pointer', ['type'])):
    """ Pointer type;
    """

    def unref_type(self):
        return self.type

    def __repr__(self):
        return '<Pointer %r>' % (self.type)

    def __str__(self):
        return '%s *' % (self.type)

class Label:
    """ Label type;
    """

    def __init__(self):
        self.addr = None


class Array(namedtuple('Array', ['type', 'size'])):
    """ Array type;
    """

    def __repr__(self):
        return '<Array %r x %r>' % (self.type, self.size)

    def __str__(self):
        return '[%s x %d]' % (self.type, self.size)


class Register(namedtuple('Register', ['type'])):
    """ Stores a register (temporary variable in a function)
        type: can be ValType, Pointer;
    """

    def __repr__(self):
        return '<Register %r>' % str(self.type)

    def __str__(self):
        return '[%s]' % str(self.type)

