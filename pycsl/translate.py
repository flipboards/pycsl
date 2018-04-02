
from numpy import product

from enum import Enum
from collections import namedtuple

from .ast import AST, ASTType, DeclNode
from .grammar.operators import Operator, OpAryLoc, OpAsnLoc
from .grammar.basic_types import ValType, Value
from .tokens import Symbol
from .ir import IR, Variable, Function, SpecialCode, Scope
from .errors import CompileError


AsnOpLoc = {
    Operator.ADDASN: Operator.ADD,
    Operator.SUBASN: Operator.SUB,
    Operator.MULASN: Operator.MUL,
    Operator.DIVASN: Operator.DIV,
    Operator.REMASN: Operator.REM,
    Operator.POWASN: Operator.POW,
    Operator.INC: Operator.ADD,
    Operator.DEC: Operator.SUB,
    Operator.POSTINC: Operator.ADD,
    Operator.POSTDEC: Operator.SUB
}


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


class IRBuilder:

    def __init__(self):
        self.global_sym_table = dict()
        self.sym_table_stack = [dict()]    # global symbol table
        self.ir_stack = []
        self.reg_count = 0      # index of unnamed variable

    def translate(self, ast:AST):
        pass 
    
    def translate_line(self, ast:AST):
        """ Translate the ast that generate by a line of code.
            There are no control / function definition in the line mode, so simply
            expression and variable declaration.
            All varaible are treated as global.
        """
        self.ir_stack.clear()
        self.reg_count = 0

        if ast.type == ASTType.DECL:
            self._translate_decl(ast)
        else:
            self._translate_expr(ast)


    def _translate_stmt(self, ast:AST):
        """ Translate statement (including compound statement)
        """

        if ast.type == ASTType.BLOCK:
            self.sym_table_stack.append(dict())
            for node in ast.nodes:
                self._translate_stmt(node)
            self.sym_table_stack.pop()

        elif ast.type == ASTType.DECL:
            self._translate_decl(ast)

        elif ast.type == ASTType.CTRL:
            self._translate_ctrl(ast)

        else:
            self._translate_expr(ast)

    def _translate_expr(self, ast:AST):
        
        if ast.type == ASTType.OP:
            return self._translate_op(ast)
        elif ast.type == ASTType.VAL:
            return ast.value
        elif ast.type == ASTType.NAME:
            return self._translate_var(ast)
        elif ast.type == ASTType.CALL:
            return self._translate_funcall(ast)
        else:
            raise RuntimeError()

    def _translate_op(self, ast:AST):

        def translate_subscript(mast, subarray):
            if mast.value != Operator.LSUB:
                return self._translate_expr(mast)
            else:
                lhs = translate_subscript(mast.nodes[0], subarray)
                subarray.append(self._translate_expr(mast.nodes[1]))
                return lhs 

        def translate_array_index(mast):
            """ Translate array indexing, return the pointer to array element;
                Currently unsupport pointer;
            """
            subarray = []
            valarr = translate_subscript(mast, subarray)
            valptr = self.create_reg()
            self.write(SpecialCode.GETPTR, valptr, valarr, subarray)  # %valptr = getptr %valarr %subarray
            return valptr

        if OpAryLoc[ast.value] != len(ast.nodes):
            raise CompileError('Operator ary not match: %r' % ast.value)

        ## This is for array indexing in RHS
        ## ptr = GETPTR(a, b)
        ## ret = LOAD ptr
        if ast.value == Operator.LSUB:
            valptr = translate_array_index(ast)
            valret = self.create_reg()
            self.write(SpecialCode.LOAD, valret, valptr)  # %valret = load %valptr
            return valret 

        # ASSIGNMENT
        if OpAsnLoc[ast.value]:
            
            ## TODO: ADD MEMBER OPERATOR (.)

            islvalarray = (ast.nodes[0].value == Operator.LSUB)

            ## REALOP: Real arithmetic operator; If op == '=' then realop is None
            if ast.value != Operator.ASN:
                try:
                    realop = AsnOpLoc[ast.value]
                except KeyError:
                    raise CompileError('Invalid assign operator: %r' % ast.value)
            else:
                realop = None  

            ## =, +=, -=
            if OpAryLoc[ast.value] == 2:
                val1 = self._translate_expr(ast.nodes[1])

                ## Special Case: a[b] = c
                ## ptr = GETPTR(a, b)
                ## STORE val, ptr
                if islvalarray:
                    valptr = translate_array_index(ast.nodes[0])

                    if realop is not None:
                        
                        # val0 = LOAD valptr
                        val0 = self.create_reg()
                        self.write(SpecialCode.LOAD, val0, valptr)

                        valret = self.create_reg() # stores the calculation result
                        self.write(realop, valret, val0, val1)
                        self.write(SpecialCode.STORE, None, valret, valptr)
                        return valret
                    else:
                        self.write(SpecialCode.STORE, None, val1, valptr)    # store retaddr val1
                        return val1
                
                ## Trivial case
                else:
                    val0 = self._translate_expr(ast.nodes[0])

                    #if not isinstance(val0, Symbol):
                    #    raise CompileError('%r cannot be lvalue' % val0)

                    if realop is not None:
                        self.write(realop, val0, val0, val1) # val0 = val0 + val1
                    else:
                        self.write(None, val0, val1)  # val0 = val1
                    return val0

            ## ++, --
            else:
                
                if islvalarray:
                    valptr = translate_array_index(ast.nodes[0])

                    val0 = self.create_reg()
                    self.write(SpecialCode.LOAD, val0, valptr)

                    valret = self.create_reg()
                    self.write(realop, valret, val0, Value(val0.type, 1))

                    self.write(SpecialCode.STORE, None, valret, valptr)

                    if ast.value in (Operator.INC, Operator.DEC):
                        return valret 
                    elif ast.value in (Operator.POSTINC, Operator.POSTDEC):
                        return val0 


                else:
                    val0 = self._translate_expr(ast.nodes[0])

                    if ast.value in (Operator.INC, Operator.DEC):
                        self.write(realop, val0, val0, Value(val0.type, 1))
                        return val0 

                    elif ast.value in (Operator.POSTINC, Operator.POSTDEC):
                        ret = self.create_reg()
                        self.write(None, ret, val0)
                        self.write(realop, val0, val0, Value(val0.type, 1))
                        return ret 

                    else:
                        raise RuntimeError()
        else:
            if OpAryLoc[ast.value] == 2:
                val1 = self._translate_expr(ast.nodes[1])
                val0 = self._translate_expr(ast.nodes[0])
                ret = self.create_reg()
                self.write(ast.value, ret, val0, val1)
            else:   # -, not
                val0 = self._translate_expr(ast.nodes[0])
                ret = self.create_reg()
                self.write(ast.value, ret, val0, None)
            return ret 
        

    def _translate_var(self, ast:AST):
        """ Translate a name
        """

        varname = ast.value.name 

        for local_sym_table in self.sym_table_stack:
            if varname in local_sym_table:
                return local_sym_table[varname]
        
        if varname in self.global_sym_table:
            return self.global_sym_table[varname]
        else:
            raise CompileError('Variable %s not defined' % varname)


    def _translate_funcall(self, ast:AST):
        
        # assert ast.type == ASTType.CALL
        
        args = [self._translate_expr(node) for node in ast.nodes[1:]]
        if ast.nodes[0].type != ASTType.NAME:
            raise CompileError('Not a function: %s' % ast.nodes[0].value)
        
        funname = ast.nodes[0].val.name

        if not funname in self.global_sym_table:
            raise CompileError('Function %s has not declared' % funname)
        if not isinstance(self.global_sym_table[funname], Function):
            raise CompileError('Cannot call variable %s' % funname)

        ret = self.create_reg()
        self.write(SpecialCode.CALL, ret, self.global_sym_table[funname], args)
        return ret 


    def _translate_decl(self, ast:AST):
        """ Translate variable decalaration
        """
        assert len(ast.value) == DeclNode.VARDECL
        assert ast.nodes[0].type == ASTType.TYPE

        if len(ast.nodes) < 2:
            raise CompileError('Invalid declaration')

        for node in ast.nodes[1:]:
            self._translate_decl_elem(node, ast.nodes[0].value)

        
    def _translate_decl_elem(self, ast:AST, typename):
        
        assert ast.type == ASTType.DECL and ast.value == DeclNode.DECLELEM
        assert len(ast.nodes) >= 1
        assert ast.nodes[0].type == ASTType.NAME

        varname = ast.nodes[0].val
        arraylen = []

        # array
        if len(ast.nodes[0].nodes) > 0:
            for node in ast.nodes[0].nodes[1]:
                newdimlen = self._translate_expr(node) # must be const node?
                if newdimlen.type != ValType.INT:
                    # type cast / raise error
                    pass 

        var = self.create_var(varname, typename if not arraylen else (typename, len(arraylen)))

        # declaration only
        if len(ast.nodes) == 1:
            self.write(SpecialCode.DEFINE, var, (typename, arraylen), None)
        else:
            # single variable: direct initialization
            if not arraylen:
                if ast.nodes[1].type == ASTType.LIST:
                    raise CompileError('Variable %s cannot be initialized by list' % varname)
                self.write(SpecialCode.DEFINE, var, (typename, arraylen), self._translate_expr(ast.nodes[1]))
            # array
            else:
                if ast.nodes[1].type != ASTType.LIST:
                    raise CompileError('Array must be initialized by list')
                self.write(SpecialCode.DEFINE, var, (typename, arraylen), None)

                # fill 0 for the whole array

                def unflat(marraylen, x):
                    return []

                def fill(mast, marraylen, coord):
                    
                    # recursive until a single bracket

                    if mast.nodes[0].type != ASTType.LIST:
                        
                        # we perform no check here. Assume every child is not list
                        
                        if len(mast.nodes) > product(arraylen):
                            raise CompileError('Initialization list too long')

                        for i in range(len(mast.nodes)):

                            ptr = self.create_reg()
                            self.write(SpecialCode.LOAD, ptr, var, coord + unflat(marraylen, i))
                            self.write(SpecialCode.STORE, None, self._translate_expr(mast.nodes[i]), ptr)   # actually translate_const_expr here, where the value will be calculated

                    else:
                        
                        if len(marraylen) == 1:
                            raise CompileError('Dimension too high')

                        for i in range(len(mast.nodes)):
                            
                            fill(mast.nodes[i], marraylen[1:], coord + [i])

                if len(ast.nodes[1].nodes) > 0: # c++ style initialization is allowed: int a[2] = {};
                    fill(ast.nodes[1], arraylen, [])


    def create_reg(self, mtype=None):
        """ Create a temporary variable that can be in stack top/register
        """
        var = Variable('%d' % self.reg_count, mtype, Scope.LOCAL)
        self.reg_count += 1
        self.sym_table_stack[-1][var.name] = var 
        return var 

    def create_var(self, varname, vartype):
        """ Register a new variable in the corresponding symbol table.
        """
        
        if len(self.sym_table_stack) == 0:
            if varname in self.global_sym_table:
                raise CompileError('Variable %s is already defined' % varname)
            var = Variable(varname, vartype, 0)
            self.global_sym_table[varname] = var 

        else:
            if varname in self.sym_table_stack[-1]:
                raise CompileError('Variable %s is already defined' % varname)
            var = Variable(varname, vartype, 1)
            self.sym_table_stack[-1][varname] = var

        return var           


    def write(self, op, ret, first=None, second=None):

        self.ir_stack.append(IR(op, ret, first, second))

