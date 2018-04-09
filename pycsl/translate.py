
from numpy import product, zeros
from enum import Enum
from collections import namedtuple, OrderedDict

from .grammar.operators import Operator, OpAryLoc, OpAsnLoc
from .grammar.basic_types import ValType, Value
from .grammar.keywords import Keyword

from .tokens import Symbol
from .ast import AST, ASTType, DeclNode
from .ir import IR, Code, Label, Variable, Pointer, Function, Scope, op2code
from .errors import CompileError
from .evalute import eval_op


class Side:
    LHS = 0
    RHS = 1


class SearchableList:
    """ Either accessed by dict / list
    """
    def __init__(self):
        self.data = list()
        self.vdata = list()
        self.labels = dict()

    def __index__(self, i):
        return self.data[i]

    def append(self, d):
        self.data.append(d)
        self.vdata.append(d)

    def clear(self):
        self.data.clear()
        self.vdata.clear()
        self.labels.clear()

    def pop(self):
        top = self.data.pop()
        while self.vdata.pop() != top:
            pass 
        return top 

    def loc(self, label):
        return self.labels[label]

    def add_label(self, label, index=-1):
        self.labels[label] = self.data[index]
        self.vdata.insert(index, label)


class Translater:

    ARRAY_SIZE_LIMIT = 16384

    def __init__(self):
        self.global_sym_table = dict()
        self.sym_table_stack = [dict()]
        self.functions = OrderedDict()
        self.functions['@global'] = SearchableList()
        self.curirstack = self.functions['@global']

        self.reg_count = 0      # index of unnamed variable
        self.label_count = 0
        self.looplabelstack = []
        self.labelqueue = []

    def clear(self):
        self.curirstack.clear()
        self.looplabelstack.clear()
        self.reg_count = 0
        self.label_count = 0

    def translate(self, ast:AST):
        """ Translate the whole block
        """
        assert ast.type == ASTType.ROOT

        for node in ast.nodes:
            if node.type == ASTType.DECL:
                self._translate_decl(node)
            elif node.type == ASTType.FUNC:
                self._translate_function(node)
            else:
                raise CompileError("Invalid code")

    
    def translate_line(self, ast:AST):
        """ Translate the ast that generate by a line of code.
            There are no control / function definition in the line mode, so simply
            expression and variable declaration.
            All varaible are treated as global.
        """
        self.clear()

        if ast.type == ASTType.DECL:
            self._translate_decl(ast)
        else:
            r = self._translate_expr(ast)
            self.write(Code.RET, r) # Controversal: Need to use something to disable it in interperator.

    def _translate_function(self, ast:AST):
        
        function = self._translate_funchead(ast.nodes[0])

        if len(ast.nodes) == 1: # decalration only
            self.write(Code.DECL, function)

        else:

            self.functions[function.name] = SearchableList()
            self.curirstack = self.functions[function.name]

            # prepare argument stack
            self.reg_count = 0
            self.sym_table_stack.append(dict())

            # allocate local copy of arguments. This need to be changed when allowing reference
            for arg in function.args:
                localarg = self.create_reg(Pointer(arg.type)) # local copy
                arg.ref = localarg.name
                self.write(Code.ALLOC, localarg, arg.type)
                self.write(Code.STORE, None, arg, localarg)
                self.sym_table_stack[-1][arg.name] = arg

            # assign a local argument into current code segment
            code_addr = self.create_reg()
            self.create_var()

            self._translate_stmt(ast.nodes[1])
            self.curirstack = self.functions['@global']

    def _translate_funchead(self, ast:AST):
        """ Translate function declaration (Correponding to FUNCDECL node)
        """

        assert ast.type == ASTType.DECL and ast.value == DeclNode.FUNCDECL

        funcname = ast.nodes[0].value.name 
        funcargs = []
        for denode in ast.nodes[1].nodes:
            argname = denode.nodes[0].value.name 

            if len(denode.nodes) == 2: # notype
                argtype = denode.nodes[1].value
            else:
                argtype = ValType.VOID

            funcargs.append(Variable(argname, argtype, Scope.LOCAL))
        
        if len(ast.nodes) == 3:
            rettype = ast.nodes[2].value 
        else:
            rettype = ValType.VOID

        return self.create_func(funcname, funcargs, rettype)

    def _translate_stmt(self, ast:AST):
        """ Translate statement (including compound statement)
        """

        if ast.type == ASTType.BLOCK:
            self.sym_table_stack.append(dict())
            for node in ast.nodes:
                if node.type == ASTType.DECL:
                    self._translate_decl(node)
                else:
                    self._translate_stmt(node)
            self.sym_table_stack.pop()

        elif ast.type == ASTType.DECL:
            self._translate_decl(ast)

        elif ast.type == ASTType.CTRL:
            self._translate_ctrl(ast)

        else:
            self._translate_expr(ast)

    def _translate_ctrl(self, ast:AST):
        ## TODO: Check empty loop
        if ast.value == Keyword.IF:
            lbltrue = self.create_label()
            lblfalse = self.create_label()

            varcond = self._translate_expr(ast.nodes[0]) ## TODO: Type check
            self.write(Code.BR, None, lbltrue, lblfalse, cond=varcond)
            self.insert_label(lbltrue)
            self._translate_stmt(ast.nodes[1])

            if len(ast.nodes) == 3:
                lblend = self.create_label()
                self.write(Code.BR, None, lblend)
                self.insert_label(lblfalse)
                self._translate_stmt(ast.nodes[2])
                self.write(Code.BR, None, lblend)
                self.insert_label(lblend)
            else:
                self.write(Code.BR, None, lblfalse)
                self.insert_label(lblfalse)

        elif ast.value == Keyword.WHILE:
            lblbegin = self.create_label()
            lblloop = self.create_label()
            lblend = self.create_label()

            self.insert_label(lblbegin)
            self.looplabelstack.append((lblbegin, lblend))
            varcond = self._translate_expr(ast.nodes[0])
            self.write(Code.BR, None, lblloop, lblend, cond=varcond)
            self.insert_label(lblloop)
            self._translate_stmt(ast.nodes[1])
            self.write(Code.BR, None, lblbegin)
            self.insert_label(lblend)
            self.looplabelstack.pop()

        elif ast.value == Keyword.FOR:
            lblbegin = self.create_label()
            lblloop = self.create_label()
            lblctn = self.create_label()
            lblend = self.create_label()

            self._translate_expr(ast.nodes[0])
            self.insert_label(lblbegin)
            self.looplabelstack.append((lblctn, lblend))
            varcond = self._translate_expr(ast.nodes[1])
            self.write(Code.BR, None, lblloop, lblend, cond=varcond)
            self.insert_label(lblloop)
            self._translate_stmt(ast.nodes[3])
            self.write(Code.BR, None, lblctn)
            self.insert_label(lblctn)
            self._translate_expr(ast.nodes[2])
            self.write(Code.BR, None, lblbegin)
            self.insert_label(lblend)
            self.looplabelstack.pop()
        
        elif ast.value == Keyword.BREAK:
            if not self.looplabelstack:
                raise CompileError('"break" must be inside loop')
            self.write(Code.BR, None, self.looplabelstack[-1][1])

        elif ast.value == Keyword.CONTINUE:
            if not self.looplabelstack:
                raise CompileError('"continue" must be inside loop')
            self.write(Code.BR, None, self.looplabelstack[-1][0])

        elif ast.value == Keyword.RETURN:
            if not ast.nodes:
                self.write(Code.RET, None, Value(ValType.VOID, None))
            else:
                varret = self._translate_expr(ast.nodes[0])
                self.write(Code.RET, None, varret)

        else:
            raise RuntimeError()

    def _translate_expr(self, ast:AST, side=Side.RHS, lazyeval=False):
        """ Translate basic expression.
            lazyeval: Generate short-circuit code for and/or. But is recommended to 
                turn off this option here and let optimizer do this task.
        """
        
        if ast.type == ASTType.OP:
            return self._translate_op(ast, side, lazyeval)
        elif ast.type == ASTType.VAL:
            if side == Side.LHS:
                raise CompileError("Cannot assign to constant")
            return ast.value
        elif ast.type == ASTType.NAME:
            return self._translate_var(ast, side)
        elif ast.type == ASTType.CALL:
            return self._translate_funcall(ast)
        else:
            raise RuntimeError()

    def _eval_expr(self, ast:AST):
        """ Evaluate constant expression (values, operations)
            const variables are not supported yet
        """
        if ast.type == ASTType.OP:
            operator = ast.value
            if OpAsnLoc[operator]:
                raise CompileError("Cannot evaluate assignment")

            else:
                lhs = self._eval_expr(ast.nodes[0])
                rhs = self._eval_expr(ast.nodes[1]) if len(ast.nodes) > 1 else None

                return eval_op(operator, lhs, rhs)

        elif ast.type == ASTType.VAL:
            return ast.value

        else:
            raise CompileError('Cannot evaluate %s' % ast.type)

    def _translate_op(self, ast:AST, side, *args):

        def translate_subscript(mast, subarray):
            """ Translate continues subscripts. Notice: assignment is not allowed in indexing.
            """
            if mast.value != Operator.LSUB:
                return self._translate_expr(mast, Side.LHS, False, *args[1:])
            else:
                lhs = translate_subscript(mast.nodes[0], subarray)
                subarray.append(self._translate_expr(mast.nodes[1], Side.RHS, False, *args[1:]))
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

        lazyeval = args[0]

        operator = ast.value
        if OpAryLoc[operator] != len(ast.nodes):
            raise CompileError('Operator ary not match: %r' % operator)

        ## This is for array indexing in RHS
        ## ptr = GETPTR(a, b)
        ## ret = LOAD ptr
        if operator == Operator.LSUB:
            valptr = translate_array_index(ast)

            if side == Side.LHS:
                return valptr

            else:
                valret = self.create_reg()
                self.write(Code.LOAD, valret, valptr)  # %valret = load %valptr
                return valret 
        
        ## TODO: ADD MEMBER OPERATOR (.)

        try:
            code = op2code(operator)
        except KeyError:
            raise CompileError("Operator %s is not valid" % operator)

        # ASSIGNMENT
        if OpAsnLoc[operator]:
            
            if side == Side.LHS:
                raise CompileError("Expression is not assignable")

            ## =, +=, -=
            if OpAryLoc[operator] == 2:
                valrhs = self._translate_expr(ast.nodes[1], Side.RHS, *args)
                vallhs = self._translate_expr(ast.nodes[0], Side.LHS, *args)

                if code is not None:
                    rvallhs = self.create_reg(vallhs.type)
                    self.write(Code.LOAD, rvallhs, vallhs)
                    valret = self.create_reg() # type cast here
                    self.write(code, valret, rvallhs, valrhs)
                    self.write(Code.STORE, None, valret, vallhs)
                    
                    return valret
                else:
                    self.write(Code.STORE, None, valrhs, vallhs)  # val0 = val1
                    
                    return valrhs

            ## ++, --
            else:
                
                vallhs = self._translate_expr(ast.nodes[0], Side.LHS)
                rvallhs = self.create_reg(vallhs.type)
                self.write(Code.LOAD, rvallhs, vallhs)
                valret = self.create_reg(vallhs.type)
                self.write(code, valret, rvallhs, Value(vallhs.type, 1))
                self.write(Code.STORE, None, valret, vallhs)

                if operator in (Operator.INC, Operator.DEC):
                    return valret

                elif operator in (Operator.POSTINC, Operator.POSTDEC):
                    return rvallhs

                else:
                    raise RuntimeError()

        else:
            vallhs = self._translate_expr(ast.nodes[0], Side.RHS, *args)
            if OpAryLoc[operator] == 2:

                if lazyeval and operator in (Operator.AND, Operator.OR):
                    return self._translate_lazyevalbool(code, vallhs, ast.nodes[1], *args)

                valrhs = self._translate_expr(ast.nodes[1], Side.RHS, *args)
                valret = self.create_reg() # type cast here
                self.write(code, valret, vallhs, valrhs)

            # -, not    
            else:   
                valret = self.create_reg(vallhs.type)
                self.write(code, valret, vallhs)
            return valret 
        
    def _translate_lazyevalbool(self, code, vallhs, astrhs, *args):

        lblprev = self.get_last_label() # get last label inserted
        lblrhs = self.create_label()
        lblskip = self.create_label()

        if code == Code.AND:
            self.write(Code.BR, None, lblrhs, lblskip, cond=vallhs)
            self.insert_label(lblrhs)
            valrhs = self._translate_expr(astrhs, *args)
            self.write(Code.BR, None, lblskip)
            self.insert_label(lblskip)
            valret = self.create_reg()
            self.write(Code.PHI, valret, (vallhs, lblprev), (valrhs, lblrhs))
            return valret

        elif code == Code.OR:
            self.write(Code.BR, None, lblskip, lblrhs, cond=vallhs)
            self.insert_label(lblrhs)
            valrhs = self._translate_expr(astrhs, *args)
            self.write(Code.BR, None, lblskip)
            self.insert_label(lblskip)
            valret = self.create_reg()
            self.write(Code.PHI, valret, (vallhs, lblprev), (valrhs, lblrhs))
            return valret

        else:
            raise RuntimeError()

    def _translate_var(self, ast:AST, side):
        """ Translate a name
        """
        assert ast.type == ASTType.NAME

        varname = ast.value.name 
        var = None

        for local_sym_table in self.sym_table_stack:
            if varname in local_sym_table:
                var = local_sym_table[varname]
                break

        if not var:

            if varname in self.global_sym_table:
                var = self.global_sym_table[varname]
            else:
                raise CompileError('Variable %s not defined' % varname)

        if side == Side.LHS:
            if var.ref == None:
                raise CompileError("Cannot perform assignment into temporary variable")
            return var
        else:
            rval = self.create_reg(var.type)
            self.write(Code.LOAD, rval, var)
            return rval


    def _translate_funcall(self, ast:AST):
        
        assert ast.type == ASTType.CALL
        
        args = [self._translate_expr(node) for node in ast.nodes[1:]]
        if ast.nodes[0].type != ASTType.NAME:
            raise CompileError('Not a function: %s' % ast.nodes[0].value)
        
        funname = ast.nodes[0].value.name

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
        assert ast.value == DeclNode.VARDECL
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

        def translate_init_list(mast, coord, inits, requireconst=False):
            """ Translation initialzation list.
                inits: List of tuple (coord, val) (for return)
            """
            evalfunc = self._translate_expr if not requireconst else self._eval_expr

            for i, node in enumerate(mast.nodes):
                if node.type == ASTType.LIST:
                    translate_init_list(node, coord + [i], inits)
                else:
                    inits.append((coord + [i], evalfunc(node)))

        def unflat(val:int, dim, coord):
            """ coord: list for return
            """
            if len(dim) > 1:
                coord.append(val//dim[0])
                unflat(val%dim[0], dim[1:], coord)
            elif len(dim) == 1:
                coord.append(val)


        assert ast.type == ASTType.DECL and ast.value == DeclNode.DECLELEM
        assert len(ast.nodes) >= 1
        assert ast.nodes[0].type == ASTType.NAME

        varname = ast.nodes[0].value.name
        arrshape = []

        ## array shape
        if len(ast.nodes[0].nodes) > 0:
            for node in ast.nodes[0].nodes:
                newdimlen = self._eval_expr(node)
                if newdimlen.type != ValType.INT:
                    # type cast / raise error
                    pass 
                newlen = newdimlen.val; # this should be int
                if not isinstance(newlen, int):
                    raise RuntimeError()
                arrshape.append(newlen)

        # type = (typename, shape)
        vartype = typename if not arrshape else [typename] + arrshape
        var = self.create_var(varname, vartype)

        if arrshape and product(arrshape) > Translater.ARRAY_SIZE_LIMIT:
            raise CompileError('Array too large (%d). Try use "new" instead.' % product(arrshape))

        if len(ast.nodes) > 1 and arrshape:
            if ast.nodes[1].type != ASTType.LIST:
                raise CompileError('Array must be initialized by list')
            inits1 = []
            translate_init_list(ast.nodes[1], [], inits1, var.scope==Scope.GLOBAL)
            inits = []

            # expand init list into full coordination
            for coord, val in inits1:
                # lower dimension
                if len(coord) < len(arrshape):
                    cvt_coord = coord[:-1]
                    unflat(coord[-1], arrshape[len(coord)-1:], cvt_coord)
                else:
                    cvt_coord = coord

                for c, s in zip(cvt_coord, arrshape):
                    if c >= s:
                        raise CompileError("Too much value in initialization list")

                inits.append((coord, val))

        # only global variables need initializer; Local variable only create pointer
        if var.scope == Scope.GLOBAL:
            var.ref = varname
            if not arrshape:
                initializer = Value(vartype, self._eval_expr(ast.nodes[1]))
            else:
                init_array = zeros(arrshape, dtype=(float if vartype[0] == ValType.FLOAT else int))
                if len(ast.nodes) == 1:
                    for c, v in inits:
                        init_array[tuple(c)] = v.val
                initializer = Value(vartype, init_array)

            self.write(Code.DECL, var, vartype, initializer)

        elif var.scope == Scope.LOCAL:

            ptr = self.create_reg(Pointer(vartype))
            var.ref = ptr.name
            self.write(Code.ALLOC, ptr, vartype)

            # declaration only
            if len(ast.nodes) == 1:
                pass

            elif not arrshape:
                initializer = self._translate_expr(ast.nodes[1])
                self.write(Code.STORE, None, initializer, ptr)

            else:

                # fill 0 for the whole array here (memcpy)

                for c, v in inits:
                    elemptr = self.create_reg()
                    self.write(Code.GETPTR, elemptr, ptr, c)
                    self.write(Code.STORE, None, v, elemptr)   # actually translate_const_expr here, where the value will be calculated


    def create_reg(self, mtype=None):
        """ Create a temporary variable that can be in stack top/register
        """
        var = Variable('%d' % self.reg_count, mtype, Scope.LOCAL)
        self.reg_count += 1
        self.sym_table_stack[-1][var.name] = var 
        return var 

    def create_var(self, varname=None, vartype=ValType.VOID):
        """ Register a new variable in the corresponding symbol table.
        """
        
        # global variable
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


    def create_func(self, funcname, funcargs, rettype):
        
        func = Function(funcname, funcargs, rettype)

        if funcname in self.global_sym_table:
            raise CompileError('Function %s is already defined' % funcname)
        self.global_sym_table[funcname] = func 
        return func

    def create_label(self, label_name=None):
        label = Label(('label_%d' % self.label_count) if not label_name else label_name)
        self.label_count += 1
        return label

    def insert_label(self, label):
        """ Apply the label into the next ir.
        """
        self.labelqueue.append(label) 

    def write(self, op, ret, first=None, second=None, *args, **kwargs):

        self.curirstack.append(IR(op, ret, first, second, *args, **kwargs))
        for label in self.labelqueue:
            self.curirstack.add_label(label)
        self.labelqueue.clear()

