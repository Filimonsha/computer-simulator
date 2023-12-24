import logging
import re
from enum import Enum

from translator.isa import Opcode

REGS_COUNT = 6
VARS_SEG_SIZE = 100
STR_SEG_SIZE = 50

class MicroprogramController:
    def __init__(self):
        self.program_counter = VARS_SEG_SIZE

    def

class ALU_OPERATION(str, Enum):
    MINUS = "MINUS",
    PLUS = "PLUS",
    DIVIDE = "DIVIDE",
    MUL = "MUL"
    MOD = "MOD",
    PASS_VALUE = "PASS_VALUE"
class ALU: 
    
    def __init__(self):
        self.l_alu = 0
        self.r_alu = 0
        self.zero_flag = 0
        self.neg_flag = 0
        self.alu = 0
    def is_zero_flag(self):
        return self.zero_flag == 1

    def is_neg_flag(self):
        return self.neg_flag == 1

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

    def set_zero_flag(self):
        if self.alu == 0:
            self.zero_flag = 1
        else:
            self.zero_flag = 0

    def set_neg_flag(self):
        if self.alu < 0:
            self.neg_flag = 1
        else:
            self.neg_flag = 0
class DataPath:
    def __init__(self, memory_size, mem, input_buffer):
        assert memory_size > 0, "Memory size should be non-zero"
        self.memory_size = memory_size

        self.instr_addr = 0
        self.data_addr = 0
        self.data_address = VARS_SEG_SIZE

        self.memory = mem
        self.input_buffer = input_buffer
        self.output_buffer = []

        self.regs = [0] * REGS_COUNT
        self.l_bus = 0
        self.r_bus = 0

        self.l_const = 0
        self.r_const = 0


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
                self.data_address = self.instr_addr
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
        print("la",out_type)
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
    


class ControlUnit:
    def __init__(self, data_path: DataPath,alu:ALU):
        self.program_counter = VARS_SEG_SIZE
        self.data_path = data_path
        self.alu = alu
        self._tick = 0

    def tick(self):
        self._tick += 1

    def current_tick(self):
        return self._tick

    def latch_program_counter(self, sel_next):
        if sel_next:
            self.program_counter += 1
        else:
            instr = self.data_path.memory[self.data_path.data_address]
            assert 'arg1' in instr or instr['arg1'] is not None, "internal error"
            self.program_counter = instr['arg1']
        self.data_path.instr_addr = self.program_counter

    def decode_instruction(self):
        instr = self.data_path.memory[self.data_path.data_address]
        opcode = instr['opcode']

        if opcode == Opcode.HLT:
            raise StopIteration()

        if opcode == Opcode.JMP:
            self.latch_program_counter(sel_next=False)
            self.data_path.sel_addr_src(0)
            self.tick()

        if opcode == Opcode.JE:
            if self.alu.is_zero_flag():
                self.latch_program_counter(sel_next=False)
            else:
                # TODO добавить тики
                self.latch_program_counter(sel_next=True)
            self.data_path.sel_addr_src(0)
            self.tick()

        if opcode == Opcode.JNE:
            if self.alu.is_zero_flag():
                self.latch_program_counter(sel_next=True)
            else:
                self.latch_program_counter(sel_next=False)
            self.data_path.sel_addr_src(0)
            self.tick()

        if opcode == Opcode.JLE:
            if self.alu.is_neg_flag() or self.alu.is_zero_flag():
                self.latch_program_counter(sel_next=False)
            else:
                self.latch_program_counter(sel_next=True)
            self.data_path.sel_addr_src(0)
            self.tick()

        if opcode == Opcode.JGE:
            if not self.alu.is_neg_flag() or self.alu.is_zero_flag():
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
                    self.alu.calc_alu(ALU_OPERATION.PLUS)
                case Opcode.SUB:
                    self.alu.calc_alu(ALU_OPERATION.MINUS)
                case Opcode.MUL:
                    self.alu.calc_alu(ALU_OPERATION.DIVIDE)
                case Opcode.DEV:
                    self.alu.calc_alu(ALU_OPERATION.MOD)
                case Opcode.MOD:
                    self.alu.calc_alu(ALU)
                case Opcode.CMP:
                    self.alu.calc_alu(1)
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
                    self.alu.calc_alu(5)
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
                self.alu.calc_alu(5)
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
                self.alu.calc_alu(5)
            elif re.search(r'^(-?[1-9][0-9]*|0)$', str(arg1)) is not None:
                const = int(re.search(r'(-?[1-9][0-9]*|0)', str(arg1)).group(0))
                self.data_path.l_const = const
                self.data_path.sel_l_inp(True)
                self.alu.calc_alu(5)

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
            self.program_counter,
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
