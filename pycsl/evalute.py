""" Compile-time evaluation
"""

from .grammar.operators import Operator
from .grammar.basic_types import ValType, Value

from .errors import CompileError


def _cdiv(a, b):
    # c-style division

    return a // b if isinstance(a, int) and isinstance(b, int) else a / b


OpEvalLoc = {
    Operator.ADD: lambda a, b: a + b,
    Operator.SUB: lambda a, b: a - b,
    Operator.MUL: lambda a, b: a * b,
    Operator.DIV: _cdiv,
    Operator.REM: lambda a, b: a % b,
    Operator.POW: lambda a, b: a ** b,

    Operator.MINUS: lambda a: -a,

    Operator.AND: lambda a, b: a and b,
    Operator.OR: lambda a, b: a or b,
    Operator.XOR: lambda a, b: a ^ b,
    Operator.NOT: lambda a: not a,

    Operator.EQ: lambda a, b: a == b,
    Operator.NE: lambda a, b: a != b,
    Operator.LT: lambda a, b: a < b,
    Operator.LE: lambda a, b: a <= b,
    Operator.GT: lambda a, b: a > b,
    Operator.GE: lambda a, b: a >= b,
}


def eval_op(op:Operator, lhs:Value, rhs=None):

    if lhs.type == ValType.VOID or (rhs is not None and rhs.type == ValType.VOID):
        raise CompileError("Need value type")

    if op.value >= Operator.EQ.value and op.value < Operator.LBRA.value: # boolean operators
        rettype = ValType.BOOL

    elif rhs:
        rettype = ValType(max(lhs.type.value, rhs.type.value))

    else:
        rettype = lhs.type

    if op.value < Operator.EQ.value:
        rettype = ValType(max(rettype.value, ValType.CHAR.value))

    try:
        evalfunc = OpEvalLoc[op]
    except KeyError:
        raise CompileError("Unrecognized operator: %s" % op)

    if rhs is None:
        
        return Value(rettype, evalfunc(lhs.val))

    else:
        return Value(rettype, evalfunc(lhs.val, rhs.val))
