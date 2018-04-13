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


class Array(namedtuple('Array', ['type', 'size'])):
    """ Array type;
    """

    def __repr__(self):
        return '<Array %r x %r>' % (self.type, self.size)

    def __str__(self):
        return '[%s x %d]' % (self.type, self.size)
