""" Convert pycsl.IR ==> LLVM.IR
"""

import struct 

from ..translate import Translater, ValType, Value
from ..ir import Block, Array, Identifier, MemoryLoc, Code, TAC, Pointer, Label
from ..util.ioutil import StrWriter


class LLConverter:

    _TypeLoc = {
        ValType.VOID: 'void',
        ValType.BOOL: 'i1',
        ValType.CHAR: 'i8',
        ValType.INT: 'i32',
        ValType.FLOAT: 'float'
    }

    _CastCodeLoc = {
        Code.EXT: 'sext',
        Code.TRUNC: 'trunc',
        Code.ITOF: 'sitofp',
        Code.FTOI: 'fptosi',
        Code.ITOP: 'inttoptr',
        Code.PTOI: 'ptrtoint',
        Code.BITC: 'bitcast'
    }

    _IcmpCodeLoc = {
        Code.EQ: 'eq',
        Code.NE: 'ne',
        Code.LT: 'slt',
        Code.LE: 'sle',
        Code.GT: 'sgt',
        Code.GE: 'sge'
    }

    _FcmpCodeLoc = {
        Code.EQ: 'ueq',
        Code.NE: 'une',
        Code.LT: 'ult',
        Code.LE: 'ule',
        Code.GT: 'ugt',
        Code.GE: 'uge'
    }

    def __init__(self, translater:Translater):
        """ Add a translater object
        """
        self.writer = None
        self.translater = translater

        self.cur_pred = None

    def output(self, filename=None):
        """ filename: None==> stdout; name ==> open filename and write it;
        """
        self.writer = StrWriter(filename, '%s')
        for name, val in self.translater.global_values.items():
            self.format_global_var(name, val)

        for fsig, fid in self.translater.function_table.items():
            if fid is not None:
                self.format_block(fsig, self.translater.functions[fid])
            else:
                self.format_function_decl(fsig)

    def format_function_decl(self, signature):
        self.writeln('declare %s @%s (%s)',
            self.format_type(signature[2]),
            str(signature[0]),
            ', '.join((self.format_type(s) for s in signature[1]))
        )

    def format_global_var(self, name:str, value:Value):
        """ 
        """
        if not isinstance(value.type, Array):
            self.writeln('@%s = global %s %s',
                name,
                self.format_type(value.type),
                str(value.val)
            )

    def format_block(self, signature, function:Block):
        
        name, argtypes, rettype = signature
        self.translater.curfunction = function

        self.writeln('\ndefine %s @%s(%s) {' ,
            self.format_type(rettype),
            name,
            ', '.join((self.format_type(argtype) for argtype in argtypes))
        )

        self.cur_pred = len(argtypes)

        for idx, code in enumerate(function.codes):
            self.write('  ')
            self.format_tac(code, idx)

        self.writeln('}')

    def format_tac(self, tac:TAC, idx:int):
        
        if tac.code == Code.HLT:
            self.writeln('hlt')

        elif tac.code == Code.RET:
            self.writeln('ret %s', self.format_var_with_type(tac.first))

        elif tac.code == Code.BR:
            if tac.cond:
                self.writeln('br %s, label %s, label %s',
                    self.format_var_with_type(tac.cond),
                    self.format_id(tac.first),
                    self.format_id(tac.second)
                )
            else:
                self.writeln('br label %s', tac.first)

            self.cur_pred = self.get_pred(idx + 1)
            self.writeln('; <label>:%d:', self.cur_pred)

        elif tac.code == Code.ALLOC:

            self.writeln('%s = alloca %s',
                self.format_id(tac.ret),
                self.format_type(tac.first)
            )

        elif tac.code == Code.LOAD:
            self.writeln('%s = load %s, %s',
                self.format_id(tac.ret),
                self.format_type(self.get_type(tac.ret)),
                self.format_var_with_type(tac.first)
            )

        elif tac.code == Code.STORE:
            self.writeln('store %s, %s',
                self.format_var_with_type(tac.first),
                self.format_var_with_type(tac.second)
            )

        elif tac.code == Code.GETPTR:
            self.writeln('%s = getelementptr %s, %s, %s',
                self.format_id(tac.ret),
                self.format_type(self.get_type(tac.first).unref_type()),
                self.format_var_with_type(tac.first),
                ', '.join((self.format_var_with_type(v) for v in tac.second))
            )

        elif tac.code.value >= Code.ADD.value and tac.code.value < Code.POW.value:
            
            if self.get_type(tac.first) == ValType.FLOAT:
                tpabbr = 'f'
            elif tac.code in (Code.MUL, Code.DIV, Code.REM):
                tpabbr = 's'
            else:
                tpabbr = ''

            self.writeln('%s = %s%s %s %s, %s',
                self.format_id(tac.ret),
                tpabbr,
                self.format_code(tac.code),
                self.format_type(self.get_type(tac.ret)),
                self.format_var(tac.first),
                self.format_var(tac.second)
            )

        elif tac.code == Code.POW:
            raise NotImplemented

        elif tac.code.value >= Code.AND.value and tac.code.value < Code.NOT.value:
            self.writeln('%s = %s %s %s, %s',
                self.format_id(tac.ret),
                self.format_code(tac.code),
                self.format_type(self.get_type(tac.ret)),
                self.format_var(tac.first),
                self.format_var(tac.second)
            )

        elif tac.code == Code.NOT:
            
            if self.get_type(tac.first) == ValType.FLOAT:
                tpabbr = 'f'
            else:
                tpabbr = 'i'
            self.writeln('%s = %scmp ne %s, 0',
                tac.ret,
                tpabbr,
                self.format_var_with_type(tac.first)
            )

        elif tac.code.value >= Code.EXT.value and tac.code.value < Code.EQ.value:
            self.writeln('%s = %s %s to %s',
                self.format_id(tac.ret),
                LLConverter._CastCodeLoc[tac.code],
                self.format_var_with_type(tac.first),
                self.format_var(tac.second)
            )

        elif tac.code.value >= Code.EQ.value and tac.code.value < Code.PHI.value:
            
            if self.get_type(tac.first) == ValType.FLOAT:
                tpabbr = 'f'
            else:
                tpabbr = 'i'
            self.writeln('%s = %scmp %s %s %s, %s',
                self.format_id(tac.ret),
                tpabbr,
                LLConverter._IcmpCodeLoc[tac.code] if tpabbr == 'i' else LLConverter._FcmpCodeLoc[tac.code],
                self.format_type(self.get_type(tac.first)),
                self.format_var(tac.first),
                self.format_var(tac.second)
            )

        elif tac.code == Code.PHI:
            self.writeln('%s = phi %s [%s %s] [%s %s]',
                self.format_id(tac.ret),
                self.format_type(self.get_type(tac.ret)),
                self.format_var_with_type(tac.first[0]),
                self.format_id(tac.first[1]),
                self.format_var_with_type(tac.second[0]),
                self.format_id(tac.second[1])
            )

        elif tac.code == Code.CALL:

            if tac.ret is not None:

                self.writeln('%s = call %s @%s(%s)',
                    self.format_id(tac.ret),
                    self.format_type(self.get_type(tac.ret)),
                    str(tac.first[0]),
                    ', '.join((self.format_var_with_type(v) for v in tac.second))
                )
            else:
                self.writeln('call void @%s(%s)',
                    str(tac.first[0]),
                    ', '.join((self.format_var_with_type(v) for v in tac.second))
                )

        else:
            raise RuntimeError('Unrecognized TAC: %r' % str(tac))

    def get_type(self, id_or_val):
        return self.translater.get_vartype(id_or_val)

    def get_pred(self, code_idx):
        for i, reg in enumerate(self.translater.curfunction.registers):
            if isinstance(reg, Label) and reg.addr == code_idx:
                return i

        raise RuntimeError('Cannot find label at address: %r' % code_idx)

    def format_code(self, code:Code):
        return code.name.lower()

    def format_id(self, id_:Identifier):
        
        if id_.loc == MemoryLoc.GLOBAL:
            return '@%s' % str(id_.addr)
        else:
            return '%%%d' % id_.addr

    def format_var(self, id_or_val):
        if isinstance(id_or_val, Identifier):
            return self.format_id(id_or_val)

        elif isinstance(id_or_val, Value):
            if id_or_val.type == ValType.FLOAT:
                return '0x' + ''.join(['%02x' % b for b in struct.pack('>d', id_or_val.val)])
            else:
                return str(id_or_val.val)

        else:
            raise RuntimeError('Unrecognized variable: %r' % str(id_or_val))        

    def format_var_with_type(self, id_or_val):
        """ id/var ==> 'type id/var'
        """

        if isinstance(id_or_val, Identifier):
            return '%s %s' % (
                self.format_type(self.get_type(id_or_val)),
                self.format_id(id_or_val)
                )

        elif isinstance(id_or_val, Value):
            if id_or_val.type == ValType.VOID:
                return 'void'
            else:
                return '%s %s' % (self.format_type(id_or_val.type), str(id_or_val.val))

        else:
            raise RuntimeError('Unrecognized variable: %r' % str(id_or_val))

    def format_type(self, tp):

        if isinstance(tp, Pointer):
            return self.format_type(tp.unref_type()) + '*'

        elif isinstance(tp, Array):
            return '[%d x %s]' % (tp.size, self.format_type(tp.type))

        elif isinstance(tp, ValType):

            return LLConverter._TypeLoc[tp]

        else:
            raise RuntimeError('Unrecognized type: %r' % str(tp))

    def writeln(self, string:str, *args):
        self.writer.writeln(string % args)

    def write(self, obj):
        self.writer.writeword(obj)
