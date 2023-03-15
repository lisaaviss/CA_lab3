"""Модуль трансляции ASM-кода в инструкции процессора"""
import re
import sys
from enum import Enum

from isa import Opcode, write_code, Register, OperandType, INTERRUPTION_VECTOR_SZ


class SectionState(str, Enum):
    """"Enum состояний section"""
    DATA = "data"
    TEXT = "text"


str2register = {
    "r0": Register.R0,
    "r1": Register.R1,
    "r2": Register.R2,
    "r3": Register.R3,
    "r4": Register.R4,
    "sp": Register.SP,
    "pc": Register.PC,
}

str2section = {
    "data": SectionState.DATA,
    "text": SectionState.TEXT,
}

str2opcode = {
    "ld": Opcode.LD,
    "sv": Opcode.SV,
    "in": Opcode.IN,
    "out": Opcode.OUT,
    "add": Opcode.ADD,
    "sub": Opcode.SUB,
    "mul": Opcode.MUL,
    "div": Opcode.DIV,
    "mod": Opcode.MOD,
    "cmp": Opcode.CMP,
    "jmp": Opcode.JMP,
    "je": Opcode.JE,
    "jne": Opcode.JNE,
    "iret": Opcode.IRET,
    "sti": Opcode.STI,
    "cli": Opcode.CLI,
    "halt": Opcode.HLT
}


def translate(script):
    """Функция трансляции ASM кода в инструкции процессора"""
    labels = {}
    data_labels = {}
    code = []
    data = ["0"] * INTERRUPTION_VECTOR_SZ
    instr_count = 0
    data_count = INTERRUPTION_VECTOR_SZ
    state = None
    for line in script.split("\n"):
        if line == '':
            continue
        terms = re.split(r'\s+(?=(?:[^\'\"]*[\'\"][^\'\"]*[\'\"])*[^\'\"]*$)', line)
        if terms[0] == '':
            terms = terms[1:]
        # Удаляем комментарии
        for i in range(len(terms)):
            terms[i] = str(terms[i])
            if terms[i][0] == ';':
                terms = terms[0:i]
        if terms[0] == "section":
            if not terms[1] in str2section:
                raise SyntaxError(f"unknown section name {terms[1]}")
            state = str2section.get(terms[1])
            continue
        if terms[0][0:-1] in labels.keys() or terms[0][0:-1] in data_labels.keys():
            raise SyntaxError(f"duplicate label: {terms[0][0:-2]}")
        if not state:
            raise SyntaxError("no active section")
        if state == SectionState.TEXT:
            if len(terms) == 1 and terms[0][-1] == ':':
                labels[terms[0][0:-1]] = str(instr_count)
                continue
            instr_count += 1
        elif state == SectionState.DATA:
            if len(terms) == 1 and terms[0][-1] == ':':
                data_labels[terms[0][0:-1]] = str(data_count)
                continue
            if terms[0] == "word":
                if len(terms) != 2:
                    raise SyntaxError("variable declaration must have 1 arg")
                if len(terms[1]) == 3 and terms[1][0] == "'" and terms[1][2] == "'":
                    terms[1] = str(ord(terms[1][1]))
                elif not terms[1].isdigit():
                    raise SyntaxError(f"invalid data: {terms[1]}. only ints and chars are supported.")
                data.append(terms[1])
                data_count += 1
            elif terms[0] == "int":
                continue
            else:
                raise SyntaxError(f"unknown instruction {terms[0]}. only word instruction is supported")
    instr_count = 0
    for line in script.split("\n"):
        if line == '':
            continue
        line = line.strip()
        terms = re.split(r'\s+(?=(?:[^\'\"]*[\'\"][^\'\"]*[\'\"])*[^\'\"]*$)', line)
        if terms[0] == '':
            terms = terms[1:]
        if len(terms) == 0 or len(terms) == 1 and terms[0] == '':
            continue
        # Удаляем комментарии
        for i in range(len(terms)):
            terms[i] = str(terms[i])
            if terms[i][0] == ';':
                terms = terms[0:i]
        if terms[0] == "section":
            if not terms[1] in str2section:
                raise SyntaxError(f"unknown section name {terms[1]}")
            state = str2section.get(terms[1])
            continue

        if not state:
            raise SyntaxError("no active section")
        if state == SectionState.TEXT:
            if len(terms) == 1 and terms[0][-1] == ':':
                continue
            command = str2opcode[terms[0]]
            if terms[0] not in str2opcode:
                raise SyntaxError(f"unknown command {terms[0]}")
            for i, term in enumerate(terms):
                if i == 0:
                    continue
                if term in labels:
                    term = labels[term]
                elif term in data_labels:
                    if command in [Opcode.SV, Opcode.LD]:
                        term = data_labels[term]
                    else:
                        raise SyntaxError(f"{term}: can only use labels from data section in ld and sv")
                if len(term) == 3 and term[0] == "'" and term[2] == "'":
                    term = str(ord(term[1]))
                if term not in str2register.keys() and not term.isdigit():
                    raise SyntaxError(f"term {term} must be either register, integer or char")
                terms[i] = term
            if command in [Opcode.ADD, Opcode.CMP, Opcode.MUL, Opcode.DIV, Opcode.MOD, Opcode.SUB]:
                if len(terms) != 4:
                    raise SyntaxError(f"{command} command must have exactly 3 args")
                if terms[1] not in str2register.keys():
                    raise SyntaxError("output must be a register")
                if terms[2] not in str2register.keys():
                    raise SyntaxError("constants can only be second arguments")
                if terms[3] not in str2register.keys():
                    code.append({'opcode': terms[0], 'arg1': terms[2],
                                 'arg2': terms[3], 'arg2_type': OperandType.CONSTANT, 'out': terms[1]})
                else:
                    code.append({'opcode': terms[0], 'arg1': terms[2],
                                 'arg2': terms[3], 'arg2_type': OperandType.REGISTER, 'out': terms[1]})
            elif command in [Opcode.JMP, Opcode.OUT, Opcode.IN]:
                if len(terms) != 2:
                    raise SyntaxError(f"{command} command must have exactly 1 arg")
                if terms[1] not in str2register.keys():
                    if command is Opcode.IN:
                        raise SyntaxError(f"{command} command arg must be a register")
                    code.append({'opcode': terms[0], 'arg2': terms[1], 'arg2_type': OperandType.CONSTANT})
                else:
                    code.append({'opcode': terms[0], 'arg2': terms[1], 'arg2_type': OperandType.REGISTER})
            elif command in [Opcode.JE, Opcode.JNE]:
                if len(terms) != 3:
                    raise SyntaxError(f"{command} command must have exactly 2 args")
                if terms[1] not in str2register.keys():
                    raise SyntaxError("arg1 must be a register")
                if terms[2] not in str2register.keys():
                    arg2_type = OperandType.CONSTANT
                else:
                    arg2_type = OperandType.REGISTER
                code.append({'opcode': terms[0], 'arg1': terms[1],
                             'arg2': terms[2], 'arg2_type': arg2_type})
            elif command is Opcode.LD:
                if len(terms) != 3:
                    raise SyntaxError(f"{command} command must have exactly 2 args")
                if terms[1] not in str2register.keys():
                    raise SyntaxError("output must be a register")
                if terms[2] not in str2register.keys():
                    code.append({'opcode': terms[0], 'arg2': terms[2],
                                 'arg2_type': OperandType.CONSTANT, 'out': terms[1]})
                else:
                    code.append({'opcode': terms[0], 'arg2': terms[2],
                                 'arg2_type': OperandType.REGISTER, 'out': terms[1]})
            elif command is Opcode.SV:
                if len(terms) != 3:
                    raise SyntaxError(f"{command} command must have exactly 2 args")
                if terms[1] not in str2register.keys():
                    raise SyntaxError("data must a register")
                if terms[2] not in str2register.keys():
                    code.append({'opcode': terms[0], 'arg2': terms[2], 'arg2_type': OperandType.CONSTANT,
                                 'arg1': terms[1]})
                else:
                    code.append({'opcode': terms[0], 'arg2': terms[2], 'arg2_type': OperandType.REGISTER,
                                 'arg1': terms[1]})
            elif command in [Opcode.IRET, Opcode.CLI, Opcode.STI, Opcode.HLT]:
                code.append({'opcode': terms[0]})
            else:
                raise SyntaxError(f"translator does not support command: {command}")
            instr_count += 1
        elif state == SectionState.DATA:
            for i, term in enumerate(terms):
                if i == 0:
                    continue
                if term in labels:
                    term = labels[term]
                terms[i] = term
            if terms[0] == 'int':
                if len(terms) != 3:
                    raise SyntaxError("interruption vector declaration must have 2 args")
                if not terms[1].isdigit() or int(terms[1]) > INTERRUPTION_VECTOR_SZ - 1:
                    raise SyntaxError(f"interruption vector num must be from 0 to {INTERRUPTION_VECTOR_SZ}")
                if not terms[2].isdigit():
                    raise SyntaxError("interruption vector address must be int")
                data[int(terms[1])] = terms[2]
    code.append({'opcode': Opcode.HLT})
    return {"code": code, "data": data}


def main(args):
    """Функция запуска транслятора.

    Реализована таким образом, чтобы:

    - ограничить область видимости внутренних переменных;
    - упростить автоматическое тестирование.
    """
    assert len(args) == 2, \
        "Wrong arguments: translator.py <input_file> <target_file>"
    source, target = args

    with open(source, "rt", encoding="utf-8") as file:
        source = file.read()

    code = translate(source)
    print("source LoC:", len(source.split("\n")), "code instr:", len(code["code"]))
    write_code(target, code)


if __name__ == '__main__':
    main(sys.argv[1:])
