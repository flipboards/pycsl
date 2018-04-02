from enums import OpName


class StackCalculator:

    SWITCH = {
        OpName.PLUS: lambda x,y: x+y,
        OpName.MINUS: lambda x,y: x-y,
        OpName.MUL: lambda x,y: x*y,
        OpName.DIV: lambda x,y: x/y
    }

    def __init__(self):

        self.stack = []

    def clear(self):
        self.stack.clear()

    def push_num(self, num):

        self.stack.append(num)

    def operate(self, op):

        if op.ary == 1:
            self.stack[-1] = StackCalculator.SWITCH[op.id](stack[-1])

        elif op.ary == 2:
            y = self.stack.pop()
            x = self.stack.pop()
            self.stack.append(StackCalculator.SWITCH[op.id](x, y))