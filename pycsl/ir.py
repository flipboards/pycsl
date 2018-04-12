
from .grammar.operators import Operator

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
        type: can be ValType, Pointer or Label;
    """
    def __repr__(self):
        return '<Register %r>' % str(self.type)

    def __str__(self):
        return '[%s]' % str(self.type)


class Block:

    def __init__(self):
        self.registers = [] # list of  Register instances
        self.codes = []     # list of IR instances


class Identifier(namedtuple('Identifier', ['addr'])):
    
    def __repr__(self):
        return '<Identifier %r>' % self.addr

    def __str__(self):
        return '%%%d' % self.addr if isinstance(self.addr, int) else '@%s' % self.addr
