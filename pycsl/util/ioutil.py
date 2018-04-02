
import sys 


class StrReader:
    """ Simple wrapper of string.
    """
    
    def __init__(self, src):
        self.obj = src 
        self.ptr = 0

    def pos(self):
        return self.ptr

    def forward(self, c):
        self.ptr += c

    def backward(self, c):
        self.ptr -= c

    def seek(self, p):
        assert p >= 0
        self.ptr = p

    def eof(self):
        return self.ptr >= len(self.obj)


class StrWriter:
    """ Writer, output string into screen/file.
    """

    def __init__(self, src=None, formatter='%r', sep=' ', sepline='\n'):

        if not src:
            self.obj = sys.stdout 
            self.closeable = False 
        elif isinstance(src, str):
            self.obj = open(src, 'w')
            self.closeable = True 
        elif hasattr(src, 'write'):
            self.obj = src 
            self.closeable = hasattr(src, 'close')
        else:
            raise NotImplemented

        self.formatter = formatter
        self.sep = sep 
        self.sepline = sepline

    def write(self, c):
        self.obj.write(c) if isinstance(c, str) else self.obj.write(self.formatter % c)

    def writeln(self, c):
        self.write(c)
        self.obj.write(self.sepline)

    def writeword(self, c):
        self.write(c)
        self.obj.write(self.sep)

    def writestr(self, c):
        self.obj.write(c)

    def close(self):
        
        if self.closeable:
            self.obj.close()


