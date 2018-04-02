
from numpy import product

from enum import Enum
from collections import namedtuple

from .ast import AST, ASTType, DeclNode
from .grammar.operators import Operator, OpAryLoc, OpAsnLoc
from .grammar.basic_types import ValType, Value
from .tokens import Symbol
from .ir import IR, Code, Variable, Function, Scope, op2code
from .errors import CompileError


class IRBuilder:

    def __init__(self):
        self.global_sym_table = dict()
        self.sym_table_stack = [dict()]    # global symbol table
        self.ir_stack = []
        self.reg_count = 0      # index of unnamed variable

    def translate(self, ast:AST):
        """ Translate the whole block
        """
        assert ast.type == ASTType.ROOT

        for node in ast.nodes:
            if node.type == ASTType.DECL:
                self._translate_decl(node)
            elif node.type == ASTType.FUNC:
                # translate function definition
                pass 
            else:
                raise CompileError("Invalid code")

    
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

    def _translate_constexpr(self, ast:AST):
        """ Constant expression: Numbers, operators (without member/sub/assignment)
        """
        pass 

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
            self.write(Code.GETPTR, valptr, valarr, subarray)  # %valptr = getptr %valarr %subarray
            return valptr

        operator = ast.value
        if OpAryLoc[operator] != len(ast.nodes):
            raise CompileError('Operator ary not match: %r' % operator)

        ## This is for array indexing in RHS
        ## ptr = GETPTR(a, b)
        ## ret = LOAD ptr
        if operator == Operator.LSUB:
            valptr = translate_array_index(ast)
            valret = self.create_reg()
            self.write(Code.LOAD, valret, valptr)  # %valret = load %valptr
            return valret 

        try:
            code = op2code(operator)
        except KeyError:
            raise CompileError("Operator %s not valid" % operator)

        # ASSIGNMENT
        if OpAsnLoc[operator]:
            
            ## TODO: ADD MEMBER OPERATOR (.)

            islvalarray = (ast.nodes[0].value == Operator.LSUB)

            ## =, +=, -=
            if OpAryLoc[operator] == 2:
                val1 = self._translate_expr(ast.nodes[1])

                ## Special Case: a[b] = c
                ## ptr = GETPTR(a, b)
                ## STORE val, ptr
                if islvalarray:
                    valptr = translate_array_index(ast.nodes[0])

                    if code is not None:
                        
                        # val0 = LOAD valptr
                        val0 = self.create_reg()
                        self.write(Code.LOAD, val0, valptr)

                        valret = self.create_reg() # stores the calculation result
                        self.write(code, valret, val0, val1)
                        self.write(Code.STORE, None, valret, valptr)
                        return valret
                    else:
                        self.write(Code.STORE, None, val1, valptr)    # store retaddr val1
                        return val1
                
                ## Trivial case
                else:
                    val0 = self._translate_expr(ast.nodes[0])

                    #if not isinstance(val0, Symbol):
                    #    raise CompileError('%r cannot be lvalue' % val0)

                    if code is not None:
                        self.write(code, val0, val0, val1) # val0 = val0 + val1
                    else:
                        self.write(None, val0, val1)  # val0 = val1
                    return val0

            ## ++, --
            else:
                
                if islvalarray:
                    valptr = translate_array_index(ast.nodes[0])

                    val0 = self.create_reg()
                    self.write(Code.LOAD, val0, valptr)

                    valret = self.create_reg()
                    self.write(realop, valret, val0, Value(val0.type, 1))

                    self.write(Code.STORE, None, valret, valptr)

                    if operator in (Operator.INC, Operator.DEC):
                        return valret 
                    elif operator in (Operator.POSTINC, Operator.POSTDEC):
                        return val0 


                else:
                    val0 = self._translate_expr(ast.nodes[0])

                    if operator in (Operator.INC, Operator.DEC):
                        self.write(code, val0, val0, Value(val0.type, 1))
                        return val0 

                    elif operator in (Operator.POSTINC, Operator.POSTDEC):
                        ret = self.create_reg()
                        self.write(None, ret, val0)
                        self.write(code, val0, val0, Value(val0.type, 1))
                        return ret 

                    else:
                        raise RuntimeError()
        else:
            if OpAryLoc[operator] == 2:
                val1 = self._translate_expr(ast.nodes[1])
                val0 = self._translate_expr(ast.nodes[0])
                ret = self.create_reg()
                self.write(code, ret, val0, val1)
            else:   # -, not
                val0 = self._translate_expr(ast.nodes[0])
                ret = self.create_reg()
                self.write(code, ret, val0, None)
            return ret 
        

    def _translate_var(self, ast:AST):
        """ Translate a name
        """
        assert ast.type == ASTType.NAME

        varname = ast.value.name 

        for local_sym_table in self.sym_table_stack:
            if varname in local_sym_table:
                return local_sym_table[varname]
        
        if varname in self.global_sym_table:
            return self.global_sym_table[varname]
        else:
            raise CompileError('Variable %s not defined' % varname)


    def _translate_funcall(self, ast:AST):
        
        assert ast.type == ASTType.CALL
        
        args = [self._translate_expr(node) for node in ast.nodes[1:]]
        if ast.nodes[0].type != ASTType.NAME:
            raise CompileError('Not a function: %s' % ast.nodes[0].value)
        
        funname = ast.nodes[0].val.name

        if not funname in self.global_sym_table:
            raise CompileError('Function %s has not declared' % funname)
        if not isinstance(self.global_sym_table[funname], Function):
            raise CompileError('Cannot call variable %s' % funname)

        ret = self.create_reg()
        self.write(Code.CALL, ret, self.global_sym_table[funname], args)
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
        """ Translate a single definition.
            ast: The definition element;
            typename: ValType instance.
        """

        def translate_init_list(mast, coord, inits):
            """ Translation initialzation list.
                inits: List of tuple (coord, val) (for return)
            """
            for i, node in enumerate(mast.nodes):
                if node.type == ASTType.LIST:
                    translate_init_list(node, coord + [i], inits)
                else:
                    inits.append((coord, self._translate_expr(node)))

        def unflat(val:int, dim, coord):
            """ coord: list for return
            """
            if len(dim) > 1:
                coord.append(val//dim[0])
                unflat(val%dim[0], dim[1:], coord)
            elif len(dim) == 1:
                if val > dim[0]:
                    raise CompileError("Too much value in initialization list")
                coord.append(val)


        assert ast.type == ASTType.DECL and ast.value == DeclNode.DECLELEM
        assert len(ast.nodes) >= 1
        assert ast.nodes[0].type == ASTType.NAME

        varname = ast.nodes[0].val
        arrshape = []

        ## array shape
        if len(ast.nodes[0].nodes) > 0:
            for node in ast.nodes[0].nodes[1]:
                newdimlen = self._translate_expr(node) # must be const node?
                if newdimlen.type != ValType.INT:
                    # type cast / raise error
                    pass 

        # type = (typename, shape)
        var = self.create_var(varname, typename if not arrshape else (typename, len(arrshape)))

        # declaration only
        if len(ast.nodes) == 1:
            self.write(Code.DECL, var, (typename, arrshape), None) # this is actually unnecessary for local variables

        # declaration of single variable
        elif not arrshape:
            if ast.nodes[1].type == ASTType.LIST:
                raise CompileError('Variable %s cannot be initialized by list' % varname)
            self.write(Code.DECL, var, (typename, arrshape), self._translate_expr(ast.nodes[1]))

        # array initialization
        else:
            if ast.nodes[1].type != ASTType.LIST:
                raise CompileError('Array must be initialized by list')
            self.write(Code.DECL, var, (typename, arrshape), None)

            # fill 0 for the whole array here

            inits = []
            translate_init_list(ast.nodes[1], [], inits)
            for coord, val in inits:
                # lower dimension
                if len(coord) < len(arrshape):
                    cvt_coord = coord[:-1]
                    unflat(coord[-1], arrshape[len(coord)-1:], cvt_coord)
                else:
                    cvt_coord = coord

                ptr = self.create_reg()
                self.write(Code.GETPTR, ptr, var, cvt_coord)
                self.write(Code.STORE, None, val, ptr)   # actually translate_const_expr here, where the value will be calculated


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

