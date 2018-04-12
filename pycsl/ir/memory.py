""" Memory model for intermediate representation
"""

from enum import Enum
from collections import namedtuple


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
