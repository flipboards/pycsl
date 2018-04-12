
from numpy import product, zeros
from enum import Enum
from collections import namedtuple, OrderedDict

from .grammar.operators import Operator, OpAryLoc, OpAsnLoc
from .grammar.basic_types import ValType, Value
from .grammar.keywords import Keyword

from .tokens import Symbol
from .ast import AST, ASTType, DeclNode
from .ir import IR, Code, Array, Label, Pointer, Register, Block, Identifier, op2code
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

    def __len__(self):
        return len(self.data)

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
        self.labels[label] = index if index >= 0 else len(self.data) + index
        self.vdata.insert(index, label)


class Translater:

    ARRAY_SIZE_LIMIT = 16384

    def __init__(self):
        self.global_sym_table = dict()  # dict{string: Variable/Function}
        self.function_table = dict()    # dict{function_signature: function block number}
        self.sym_table_stack = [dict()] # dict{string <-- var name:int <-- register id}
        self.functions = []             # list [Block]
        self.curfunction = None
        self.looplabelstack = []

    def clear(self):
        self.curfunction = None
        self.looplabelstack.clear()

    def translate(self, ast:AST):
        """ Translate the whole block
        """
        assert ast.type == ASTType.ROOT

        for node in ast.nodes:
            if node.type == ASTType.DECL:
                self._translate_decl(node, True)
            elif node.type == ASTType.FUNC:
                self._translate_function(node)
            else:
                raise CompileError("Invalid code outside function")

    
    def translate_line(self, ast:AST):
        """ Translate the ast that generate by a line of code.
            There are no control / function definition in the line mode, so simply
            expression and variable declaration.
            All varaible are treated as global.
        """
        self.clear()

        if ast.type == ASTType.DECL:
            self._translate_decl(ast, False)
        else:
            r = self._translate_expr(ast)
            self.write(Code.RET, r) # Controversal: Need to use something to disable it in interperator.

    def _translate_function(self, ast:AST):
        """ Translate a function ast.
            The root of ast must be ASTType.FUNC;
                First child (must present) is function definition (ASTType.DECL);
                Second child is function block (ASTType.BLOCK);
        """
        assert ast.type == ASTType.FUNC, 'Invalid function ast'

        signature, argnames = self._translate_function_decl(ast.nodes[0])
        funcname, argtypes, rettype = signature

        if len(ast.nodes) == 1: # decalration only
            return

        self.function_table[signature] = len(self.functions)

        self.functions.append(Block())
        self.curfunction = self.functions[-1]

        self.sym_table_stack.append(dict())

        # allocate registers that stores original arguments
        for argname, argtype in zip(argnames, argtypes):
            self.sym_table_stack[-1][argname] = self.create_reg(argtype)

        # label of function block
        lblentry = self.create_label()
        self.insert_label(lblentry)

        # allocate local copy of arguments. This need to be changed when allowing reference
        for argname, argtype in zip(argnames, argtypes):
            
            argptr = self.create_reg(Pointer(argtype))
            self.write(Code.ALLOC, argptr, argtype)
            self.write(Code.STORE, None, self.sym_table_stack[-1][argname], argptr)

            self.sym_table_stack[-1][argname] = argptr # now change reference into local copy


        assert ast.nodes[1].type == ASTType.BLOCK

        self._translate_stmt(ast.nodes[1])
        self.sym_table_stack.pop()

    def _translate_function_decl(self, ast:AST):
        """ Translate function declaration.
            The root must be ASTType.DECL and DeclNode.FUNCDECL.
            Will register the function into function table.

            Returns: 
                signature: function signature
                argnames: list of argument names
                argtypes: list of argument types
        """

        assert ast.type == ASTType.DECL and ast.value == DeclNode.FUNCDECL

        funcname = ast.nodes[0].value.name 
        argnames = []
        argtypes = []

        for arg_node in ast.nodes[1].nodes:

            assert arg_node.type == ASTType.DECL
            assert arg_node.nodes[0].type == ASTType.NAME

            argnames.append(arg_node.nodes[0].value.name)
            argtypes.append(arg_node.nodes[1].value if len(arg_node.nodes) == 2 else ValType.VOID)
        
        rettype = ast.nodes[2].value if len(ast.nodes) == 3 else ValType.VOID

        signature = funcname, tuple(argtypes), rettype
        if signature in self.function_table:
            if self.function_table[signature] is not None:
                raise CompileError("Function already defined: %s(%s):%s" % (
                    funcname, 
                    ','.join((str(t) for t in argtypes)),
                    str(rettype)
                    ))
        else:
            self.function_table[signature] = None

        return signature, argnames

    def _translate_stmt(self, ast:AST):
        """ Translate statement (including compound statement)
        """

        if ast.type == ASTType.BLOCK:
            self.sym_table_stack.append(dict())
            for node in ast.nodes:
                if node.type == ASTType.DECL:
                    self._translate_decl(node, False)
                else:
                    self._translate_stmt(node)
            self.sym_table_stack.pop()

        elif ast.type == ASTType.DECL:
            self._translate_decl(ast, False)

        elif ast.type == ASTType.CTRL:
            self._translate_ctrl(ast)

        else:
            self._translate_expr(ast)

    def _translate_ctrl(self, ast:AST):
        
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
            return self._translate_name(ast, side)

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
        """ Translate an operator (ASTType.OP)
        """

        def translate_subscript(mast, subarray):
            """ Translate continues subscripts. Notice: assignment is not allowed in indexer.
            """
            if mast.value != Operator.LSUB:
                return self._translate_expr(mast, Side.LHS, *args[1:])
            else:
                lhs = translate_subscript(mast.nodes[0], subarray)
                subarray.append(self._translate_expr(mast.nodes[1], Side.RHS, *args[1:]))
                return lhs 

        def translate_array_index(mast):
            """ Translate array indexing, return the pointer to array element;
                Currently unsupport pointer;
            """
            subarray = []
            valarr = translate_subscript(mast, subarray)
            valptr = self.create_reg(self.get_vartype(valarr))
            self.write(Code.GETPTR, valptr, valarr, subarray)  # %valptr = getptr %valarr %subarray
            return valptr

        lazyeval = args[0]

        assert ast.type == ASTType.OP

        operator = ast.value
        assert OpAryLoc[operator] == len(ast.nodes)

        ## This is for array indexing in RHS
        ## ptr = GETPTR(a, b)
        ## ret = LOAD ptr
        if operator == Operator.LSUB:
            valptr = translate_array_index(ast)

            if side == Side.LHS:
                return valptr

            else:
                valret = self.create_reg(self.get_vartype(valptr).unref_type())
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
                    typelhs = self.get_vartype(vallhs).unref_type() # valllhs is supposed to be a Pointer
                    rvallhs = self.create_reg(typelhs) 
                    self.write(Code.LOAD, rvallhs, vallhs)
                    valret = self.create_reg() # type cast here
                    self.write(code, valret, rvallhs, valrhs)
                    self.write(Code.STORE, None, valret, vallhs)
                    
                    return valret
                else:
                    self.write(Code.STORE, None, valrhs, vallhs)
                    
                    return valrhs

            ## ++, --
            else:
                
                vallhs = self._translate_expr(ast.nodes[0], Side.LHS)
                typelhs = self.get_vartype(vallhs).unref_type()
                rvallhs = self.create_reg(typelhs)
                self.write(Code.LOAD, rvallhs, vallhs)
                valret = self.create_reg(typelhs)
                self.write(code, valret, rvallhs, Value(typelhs, 1))
                self.write(Code.STORE, None, valret, vallhs)

                if operator in (Operator.INC, Operator.DEC):
                    return valret

                elif operator in (Operator.POSTINC, Operator.POSTDEC):
                    return rvallhs

                else:
                    raise RuntimeError()

        else:
            vallhs = self._translate_expr(ast.nodes[0], Side.RHS, *args)
            typelhs = self.get_vartype(vallhs)
            if OpAryLoc[operator] == 2:

                if lazyeval and operator in (Operator.AND, Operator.OR):
           #         return self._translate_lazyevalbool(code, vallhs, ast.nodes[1], *args)
                    pass

                valrhs = self._translate_expr(ast.nodes[1], Side.RHS, *args)
                valret = self.create_reg() # type cast here
                self.write(code, valret, vallhs, valrhs)

            # -, not    
            else:   
                valret = self.create_reg(typelhs)
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

    def _translate_name(self, ast:AST, side):
        """ Translate a name
        """
        assert ast.type == ASTType.NAME

        varname = ast.value.name 
        varid = None

        for local_sym_table in reversed(self.sym_table_stack):
            if varname in local_sym_table:
                varid = local_sym_table[varname]
                break

        if not varid:

            if varname in self.global_sym_table:
                varid = Identifier(varname)
            else:
                raise CompileError('Variable %s not defined' % varname)

        if side == Side.LHS:
            return varid
        else:
            rval = self.create_reg(self.get_vartype(varid).unref_type())
            self.write(Code.LOAD, rval, varid)
            return rval


    def _translate_funcall(self, ast:AST):
        
        assert ast.type == ASTType.CALL
        
        argids = [self._translate_expr(node) for node in ast.nodes[1:]] # identifier / value
        if ast.nodes[0].type != ASTType.NAME:
            raise CompileError('Not a function: %s' % ast.nodes[0].value)
        
        funcname = ast.nodes[0].value.name

        signature = None
        for f in self.function_table:
            if f[0] == funcname:
                signature = f
                break

        funcname, argtypes, rettype = signature

        if len(argtypes) != len(argids):
            raise CompileError("Argument number not match")

        for argid, argtype in zip(argids, argtypes):
            if self.get_vartype(argid) != argtype:
                # emit type cast code here
                pass

        ret = self.create_reg(rettype)
        self.write(Code.CALL, ret, funcname, argids)
        return ret 

    def _translate_decl(self, ast:AST, isglobal):
        """ Translate variable decalaration
        """
        assert ast.value == DeclNode.VARDECL
        assert ast.nodes[0].type == ASTType.TYPE

        for node in ast.nodes[1:]:
            self._translate_decl_elem(node, ast.nodes[0].value, isglobal)
        
    def _translate_decl_elem(self, ast:AST, typename, isglobal):
        """ Translate a single definition.
            ast: The definition element;
            typename: ValType instance.
        """

        def translate_array_shape(mast):
            arrshape = []
            for node in mast.nodes:
                newdimlen = self._eval_expr(node)
                if newdimlen.type != ValType.INT:
                    # type cast / raise error
                    pass 
                newlen = newdimlen.val  # this should be int
                arrshape.append(newlen)
                return arrshape

        def translate_init_list(mast, coord, inits, requireconst=False):
            """ Translation initialzation list.
                requireconst is used in global definition;
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

        def convert_init_list(mast):

            if mast.type != ASTType.LIST:
                raise CompileError('Array must be initialized by list')

            inits1 = []
            translate_init_list(mast, [], inits1, isglobal)
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
            return inits

        assert ast.type == ASTType.DECL and ast.value == DeclNode.DECLELEM
        assert ast.nodes[0].type == ASTType.NAME

        varname = ast.nodes[0].value.name
        arrshape = None

        ## array shape
        if len(ast.nodes[0].nodes) > 0:
            arrshape = translate_array_shape(ast.nodes[0])

            # size check (may not be necessary)
            if product(arrshape) > Translater.ARRAY_SIZE_LIMIT:
                raise CompileError('Array too large (%d). Try use "new" instead.' % product(arrshape))

            vartype = typename
            for s in reversed(arrshape):
                vartype = Array(vartype, s)
        else:
            vartype = typename


        # register variable
        if varname in self.global_sym_table:
            raise CompileError('Variable "%s" already defined' % varname)

        # only global variables need initializer; Local variable only create pointer
        if isglobal:
            if not arrshape:
                if len(ast.nodes) > 1:
                    initializer = self._eval_expr(ast.nodes[1]) # may require type cast
                else:
                    initializer = Value(vartype, 0)
            else:
                init_array = zeros(arrshape, dtype=(float if vartype[0] == ValType.FLOAT else int))
                if len(ast.nodes) > 1:
                    for c, v in convert_init_list(ast.nodes[1]):
                        init_array[tuple(c)] = v.val
                initializer = Value(vartype, init_array)

            initializer.type = Pointer(initializer.type)
            self.global_sym_table[varname] = initializer

        else:

            for local_sym_table in self.sym_table_stack:
                if varname in local_sym_table:
                    raise CompileError('Variable "%s" already defined' % varname)
            varid = self.create_reg(Pointer(vartype))
            self.write(Code.ALLOC, varid, vartype)
            self.sym_table_stack[-1][varname] = varid

            # declaration only
            if len(ast.nodes) == 1:
                pass

            elif not arrshape:
                initializer = self._translate_expr(ast.nodes[1])
                self.write(Code.STORE, None, initializer, varid)

            else:

                # fill 0 for the whole array here (memcpy)

                for c, v in convert_init_list(ast.nodes[1]):
                    elemptr = self.create_reg(Pointer(typename))
                    self.write(Code.GETPTR, elemptr, varid, c)
                    self.write(Code.STORE, None, v, elemptr)


    def create_reg(self, mtype=None):
        """ Create a temporary variable that can be in stack top/register
        """
        self.curfunction.registers.append(Register(mtype))
        return Identifier(len(self.curfunction.registers) - 1)   

    def create_label(self):
        return self.create_reg(Label())

    def insert_label(self, label_id):
        """ Pointer label with label_id to next code
        """
        self.curfunction.registers[label_id.addr].type.addr = len(self.curfunction.codes)

    def get_vartype(self, varid):

        if isinstance(varid, Value):
            return varid.type

        elif isinstance(varid, Identifier):
            if isinstance(varid.addr, int): # local var / arg
                return self.curfunction.registers[varid.addr].type
            else:
                return self.global_sym_table[varid.addr].type

        else:
            raise RuntimeError()

    def write(self, op, ret, first=None, second=None, *args, **kwargs):

        self.curfunction.codes.append(IR(op, ret, first, second, *args, **kwargs))


