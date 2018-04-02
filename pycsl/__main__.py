
import sys 

from . import parse
from .ast import printast

def main(argv):

    parser = parse.Parser()
    sym_table = {}

    while True:

        line = input()
        ast = parser.parse_line(line, sym_table)
        printast(ast)


main(sys.argv)