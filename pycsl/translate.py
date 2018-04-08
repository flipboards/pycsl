
from numpy import product
from enum import Enum
from collections import namedtuple, OrderedDict

from .grammar.operators import Operator, OpAryLoc, OpAsnLoc
from .grammar.basic_types import ValType, Value
from .grammar.keywords import Keyword

from .tokens import Symbol
from .ast import AST, ASTType, DeclNode
from .ir import IR, Code, Label, Variable, Function, Scope, op2code
from .errors import CompileError


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

    def __init__(self):
        self.global_sym_table = dict()
        self.sym_table_stack = [dict()]    # global symbol table
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

            # prepare local arguments
            self.sym_table_stack.append(dict())
            for arg in function.args:
                self.sym_table_stack[-1][arg.name] = arg 

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

    def _translate_expr(self, ast:AST, asn=True, lazyeval=False, isconst=False):
        """ Translate basic expression.
            asn: Allow assignment;
            lazyeval: Generate short-circuit code for and/or. But is recommended to 
                turn off this option here and let optimizer do this task.
            isconst: Requires Values / non-assignment operators only;
        """
        
        if ast.type == ASTType.OP:
            return self._translate_op(ast, asn, lazyeval, isconst)
        elif ast.type == ASTType.VAL:
            return ast.value
        elif ast.type == ASTType.NAME:
            if isconst:
                raise CompileError("Constant expression required") ## TODO: 'const' keyword required
            return self._translate_var(ast)
        elif ast.type == ASTType.CALL:
            if isconst:
                raise CompileError("Constant expression required")
            return self._translate_funcall(ast)
        else:
            raise RuntimeError()         

    def _translate_op(self, ast:AST, *args):

        def translate_subscript(mast, subarray):
            """ Translate continues subscripts. Notice: assignment is not allowed in indexing.
            """
            if mast.value != Operator.LSUB:
                return self._translate_expr(mast, False, *args[1:])
            else:
                lhs = translate_subscript(mast.nodes[0], subarray)
                subarray.append(self._translate_expr(mast.nodes[1], False, *args[1:]))
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

        asn, lazyeval, isconst = args 

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
        ## TODO: ADD MEMBER OPERATOR (.)

        try:
            code = op2code(operator)
        except KeyError:
            raise CompileError("Operator %s not valid" % operator)

        # ASSIGNMENT
        if OpAsnLoc[operator]:
            
            if not asn or isconst:
                raise CompileError("Assignment is not allowed")

            islvalarray = (ast.nodes[0].value == Operator.LSUB)

            ## =, +=, -=
            if OpAryLoc[operator] == 2:
                val1 = self._translate_expr(ast.nodes[1], *args)

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
                    val0 = self._translate_expr(ast.nodes[0], *args)

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
                        ret = self.create_reg(val0.type)
                        self.write(None, ret, val0)
                        self.write(code, val0, val0, Value(val0.type, 1))
                        return ret 

                    else:
                        raise RuntimeError()
        else:
            val0 = self._translate_expr(ast.nodes[0], *args)
            if OpAryLoc[operator] == 2:

                if lazyeval and operator in (Operator.AND, Operator.OR):
                    return self._translate_lazyevalbool(code, val0, ast.nodes[1], *args)

                val1 = self._translate_expr(ast.nodes[1], *args)
                ret = self.create_reg()
                self.write(code, ret, val0, val1)
            else:   # -, not
                ret = self.create_reg(val0.type)
                self.write(code, ret, val0)
            return ret 
        
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

        def translate_init_list(mast, coord, inits):
            """ Translation initialzation list.
                inits: List of tuple (coord, val) (for return)
            """
            for i, node in enumerate(mast.nodes):
                if node.type == ASTType.LIST:
                    translate_init_list(node, coord + [i], inits)
                else:
                    inits.append((coord + [i], self._translate_expr(node)))

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
                newdimlen = self._translate_expr(node, asn=False, isconst=True) # must be const node?
                if newdimlen.type != ValType.INT:
                    # type cast / raise error
                    pass 
                newlen = newdimlen.val; # this should be int
                if not isinstance(newlen, int):
                    raise RuntimeError()
                arrshape.append(newlen)

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

                for c, s in zip(cvt_coord, arrshape):
                    if c >= s:
                        raise CompileError("Too much value in initialization list")

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

    def create_var(self, varname=None, vartype=ValType.VOID):
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

