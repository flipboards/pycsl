
from . import lex

from .util import ioutil
from .errors import SynError
from .tokens import Token, TokenType, Symbol

from .grammar.keywords import Keyword, Separator
from .grammar.basic_types import Value
from .grammar.operators import Operator, precedence, OpAryLoc, OpAssoLoc, OpAsso 

from .ast import AST, ASTType, ASTBuilder, DeclNode, token2ast


class Parser:
    """
    The main parser for CSL.
    Using recursive descent here (except for operators, where LR(1) is applied).
    """

    def __init__(self):
        self.cur_token = None
        self.next_token = None 
        self.next_look_token = None 
        self.lexer = lex.Lexer()
        self.aststack = []

    def clear(self):
        """ Clear token, tokenbuffer, aststack, lex.
        """
        self.cur_token = None
        self.next_token = None    
        self.next_look_token = None   
        self.lexer.clear()
        self.aststack.clear() 

    def parse(self, ifile):
        """ Parse a file containing functions.
            Returns an AST with node as ROOT.
        """
        self.clear()
        self.lexer.load(ifile)
        self.next_token = self.lexer.get_token()

        blocks = []

        while True:

            if self.match_noget(TokenType.DEF, lambda x:x == Keyword.DEF):
                blocks.append(self._parse_func_or_def())
            elif self.match_noget(TokenType.TYPE):
                blocks.append(self._parse_decl())
                if not self.match(TokenType.EOF):
                    self.force_match(TokenType.EOL)
            elif self.match(TokenType.EOL):
                continue 
            elif self.match(TokenType.EOF):
                break 
            else:
                raise SynError('Unrecognized head: %s' % self.next_token, self.lexer.cur_pos())

        return AST(ASTType.ROOT, nodes=blocks)

    def parse_line(self, ifile):
        """ Parse simple expression & statement.
            Returns the AST.

            Notice: Only part before semicolon ';' is parsed.
        """
        self.clear()
        self.lexer.load(ifile)
        self.next_token = self.lexer.get_token()

        if self.match_noget(TokenType.TYPE):
            mast = self._parse_decl()
        elif self.match_noget(TokenType.EOL):
            return None 
        elif self.match_noget(TokenType.EOF):
            return None 
        else:
            mast = self._parse_expr()

        self.match(TokenType.EOL)  # both line with/without ';' is OK. After ';' is not parsed.
        return mast 

    def _parse_func_or_def(self):
        """ Parse function or function definition.
        Syntax:
            func_def_or_decl = func_declarator ';'
                | func_declarator compound_stmt;
            func_declarator = 'def' id '(' id_list? ')'
            
        """
        
        # func head
        self.force_match(TokenType.DEF, lambda x:x == Keyword.DEF)
        self.force_match(TokenType.NAME)

        ast_head = AST(ASTType.DECL, DeclNode.FUNCDECL)
        ast_head.append(AST(ASTType.NAME, self.cur_token.val))

        self.force_match_op(Operator.LBRA)
        while True:
            if self.match(TokenType.NAME):
                ast_head.append(token2ast(self.cur_token))
                if self.match_sep(Separator.COMMA):
                    continue 
            elif self.match_op(Operator.RBRA):
                break 
            else:
                raise SynError('Unrecognized symbol %s' % self.next_token, self.lexer.cur_pos())

        mast = AST(ASTType.FUNC)
        mast.append(ast_head)

        if self.match(TokenType.EOL):
            return mast 
        else:
            mast.append(self._parse_compound_stmt())
            return mast 
            
    def _parse_compound_stmt(self):
        """ Parse a statement with compound bracket.
        Syntax:
            compound_stmt = '{''}'
                | '{' stmt_list? decl_list? '}'
        """

        self.force_match_sep(Separator.LCPD)
        mast = AST(ASTType.BLOCK)
        while True:
            if self.match_sep(Separator.RCPD):
                break 
            elif self.match(TokenType.EOL):
                continue 
            elif self.match_noget(TokenType.SEP, lambda x: x == Separator.LCPD):
                mast.append(self._parse_compound_stmt())
            elif self.match_noget(TokenType.TYPE):
                mast.append(self._parse_decl())
            else:
                mast.append(self._parse_stmt())

        return mast 

    def _parse_stmt(self):
        """ Parse a statement.
        Syntax:
            stmt = compound_stmt
                | expr_stmt
                | select_stmt
                | iter_stmt
                | jump_stmt
        """

        # if
        if self.match(TokenType.CTRL, lambda x:x == Keyword.IF):
            mast = token2ast(self.cur_token)
            self.force_match_op(Operator.LBRA)
            mast.append(self._parse_expr())
            self.force_match_op(Operator.RBRA)
            mast.append(self._parse_stmt())
            if self.match(TokenType.CTRL, lambda x:x == Keyword.ELSE):
                mast.append(self._parse_stmt())
            return mast 

        # while
        elif self.match(TokenType.CTRL, lambda x:x == Keyword.WHILE):
            mast = token2ast(self.cur_token)
            self.force_match_op(Operator.LBRA)
            mast.append(self._parse_expr())
            self.force_match_op(Operator.RBRA)
            mast.append(self._parse_stmt())
            return mast 

        # for
        elif self.match(TokenType.CTRL, lambda x:x == Keyword.FOR):
            mast = token2ast(self.cur_token)
            self.force_match_op(Operator.LBRA)
            mast.append(self._parse_expr())
            self.force_match(TokenType.EOL)
            mast.append(self._parse_expr())
            self.force_match(TokenType.EOL)
            mast.append(self._parse_expr())
            self.force_match_op(Operator.RBRA)
            mast.append(self._parse_stmt())
            return mast 
            
        # continue/break
        elif self.match(TokenType.CTRL, lambda x:x in (Keyword.CONTINUE, Keyword.BREAK)):
            return token2ast(self.cur_token)

        # return
        elif self.match(TokenType.CTRL, lambda x:x == Keyword.RETURN):
            mast = token2ast(self.cur_token)
            if self.match(TokenType.EOL):
                return mast 
            else:
                mast.append(self._parse_expr())
                return mast 

        elif self.match_noget(TokenType.SEP, lambda x:x == Separator.LCPD):
            return self._parse_compound_stmt()

        else:
            mast = self._parse_expr()
            self.force_match(TokenType.EOL)
            return mast


    def _parse_expr(self):
        """ Parse an expression (include assignment)
        Syntax:
            expr = simple_expr | postfix_expr '=' expr
        """

        mast, maxpred = self._parse_simple_expr()

        # assignment
        if self.match(TokenType.OP, lambda x: OpAryLoc[x] == 2 and OpAssoLoc[x] == 1):
            # check if left is simple enough
            if maxpred > 1:
                raise SynError('Lvalue required for assignment', self.lexer.cur_pos())
            
            return AST(ASTType.OP, self.cur_token.val, nodes=[mast, self._parse_expr()])

        else:
            return mast 

    def _parse_simple_expr(self):
        """ Parse an expression without assignment.
        Returns: Maximum precedence of operator appeared.
        """

        def parse_unary_expr():
            """ Parse an unary expression.
            Syntax:

                unary_expr = postfix_expr | '++|--|+|-' unary_expr;
                postfix_expr = primary_expr 
                    | postfix_expr '[' expr ']'
                    | postfix_expr '(' expr_list? ')'
                    | postfix_expr '.' id
                    | postfix_expr '++|--';
                primary_expr = id | value | '(' expr ')';
            """

            builder_pre = ASTBuilder()
            builder_post = ASTBuilder()

            # unary operators

            while True:
                if self.match_op(Operator.INC) or self.match_op(Operator.DEC):
                    builder_pre.ext_child(self.cur_token)
                elif self.match_op(Operator.ADD):
                    builder_pre.ext_child(AST(ASTType.OP, Operator.PLUS))
                elif self.match_op(Operator.SUB):
                    builder_pre.ext_child(AST(ASTType.OP, Operator.MINUS))
                elif self.match_op(Operator.NOT):
                    builder_pre.ext_child(AST(ASTType.OP, Operator.NOT))
                else:
                    break 

            # primary_expr

            if self.match(TokenType.NAME) or self.match(TokenType.VAL):
                builder_post.ext_child(self.cur_token)
            elif self.match_op(Operator.LBRA):
                builder_post.ext_child(self._parse_expr())
                self.force_match_op(Operator.RBRA)
            else:
                raise SynError('Unrecognized token: %r' % self.next_token, self.lexer.cur_pos())

            # postfix expr

            while True:
                # subscript
                if self.match_op(Operator.LSUB):
                    builder_post.ext_parent(AST(ASTType.OP, Operator.LSUB))
                    builder_post.add_child(self._parse_expr())
                    self.force_match_op(Operator.RSUB)

                # function call
                elif self.match_op(Operator.LBRA):
                    builder_post.ext_parent(AST(ASTType.CALL))
                    if not self.match_op(Operator.RBRA):
                        while True:
                            builder_post.add_child(self._parse_expr())
                            if not self.match_sep(Separator.COMMA):
                                break
                        self.force_match_op(Operator.RBRA)

                elif self.match_op(Operator.MBER):
                    builder_post.ext_parent(self.cur_token)
                    self.force_match(TokenType.NAME)
                    builder_post.add_child(self.cur_token)
                elif self.match_op(Operator.INC): # actually post inc
                    builder_post.ext_parent(AST(ASTType.OP, Operator.POSTINC))
                elif self.match_op(Operator.DEC):
                    builder_post.ext_parent(AST(ASTType.OP, Operator.POSTDEC))                    
                else:
                    break 

            builder_pre.ext_child(builder_post.ast)
            return builder_pre.ast 

        op_stack = [None]
        var_stack = []
        maxpred = 0

        while True:
            var_stack.append(parse_unary_expr())
            if not self.match_noget(TokenType.OP):
                break 

            cur_op = self.next_token.val 

            # assignment
            if OpAryLoc[cur_op] == 2 and OpAssoLoc[cur_op] == 1:
                break

            # right bracket
            if cur_op == Operator.RBRA or cur_op == Operator.RSUB:
                break 

            self.match(TokenType.OP)

            if OpAryLoc[cur_op] == 1 or OpAssoLoc[cur_op] != 0:
                raise SynError('Incorrect operator: %s' % self.cur_token.val, self.lexer.cur_pos())

            curpred = precedence(cur_op)
            maxpred = max(maxpred, curpred)
            # check precedence
            # push operator
            if curpred < precedence(op_stack[-1]):
                op_stack.append(cur_op)

            else: # all left association
                while curpred >= precedence(op_stack[-1]):
                    rv, lv = var_stack.pop(), var_stack.pop()
                    var_stack.append(AST(ASTType.OP, op_stack.pop(), nodes=[lv, rv]))
                op_stack.append(cur_op)

        while len(op_stack) > 1:
            rv, lv = var_stack.pop(), var_stack.pop()
            var_stack.append(AST(ASTType.OP, op_stack.pop(), nodes=[lv, rv]))

        if len(op_stack) != 1 or len(var_stack) != 1:
            raise SynError('Binary operator not match', self.lexer.cur_pos())

        return var_stack.pop(), maxpred

    def _parse_decl(self):
        """ Parse a variable declaration without line end.
        Syntax:

            decl = TYPE decl_init_list
            decl_init_list = decl_init | decl_init_list ',' decl_init
            decl_init = declarator | declarator '=' initializer
        """
        
        def parse_declarator():
            """ Parse a declarator
            Syntax:

                declarator = id | declarator '[' simple_expr? ']'
            """
            builder = ASTBuilder()
            self.match(TokenType.NAME) # must begin with id
            builder.ext_child(self.cur_token)

            while True:
                # []
                if self.match_op(Operator.LSUB):
                   # builder.ext_parent(AST(ASTType.DECL, DeclNode.ARRAYDECL))
                    if not self.match(Operator.RSUB):
                        builder.add_child(self._parse_simple_expr()[0])
                        self.force_match_op(Operator.RSUB)
                else:
                    break 
            return builder.ast 
                        
        def parse_initializer():
            """ Parse an initializer
            Syntax:

            initalizer = expr
                | '{' initializer_list '}'
                | '{' initializer_list ',' expr

            initializer_list := initalizer | initializer_list ',' initalizer;
            """
            
            if self.match_sep(Separator.LCPD):
                mast = AST(ASTType.LIST)
                while True:
                    mast.append(parse_initializer())
                    if not self.match_sep(Separator.COMMA):
                        break 

                self.force_match_sep(Separator.RCPD)
                return mast 

            else:
                return self._parse_expr()

        mast = AST(ASTType.DECL, DeclNode.VARDECL)
        self.force_match(TokenType.TYPE)
        mast.append(AST(ASTType.TYPE, self.cur_token.val))

        # decl_init_list
        while True:
            mast.append(AST(ASTType.DECL, DeclNode.DECLELEM))
            mast.nodes[-1].append(parse_declarator())
            if self.match_op(Operator.ASN):
                mast.nodes[-1].append(parse_initializer())
            if not self.match_sep(Separator.COMMA):
                break

        return mast 

    def match(self, token_type, func=None):
        if self.next_token.tp == token_type:
            if func is None or func(self.next_token.val):
                self.cur_token = self.next_token
                self.next_token = self.lexer.get_token()
                return True 
        else:
            return False 

    def match_op(self, opname):
        return self.match(TokenType.OP, lambda x:x == opname)

    def match_sep(self, sepname):
        return self.match(TokenType.SEP, lambda x:x == sepname)

    def force_match(self, token_type, func=None):
        if not self.match(token_type, func):
            raise SynError('Token not match: %s required, got %s' % (token_type, self.next_token), self.lexer.cur_pos())
        
    def force_match_op(self, opname):
        if not self.match_op(opname):
            raise SynError('Operator not match: %s required, got %s' % (opname, self.next_token.val), self.lexer.cur_pos())

    def force_match_sep(self, sepname):
        if not self.match_sep(sepname):
            raise SynError('Separator not match: %s required, got %s' % (sepname, self.next_token.val), self.lexer.cur_pos())

    def match_noget(self, token_type, func=None):
        """ Match without get. So next time still same token.
        """
        if self.next_token.tp == token_type:
            if func is None or func(self.next_token.val):
                return True 
        else:
            return False 
        
    def match_ahead(self, token_type, func=None):
        """ Match with look ahead.
        """
        if not self.next_look_token:
            self.next_look_token = self.next_token

        if self.next_look_token.tp == token_type:
            if func is None or func(self.next_token.val):
                self.next_look_token = self.lexer.look_ahead()
                return True 
            else:
                return False 

    def revert(self):
        self.next_look_token = None 
