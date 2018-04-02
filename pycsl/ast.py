""" Abstract Syntax Tree: Definition and representation.
"""

from enum import Enum 

from .tokens import Token, TokenType


class DeclNode(Enum):
    """ Declaration node in Abstract Syntax Tree.
        Used only when AST.type == ASTType.DECL
    """
    FUNCDECL = 1    # function declaration
    VARDECL = 2     # variable declaration
    ARRAYDECL = 3   # array declaration
    DECLELEM = 4    # declaration element


class ASTType(Enum):
    NONE = 0    # reserved
    VAL = 1     # direct value
    NAME = 2    # variable name
    CALL = 3    # function call
    OP = 4      # operator
    CTRL = 5    # control (if/else/while/for/...)
    TYPE = 6    # typename (reserved)
    EXPR = 7    # expression node 
    DECL = 8    # decalaration (either function decl/variable decl)
    FUNC = 9    # function node
    BLOCK = 10  # a block by compound
    LIST = 11   # initialize list
    ROOT = 12   # root node
    


class AST:
    """ Abstract Syntax Tree
    """

    def __init__(self, mtype, mval=None, nodes=None, **kwargs):
        """ mval --> value of self (like operator.name)
        """
        self.type = mtype
        self.value = mval 
        self.attr = kwargs
        self.nodes = [] if not nodes else nodes 

    def __repr__(self):
        if len(self.nodes) > 0:
            return '%s{%s}' % (self.value, ''.join(['%s' % n for n in self.nodes]))
        else:
            return '%s' % self.value

    def append(self, child):
        """ Add a child.
        """
        self.nodes.append(child)
        

def token2ast(token:Token):
    """ Convert token to AST node.
        The type of token is limited in
        NONE, VAL, NAME, OP, TYPE, CTRL
    """

    ConvertTable = {
        TokenType.NONE: ASTType.NONE,
        TokenType.VAL: ASTType.VAL,
        TokenType.NAME: ASTType.NAME,
        TokenType.OP: ASTType.OP,
        TokenType.TYPE: ASTType.TYPE,
        TokenType.CTRL: ASTType.CTRL
    }

    return AST(ConvertTable[token.tp], token.val)


class ASTBuilder:
    """ Building an AST from token.
    """
    def __init__(self):

        self.ast = None # root
        self.curast = None

    def _checkinit(self, node):
        if self.ast is None:
            self.ast = self._translate(node)
            self.curast = self.ast
            return True 
        else:
            return False

    def add_child(self, child):
        """ Add a child, not move ptr.
        """
        if self._checkinit(child):
            pass 
        else:
            self.curast.append(self._translate(child))

    def ext_child(self, child):
        """ Add child, and move ptr to child.
        """
        if self._checkinit(child):
            pass 
        else:
            self.curast.append(self._translate(child))
            self.curast = self.curast.nodes[-1]

    def ext_parent(self, parent):
        """ Add parent to root, and move ptr to new root.
        """
        if self._checkinit(parent):
            pass 
        else:
            newast = self._translate(parent)
            newast.append(self.ast)
            self.ast = newast        
            self.curast = self.ast

    def _translate(self, obj):
        """ Try converting the object into AST.
        """
        if isinstance(obj, AST):
            return obj 
        elif isinstance(obj, Token):
            return token2ast(obj)


def printast(root:AST, indent='\t', level=0):
    """ Formatted print an AST.
    """
    if root.value is None:
        print('%s%s' % (indent * level, root.type))
    elif root.nodeval is None:
        print('%s%s' % (indent * level, root.value))
    else:
        print('%s%s (%r)' % (indent * level, root.value, root.nodeval))

    for node in root.nodes:
        printast(node, indent, level+1)
