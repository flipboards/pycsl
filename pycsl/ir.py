
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

    # Arithmetic Operator
    ADD = 3
    SUB = 4
    MUL = 5
    DIV = 6
    REM = 7
    POW = 8
    AND = 9
    OR = 10
    XOR = 11
    NOT = 12

    # Memory
    ALLOC = 13
    LOAD = 14
    STORE = 15
    GETPTR = 16

    # Control
    EQ = 17
    NE = 18
    LT = 19
    LE = 20
    GT = 21
    GE = 22
    CALL = 23
    DECL = 24


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
        Operator.POSTDEC: Code.SUB
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


# Stores meta data of a variable
# type: ValType
# scope: local == 0 / global == 1
Variable = namedtuple('Variable', ['name', 'type', 'scope'])


Function = namedtuple('Function', ['name', 'rettype', 'args'])


class Scope:
    """ Variable scope
    """
    LOCAL = 0
    GLOBAL = 1


def printir(ir:IR):
    
    if ir.code is None: # direct assignment
        print('%s = %s' % (ir.ret, ir.first))

    else:
        if ir.ret is None:
            if ir.second is None:
                print('%s %s' % (ir.code, ir.first))
            else:
                print('%s %s %s' % (ir.code, ir.first, ir.second))
        else:
            if ir.second is not None:
                print('%s = %s %s %s' % (ir.ret, ir.code, ir.first, ir.second))
            else:
                print('%s = %s %s' % (ir.ret, ir.code, ir.first))