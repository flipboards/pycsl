
from enum import Enum
from collections import namedtuple

class Operator(Enum):   
    # arithmetics
    ADD = 0
    SUB = 1
    MUL = 2
    DIV = 3
    REM = 4
    POW = 5
    # post/prefix
    PLUS = 6
    MINUS = 7
    INC = 8
    DEC = 9
    POSTINC = 10
    POSTDEC = 11
    # relationship
    EQ = 12
    NE = 13
    LT = 14
    LE = 15
    GT = 16
    GE = 17
    # logic
    AND = 18
    OR = 19
    XOR = 20
    NOT = 21
    # brackets
    LBRA = 22
    RBRA = 23
    LSUB = 24
    RSUB = 25
    # assignment
    ASN = 26
    ADDASN = 27
    SUBASN = 28
    MULASN = 29
    DIVASN = 30
    REMASN = 31
    POWASN = 32
    # comma
    MBER = 33
    COMMA = 34


OperatorRe = r'\+\+|\-\-|\!\=|[\+\-\*\/\=\^\<\>]\=?|[\(\)\[\]\.]'

OpSymbols = ['+', '-', '*', '/', '%', '^', 
            '++', '--','==', '!=', '<', '<=', '>', '>=', 
            '(', ')', '[', ']',
            '=', '+=', '-=', '*=', '/=', '%=', '^=',
            '.', ','
]

class OpAsso(Enum):
    
    LEFT = 0
    RIGHT = 1


OpPrecedenceLoc = dict(zip(Operator, [
    5, 5, 4, 4, 4, 3,
    2, 2, 2, 2, 1, 1,
    7, 7, 6, 6, 6, 6,
    8, 10, 9, 2,
    1, 1, 1, 1,
    11, 11, 11, 11, 11, 11, 11,
    1, 12
]))

OpAryLoc = dict(zip(Operator, [
    2, 2, 2, 2, 2, 2,
    1, 1, 1, 1, 1, 1,
    2, 2, 2, 2, 2, 2,
    2, 2, 2, 1,
    1, 1, 2, 1,
    2, 2, 2, 2, 2, 2, 2,
    2, 2
]))

OpAssoLoc = dict(zip(Operator, [
    0, 0, 0, 0, 0, 0,
    1, 1, 1, 1, 0, 0,
    0, 0, 0, 0, 0, 0,
    0, 0, 0, 1,
    0, 0, 0, 0,
    1, 1, 1, 1, 1, 1, 1,
    0, 0
]))

OpAsnLoc = dict(zip(Operator, [
    0, 0, 0, 0, 0, 0,
    0, 0, 1, 1, 1, 1,
    0, 0, 0, 0, 0, 0,
    0, 0, 0, 0,
    0, 0, 1, 1,
    1, 1, 1, 1, 1, 1,
    0, 0
]))

OpLoc = {}

def _build_oploc():
    global OpLoc
    
    if OpLoc:
        return 


    op_strs = OpSymbols[:6] + [
        'PLUS', 'MINUS'] + OpSymbols[6:8] + [
        'POSTINC', 'POSTDEC'] + OpSymbols[8:14] + [
        'and', 'or', 'xor', 'not'] + OpSymbols[14:]

    OpLoc = dict(zip(op_strs, Operator))
    OpLoc.pop('PLUS')
    OpLoc.pop('MINUS')
    OpLoc.pop('POSTINC')
    OpLoc.pop('POSTDEC')

_build_oploc()

def precedence(opname):
    
    if opname is None:
        return 99
    else:
        return OpPrecedenceLoc[opname]
