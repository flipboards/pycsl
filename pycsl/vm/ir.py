""" Intermediate code.
"""

from enum import Enum

class StackIR:
    
    class Code(Enum):
        HLT = 0

        PUSH = 20
        ASN = 21
        POP = 22

        ADD = 50
        SUB = 51
        MUL = 52
        DIV = 53
        POW = 54

        PASS = 60
        AND = 61
        OR = 62
        XOR = 63
        NOT = 64

        EQ = 70
        NE = 71
        GT = 72
        GE = 73
        LT = 74
        LE = 75

    def __init__(self, code:StackIR.Code, arg):
        self.code = code 
        self.arg = arg 
