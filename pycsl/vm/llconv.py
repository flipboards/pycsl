""" Convert pycsl.IR ==> LLVM.IR
"""

from ..translate import Translater, ValType
from ..ir import Block, Array, Identifier, MemoryLoc, Code, IR
from ..util.ioutil import StrWriter

class LLConverter:

    def __init__(self, translater:Translater):
        self.writer = None
        self.translater = translater

    def write(self, output=None):
        self.writer = StrWriter(output, '%s')
        for name, val in self.translater.global_values.items():
            self.write_global_var(name, val)

        for fsig, fid in self.translater.function_table.items():
            self.write_block(fsig, self.translater.function[fid])

    def write_global_var(self, name, value):

        self.output('@%s = global' % name)

        if not isinstance(value.type, Array):
            self.output(self.convert_type(value.type))
            self.output(value.val)

        self.output_line('')

    def write_block(self, signature, function:Block):
        
        name, argtypes, rettype = signature
        self.translater.curfunction = function

        self.output_line('define %s @%s(%s) {' % (
            self.convert_type(rettype),
            name,
            ', '.join((self.convert_type(argtype) for argtype in argtypes))
        ))

        for code in function.codes:
            self.write_code(code)

        self.output_line('}')

    def write_code(self, code:IR):
        
        if code.code == Code.HLT:
            self.output_line('hlt')

        elif code.code == Code.RET:
            if code.first:
                self.output_line('ret %s' % self.convert_id_or_val(code.first))
            else:
                self.output_line('ret')

        elif code.code == Code.BR:
            if code.cond:
                self.output_line('br %s, label %s, label %s' % (
                    self.convert_id_or_val(code.cond),
                    code.first,
                    code.second
                ))
            else:
                self.output_line('br label %s' % code.first)

        elif code.code == Code.ALLOC:
            self.write('%s = alloc %s' % (
                code.ret,
                self.convert_type(code.first)
                ))

        elif code.code == Code.LOAD:
            self.write('%s = load %s, %s' % (
                code.ret,
                self.convert_type(code.first).unref(),
                self.convert_id_or_val(code.first)
                ))

        elif code.code == Code.STORE:
            self.write('store %s, %s' % (
                self.convert_id_or_val(code.first),
                self.convert_id_or_val(code.second)
            ))

        elif code.code == Code.GETPTR:
            pass

        elif code.code >= Code.ADD and code.code < Code.POW:
            tpabbr = 'i'
            self.write('%s = %s%s %s, %s' % (
                code.ret,
                tpabbr,
                code.code,
                self.convert_id_or_val(code.first),
                self.convert_id_or_val(code.second)
            ))

        elif code.code == Code.POW:
            raise NotImplemented

        elif code.code >= Code.AND and code.code < Code.NOT:
            self.write('%s = %s %s, %s' % (
                code.ret,
                code.code,
                self.convert_id_or_val(code.first),
                self.convert_id_or_val(code.second)
            ))

        elif code.code == Code.NOT:
            self.write('%s = icmp ne %s, 0' % (
                code.ret,
                self.convert_id_or_val(code.first)
            ))

        elif code.code >= Code.EQ and code.code < Code.PHI:
            self.write('%s = icmp %s %s, %s' % (
                code.ret,
                code.code,
                self.convert_id_or_val(code.first),
                self.convert_id_or_val(code.second)
            ))

        elif code.code == Code.PHI:
            pass

        elif code.code == Code.CALL:
            pass

        else:
            raise RuntimeError()

    def convert_id_or_val(self, id_or_val):
            
        return '%s %s' % (self.convert_type(self.translater.get_vartype(id_)), id_or_val)

    def convert_type(self, tp):
        TypeLoc = {
            ValType.BOOL: 'i1',
            ValType.CHAR: 'i8',
            ValType.INT: 'i32'
        }
        return TypeLoc[tp]

    def output(self, obj):
        self.writer.writeword(obj)

    def output_line(self, obj):
        self.writer.writeln(obj)