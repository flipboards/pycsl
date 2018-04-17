
import sys

if __name__ == '__main__':

    if len(sys.argv) == 1 or sys.argv[1] == '-h':
        print('''Please use 'cslc' / 'csl' to start pycsl.
        ''')
        exit(0)

    if sys.argv[1] == 'compile':

        if '-h' in sys.argv[2:]:
            print('''cslc [ARGS...] [FILE]
Additional arguments will be passed to llc.''')
            exit(0)

        filename = None

        for arg in sys.argv[2:]:
            if arg[0] != '-':
                filename = arg

        if not filename:
            print('Error: No input files')
            exit(1)

        import os
        from . import parse, ast, translate, vm

        parser = parse.Parser()
        tree = parser.parse_file(filename)
        translater = translate.Translater()
        translater.translate(tree)
        converter = vm.LLConverter(translater)
        irfilename = filename.rsplit('.', 1)[0] + '.ll'
        converter.output(irfilename)

        if not '-emit-llvm' in sys.argv[2:]:
            sys.argv.remove(filename)
            os.system('clang %s %s' % ( ' '.join(sys.argv[2:]), irfilename))
            os.remove(irfilename)

    elif sys.argv[1] == 'interpret':

        pass

    else:
        print('Error: Unknown command %s' % sys.argv[1])
