/* SPDX-License-Identifier: GPL-2.0-or-later */
.text
.globl invoke_cheat_fixture
#ifndef _WIN32
.type invoke_cheat_fixture,@function
#endif
invoke_cheat_fixture:
    push %rbx
    push %rbp
    push %r12
    push %r13
    push %r14
    push %r15
    sub $40,%rsp
    mov %rsi,0(%rsp)
    mov %rdi,8(%rsp)
    mov %rdx,16(%rsp)
    mov %rcx,24(%rsp)
    .irp reg,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15
    vmovdqu (32*\reg)(%rdx),%ymm\reg
    .endr
    lea -136(%rsp),%rdi
    mov $128,%ecx
    mov $0xa5,%al
    rep stosb
    mov 8(%rsp),%r11
    pushq 120(%r11)
    popfq
    mov 0(%r11),%r15
    mov 8(%r11),%r14
    mov 16(%r11),%r13
    mov 24(%r11),%r12
    mov 40(%r11),%r10
    mov 48(%r11),%r9
    mov 56(%r11),%r8
    mov 64(%r11),%rdi
    mov 72(%r11),%rsi
    mov 80(%r11),%rbp
    mov 88(%r11),%rbx
    mov 96(%r11),%rdx
    mov 104(%r11),%rcx
    mov 112(%r11),%rax
    mov 32(%r11),%r11
    call *0(%rsp)
    mov %r11,0(%rsp)
    mov 24(%rsp),%r11
    mov %r15,0(%r11)
    mov %r14,8(%r11)
    mov %r13,16(%r11)
    mov %r12,24(%r11)
    mov %r10,40(%r11)
    mov %r9,48(%r11)
    mov %r8,56(%r11)
    mov %rdi,64(%r11)
    mov %rsi,72(%r11)
    mov %rbp,80(%r11)
    mov %rbx,88(%r11)
    mov %rdx,96(%r11)
    mov %rcx,104(%r11)
    mov %rax,112(%r11)
    mov 0(%rsp),%rax
    mov %rax,32(%r11)
    pushfq
    popq 120(%r11)
    mov 16(%rsp),%r10
    .irp reg,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15
    vmovdqu %ymm\reg,(32*\reg)(%r10)
    .endr
    lea -136(%rsp),%rdi
    mov $128,%ecx
    mov $0xa5,%al
    repe scasb
    sete %al
    movzbl %al,%eax
    add $40,%rsp
    pop %r15
    pop %r14
    pop %r13
    pop %r12
    pop %rbp
    pop %rbx
    ret
#ifndef _WIN32
.size invoke_cheat_fixture,.-invoke_cheat_fixture
#endif
#ifndef _WIN32
.section .note.GNU-stack,"",@progbits
#endif
