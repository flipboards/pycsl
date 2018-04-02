# pycsl - Python Implementation of Computation Script Language

## Introduction

### Computation Script Language (CSL)

Computation Script Language (CSL) is a language for computation scripts and simple arithmetics. It supports:

- Arithmetic calculation (+, -, *, /, %, ^[power]);
- Boolean calculation (and, or, not) same as Python;
- Controls (if, else, for, while, goto) same as C;
- Variables and declarations;
- Types (int, float, char, string);
- Functions (Pre-defined functions and self-definition);
- Structs (not support currently);
- Modules (Include other files by #include)

Similar to Python, a CSL program can run directly by line or by block. If input is a block, the CSL interpreter detects _main()_ function as the entry point.

### Examples

By line:

    > 1+2*(3+4)
    15
    > abs(-5)
    5

By block:

sum.csl:

    #include <std.h>

    def plus(x, y){
        return x + y;
    }

    def main(){
        int a;
        int i;
        a = 0;

        for (i=0;i<5;i++){
            a = plus(a, i);
            printi(a);
        }
    }

Execution:

    $csl sum.csl
    1
    3
    6
    10
    15


