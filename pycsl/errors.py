""" Errors raised in pyscl
"""

class ReadError(RuntimeError):
    """ Errors in preprocessing
    """

    def __init__(self, err):
        super().__init__('Reading error: %s' % err)


class SynError(RuntimeError):
    """ General syntax error
    """
    
    def __init__(self, err, pos):
        self.err = err 
        self.pos = pos 

        super().__init__('SyntaxError at pos %d: ' % self.pos + self.err)


class ParseError(RuntimeError):
    """ Cannot recognize symbol.
    """

    def __init__(self, err):

        super().__init__('Cannot parse symbol "%s"' % err)
        

class CompileError(RuntimeError):
    """ Translate error
    """

    def __init__(self, err):
        super().__init__(err)
        