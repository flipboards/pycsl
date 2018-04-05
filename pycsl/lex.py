""" Lexer.
"""

import re 
from collections import deque

from .errors import SynError

from .grammar import keywords
from .grammar.keywords import KeywordLoc, SepLoc
from .grammar.operators import OpLoc, OperatorRe
from .grammar.basic_types import typenames, TypenameLoc, Value

from .tokens import Token, Symbol, TokenType
from .util.ioutil import StrReader


class Lexer:
    
    """
    Token table:

    ws:       [ \\t\\n]+
    number:   (\\d*[.])?(\\d)+(e[+\\-]?\\d+)?
    var:      [a-zA-Z_]\\w*
    function: {var}\\(
    operator: [+\\-\\*\\/\\=\\%\\^\\!\\:\\,\\.\\<\\>]+
    lineend:  ;
    """
    
    re_ws = re.compile(r'[ \t\n]+')
    re_val = re.compile(r'(\d*[.])?(\d)+(e[+\-]?\d+)?')
    re_id = re.compile(r'[a-zA-Z_\w]*')
    re_op = re.compile(OperatorRe)
    re_eol = re.compile(r';')
    re_lbra = re.compile(r'\(')
    re_kwd_ctrl = re.compile('|'.join(keywords.ctrl_kwds))
    re_kwd_type = re.compile('|'.join(typenames))
    re_kwd_def = re.compile('|'.join(keywords.def_kwds))
    re_kwd_logic = re.compile('|'.join(keywords.logic_kwds))
    re_kwd_sep = re.compile(r'[\{\}\,\:]')


    def __init__(self):
        self.reader = None 
        self.token_str = None 
        self.token_buf = deque()
        self.next_get_pos = 0
        self.next_look_pos = 0

    def clear(self):
        self.reader = None
        self.token_buf.clear()
        self.token_str = None
        self.next_get_pos = self.next_look_pos = 0

    def load(self, ifile):
        """ Load an input.
            Args:
            --
            ifile: string/file-like object
            sym_table: dict-like object. If `None`, keep current sym_table.
        """
        self.clear()
        self.reader = StrReader(ifile)
        
    def get_token(self):
        """ Get next token ahead after last get(), regardless of how much
            look ahead.
        """

        if len(self.token_buf) == 0: # empty
            self.fetch_token()
        self.next_get_pos += 1
        self.next_look_pos = self.next_get_pos
        return self.token_buf.popleft()

    def get_all(self):
        """ get all tokens since last get() until current look_ahead()
        """
        out_buf = []
        while self.next_get_pos < self.next_look_pos:
            out_buf.append(self.token_buf.popleft())
            self.next_get_pos += 1
        return out_buf

    def look_ahead(self):
        """ 
        """
        buf_idx = self.next_look_pos - self.next_get_pos
        if buf_idx == len(self.token_buf):
            self.fetch_token()
        self.next_look_pos += 1
        return self.token_buf[buf_idx]

    def unlook_ahead(self):
        assert self.next_look_pos > self.next_get_pos, "Cannot unlook"
        self.next_look_pos -= 1

    def fetch_token(self):
        self.token_buf.append(self._fetch_token())

    def _fetch_token(self): 
        """ Fetch a new token from string. 
        """

        if self.reader.eof():
            return Token(TokenType.EOF, None)

        self.match(self.re_ws)

        if self.reader.eof():
            return Token(TokenType.EOF, None)
       
        if self.match(self.re_eol):
            return Token(TokenType.EOL, None)

        elif self.match(self.re_val):
            return Token(TokenType.VAL, Value.parse(self.token_str))

        elif self.match(self.re_op):
            return Token(TokenType.OP, OpLoc[self.token_str])

        elif self.match(self.re_kwd_sep):
            return Token(TokenType.SEP, SepLoc[self.token_str])

        elif self.match(self.re_id):
            if self.re_kwd_ctrl.fullmatch(self.token_str):
                return Token(TokenType.CTRL, KeywordLoc[self.token_str])
            elif self.re_kwd_def.fullmatch(self.token_str):
                return Token(TokenType.DEF, KeywordLoc[self.token_str])
            elif self.re_kwd_type.fullmatch(self.token_str):
                return Token(TokenType.TYPE, TypenameLoc[self.token_str])
            elif self.re_kwd_logic.fullmatch(self.token_str):
                return Token(TokenType.OP, OpLoc[self.token_str])

            return Token(TokenType.NAME, Symbol(self.token_str))
        
        else:

            raise SynError('Unrecognized token: %s' % self.next_char, self.cur_pos())


    def cur_pos(self):
        return self.reader.pos()

    def match(self, regex):
        # if match succeed. iter+=span, self.token_str changed, return True. else return False

        match_obj = regex.match(self.reader.obj, self.reader.pos())
        if match_obj:
            self.token_str = match_obj.group()
            self.reader.seek(match_obj.end())
            return True 
        else:
            return False 
            