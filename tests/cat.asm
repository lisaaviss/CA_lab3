section data
    int 0 int_handler ;dddd
section text
    sti
    halt
    int_handler:
        sv r1 sp
        in r1
        out r1
        ld r1 sp
        iret