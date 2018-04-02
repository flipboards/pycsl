
from collections import namedtuple
from enum import Enum

# Intermediate Representation
# We use four element codes here. 
# code: Operator/SpecialCode
# ret, first, second: usually Variable; in come cases Label
IR = namedtuple('IR', ['code', 'ret', 'first', 'second']) 

# Stores meta data of a variable
# type: ValType
# scope: local == 0 / global == 1
Variable = namedtuple('Variable', ['name', 'type', 'scope'])


Function = namedtuple('Function', ['name', 'rettype', 'args'])

class Scope:
    LOCAL = 0
    GLOBAL = 1


class SpecialCode(Enum):
    """ Special code used in IR.
    """

    JUMP = 0        # jump to a certain address
    CJUMP = 1       # jump to first when second == 0
    CALL = 2        # call a function address
    LOAD = 3        # ret = *first
    STORE = 4       # *second = first
    GETPTR = 5      # ret = first + second
    DEFINE = 6
