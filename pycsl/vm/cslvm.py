
from collections import namedtuple

from ..ir import IR, Code, Variable, Function
from ..translate import SearchableList, ValType, Value

from ..evalute import eval_op, OpEvalLoc

class FuncEnv:

    def __init__(self):
        self.registers = {} # dict: name, value. $ret register stores return value
        self.memory = []
        self.block = ''
        self.pc = []


class CSLVM:
    """ Virtual machine executing CSL IR code
    """

    def __init__(self, functions):
        self.stack = []
        self.stacktop = None
        self.ret = None
        self.global_vars = []
        self.functions = []

    def run(self):
        self.execute_line(IR(Code.CALL, None, self.functions['main'])

    def execute_function(self):
        """ Execute a function (list of code)
            args: dict of varname: value
        """
        while True:
            if self.execute_line(self.fetch_code()):
                return

    def execute_line(self, line:IR):
        """ Execute one line of code
        """

        if line.code in OpEvalLoc:
            self.stacktop.registers[line.ret.name] = eval_op(self.get_val(line.first.name), self.get_val(line.second.name))

        elif line.code == Code.HLT:
            return 1

        elif line.code == Code.CALL: # ret = call Function() arg_list
            self.stacktop.register['$ret'] = None
            self.stack.append(FuncEnv())
            self.stacktop = self.stack[-1]

            function = line.first
            self.stacktop.pc = [function.name, 0]
            self.stacktop.registers.update(((farg.name, varg) for farg, varg in zip(function.args, line.second))) # replace variable names

        elif line.code == Code.RET: # ret lhs
            self.stack.pop()
            self.stacktop = self.stack[-1]
            self.stacktop.register['$ret'] = line.lhs
            return 1

        elif line.code == Code.BR: # br label / br cond label1 label2
            if not line.second:

                self.stacktop.pc = self.get_dest(line.first.name)
            else:
                if self.get_val(line.cond.name).val != 0:
                    self.stacktop.pc = self.get_dest(line.first.name)
                else:
                    self.stacktop.pc = self.get_dest(line.second.name)

        elif line.code == Code.ALLOC:
            self.stacktop.registers[line.ret.name] = len(self.stacktop.memory)
            self.stacktop.memory.append(Value(line.ret.type.type)) # ret.type should be a pointer, so ret.type.type ==> correct type

        elif line.code == Code.LOAD: # ret = load addr
            self.stacktop.registers[line.ret.name] = self.stacktop.memory[self.get_val(line.first.name)]

        elif line.code == Code.STORE: # store val addr
            self.stacktop.memory[self.get_val(line.second.name)] = self.get_val(line.first.name)

        elif line.code == Code.GETPTR:
            self.stacktop.registers[line.ret.name] = #

        elif line.code == Code.PHI:
            pass 

        elif line.code == Code.INVOKE:
            pass 

    def get_val(self, valname):
        return self.stacktop.registers[valname]

    def get_dest(self, labelname):
        f = self.functions[self.stacktop.pc[0]]
        return [self.stacktop.pc[0], f.loc[labelname]]

