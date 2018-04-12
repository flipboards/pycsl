
from ..grammar.operators import Operator

from collections import namedtuple
from enum import Enum


class Code(Enum):
    """ Code used in CSL IR.
    """
    # Terminator
    HLT = 0
    RET = 1
    BR = 2
    INVOKE = 3

    # Arithmetic Operator
    ADD = 10
    SUB = 11
    MUL = 12
    DIV = 13
    REM = 14
    POW = 15
    AND = 16
    OR = 17
    XOR = 18
    NOT = 19

    # Memory
    ALLOC = 30
    LOAD = 31
    STORE = 32
    GETPTR = 33

    # Control
    EQ = 40
    NE = 41
    LT = 42
    LE = 43
    GT = 44
    GE = 45
    PHI = 46
    CALL = 47

    def __str__(self):
        return self.name.lower()


def op2code(op:Operator):

    ConvertTable = {
        Operator.ADD: Code.ADD,
        Operator.SUB: Code.SUB,
        Operator.MUL: Code.MUL,
        Operator.DIV: Code.DIV,
        Operator.REM: Code.REM,
        Operator.POW: Code.POW,
        Operator.ASN: None,
        Operator.ADDASN: Code.ADD,
        Operator.SUBASN: Code.SUB,
        Operator.MULASN: Code.MUL,
        Operator.DIVASN: Code.DIV,
        Operator.REMASN: Code.REM,
        Operator.POWASN: Code.POW,
        Operator.INC: Code.ADD,
        Operator.DEC: Code.SUB,
        Operator.POSTINC: Code.ADD,
        Operator.POSTDEC: Code.SUB,
        Operator.AND: Code.AND,
        Operator.OR: Code.OR,
        Operator.XOR: Code.XOR,
        Operator.NOT: Code.NOT,
        Operator.EQ: Code.EQ,
        Operator.NE: Code.NE,
        Operator.LT: Code.LT,
        Operator.LE: Code.LE,
        Operator.GT: Code.GT,
        Operator.GE: Code.GE
    }

    return ConvertTable[op]


class IR:
    """ Intermediate representation
    """
    def __init__(self, code:Code, ret, first, second=None, cond=None):
        """ code: Code instance.
            ret, first, second, cond: Can be variable/value/label, depends on code.
        """
        self.code = code 
        self.ret = ret
        self.first = first 
        self.second = second 
        self.cond = cond 

    def __str__(self):
        ret = ''

        if self.ret is not None:
            ret += ('%s =' % str(self.ret))

        if self.code is not None:
            ret += (' %s' % str(self.code))

        if self.cond is not None:
            ret += (' %s' % str(self.cond))

        if self.first is not None:
            ret += (' %s' % str(self.first))

        if isinstance(self.second, list):
            ret += (''.join((' %s' % str(s) for s in self.second)))
        elif self.second is not None:
            ret += (' %s' % str(self.second))

        return ret 
