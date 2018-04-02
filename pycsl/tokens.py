""" Tokens, variables and other definitions.
"""

from enum import Enum


class Symbol:
    """ Represent a symbol. Note: only store left value here.
    """

    def __init__(self, name):
        
        self.name = name 
        self.val = None # Left value!!!!

    def __repr__(self):
        return '[Symbol %s: %r]' % (self.name, self.val)


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
