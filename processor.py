"""
Модуль, эмулирующий работу процессора
"""
import json
import logging
import sys
from enum import Enum

from isa import Opcode, Register, OperandType, read_code

DATA_MEM_SZ = 10000


class AluOperations(str, Enum):
    """Enum операций для АЛУ"""
    DIV = 'r0'
    MOD = 'r1'
    CMP = 'r2'
    ADD = 'r3'
    INC = 'r4'
    DEC = 'pc'
    SUB = 'sp'
    MUL = 'mul'
    LEFT = 'left'
    RIGHT = 'right'
    NOP = 'nop'


opcode2alu = {
    Opcode.DIV: AluOperations.DIV,
    Opcode.MOD: AluOperations.MOD,
    Opcode.CMP: AluOperations.CMP,
    Opcode.ADD: AluOperations.ADD,
    Opcode.SUB: AluOperations.SUB,
    Opcode.MUL: AluOperations.MUL,
}


class Alu:
    """Арифметико-логическое устройство с двумя входами данных и сигналом операции."""

    def __init__(self):
        self.left: int = 0
        self.right: int = 0
        self.operations: dict = {
            AluOperations.DIV: lambda left, right: left / right,
            AluOperations.MOD: lambda left, right: left % right,
            AluOperations.CMP: lambda left, right: left - right,
            AluOperations.ADD: lambda left, right: left + right,
            AluOperations.INC: lambda left, right: left + 1,
            AluOperations.DEC: lambda left, right: left - 1,
            AluOperations.SUB: lambda left, right: left - right,
            AluOperations.MUL: lambda left, right: left * right,
            AluOperations.LEFT: lambda left, right: left,
            AluOperations.RIGHT: lambda left, right: right,
            AluOperations.NOP: lambda left, right: 0
        }
        self.zero_flag = True


class RegFile:
    """Класс эмулирующий регистровый файл"""

    def __init__(self):
        self.registers = {
            Register.R0: 0,
            Register.R1: 0,
            Register.R2: 0,
            Register.R3: 0,
            Register.R4: 0,
            Register.PC: 0,
            Register.SP: DATA_MEM_SZ
        }
        self.operand_1 = Register.R0
        self.operand_2 = Register.R0
        self.output = Register.R1


class DataPath:
    """Класс, эмулирующий тракт данных, предоставляющий интерфейс для CU"""

    def __init__(self, data_memory, output_int: bool):
        self.data_memory: list[int] = data_memory
        self.reg_file = RegFile()
        self.alu = Alu()
        self.alu_bus: int = 0
        self.output_bus: int = 0
        self.data_bus: int = 0
        self.input_buffer = []
        self.input_pointer = 0
        self.output_buffer = []
        self.output_int = output_int

    def latch_registers(self, operand_1, operand_2=Register.R0, output=Register.R1):
        """Метод для выбора набора регистров из регистрового файла для инструкции"""
        self.reg_file.operand_1 = operand_1
        self.reg_file.operand_2 = operand_2
        if output == Register.R0:
            raise MemoryError("can't write to r0")
        self.reg_file.output = output

    def latch_alu(self, const_operand=None):
        """Метод для эмуляции ввода данных в АЛУ"""
        self.alu.left = self.reg_file.registers[self.reg_file.operand_1]
        if const_operand is not None:
            self.alu.right = const_operand
        else:
            self.alu.right = self.reg_file.registers[self.reg_file.operand_2]
        self.data_bus = self.reg_file.registers[self.reg_file.operand_2]

    def latch_output(self):
        """Метод для эмуляции вывода данных в регистры"""
        self.reg_file.registers[self.reg_file.output] = self.output_bus

    def execute_alu(self, instruction: AluOperations):
        """Метод для эмуляции исполнения CU"""
        res = self.alu.operations[instruction](self.alu.left, self.alu.right)
        while res > 2147483647:
            res = -2147483648 + (res - 2147483647)
        while res < -2147483648:
            res = 2147483647 - (res + 2147483648)
        self.alu.zero_flag = (res == 0)
        self.alu_bus = res
        self.output_bus = res

    def write(self):
        """Метод для эмуляции сигнала записи в память данных"""
        self.data_memory[self.alu_bus] = self.data_bus

    def read(self):
        """Метод для эмуляции сигнала чтения из памяти данных"""
        self.output_bus = self.data_memory[self.alu_bus]

    def print(self):
        """Метод для эмуляции сигнала вывода данных на внешнее устройство"""
        if self.output_int:
            self.output_buffer.append(self.alu_bus)
        else:
            self.output_buffer.append(chr(self.alu_bus))

    def input(self):
        """Метод для эмуляции сигнала ввода данных с внешнего устройства"""
        try:
            self.output_bus = ord(self.input_buffer[self.input_pointer])
        except KeyError as exc:
            raise EOFError() from exc
        self.input_pointer += 1

    def get_zero_flag(self) -> bool:
        """Метод для получения Zero флага"""
        return self.alu.zero_flag


class ControlUnit:
    """Блок управления процессора. Выполняет декодирование инструкций и
    управляет состоянием процессора, включая обработку данных (DataPath).
    """

    def __init__(self, program, data_path, interrupt_queue):
        self.instr = None
        self.program: list = program
        self.int_queue: dict = interrupt_queue
        self.data_path: DataPath = data_path
        self._sig_branch = False
        self.interrupt_vector = [0]
        self._tick: int = 0
        self.is_interrupted: bool = False
        self.int_enabled: bool = False
        self.instr_cnt = 0

    def tick(self) -> None:
        """Счётчик тактов процессора. Вызывается при переходе на следующий такт."""
        self._tick += 1

    def current_tick(self):
        """Получить номер текущего такта"""
        return self._tick

    def latch_program_counter(self) -> None:
        """Инкрементировать счетчик команд"""
        self.data_path.reg_file.registers[Register.PC] += 1

    def decode_and_execute_instruction(self):
        """Выбрать из памяти инструкцию и выполнить ее"""
        if self.int_enabled and not self.is_interrupted and len(self.int_queue) != 0 \
                and self._tick >= min(self.int_queue.keys()):
            interrupt = self.int_queue[min(self.int_queue.keys())]
            del self.int_queue[min(self.int_queue.keys())]
            self.data_path.latch_registers(Register.SP, Register.PC)
            self.data_path.latch_alu()
            self.data_path.execute_alu(AluOperations.LEFT)
            self.data_path.write()
            self.tick()
            self.data_path.latch_registers(Register.SP, output=Register.SP)
            self.data_path.latch_alu()
            self.data_path.execute_alu(AluOperations.DEC)
            self.data_path.latch_output()
            self.tick()
            self.data_path.latch_registers(Register.R0, output=Register.PC)
            self.data_path.latch_alu(self.interrupt_vector[0])
            self.data_path.execute_alu(AluOperations.RIGHT)
            self.data_path.read()
            self.data_path.latch_output()
            self.tick()
            self.data_path.input_buffer.append(interrupt)
            self.is_interrupted = True

        instr = self.program[self.data_path.reg_file.registers[Register.PC]]
        self.instr = instr
        opcode = instr["opcode"]
        self.instr_cnt += 1

        if opcode is Opcode.HLT:
            raise StopIteration()

        if opcode is Opcode.IRET:
            self.data_path.latch_registers(Register.SP, output=Register.SP)
            self.data_path.latch_alu()
            self.data_path.execute_alu(AluOperations.INC)
            self.data_path.latch_output()
            self.tick()
            self.data_path.latch_registers(Register.SP, output=Register.PC)
            self.data_path.latch_alu()
            self.data_path.execute_alu(AluOperations.LEFT)
            self.data_path.read()
            self.data_path.latch_output()
            self.tick()
            self.is_interrupted = False
            return

        if opcode in [Opcode.JNE, Opcode.JE, Opcode.JMP]:
            if opcode is not Opcode.JMP:
                self.data_path.latch_registers(instr["arg1"], Register.R0)
                self.data_path.latch_alu()
                self.data_path.execute_alu(AluOperations.CMP)
                self.tick()
            if opcode is opcode.JMP or opcode is Opcode.JE and self.data_path.get_zero_flag() \
                    or opcode is Opcode.JNE and not self.data_path.get_zero_flag():
                if instr["arg2_type"] is OperandType.CONSTANT:
                    self.data_path.latch_registers(Register.R0, output=Register.PC)
                    self.data_path.latch_alu(instr["arg2"])
                else:
                    self.data_path.latch_registers(Register.R0, instr["arg2"], Register.PC)
                    self.data_path.latch_alu()
                self.data_path.execute_alu(AluOperations.RIGHT)
                self.data_path.latch_output()
                self.tick()
                return

        elif opcode is Opcode.OUT:
            if instr["arg2_type"] is OperandType.CONSTANT:
                self.data_path.latch_registers(Register.R0)
                self.data_path.latch_alu(instr["arg2"])
            else:
                self.data_path.latch_registers(Register.R0, instr["arg2"])
                self.data_path.latch_alu()
            self.data_path.execute_alu(AluOperations.RIGHT)
            self.data_path.print()
            self.tick()

        elif opcode is Opcode.IN:
            self.data_path.latch_registers(Register.R0, output=instr["arg2"])
            self.data_path.latch_alu()
            self.data_path.execute_alu(AluOperations.NOP)
            self.data_path.input()
            self.data_path.latch_output()
            self.tick()

        elif opcode in [Opcode.ADD, Opcode.CMP, Opcode.MUL, Opcode.DIV, Opcode.MOD, Opcode.SUB]:
            if instr["arg2_type"] is OperandType.REGISTER:
                self.data_path.latch_registers(instr["arg1"], operand_2=instr["arg2"], output=instr["out"])
                self.data_path.latch_alu()
            else:
                self.data_path.latch_registers(instr["arg1"], output=instr["out"])
                self.data_path.latch_alu(instr["arg2"])
            self.data_path.execute_alu(opcode2alu.get(instr["opcode"]))
            self.data_path.latch_output()
            self.tick()

        elif opcode is Opcode.LD:
            if instr["arg2_type"] is OperandType.REGISTER:
                self.data_path.latch_registers(instr["arg2"], Register.R0, instr["out"])
                self.data_path.latch_alu()
            else:
                self.data_path.latch_registers(Register.R0, Register.R0, instr["out"])
                self.data_path.latch_alu(const_operand=instr["arg2"])
            self.data_path.execute_alu(AluOperations.RIGHT)
            self.data_path.read()
            self.data_path.latch_output()
            self.tick()

        elif opcode is Opcode.SV:
            if instr["arg2_type"] is OperandType.REGISTER:
                self.data_path.latch_registers(instr["arg2"], instr["arg1"])
                self.data_path.latch_alu()
                self.data_path.execute_alu(AluOperations.LEFT)
            else:
                self.data_path.latch_registers(Register.R0, instr["arg1"])
                self.data_path.latch_alu(const_operand=instr["arg2"])
                self.data_path.execute_alu(AluOperations.RIGHT)
            self.data_path.write()
            self.tick()

        elif opcode in [Opcode.STI, Opcode.CLI]:
            self.int_enabled = (opcode == Opcode.STI)
            self.tick()

        self.latch_program_counter()

    def __repr__(self):
        data_memory = self.data_path.data_memory[self.data_path.reg_file.registers[Register.SP]]
        frmt = "{{INSTR: {}, TICK: {}, PC: {}, R0: {}, R1: {}, R2: {}, R3: {}, R4: {}, SP: {}, MEM[SP]: {}, OP1: {}, OP2: {}, OUT: {}, INT: {}}}"
        state = frmt.format(
            self.instr_cnt,
            self.current_tick(),
            self.data_path.reg_file.registers[Register.PC],
            self.data_path.reg_file.registers[Register.R0],
            self.data_path.reg_file.registers[Register.R1],
            self.data_path.reg_file.registers[Register.R2],
            self.data_path.reg_file.registers[Register.R3],
            self.data_path.reg_file.registers[Register.R4],
            self.data_path.reg_file.registers[Register.SP],
            data_memory,
            self.data_path.reg_file.operand_1,
            self.data_path.reg_file.operand_2,
            self.data_path.reg_file.output,
            self.is_interrupted,
        )
        if self.instr:
            arg1 = ''
            arg2 = ''
            out = ''
            if 'out' in self.instr:
                out = self.instr['out']
            if 'arg1' in self.instr:
                arg1 = self.instr['arg1']
            if 'arg2' in self.instr:
                arg2 = self.instr['arg2']
            action = f"{self.instr['opcode']} {out} {arg1} {arg2}"
            return f"{state} {action}"
        return f"{state}"


def simulation(program, interrupt_queue, limit, output_int):
    """Запуск симуляции процессора.

    Длительность моделирования ограничена количеством выполненных инструкций.
    """
    code: list = program["code"]
    data: list = program["data"]
    data_memory = [0] * (DATA_MEM_SZ + 2)
    for i in range(len(data)):
        data_memory[i] = data[i]
    data_path = DataPath(data_memory, output_int)
    control_unit = ControlUnit(code, data_path, interrupt_queue)
    instr_counter = 0
    logging.debug('%s', control_unit)
    try:
        while True:
            assert limit > instr_counter, "too long execution, increase limit!"
            control_unit.decode_and_execute_instruction()
            instr_counter += 1
            logging.debug('%s', control_unit)
    except EOFError:
        logging.warning('Input buffer is empty!')
    except MemoryError:
        logging.warning('Can not write to read-only register!')
    except StopIteration:
        pass
    if not output_int:
        buffer = ''.join(data_path.output_buffer)
        logging.info('output_buffer: %s', repr(buffer))
    else:
        buffer = ''
        for data in data_path.output_buffer:
            buffer += str(data)
        logging.info('output_buffer: %s', buffer)
    return buffer, instr_counter, control_unit.current_tick()


def main(args):
    """Метод для запуска программы из командной строки"""
    output, instr_counter, ticks = launch_processor(args)
    print(''.join(output))
    print("instr_counter: ", instr_counter, "ticks:", ticks)


def launch_processor(args):
    """Метод для эмуляции запуска программы из командной строки в тестах"""
    assert len(args) == 2 or len(args) == 3, "Wrong arguments: machine.py <code_file> <input_file> ?[int, str]"
    code_file, input_file = (None, None)
    if len(args) == 2:
        code_file, input_file = args
    output_int = False
    if len(args) == 3:
        code_file, input_file, output_type = args
        output_int = (output_type == 'int')
    program = read_code(code_file)
    with open(input_file, encoding="utf-8") as file:
        input_dict = json.loads(file.read())
    interruption_dict = {int(key): value for key, value in input_dict.items()}
    return simulation(program, interruption_dict, 100000, output_int)


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    main(sys.argv[1:])
