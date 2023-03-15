"""Модуль интерфейса инструкций модели процессора"""
import json
from enum import Enum

INTERRUPTION_VECTOR_SZ = 1


class Opcode(str, Enum):
    """Enum доступных инструкций процессора"""
    DECLARE = 'declare'

    LD = 'ld'
    SV = 'sv'

    ADD = 'add'
    SUB = 'sub'
    MUL = 'mul'
    DIV = 'div'
    MOD = 'mod'
    CMP = 'cmp'

    OUT = 'out'
    IN = 'in'

    JMP = 'jmp'
    JE = 'je'
    JNE = 'jne'

    IRET = 'iret'
    STI = 'sti'
    CLI = 'cli'

    HLT = 'halt'


class Register(str, Enum):
    """Enum доступных регистров процессора"""
    R0 = 'r0'
    R1 = 'r1'
    R2 = 'r2'
    R3 = 'r3'
    R4 = 'r4'
    PC = 'pc'
    SP = 'sp'


class OperandType(str, Enum):
    """Enum типов операндов в инструкциях процессора"""
    REGISTER = 'reg'
    CONSTANT = 'const'


def write_code(filename, code):
    """Записать машинный код в файл."""
    with open(filename, "w", encoding="utf-8") as file:
        file.write(json.dumps(code, indent=4))


def read_code(filename):
    """Прочесть машинный код из файла."""
    with open(filename, encoding="utf-8") as file:
        program = json.loads(file.read())
    code = program["code"]
    for i, cell in enumerate(program["data"]):
        program["data"][i] = int(cell)
    for instr in code:
        instr['opcode'] = Opcode(instr['opcode'])
        if 'arg1' in instr:
            instr['arg1'] = Register(instr['arg1'])
        if 'arg2_type' in instr:
            instr['arg2_type'] = OperandType(instr['arg2_type'])
            if instr['arg2_type'] is OperandType.REGISTER:
                instr['arg2'] = Register(instr['arg2'])
            else:
                instr['arg2'] = int(instr['arg2'])
        if 'out' in instr:
            instr['out'] = Register(instr['out'])
    return {"code": code, "data": program["data"]}
