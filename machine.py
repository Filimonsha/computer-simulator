import logging
import re
import sys

from isa import Opcode, read_code
from utils import REGS_COUNT

VARS_START_POS = 100
STR_START_POS = 50


class ALU:
    def __init__(self):
        self.l_alu = 0
        self.r_alu = 0
        self.zero = 0
        self.neg = 0
        self.alu = 0

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

    def is_zero(self):
        return self.zero == 1

    def is_neg(self):
        return self.neg == 1

    def execute_alu_op(self, operation):
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


class CommonMemory:
    def __init__(self, code):
        self.code = code

        self.data = self.code.pop()['data']

        self.memory = [0] * VARS_START_POS

        self.load_memory()

    def load_memory(self):
        for key in self.data:
            if isinstance(self.data[key], int):
                self.memory[int(key)] = self.data[key]
            else:
                self.memory[int(key)] = ord(self.data[key][0])

        # Кладем инструкции
        for instr in self.code:
            self.memory.append(instr)


class DataPath:
    def __init__(self, memory_size, input_buffer, code):
        assert memory_size > 0, "Memory size should be non-zero"
        self.memory_size = memory_size

        self.IR = 0
        self.pointer_of_indirect_addressing = 0
        self.data_address = VARS_START_POS

        self.common_memory = CommonMemory(code).memory
        self.input_buffer = input_buffer
        self.output_buffer = []

        self.regs = [0] * REGS_COUNT
        # Левая Шина для АЛУ
        self.left_bus_signal = 0
        # Правая Шина для АЛУ
        self.right_bus_signal = 0

        self.l_const = 0
        self.r_const = 0

        self.ALU_instance = ALU()

    def set_left_bus_signal(self, reg):
        assert 0 <= reg < 6, "Machine has only 6 regs"
        self.left_bus_signal = self.regs[reg]

    def set_right_bus_signal(self, reg):
        assert 0 <= reg < 6, "Machine has only 6 regs"
        self.right_bus_signal = self.regs[reg]

    def set_left_alu_input_signal(self, inp_type):
        if inp_type:
            self.ALU_instance.l_alu = self.l_const
        else:
            self.ALU_instance.l_alu = self.left_bus_signal

    def sel_right_alu_input_signal(self, inp_type):
        if inp_type:
            self.ALU_instance.r_alu = self.r_const
        else:
            self.ALU_instance.r_alu = self.right_bus_signal

    def sel_reg(self, reg, src):
        match src:
            case 0:
                self.regs[reg] = self.common_memory[self.data_address]
            case 1:
                self.regs[reg] = self.ALU_instance.alu
            case 2:
                self.input(reg)

    def sel_addr_src(self, src):
        match src:
            case 0:
                self.data_address = self.IR
            #     Косвенная адресация
            case 1:
                self.data_address = self.pointer_of_indirect_addressing
            #     Рассчитанная адресация
            case 2:
                self.data_address = self.ALU_instance.alu

    def write(self):
        self.common_memory[self.data_address] = self.ALU_instance.alu

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

        def is_hex_string(char):
            char.isdigit() or (char.lower() >= 'a' and char.lower() <= 'f')

        if out_type:
            symbol = self.ALU_instance.alu
            logging.debug('output: %s << %s', repr(
                ''.join(self.output_buffer)), repr(str(symbol)))
            self.output_buffer.append(str(symbol))
        else:
            symbol = chr(self.ALU_instance.alu)
            if symbol != "\0":
                logging.debug('output: %s << %s', repr(''.join(self.output_buffer)), repr(symbol))
                self.output_buffer.append(symbol)


class MCUnit:
    def __init__(self, data_path):
        self.mc_mem = []
        self.PC = VARS_START_POS
        self.data_path = data_path
        # self.latch_program_counter = latch_program_counter
        self.tick_counter = 0

    def latch_program_counter(self, sel_next):
        if sel_next:
            self.PC += 1
        else:
            instr = self.data_path.common_memory[self.data_path.data_address]
            assert 'arg1' in instr or instr['arg1'] is not None, "internal error"
            self.PC = instr['arg1']

        self.data_path.IR = self.PC

    def tick(self):
        self.tick_counter += 1

    def set_const(self, arg1, arg2):
        if re.search(r'^r[0-5]$', str(arg1)) is not None:
            reg = int(re.search(r'[0-5]', re.search(r'^r[0-5]$', str(arg1)).group(0)).group(0))
            self.data_path.set_left_bus_signal(reg)
            self.data_path.set_left_alu_input_signal(False)
        elif re.search(r'^(-?[1-9][0-9]*|0)$', str(arg1)) is not None:
            const = int(re.search(r'(-?[1-9][0-9]*|0)', str(arg1)).group(0))
            self.data_path.l_const = const
            self.data_path.set_left_alu_input_signal(True)

        if re.search(r'^r[0-5]$', str(arg2)) is not None:
            reg = int(re.search(r'[0-5]', re.search(r'^r[0-5]$', str(arg2)).group(0)).group(0))
            self.data_path.set_right_bus_signal(reg)
            self.data_path.sel_right_alu_input_signal(False)
        elif re.search(r'^(-?[1-9][0-9]*|0)$', str(arg2)) is not None:
            const = int(re.search(r'(-?[1-9][0-9]*|0)', str(arg2)).group(0))
            self.data_path.r_const = const
            self.data_path.sel_right_alu_input_signal(True)
        elif arg2 == '\0':
            const = 0
            self.data_path.r_const = const
            self.data_path.sel_right_alu_input_signal(True)

    def execute(self, mc, instr=None):
        opcode = self.decode(microcode=mc)

        if opcode == Opcode.HLT:
            raise StopIteration()

        if opcode == Opcode.JMP:
            self.latch_program_counter(sel_next=False)
            self.data_path.sel_addr_src(0)
            self.tick()

        if opcode == Opcode.JE:
            if self.data_path.ALU_instance.is_zero():
                self.latch_program_counter(sel_next=False)
            else:
                # TODO добавить тики
                self.latch_program_counter(sel_next=True)
            self.data_path.sel_addr_src(0)
            self.tick()

        if opcode == Opcode.JNE:
            if self.data_path.ALU_instance.is_zero():
                self.latch_program_counter(sel_next=True)
            else:
                self.latch_program_counter(sel_next=False)
            self.data_path.sel_addr_src(0)
            self.tick()

        if opcode == Opcode.JLE:
            if self.data_path.ALU_instance.is_neg() or self.data_path.ALU_instance.is_zero():
                self.latch_program_counter(sel_next=False)
            else:
                self.latch_program_counter(sel_next=True)
            self.data_path.sel_addr_src(0)
            self.tick()

        if opcode == Opcode.JGE:
            if not self.data_path.ALU_instance.is_neg() or self.data_path.ALU_instance.is_zero():
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

            self.set_const(arg1, arg2)

            match opcode:
                case Opcode.ADD:
                    self.data_path.ALU_instance.execute_alu_op(0)
                    self.tick()
                case Opcode.SUB:
                    self.data_path.ALU_instance.execute_alu_op(1)
                    self.tick()
                case Opcode.MUL:
                    self.data_path.ALU_instance.execute_alu_op(2)
                    self.tick()
                case Opcode.DEV:
                    self.data_path.ALU_instance.execute_alu_op(3)
                    self.tick()
                case Opcode.MOD:
                    self.data_path.ALU_instance.execute_alu_op(4)
                    self.tick()
                case Opcode.CMP:
                    self.data_path.ALU_instance.execute_alu_op(1)
                    self.tick()
                    self.data_path.ALU_instance.set_zero()
                    self.tick()
                    self.data_path.ALU_instance.set_neg()
                    self.tick()
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
            if re.search(r'^r[0-5]$', str(arg1)) is not None:
                reg = int(re.search(r'[0-5]', re.search(r'^r[0-5]$', arg1).group(0)).group(0))
                if isinstance(arg2, int):
                    pointer_of_indirect_addressing = int(arg2)
                    self.data_path.pointer_of_indirect_addressing = pointer_of_indirect_addressing
                    self.data_path.sel_addr_src(1)

                elif re.search(r'^\[r[0-5]\]$', str(arg2)) is not None:
                    reg2 = int(re.search(r'[0-5]', re.search(r'^\[r[0-5]\]$', arg2).group(0)).group(0))
                    self.data_path.set_left_bus_signal(reg2)
                    self.data_path.set_left_alu_input_signal(False)
                    self.data_path.ALU_instance.execute_alu_op(5)
                    self.data_path.sel_addr_src(2)
                self.data_path.sel_reg(reg, 0)
            elif isinstance(arg1, int):
                pointer_of_indirect_addressing = int(arg1)
                self.data_path.pointer_of_indirect_addressing = pointer_of_indirect_addressing
                self.data_path.sel_addr_src(1)
                if re.search(r'^r[0-5]$', str(arg2)) is not None:
                    reg = int(re.search(r'[0-5]', re.search(r'^r[0-5]$', arg2).group(0)).group(0))
                    self.data_path.set_left_bus_signal(reg)
                    self.data_path.set_left_alu_input_signal(False)

                if re.search(r'^(-?[1-9][0-9]*|0)$', str(arg2)) is not None:
                    const = int(re.search(r'(-?[1-9][0-9]*|0)', str(arg2)).group(0))
                    self.data_path.l_const = const
                    self.data_path.set_left_alu_input_signal(True)
                self.data_path.ALU_instance.execute_alu_op(5)
                self.data_path.write()
            self.tick()

            if 'res_reg' in instr:
                reg = int(re.search(r'[0-5]', re.search(r'^r[0-5]$', instr['res_reg']).group(0)).group(0))
                # Записывает в регистры
                self.data_path.sel_reg(reg, 1)

            self.latch_program_counter(True)
            self.data_path.sel_addr_src(0)
            self.tick()

        if opcode in {Opcode.PRINTINT, Opcode.PRINTC}:
            arg1 = instr['arg1']
            if re.search(r'^r[0-5]$', str(arg1)) is not None:
                reg = int(re.search(r'[0-5]', re.search(r'^r[0-5]$', arg1).group(0)).group(0))
                self.data_path.set_left_bus_signal(reg)
                self.data_path.set_left_alu_input_signal(False)
                self.data_path.ALU_instance.execute_alu_op(5)
            elif re.search(r'^(-?[1-9][0-9]*|0)$', str(arg1)) is not None:
                const = int(re.search(r'(-?[1-9][0-9]*|0)', str(arg1)).group(0))
                self.data_path.l_const = const
                self.data_path.set_left_alu_input_signal(True)
                self.data_path.ALU_instance.execute_alu_op(5)

            if opcode == Opcode.PRINTINT:
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
            # TODO
            arg1 = instr['reg']
            if re.search(r'^r[0-5]$', str(arg1)) is not None:
                reg = int(re.search(r'[0-5]', re.search(r'^r[0-5]$', arg1).group(0)).group(0))
                self.data_path.sel_reg(reg, 2)
                self.tick()
            self.latch_program_counter(True)
            self.data_path.sel_addr_src(0)
            self.tick()

    def encode(self, opcode_value, arg1=None, arg2=None):
        """Кодирование микрокоманды."""

        value_to_index = {opcode.value: index for index, opcode in enumerate(Opcode, start=1)}
        opcode_index = value_to_index[opcode_value]
        opcode_bits = format(opcode_index, '05b')  # 5 bits for opcode
        arg1_bits = format(hash(arg1) & ((1 << 10) - 1),
                           '013b') if arg1 is not None else '0000000000'  # 10 bits for arg1
        arg2_bits = format(hash(arg1) & ((1 << 10) - 1),
                           '013b') if arg2 is not None else '0000000000'  # 10 bits for arg2

        microcode = f"{opcode_bits}{arg1_bits}{arg2_bits}"
        self.mc_mem.append(microcode)
        return microcode

    def decode(self, microcode):
        """Декодирование микрокоманды."""
        opcode_bits = microcode[:5]
        # arg1_bits = microcode[5:15]
        # arg2_bits = microcode[15:]
        # arg1 = int(arg1_bits, 2)
        # arg2 = int(arg2_bits, 2)
        enum_list = list(Opcode)
        opcode = enum_list[int(opcode_bits, 2) - 1]


        return opcode


class ControlUnit:

    def __init__(self, data_path: DataPath):
        self.mc_unit = MCUnit(data_path)

    def decode_and_execute_instruction(self):
        instr = self.mc_unit.data_path.common_memory[self.mc_unit.data_path.data_address]
        opcode = instr['opcode']
        self.mc_unit.execute(self.mc_unit.encode(opcode), instr)

    def __prep__(self):
        state = "{{TICK: {}, PC: {}, ADDR: {}, R0: {}, R1: {}, R2: {}, R3: {}, R4: {}, R5: {} }}".format(
            self.mc_unit.tick_counter,
            self.mc_unit.PC,
            self.mc_unit.data_path.data_address,
            self.mc_unit.data_path.regs[0],
            self.mc_unit.data_path.regs[1],
            self.mc_unit.data_path.regs[2],
            self.mc_unit.data_path.regs[3],
            self.mc_unit.data_path.regs[4],
            self.mc_unit.data_path.regs[5],
        )
        instr = self.mc_unit.data_path.common_memory[self.mc_unit.data_path.data_address]
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

    data_path = DataPath(memory_size, input_buffer, code)
    control_unit = ControlUnit(data_path)
    # instr_counter = 0

    logging.debug('%s', control_unit.__prep__())
    try:
        while True:
            # TODO
            assert limit > control_unit.mc_unit.tick_counter, "too long execution, increase limit!"

            control_unit.decode_and_execute_instruction()
            logging.debug('%s', "control_unit.__prep__()")
    except EOFError:
        logging.warning('Input buffer is empty!')
    except StopIteration:
        pass

    logging.info('output_buffer: %s', repr(''.join(data_path.output_buffer)))
    return ''.join(data_path.output_buffer)


def main(args):
    assert len(args) == 2, "Wrong arguments: machine.py <code_file> <input_file>"
    input_buff = []
    code_file, input_file = args
    code = read_code(code_file)

    with open(input_file, encoding="utf-8") as file:
        input_text = file.read()
        # input_buffer.append(str(len(input_text)))
        for char in input_text:
            input_buff.append(char)
    output = simulation(code, input_buffer=input_buff, memory_size=150, limit=10000)
    print(''.join(output).strip())
    print("instr_counter: ", 2)
    return output


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    main(sys.argv[1:])
