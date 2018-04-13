# CSL IR Documentation

Documentation of CSL intermediate representation.


## Memory structure

### Register

Registers are function specific. In IR, registers only stores type, not value.

### Label

Lables are also function specific. They share same namespace with registers. Label's target address (represented by __int__) points the line of target TAC.

### Identifier

An identifier can only used in symbol table, can be targeted to a local label / register, or a global variable. The target position should be unique for an identifier.


## Codes

There are 26 codes currently in CSL IR. __hlt__, __invoke__, __pow__ are not appeared in LLVM IR, and they will cause error when compiling.


### Type system

Basic types are: __void__, __bool__, __char__, __int__ (i32), __float__ (f64).

__Array__ type is used for arrays.

__Pointer__ is only used in variable addressing.


### TAC

The tac has five components: __ret__, __code__, __first__, __second__ and __cond__. Only __code__ must be present. The required value of components in different code are listed below:

code    | ret       | first     | second    | cond      |note
---     | ---       | ---       | ---       | ---       |---
hlt     |           |           |           |           |cannot implement in LLVM
ret     |           |value_or_id|           |           |
br      |           |label      |           |           |branch to a label
br      |           |label      |label      |value_or_id|branch by condition
invoke  |           |           |           |           |reserved for future use
add     |id         |value_or_id|value_or_id|           |
sub     |id         |value_or_id|value_or_id|           |
mul     |id         |value_or_id|value_or_id|           |
div     |id         |value_or_id|value_or_id|           |
rem     |id         |value_or_id|value_or_id|           |
pow     |id         |value_or_id|value_or_id|           |cannot implement in LLVM
and     |id         |value_or_id|value_or_id|           |
or      |id         |value_or_id|value_or_id|           |
xor     |id         |value_or_id|value_or_id|           |
not     |id         |value_or_id|value_or_id|           |will be changed to icmp in LLVM
alloc   |id         |type       |           |           |
load    |id         |id         |           |           |
store   |           |id         |id         |           |
getptr  |id         |id         |list of voi|           |
eq      |id         |value_or_id|value_or_id|           |
ne      |id         |value_or_id|value_or_id|           |
lt      |id         |value_or_id|value_or_id|           |
le      |id         |value_or_id|value_or_id|           |
ge      |id         |value_or_id|value_or_id|           |
phi     |id         |(voi, label)|(voi, label)|         |
call    |id         |function   |list of voi|           |

