""" Preprocessing of text file (strip comment, include)
"""

import re 
import os.path

from .errors import ReadError


class Preprocessor:

    def __init__(self):
        self.suffix = '.csl'
        self.include_paths = ['.']
        self.macro_flag = r'\#' # macro is not used currently
        self.linecomm_flag = r'\/\/'
        self.blockcomm_flags = (r'\/\*', r'\*\/')
        self.on_blockcomm = False
        self.strstack = []
        self.included_files = set()

        self.clear()

    def clear(self):
        """ Clear and rebuild cache
        """
        self.on_blockcomm = False 
        self.strstack.clear()
        self.included_files.clear()
        self.re_macro = re.compile(self.macro_flag)
        self.re_linecomm = re.compile(self.linecomm_flag)
        self.re_blkcomm_begin = re.compile(self.blockcomm_flags[0])
        self.re_blkcomm_end = re.compile(self.blockcomm_flags[1])

    def get_fullname(self, filename):
        # searching full filename
        fullname = None
        for path in self.include_paths:
            if os.path.isfile(os.path.join(path, filename)):
                fullname = os.path.abspath(os.path.join(path, filename))
                break 

        if not fullname:
            raise ReadError('File %s does not exist' % filename)
        return fullname        

    def process_file(self, filename):

        if self.on_blockcomm:
            raise ReadError('Still on block comment')

        fullname = self.get_fullname(filename)


        if fullname in self.included_files:
            print('Ignoring included file: %s' % filename)
            return

        else:
            self.included_files.add(fullname)
            self.include_paths.append(os.path.dirname(fullname))
            with open(fullname, 'r') as finput:
                for line in finput:
                    self.process_line(line)


    def process_line(self, string):
        """ Process a string in one line
        """
        if self.on_blockcomm:
            blockcomm_end = self.re_blkcomm_end.search(string)
            if blockcomm_end:
                string = string[blockcomm_end.endpos:]
                self.on_blockcomm = False
            else:
                return
        
        comm_start = self.re_linecomm.search(string)
        if comm_start:
            string = string[:comm_start.pos]

        blockcomm_start = self.re_blkcomm_begin.search(string)
        if blockcomm_start:
            string = string[:blockcomm_start.pos]
            self.on_blockcomm = True 

        self.strstack.append(string)


    def result(self):
        """ Output result.
        """
        return ''.join(self.strstack)
