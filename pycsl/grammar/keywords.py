""" Keywords definition.
"""

from enum import Enum

ctrl_kwds = ['if', 'else', 'for', 'while', 'return', 'break', 'continue']
def_kwds = ['def', 'class']
logic_kwds = ['and', 'or', 'xor', 'not']    # they are operators
sep_kwds = ['{', '}', ',', ':']                  # they are separators

class Keyword(Enum):

    IF = 0
    ELSE = 1
    FOR = 2
    WHILE = 3
    RETURN = 4
    BREAK = 5
    CONTINUE = 6
    DEF = 7
    CLASS = 8


class Separator(Enum):
    LCPD = 0
    RCPD = 1
    COMMA = 2
    COLON = 3


KeywordLoc = dict(zip(ctrl_kwds + def_kwds, Keyword))
SepLoc = dict(zip(sep_kwds, Separator))

