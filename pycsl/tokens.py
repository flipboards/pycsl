""" Tokens, variables and other definitions.
"""

from enum import Enum
from collections import namedtuple

# A simple wrapper for string
Symbol = namedtuple('Symbol', ['name'])


class TokenType(Enum):
    NONE = 0    # reserved
    VAL = 1     # value
    NAME = 2    # either variable/class name
    OP = 3      # operator
    TYPE = 4    # type keyword (int, float, ...)
    DEF = 5     # definition keyword (class, def, struct, ...)
    CTRL = 6    # control keyword (if, else, ...)
    SEP = 7     # separator ({}, comma)
    EOF = 8     # EOF
    EOL = 9     # EOL (;)


class Token:
    """ Token object
    """

    def __init__(self, tp:TokenType, val):
        """ tp ===> Type
            val ===> Specific value
        """
        self.tp = tp 
        self.val = val 
        
    def __repr__(self):
        return '<%s, %r>' % (self.tp.name, self.val)
