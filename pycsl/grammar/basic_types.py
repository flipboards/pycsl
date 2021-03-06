
from enum import Enum

typenames = ['void', 'bool', 'char', 'int', 'float']

class ValType(Enum):
        
    VOID = 0
    BOOL = 1
    CHAR = 2
    INT = 3
    FLOAT = 4

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name.lower()


TypenameLoc = dict(zip(typenames, ValType))

SizeofLoc = {
    ValType.BOOL: 1,
    ValType.CHAR: 1,
    ValType.INT: 4,
    ValType.FLOAT: 4
}

class Value:
    """ Represent an immediate value (like a number/char/string)
    """

    def __init__(self, vtype, val):
        self.type = vtype 
        self.val = val 

    @staticmethod
    def parse(string:str):
        
        if string == '':
            self.vtype == ValType.STR
            self.val = ''

        elif '.' in string or 'e' in string:
            try:
                return Value(ValType.FLOAT, float(string))
            except ValueError:
                raise ParseError(string)
        else:
            try:
                return Value(ValType.INT, int(string))
            except ValueError:
                raise ParseError(string)

    def __repr__(self):
        return '[%s: %r]' % (self.type, self.val)

    def __str__(self):
        return '[%s %r]' % (self.type, self.val)
