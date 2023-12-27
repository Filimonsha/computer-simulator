import logging
import re
import sys
from enum import Enum

from isa import Opcode, read_code
from utils import REGS_COUNT

VARS_START_POS = 100
STR_START_POS = 50


class DataPath:
    def __init__(self, memory_size, input_buffer, mem):
        assert memory_size > 0, "Memory size should be non-zero"
        self.memory_size = memory_size

        self.IR = 0
        self.data_addr = 0
        self.data_address = VARS_START_POS

        self.memory = mem
        self.input_buffer = input_buffer
        self.output_buffer = []

        self.regs = [0] * REGS_COUNT
        self.l_bus = 0
        self.r_bus = 0

        self.l_const = 0
        self.r_const = 0

        self.l_alu = 0
        self.r_alu = 0
        self.zero = 0
        self.neg = 0
        self.alu = 0

    def sel_l_bus(self, reg):
        assert 0 <= reg < 6, "Machine has only 6 regs"
        self.l_bus = self.regs[reg]

    def sel_r_bus(self, reg):
        assert 0 <= reg < 6, "Machine has only 6 regs"
        self.r_bus = self.regs[reg]

    def sel_l_inp(self, inp_type):
        if inp_type:
            self.l_alu = self.l_const
        else:
            self.l_alu = self.l_bus

    def sel_r_inp(self, inp_type):
        if inp_type:
            self.r_alu = self.r_const
        else:
            self.r_alu = self.r_bus

    def is_zero(self):
        return self.zero == 1

    def is_neg(self):
        return self.neg == 1

    def calc_alu(self, operation):
        match operation:
            case 0:
                self.alu = self.l_alu + self.r_alu
            case 1:
                self.alu = self.l_alu - self.r_alu
            case 2:
                self.alu = self.l_alu * self.r_alu
            case 3:
                self.alu = self.l_alu // self.r_alu
            case 4:
                self.alu = self.l_alu % self.r_alu
            case 5:
                self.alu = self.l_alu

    def set_zero(self):
        if self.alu == 0:
            self.zero = 1
        else:
            self.zero = 0

    def set_neg(self):
        if self.alu < 0:
            self.neg = 1
        else:
            self.neg = 0

    def sel_reg(self, reg, src):
        match src:
            case 0:
                self.regs[reg] = self.memory[self.data_address]
            case 1:
                self.regs[reg] = self.alu
            case 2:
                self.input(reg)

    def sel_addr_src(self, src):
        match src:
            case 0:
                self.data_address = self.IR
            case 1:
                self.data_address = self.data_addr
            case 2:
                self.data_address = self.alu

    def write(self):
        self.memory[self.data_address] = self.alu

    def input(self, reg):
        if len(self.input_buffer) == 0:
            raise EOFError()
        symbol = self.input_buffer.pop(0)
        symbol_code = ord(symbol)
        assert -128 <= symbol_code <= 127, \
            "input token is out of bound: {}".format(symbol_code)
        self.regs[reg] = symbol_code
        logging.debug('input: %s', repr(symbol))

    def output(self, out_type):
        print("la", out_type)
        if out_type:
            symbol = self.alu
            logging.debug('output: %s << %s', repr(
                ''.join(self.output_buffer)), repr(str(symbol)))
            self.output_buffer.append(str(symbol))
        else:
            symbol = chr(self.alu)
            # TODO change on pascal
            if symbol != "\0":
                logging.debug('output: %s << %s', repr(''.join(self.output_buffer)), repr(symbol))
                self.output_buffer.append(symbol)


class MC_Unit:
    def __init__(self):
        self.mc_mem = []

    #     self.opcode_mapping = {
    #         Opcode.VAR: 0b00000000,
    #         Opcode.JMP: 0b00000001,
    #         Opcode.JMPR: 0b00000010,
    #         Opcode.HLT: 0b00000011,
    #         Opcode.JNE: 0b00000100,
    #         Opcode.JE: 0b00000101,
    #         Opcode.CMP: 0b00000110,
    #         Opcode.PRINT: 0b00000111,
    #         Opcode.NOP: 0b00001000,
    #         Opcode.READ: 0b00001001,
    #         Opcode.PRINTSTR: 0b00001010,
    #         Opcode.JLE: 0b00001011,
    #         Opcode.JGE: 0b00001100,
    #         Opcode.PRINTC: 0b00001101,
    #         Opcode.ADD: 0b00001110,
    #         Opcode.SUB: 0b00001111,
    #         Opcode.MUL: 0b00010000,
    #         Opcode.DEV: 0b00010001,
    #         Opcode.MOD: 0b00010010,
    #         Opcode.MOV: 0b00010011
    #     }
    #
    # def execute(self,instruction):
    #     opcode, arg1, arg2, arg3 = self.decode_instruction(instruction)
    #     for key, value in self.opcode_mapping.items():
    #         print("OMG IS",key)
    #         if value == opcode:
    #             if key == Opcode.VAR:
    #                 # Обработка инструкции VAR
    #                 print("Processing VAR instruction")
    #                 # Дополнительная обработка для каждой инструкции
    #
    #             elif key == Opcode.JMP:
    #                 # Обработка инструкции JMP
    #                 print("Processing JMP instruction")
    #                 # Дополнительная обработка для каждой инструкции
    #
    #             # Добавьте обработку других инструкций
    #
    #             else:
    #                 print(f"Unhandled instruction: {key}")
    #
    #             return
    #
    #     print("Unknown opcode")
    #
    # def encode_instruction(self, opcode: Opcode, arg1, arg2, arg3):
    #     print(Opcode["MOV"].,"AAA")
    #     # Кодирование инструкции в микрокоманду
    #     return (int(opcode.value) << 24) | (arg1 << 16) | (arg2 << 8) | arg3
    #
    # def encode_instruction_decimal(self, opcode:Opcode, arg1, arg2, arg3):
    #     # Кодирование инструкции в микрокоманду из десятичной формы
    #     return self.encode_instruction(opcode, arg1, arg2, arg3)
    # def decode_instruction(self, instruction):
    #     # Декодирование микрокоманды в значения Opcode и аргументы
    #     # Эта операция выполняет "битовое И" (&) между значением инструкции и маской 0xFF000000. Маска содержит единицы в старших байтах и нули в младших байтах. Это оставляет только старший байт значения инструкции.
    #
    #     opcode = Opcode((instruction & 0xFF000000) >> 24)
    #     arg1 = (instruction & 0x00FF0000) >> 16
    #     arg2 = (instruction & 0x0000FF00) >> 8
    #     arg3 = (instruction & 0x000000FF)
    #     return opcode, arg1, arg2, arg3

    def encode(self, opcode_value, arg1=None, arg2=None):

        # for member in Opcode:
        #     if member.value == opcode_value:
        #         obcode_name = member.name
        #         break
        value_to_index = {opcode.value: index for index, opcode in enumerate(Opcode, start=1)}
        opcode_index = value_to_index[opcode_value]
        """Кодирование микрокоманды."""
        opcode_bits = format(opcode_index, '05b')  # 5 bits for opcode
        arg1_bits = format(arg1, '010b') if arg1 is not None else '0000000000'  # 10 bits for arg1
        arg2_bits = format(arg2, '010b') if arg2 is not None else '0000000000'  # 10 bits for arg2

        microcode = f"{opcode_bits}{arg1_bits}{arg2_bits}"
        return microcode

    def decode(self,microcode):
        """Декодирование микрокоманды."""
        opcode_bits = microcode[:5]
        arg1_bits = microcode[5:15]
        arg2_bits = microcode[15:]

        enum_list = list(Opcode)
        opcode = enum_list[int(opcode_bits, 2) - 1]

        print(opcode)
        # opcode = Opcode[int(opcode_bits, 2)].name
        arg1 = int(arg1_bits, 2)
        arg2 = int(arg2_bits, 2)

        return opcode, arg1, arg2


class ControlUnit:

    def __init__(self, data_path: DataPath):
        self.PC = VARS_START_POS
        self.data_path = data_path
        self._tick = 0
        self.mc_unit = MC_Unit()

    def tick(self):
        self._tick += 1

    def current_tick(self):
        return self._tick

    def latch_program_counter(self, sel_next):
        if sel_next:
            self.PC += 1
        else:
            instr = self.data_path.memory[self.data_path.data_address]
            assert 'arg1' in instr or instr['arg1'] is not None, "internal error"
            self.PC = instr['arg1']
        self.data_path.IR = self.PC

    def decode_and_execute_instruction(self):
        instr = self.data_path.memory[self.data_path.data_address]
        opcode = instr['opcode']
        if opcode == Opcode.HLT:
            raise StopIteration()

        if opcode == Opcode.JMP:
            self.latch_program_counter(sel_next=False)
            self.data_path.sel_addr_src(0)
            self.tick()

        if opcode == Opcode.JE:
            if self.data_path.is_zero():
                self.latch_program_counter(sel_next=False)
            else:
                # TODO добавить тики
                self.latch_program_counter(sel_next=True)
            self.data_path.sel_addr_src(0)
            self.tick()

        if opcode == Opcode.JNE:
            if self.data_path.is_zero():
                self.latch_program_counter(sel_next=True)
            else:
                self.latch_program_counter(sel_next=False)
            self.data_path.sel_addr_src(0)
            self.tick()

        if opcode == Opcode.JLE:
            if self.data_path.is_neg() or self.data_path.is_zero():
                self.latch_program_counter(sel_next=False)
            else:
                self.latch_program_counter(sel_next=True)
            self.data_path.sel_addr_src(0)
            self.tick()

        if opcode == Opcode.JGE:
            if not self.data_path.is_neg() or self.data_path.is_zero():
                self.latch_program_counter(sel_next=False)
            else:
                self.latch_program_counter(sel_next=True)
            self.data_path.sel_addr_src(0)
            self.tick()

        if opcode in {Opcode.ADD, Opcode.SUB, Opcode.MUL, Opcode.DEV, Opcode.MOD, Opcode.CMP}:

            arg1 = 0
            arg2 = 0
            if opcode == Opcode.CMP:
                arg1 = instr['arg1']
                arg2 = instr['arg2']
            else:
                arg1 = instr['args'][0]
                arg2 = instr['args'][1]
            if re.search(r'^r[0-5]$', str(arg1)) is not None:
                reg = int(re.search(r'[0-5]', re.search(r'^r[0-5]$', str(arg1)).group(0)).group(0))
                self.data_path.sel_l_bus(reg)
                self.data_path.sel_l_inp(False)
            elif re.search(r'^(-?[1-9][0-9]*|0)$', str(arg1)) is not None:
                const = int(re.search(r'(-?[1-9][0-9]*|0)', str(arg1)).group(0))
                self.data_path.l_const = const
                self.data_path.sel_l_inp(True)

            if re.search(r'^r[0-5]$', str(arg2)) is not None:
                reg = int(re.search(r'[0-5]', re.search(r'^r[0-5]$', str(arg2)).group(0)).group(0))
                self.data_path.sel_r_bus(reg)
                self.data_path.sel_r_inp(False)
            elif re.search(r'^(-?[1-9][0-9]*|0)$', str(arg2)) is not None:
                const = int(re.search(r'(-?[1-9][0-9]*|0)', str(arg2)).group(0))
                self.data_path.r_const = const
                self.data_path.sel_r_inp(True)
            elif arg2 == '\0':
                const = 0
                self.data_path.r_const = const
                self.data_path.sel_r_inp(True)

            match opcode:
                case Opcode.ADD:
                    self.data_path.calc_alu(0)
                case Opcode.SUB:
                    self.data_path.calc_alu(1)
                case Opcode.MUL:
                    self.data_path.calc_alu(2)
                case Opcode.DEV:
                    self.data_path.calc_alu(3)
                case Opcode.MOD:
                    self.data_path.calc_alu(4)
                case Opcode.CMP:
                    self.data_path.calc_alu(1)
                    self.data_path.set_zero()
                    self.data_path.set_neg()
            self.tick()

            if 'res_reg' in instr:
                reg = int(re.search(r'[0-5]', re.search(r'^r[0-5]$', instr['res_reg']).group(0)).group(0))
                self.data_path.sel_reg(reg, 1)

            self.latch_program_counter(True)
            self.data_path.sel_addr_src(0)
            self.tick()

        if opcode == Opcode.MOV:
            arg1 = instr['arg1']
            arg2 = instr['arg2']
            print("fAAAA", type(opcode))
            mc = self.mc_unit.encode(opcode,15,20)
            print(mc)
            print(self.mc_unit.decode(mc))

            if re.search(r'^r[0-5]$', str(arg1)) is not None:
                reg = int(re.search(r'[0-5]', re.search(r'^r[0-5]$', arg1).group(0)).group(0))
                if isinstance(arg2, int):
                    data_addr = int(arg2)
                    self.data_path.data_addr = data_addr
                    self.data_path.sel_addr_src(1)

                elif re.search(r'^\[r[0-5]\]$', str(arg2)) is not None:
                    reg2 = int(re.search(r'[0-5]', re.search(r'^\[r[0-5]\]$', arg2).group(0)).group(0))
                    self.data_path.sel_l_bus(reg2)
                    self.data_path.sel_l_inp(False)
                    self.data_path.calc_alu(5)
                    self.data_path.sel_addr_src(2)
                self.data_path.sel_reg(reg, 0)
            elif isinstance(arg1, int):
                data_addr = int(arg1)
                self.data_path.data_addr = data_addr
                self.data_path.sel_addr_src(1)
                if re.search(r'^r[0-5]$', str(arg2)) is not None:
                    reg = int(re.search(r'[0-5]', re.search(r'^r[0-5]$', arg2).group(0)).group(0))
                    self.data_path.sel_l_bus(reg)
                    self.data_path.sel_l_inp(False)

                if re.search(r'^(-?[1-9][0-9]*|0)$', str(arg2)) is not None:
                    const = int(re.search(r'(-?[1-9][0-9]*|0)', str(arg2)).group(0))
                    self.data_path.l_const = const
                    self.data_path.sel_l_inp(True)
                self.data_path.calc_alu(5)
                self.data_path.write()
            self.tick()

            if 'res_reg' in instr:
                reg = int(re.search(r'[0-5]', re.search(r'^r[0-5]$', instr['res_reg']).group(0)).group(0))
                # Записывает в регистры
                self.data_path.sel_reg(reg, 1)

            self.latch_program_counter(True)
            self.data_path.sel_addr_src(0)
            self.tick()

        if opcode in {Opcode.PRINT, Opcode.PRINTC}:
            arg1 = instr['arg1']
            if re.search(r'^r[0-5]$', str(arg1)) is not None:
                reg = int(re.search(r'[0-5]', re.search(r'^r[0-5]$', arg1).group(0)).group(0))
                self.data_path.sel_l_bus(reg)
                self.data_path.sel_l_inp(False)
                self.data_path.calc_alu(5)
            elif re.search(r'^(-?[1-9][0-9]*|0)$', str(arg1)) is not None:
                const = int(re.search(r'(-?[1-9][0-9]*|0)', str(arg1)).group(0))
                self.data_path.l_const = const
                self.data_path.sel_l_inp(True)
                self.data_path.calc_alu(5)

            if opcode == Opcode.PRINT:
                self.data_path.output(True)
            else:
                self.data_path.output(False)
            self.tick()

            if 'res_reg' in instr:
                reg = int(re.search(r'[0-5]', re.search(r'^r[0-5]$', instr['res_reg']).group(0)).group(0))
                self.data_path.sel_reg(reg, 1)

            self.latch_program_counter(True)
            self.data_path.sel_addr_src(0)
            self.tick()

        if opcode == Opcode.READ:
            arg1 = instr['reg']
            if re.search(r'^r[0-5]$', str(arg1)) is not None:
                reg = int(re.search(r'[0-5]', re.search(r'^r[0-5]$', arg1).group(0)).group(0))
                self.data_path.sel_reg(reg, 2)
                self.tick()
            self.latch_program_counter(True)
            self.data_path.sel_addr_src(0)
            self.tick()

    def __prep__(self):
        state = "{{TICK: {}, PC: {}, ADDR: {}, R0: {}, R1: {}, R2: {}, R3: {}, R4: {}, R5: {} }}".format(
            self._tick,
            self.PC,
            self.data_path.data_address,
            self.data_path.regs[0],
            self.data_path.regs[1],
            self.data_path.regs[2],
            self.data_path.regs[3],
            self.data_path.regs[4],
            self.data_path.regs[5],
        )
        instr = self.data_path.memory[self.data_path.data_address]
        opcode = instr["opcode"]
        if opcode in {Opcode.ADD, Opcode.SUB, Opcode.MUL, Opcode.DEV, Opcode.MOD}:
            arg1 = instr.get("args", "")[0]
            arg2 = instr.get("args", "")[1]
        else:
            arg1 = instr.get("arg1", "")
            arg2 = instr.get("arg2", "")
        if arg2 == '\0':
            arg2 = "null_term"
        term = instr.get("term", None)
        action = "xxx"
        if term is not None:
            if arg2 != '':
                if 'res_reg' in instr:
                    action = "{} {} {} -> {}".format(opcode, arg1, arg2, instr['res_reg'])
                else:
                    action = "{} {} {}".format(opcode, arg1, arg2)
            else:
                if 'res_reg' in instr:
                    action = "{} {} -> {}".format(opcode, arg1, instr['res_reg'])
                else:
                    action = "{} {}".format(opcode, arg1)
        return "{} {}".format(state, action)


def simulation(code, input_buffer, memory_size, limit):
    data = code.pop()
    # Переменные в память
    mem = [0] * VARS_START_POS
    for key in data['data']:
        if isinstance(data['data'][key], int):
            mem[int(key)] = data['data'][key]
        else:
            mem[int(key)] = ord(data['data'][key][0])
    # Кладем инструкции
    for instr in code:
        mem.append(instr)

    data_path = DataPath(memory_size, input_buffer, mem)
    control_unit = ControlUnit(data_path)
    instr_counter = 0

    logging.debug('%s', control_unit.__prep__())
    try:
        while True:
            assert limit > instr_counter, "too long execution, increase limit!"
            # TODO
            control_unit.decode_and_execute_instruction()
            instr_counter += 1
            logging.debug('%s', control_unit.__prep__())
    except EOFError:
        logging.warning('Input buffer is empty!')
    except StopIteration:
        pass
    logging.info('output_buffer: %s', repr(''.join(data_path.output_buffer)))
    return ''.join(data_path.output_buffer), instr_counter


def main(args):
    assert len(args) == 2, "Wrong arguments: machine.py <code_file> <input_file>"
    code_file, input_file = args

    code = read_code(code_file)
    input_buffer = []
    with open(input_file, encoding="utf-8") as file:
        input_text = file.read()
        for char in input_text:
            input_buffer.append(char)
    input_buffer.append("\0")
    output, instr_counter = simulation(code, input_buffer=input_buffer, memory_size=150, limit=1000)
    print("instr_counter: ", instr_counter)
    return output


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    main(sys.argv[1:])
