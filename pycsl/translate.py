
from numpy import product, zeros
from enum import Enum
from collections import namedtuple, OrderedDict

from .grammar.operators import Operator, OpAryLoc, OpAsnLoc
from .grammar.basic_types import ValType, Value
from .grammar.keywords import Keyword

from .tokens import Symbol
from .ast import AST, ASTType, DeclNode

from .ir.tac import Code, TAC, op2code
from .ir.types import Array, Pointer
from .ir.memory import Register, Label, Block, MemoryLoc, Identifier

from .errors import CompileError
from .evalute import eval_op


class Side:
    LHS = 0
    RHS = 1


class Translater:

    ARRAY_SIZE_LIMIT = 16384        # maximum size of single array decalared
    POINTER_ARITHMETIC = True       # allow add and sub between pointers with same type
    POINTER_TO_VAL = False          # allow cast pointer to int
    ARRAY_POINTER_DECAY = False     # allow cast array pointer to value pointer
    EXPLICIT_TYPE = True            # type must be explicitly declared (not allow void)

    def __init__(self):

        # symbol tables
        self.global_sym_table = dict()  # dict{string: Register}
        self.function_table = dict()    # dict{function name: function signature}
        self.sym_table_stack = []       # dict{string <-- var name:Identifier <-- register id}
        
        # functions
        self.functions = []             # list [Block]
        self.global_values = {}         # dict{string: Value}; Value of global vars;

        # temporary variables
        self.curfunction = None
        self.currettype = None
        self.looplabelstack = []
        self.labelidpool = []

    def clear(self):
        self.curfunction = None
        self.looplabelstack.clear()
        self.labelidpool.clear()

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
        self.currettype = rettype
        self.looplabelstack.clear()
        self.labelidpool.clear()

        self.sym_table_stack.append(dict())

        # allocate registers that stores original arguments
        for argname, argtype in zip(argnames, argtypes):
            self.sym_table_stack[-1][argname] = self.create_reg(argtype)

        # label of function block
        lblentry = self.create_label()
        self.insert_label(lblentry)

        # allocate local copy of arguments. This need to be changed when allowing reference
        for argname, argtype in zip(argnames, argtypes):
            
            argid = self.create_reg(Pointer(argtype))
            self.write(Code.ALLOC, argid, argtype)
            self.write(Code.STORE, None, self.sym_table_stack[-1][argname], argid)
            self.sym_table_stack[-1][argname] = argid # now change reference into local copy


        assert ast.nodes[1].type == ASTType.BLOCK

        self._translate_stmt(ast.nodes[1])
        self.sym_table_stack.pop()

        if Translater.EXPLICIT_TYPE and self.curfunction.codes[-1].code != Code.RET:
            if rettype != ValType.VOID:
                raise CompileError('Function "%s" must return a value' % funcname)
            else:
                self.write(Code.RET, None, Value(ValType.VOID, None))

        assert len(self.sym_table_stack) == 0
        assert len(self.looplabelstack) == 0
        self.curfunction = None
        self.currettype = None

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

            if len(arg_node.nodes) == 2:
                assert arg_node.nodes[1].type == ASTType.TYPE
                argtypes.append(arg_node.nodes[1].value)

            elif not Translater.EXPLICIT_TYPE:
                argtypes.append(ValType.VOID)

            else:
                raise CompileError('Function argument type must be explicitly stated')
        
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
            varcond = self._translate_expr(ast.nodes[0]) ## TODO: Type check
            lbltrue = self.create_label()
            lblfalse = self.create_label()
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
            self.write(Code.BR, None, lblbegin)
            self.insert_label(lblbegin)
            varcond = self._translate_expr(ast.nodes[0])
            lblloop = self.create_label()
            lblend = self.create_label()
            self.write(Code.BR, None, lblloop, lblend, cond=varcond)
            self.looplabelstack.append((lblbegin, lblend))
            self.insert_label(lblloop)
            self._translate_stmt(ast.nodes[1])
            self.write(Code.BR, None, lblbegin)
            self.insert_label(lblend)
            self.looplabelstack.pop()

        elif ast.value == Keyword.FOR:

            self._translate_expr(ast.nodes[0])
            lblbegin = self.create_label()
            self.write(Code.BR, None, lblbegin)
            self.insert_label(lblbegin)
            varcond = self._translate_expr(ast.nodes[1])
            lblloop = self.create_label()
            lblend = self.create_label()
            self.write(Code.BR, None, lblloop, lblend, cond=varcond)
            self.insert_label(lblloop)
            lblctn = self.create_label()
            self.looplabelstack.append((lblctn, lblend))
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
                if Translater.EXPLICIT_TYPE and self.currettype == ValType.VOID:
                    return Value(ValType.VOID, None)
                else:
                    raise CompileError('Must return a value')
            else:
                valret = self._translate_expr(ast.nodes[0])
                valret_cast = valret if self.get_vartype(valret) == self.currettype else self._translate_typecast(valret, self.currettype)
                self.write(Code.RET, None, valret_cast)

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
                arr = self._translate_expr(mast, Side.LHS, *args[1:])
                arrtype = self.get_vartype(arr) 
                if not isinstance(arrtype, Pointer) or not (isinstance(arrtype.unref_type(), Pointer) or isinstance(arrtype.unref_type(), Array)):
                    raise CompileError('Subscript may only applied to pointer or array')
                return arr
            else:
                lhs = translate_subscript(mast.nodes[0], subarray)
                idx = self._translate_expr(mast.nodes[1], Side.RHS, *args[1:])
                idx_cast = idx if self.get_vartype(idx) == ValType.INT else self._translate_typecast(idx, ValType.INT)
                subarray.append(idx_cast)
                return lhs 

        def translate_array_index(mast):
            """ Translate array indexing, return the pointer to array element;
                Currently unsupport pointer;
            """
            subarray = [Value(ValType.INT, 0)]
            valarr = translate_subscript(mast, subarray)
            valptr = self.create_reg(Pointer(self.get_vartype(valarr).unref_type().type))
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
                typelhs = self.get_vartype(vallhs).unref_type() # valllhs is supposed to be a Pointer
                typerhs = self.get_vartype(valrhs)
                valrhs_cast = valrhs if typelhs == typerhs else self._translate_typecast(valrhs, typelhs)

                if code is not None:
                    rvallhs = self.create_reg(typelhs) 
                    self.write(Code.LOAD, rvallhs, vallhs)

                    valret = self.create_reg(typelhs)
                    self.write(code, valret, rvallhs, valrhs_cast)
                    self.write(Code.STORE, None, valret, vallhs)
                    
                    return valret
                else:
                    self.write(Code.STORE, None, valrhs_cast, vallhs)
                    
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

           #     if lazyeval and operator in (Operator.AND, Operator.OR):
           #         return self._translate_lazyevalbool(code, vallhs, ast.nodes[1], *args)
           #         pass

                valrhs = self._translate_expr(ast.nodes[1], Side.RHS, *args)
                typerhs = self.get_vartype(valrhs)
                ptr_arithmetic = operator in (Operator.ADD, Operator.SUB) and Translater.POINTER_ARITHMETIC
                typeret = self.get_target_type(typelhs, typerhs, ptr_arithmetic)

                if isinstance(vallhs, Value) and isinstance(valrhs, Value):
                    return eval_op(operator, vallhs, valrhs)

                vallhs_cast = self._translate_typecast(vallhs, typeret) if typelhs != typeret else vallhs
                valrhs_cast = self._translate_typecast(valrhs, typeret) if typerhs != typeret else valrhs

                # compare
                if operator.value >= Operator.EQ.value and operator.value <= Operator.GE.value:
                    typeret = ValType.BOOL

                valret = self.create_reg(typeret)
                self.write(code, valret, vallhs_cast, valrhs_cast)

            # -, not    
            else:   

                if isinstance(vallhs, Value):
                    return eval_op(operator, vallhs)

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

        argids_cast = []
        for argid, argtype in zip(argids, argtypes):
            if self.get_vartype(argid) == argtype:
                argids_cast.append(argid)
            else:
                argids_cast.append(self._translate_typecast(argid, argtype))

        if Translater.EXPLICIT_TYPE and rettype == ValType.VOID:
            self.write(Code.CALL, None, signature, argids_cast)
        else:
            ret = self.create_reg(rettype)
            self.write(Code.CALL, ret, signature, argids_cast)
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

            self.global_sym_table[varname] = Register(Pointer(vartype))
            initialzer_cast = initializer if initializer.type == typename else self._translate_typecast(initializer, typename)
            self.global_values[varname] = initialzer_cast

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
                initialzer_cast = initializer if self.get_vartype(initializer) == typename else self._translate_typecast(initializer, typename)
                self.write(Code.STORE, None, initialzer_cast, varid)

            else:

                # fill 0 for the whole array here (memcpy)

                for c, v in convert_init_list(ast.nodes[1]):
                    v_cast = v if self.get_vartype(v) == typename else self._translate_typecast(v, typename)                    
                    elemptr = self.create_reg(Pointer(typename))

                    c_var = [Value(ValType.INT, 0)]
                    for c_ in c:
                        c_var.append(Value(ValType.INT, c_))

                    self.write(Code.GETPTR, elemptr, varid, c_var)
                    self.write(Code.STORE, None, v_cast, elemptr)

    def _translate_typecast(self, var_or_id, target_type):
        
        src_type = self.get_vartype(var_or_id)

        if Translater.EXPLICIT_TYPE and target_type == ValType.VOID:
            raise CompileError('An explicit type is required, not void')

        elif target_type == ValType.VOID:
            return var_or_id

        elif src_type == ValType.VOID and isinstance(target_type, ValType):
            return Value(src_type, target_type)

        else:
            raise CompileError('Cannot cast type "void" to "%s"' % target_type)

        # var_or_id.type 
        if isinstance(var_or_id, Value):
            
            assert not isinstance(target_type, Array) and not isinstance(src_type, Array)

            if (isinstance(target_type, Pointer) and isinstance(src_type, Pointer)) or (
                isinstance(target_type, ValType) and isinstance(src_type, ValType)):
                return Value(target_type, var_or_id.val)
            
            elif Translater.POINTER_TO_VAL:
                return Value(tar)

            else:
                raise CompileError('Cannot cast type %s to %s' % (src_type, target_type))

        elif isinstance(var_or_id, Identifier):

            if isinstance(src_type, ValType):
                if isinstance(target_type, ValType):

                    target = self.create_reg(target_type)
                    if src_type.value < ValType.FLOAT.value and target_type.value < ValType.FLOAT.value:
                        code = Code.EXT if src_type.value < target_type.value else Code.TRUNC
                    else:
                        code = Code.ITOF if src_type == ValType.FLOAT else Code.FTOI
                        
                    self.write(code, target, var_or_id, target_type)

                elif Translater.POINTER_TO_VAL and isinstance(target_type, Pointer):

                    if src_type.value < ValType.INT.value:
                        target1 = self.create_reg(ValType.INT)
                        self.write(Code.EXT, target1, var_or_id, ValType.INT)
                    elif src_type.value == ValType.INT.value:
                        target1 = var_or_id
                    else:
                        raise CompileError('Cannot cast float to pointer')

                    target = self.create_reg(target_type)                    
                    self.write(Code.ITOP, target, target1, target_type)

                else:
                    raise CompileError('Cannot cast %s to %s' % (src_type, target_type))

            elif isinstance(src_type, Pointer):

                if Translater.POINTER_TO_VAL and isinstance(target_type, ValType):

                    if target_type != ValType.FLOAT:
                        target = self.create_reg(target_type)                    
                        self.write(Code.PTOI, target, var_or_id, target_type)
                    else:
                        raise CompileError('Cannot cast pointer to float')

                elif isinstance(target_type, Pointer):
                    target = self.create_reg(target_type)
                    self.write(Code.BITC, target, var_or_id, target_type)

                else:
                    raise CompileError('Cannot cast %s to %s' % (src_type, target_type))

            elif isinstance(src_type, Array):
                if Translate.ARRAY_POINTER_DECAY and isinstance(target_type, Pointer):
                    if src_type.type == target_type.type:
                        target = self.create_reg(target_type)
                        self.write(Code.GETPTR, target, var_or_id, Value(ValType.INT, 0))
                    else:
                        raise CompileError('Cannot cast array to pointer with different type')

                else:
                    raise CompileError('Cannot cast %s to %s' % (src_type, target_type))

            else:
                raise RuntimeError()

            return target

        else:
            raise RuntimeError()

    def get_target_type(self, type1, type2, ptr_arithmetic=False):
        """ Returns the type cast target.
        """

        if isinstance(type1, ValType) and isinstance(type2, ValType):
            return ValType(max(type1.value, type2.value))

        elif ptr_arithmetic:

            if isinstance(type1, Pointer) and isinstance(type2, Pointer):
                if type1.unref_type() == type2.unref_type():
                    return ValType.INT
                else:
                    raise CompileError("Cannot perform calculation between different type pointers")

            elif isinstance(type1, Pointer) and isinstance(type2, ValType):
                if type2 == ValType.INT:
                    return ValType.INT

            elif isinstance(type2, Pointer) and isinstance(type1, ValType):
                if type1 == ValType.INT:
                    return ValType.INT            

            elif Translater.ARRAY_POINTER_DECAY:

                if isinstance(type1, Array) and isinstance(type2, ValType):
                    if type2 == ValType.INT:
                        return ValType.INT

                elif isinstance(type2, Array) and isinstance(type1, ValType):
                    if type1 == ValType.INT:
                        return ValType.INT           
                
                elif type1.type == type2.type: # Array - ?
                    return ValType.INT


        raise CompileError('Cannot perform calculation between type "%s" and "%s"' % (type1, type2))

    def create_reg(self, mtype=None):
        """ Create a temporary variable that can be in stack top/register
        """
        self.curfunction.registers.append(Register(mtype))
        return Identifier(MemoryLoc.LOCAL, len(self.curfunction.registers) - 1)   

    def create_label(self):
        self.labelidpool.append(Identifier(MemoryLoc.LOCAL, None))
        return self.labelidpool[-1]

    def insert_label(self, label_id:Identifier):
        """ Pointer label with label_id to next code
        """
        target_addr = len(self.curfunction.codes)

        # check if already exists
        for i, reg in enumerate(self.curfunction.registers):
            if isinstance(reg, Label) and reg.addr == target_addr:
                label_id.addr = i 
                self.labelidpool.remove(label_id)
                return

        label_id.addr = len(self.curfunction.registers)
        self.curfunction.registers.append(Label(target_addr))
        self.labelidpool.remove(label_id)

    def locate(self, id_):
        """ id_: Identifier;
            Returns: Label / Register / Value
        """
        if id_.loc == MemoryLoc.GLOBAL:
            return self.global_sym_table[id_.addr]

        elif id_.loc == MemoryLoc.LOCAL:
            return self.curfunction.registers[id_.addr]

        else:
            raise RuntimeError('Cannot recognize id: %r' % str(id_))

    def get_vartype(self, value_or_id):
        """ Returns the type of variable / value
        """

        if isinstance(value_or_id, Value):
            return value_or_id.type

        elif isinstance(value_or_id, Identifier):
            return self.locate(value_or_id).type

        else:
            raise RuntimeError('Cannot recognize variable: %r' % str(value_or_id))

    def write(self, code, ret, first=None, second=None, *args, **kwargs):

        self.curfunction.codes.append(TAC(code, ret, first, second, *args, **kwargs))


