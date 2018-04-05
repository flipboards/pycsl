
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
    DECL = 48

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

        if isinstance(self.second, tuple) or isinstance(self.second, list):
            ret += (''.join((' %s' % s for s in self.second)))
        elif self.second is not None:
            ret += (' %s' % str(self.second))

        return ret 


class Label(namedtuple('Label', ['name'])):
    """ Label used for code.
    """

    def __repr__(self):
        return '<Label %r>' % self.name

    def __str__(self):
        return str(self.name)


class Variable(namedtuple('Variable', ['name', 'type', 'scope'])):
    """ Stores meta data of a variable
        type: ValType
        cope: local == 0 / global == 1
    """
    def __repr__(self):
        return '<Variable %r %r %r>' % (self.scope, self.type, self.name)

    def __str__(self):
        if self.scope == Scope.GLOBAL:
            return '[Global %s %s]' % (self.type, self.name)
        else:
            return '[%s %s]' % (self.type, self.name)


class Function(namedtuple('Function', ['name', 'type', 'args'])):
    """ Stores meta data of function.
        type: ValType (type of returned variable)
        args: list of Variables that are present in this function.
        (Arguments are registered in local variables before)
    """
    def __repr__(self):
        return '<Function %r %r(%r)>' (self.type, self.name, ''.join((str(a) for a in self.args)))

    def __str__(self):
        return '[%s %s(%s)]' % (self.type, self.name, ''.join((str(a) for a in self.args))


class Scope:
    """ Variable scope
    """
    GLOBAL = 0
    LOCAL = 1
