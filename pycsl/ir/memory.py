""" Memory model for intermediate representation
"""

from enum import Enum
from collections import namedtuple


class Register(namedtuple('Register', ['type'])):
    """ Stores a register (temporary variable in a function)
        type: can be ValType, Pointer;
    """

    def __repr__(self):
        return '<Register %r>' % str(self.type)

    def __str__(self):
        return '[%s]' % str(self.type)


class Label:
    """ Label type;
    """

    def __init__(self):
        self.addr = None


class Block:

    def __init__(self):
        self.registers = [] # list of  Register instances
        self.codes = []     # list of IR instances


class MemoryLoc(Enum):

    GLOBAL = 0
    LOCAL = 1


class Identifier(namedtuple('Identifier', ['loc', 'addr'])):
    
    def __repr__(self):
        return '<Identifier %r>' % self.addr

    def __str__(self):
        return '%%%d' % self.addr if self.loc == MemoryLoc.LOCAL else '@%s' % self.addr
