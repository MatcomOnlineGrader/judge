%include "io.inc"

section .data

a dd 0
b dd 0

section .text

global CMAIN

CMAIN:

mov ebp, esp; for correct debugging

;write your code here
GET_DEC 4,a
GET_DEC 4,b
mov eax,[a]
mov ebx,[b]
add eax,ebx
PRINT_DEC 4, eax

xor eax, eax

ret
