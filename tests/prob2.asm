section text
ld r0 0
ld r1 1
ld r2 2
loop:
cmp r2 4000000
jne check_even
jmp end_loop
check_even:
mod r3 r2 2
jne not_even
add r0 r0 r2
not_even:
add r2 r1 r2
sv r1
sv r2
jmp loop
end_loop:
out r0