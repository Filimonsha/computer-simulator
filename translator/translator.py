import re
import sys
from collections import namedtuple
from enum import Enum

from isa import Opcode, write_code
from utils import RegisterController, VARS_SEG_SIZE, STR_SEG_SIZE

key_words = {"var", "setvar", "loop", "if", "(", ")", "+", "-", "*", "/", "%", "print", "println", "!=", "=", ">", "<",
             "<=", ">=", "return-from", "read", "printc"}


class Term(namedtuple('Term', 'pos word')):
    """Описание выражения из исходного текста программы."""
    # сделано через класс, чтобы был docstring


class Translator:
    deep = 0
    code = []
    variables = {}
    strings = []
    instr_stack = []
    instr_counter = VARS_SEG_SIZE
    jmp_stack = []
    if_jmp_stack = []
    label_list = {}
    registerController = RegisterController()
    terms = []

    source_code = None

    def __init__(self, source_code):
        self.source_code = source_code
        RegisterController.init_regs()

    def slice_source_on_terms(self, text):
        text = re.sub(r'\(', "( ", text)
        text = re.sub(r'\)', " )", text)
        text = re.sub(r'\)\(', ") (", text)
        text = re.sub(r'\" \)', "\0\" )", text)
        for pos, word in enumerate(re.split(r'\s+(?![^"]*"[ )])', text), 1):
            if word in key_words or re.fullmatch("[a-zA-Z]+", word) or re.fullmatch("[0-9]+", word) or re.fullmatch(
                    "\"[^\"]+\"", word):
                self.terms.append(Term(pos, word))

    def check_on_brackets(self):
        deep = 0
        for term in self.terms:
            if term.word == "(":
                deep += 1
            if term.word == ")":
                deep -= 1
            assert deep >= 0, "Unbalanced brackets!"
        assert deep == 0, "Unbalanced brackets!"

    def translate_into_opcode(self):
        self.slice_source_on_terms(self.source_code)
        self.check_on_brackets()
        return self.lex_source_terms(
            terms=self.terms,
            deep=self.deep,
            code=self.code,
            variables=self.variables,
            strings=self.strings,
            instr_stack=self.instr_stack,
            instr_counter=self.instr_counter,
            jmp_stack=self.jmp_stack,
            if_jmp_stack=self.if_jmp_stack,
            label_list=self.label_list,
        )

    def lex_source_terms(
            self,
            terms,
            deep,
            code,
            variables,
            strings,
            instr_stack,
            instr_counter,
            jmp_stack,
            if_jmp_stack,
            label_list,
    ):
        for pos, term in enumerate(terms):
            match term.word:
                case "(":
                    deep += 1
                case ")":
                    deep -= 1
                    if len(instr_stack) > 0:
                        instr = instr_stack.pop()

                        if instr['opcode'] is Opcode.JMP:
                            instr['arg1'] = jmp_stack.pop()[0]
                            if 'label' in instr:
                                if len(label_list) > 0 and instr['label'] in label_list:
                                    for num in label_list[instr['label']]:
                                        code[num - VARS_SEG_SIZE]['arg1'] = instr_counter + 1
                            instr['term'] = instr['opcode'].value
                            code.append(instr)
                            instr_counter += 1

                        if instr['opcode'] is Opcode.JMPR:
                            assert 'target_label' in instr, "return-from without label"
                            if instr['target_label'] not in label_list:
                                label_list[instr['target_label']] = [instr_counter]
                            label_list[instr['target_label']].append(instr_counter)
                            instr['opcode'] = Opcode.JMP
                            instr['res_reg'] = RegisterController.get_free_reg()
                            instr['term'] = instr['opcode'].value
                            code.append(instr)
                            instr_counter += 1

                        if instr['opcode'] in {Opcode.ADD, Opcode.SUB, Opcode.MUL, Opcode.DEV, Opcode.MOD}:
                            args = instr['args']
                            for i, arg in enumerate(args):
                                if isinstance(args[i], int):
                                    reg = RegisterController.get_free_reg()
                                    add_mov = {'opcode': Opcode.MOV, 'arg1': reg,
                                               'arg2': args[i], 'term': Opcode.MOV.value}
                                    code.append(add_mov)
                                    instr_counter += 1
                                    args[i] = reg
                            for arg in args:
                                if re.fullmatch(r'r[0-5]', arg):
                                    RegisterController.free_reg(int(re.search(r'[0-5]', arg).group(0)))
                            instr['res_reg'] = RegisterController.get_free_reg()
                            if len(args) > 2:
                                for i in range(2, len(instr['args'])):
                                    add_math_instr = None
                                    if i == 2:
                                        add_math_instr = {'opcode': instr['opcode'],
                                                          'args': [instr['args'][i - 2], instr['args'][i - 1]],
                                                          'res_reg': instr['res_reg'], 'term': Opcode.ADD.value}
                                    else:
                                        add_math_instr = {'opcode': instr['opcode'],
                                                          'args': [instr['res_reg'], instr['args'][i - 1]],
                                                          'res_reg': instr['res_reg'], 'term': Opcode.ADD.value}
                                    code.append(add_math_instr)
                                    instr_counter += 1
                                instr = {'opcode': instr['opcode'],
                                         'args': [instr['res_reg'], instr['args'][len(instr['args']) - 1]],
                                         'res_reg': instr['res_reg'], 'term': Opcode.ADD.value}

                            if len(instr_stack) > 0:
                                instr1 = instr_stack.pop()
                                match instr1['opcode']:

                                    case Opcode.CMP:
                                        if instr1['arg1'] is None:
                                            instr1['arg1'] = instr['res_reg']
                                        elif instr1['arg2'] is None:
                                            instr1['arg2'] = instr['res_reg']
                                        instr1['res_reg'] = instr['res_reg']

                                    case Opcode.MOV:
                                        if instr1['arg2'] is None:
                                            instr1['arg2'] = instr['res_reg']
                                        instr1['res_reg'] = instr['res_reg']

                                    case Opcode.ADD | Opcode.SUB | Opcode.MUL | Opcode.DEV | Opcode.MOD:
                                        instr1['args'].append(instr['res_reg'])

                                    case Opcode.PRINT:
                                        if instr1['arg1'] is None:
                                            instr1['arg1'] = instr['res_reg']
                                        instr1['res_reg'] = instr['res_reg']

                                    case Opcode.JMP:
                                        reg = instr['res_reg']
                                        RegisterController.free_reg(int(re.search(r'[0-5]', reg).group(0)))

                                instr_stack.append(instr1)
                            instr['term'] = instr['opcode'].value
                            code.append(instr)
                            instr_counter += 1

                        if instr['opcode'] is Opcode.MOV:
                            if isinstance(instr['arg2'], int):
                                reg = RegisterController.get_free_reg()
                                add_mov = {'opcode': Opcode.MOV, 'arg1': reg, 'arg2': instr['arg2'],
                                           'term': Opcode.MOV.value}
                                code.append(add_mov)
                                instr_counter += 1
                                instr['arg2'] = reg
                                instr['res_reg'] = reg
                            if 'res_reg' not in instr:
                                instr['res_reg'] = RegisterController.get_free_reg()
                            instr['term'] = instr['opcode'].value
                            code.append(instr)
                            instr_counter += 1

                            if len(instr_stack) > 0:
                                instr1 = instr_stack.pop()
                                if instr1['opcode'] == Opcode.PRINT:
                                    if instr1['arg1'] is None:
                                        instr1['arg1'] = instr['res_reg']
                                    instr1['res_reg'] = instr['res_reg']

                                elif instr1['opcode'] in {Opcode.ADD, Opcode.SUB, Opcode.MUL, Opcode.DEV, Opcode.MOD}:
                                    instr1['args'].append(instr['res_reg'])

                                elif instr1['opcode'] == Opcode.JMP:
                                    reg = instr['res_reg']
                                    RegisterController.free_reg(int(re.search(r'[0-5]', reg).group(0)))

                                instr_stack.append(instr1)

                        if instr['opcode'] in {Opcode.PRINT, Opcode.PRINTC}:
                            arg1 = instr['arg1']
                            if isinstance(arg1, int):
                                reg = RegisterController.get_free_reg()
                                add_mov = {'opcode': Opcode.MOV, 'arg1': reg,
                                           'arg2': arg1, 'term': Opcode.MOV.value}
                                code.append(add_mov)
                                instr_counter += 1
                                instr['arg1'] = reg
                                instr['res_reg'] = reg
                            if 'res_reg' not in instr:
                                instr['res_reg'] = RegisterController.get_free_reg()
                            if len(instr_stack) > 0:
                                instr1 = instr_stack.pop()
                                match instr1['opcode']:

                                    case Opcode.CMP:
                                        if instr1['arg1'] is None:
                                            instr1['arg1'] = instr['res_reg']
                                        elif instr1['arg2'] is None:
                                            instr1['arg2'] = instr['res_reg']
                                        instr1['res_reg'] = instr['res_reg']

                                    case Opcode.MOV:
                                        if instr1['arg2'] is None:
                                            instr1['arg2'] = instr['res_reg']
                                        instr1['res_reg'] = instr['res_reg']

                                    case Opcode.ADD | Opcode.SUB | Opcode.MUL | Opcode.DEV | Opcode.MOD:
                                        instr1['args'].append(instr['res_reg'])

                                    case Opcode.PRINT:
                                        if instr1['arg1'] is None:
                                            instr1['arg1'] = instr['res_reg']
                                        instr1['res_reg'] = instr['res_reg']

                                instr_stack.append(instr1)
                            instr['term'] = instr['opcode'].value
                            code.append(instr)
                            instr_counter += 1

                        if instr['opcode'] is Opcode.PRINTSTR:
                            reg1 = RegisterController.get_free_reg()
                            reg2 = RegisterController.get_free_reg()
                            assert re.fullmatch(r'\[[0-9]+\]', instr['arg1']), "Unexpected arg for printstr"
                            addr = int(re.search(r'[0-9]+', instr['arg1']).group(0))
                            mov_instr1 = {'opcode': Opcode.MOV, 'arg1': reg1, 'arg2': addr, 'term': Opcode.MOV.value}
                            mov_instr2 = {'opcode': Opcode.MOV, 'arg1': reg2, 'arg2': "[" + reg1 + "]",
                                          'term': Opcode.MOV.value}
                            add_instr = {'opcode': Opcode.ADD, 'args': [reg1, 1], 'res_reg': reg1,
                                         'term': Opcode.ADD.value}
                            print_instr = {'opcode': Opcode.PRINTC, 'arg1': reg2, 'term': Opcode.PRINTSTR.value}
                            cmp_instr = {'opcode': Opcode.CMP, 'arg1': reg2, 'arg2': '\0', 'res_reg': reg2,
                                         'term': Opcode.CMP.value}
                            jne_instr = {'opcode': Opcode.JNE, 'arg1': instr_counter + 1, 'term': Opcode.JNE.value}
                            code.append(mov_instr1)
                            code.append(mov_instr2)
                            code.append(add_instr)
                            code.append(print_instr)
                            code.append(cmp_instr)
                            code.append(jne_instr)
                            instr_counter += 6
                            RegisterController.free_reg(int(re.search(r'[0-5]', reg2).group(0)))
                            if len(instr_stack) > 0:
                                instr1 = instr_stack.pop()
                                match instr1['opcode']:

                                    case Opcode.CMP:
                                        if instr1['arg1'] is None:
                                            instr1['arg1'] = cmp_instr['res_reg']
                                        elif instr1['arg2'] is None:
                                            instr1['arg2'] = cmp_instr['res_reg']
                                        instr1['res_reg'] = cmp_instr['res_reg']

                                    case Opcode.MOV:
                                        if instr1['arg2'] is None:
                                            instr1['arg2'] = cmp_instr['res_reg']
                                        instr1['res_reg'] = cmp_instr['res_reg']

                                    case Opcode.ADD | Opcode.SUB | Opcode.MUL | Opcode.DEV | Opcode.MOD:
                                        instr1['args'].append(cmp_instr['res_reg'])

                                    case Opcode.PRINT:
                                        if instr1['arg1'] is None:
                                            instr1['arg1'] = cmp_instr['res_reg']
                                        instr1['res_reg'] = cmp_instr['res_reg']

                                instr_stack.append(instr1)

                        if instr['opcode'] is Opcode.READ:
                            reg = RegisterController.get_free_reg()
                            instr['reg'] = reg
                            instr['res_reg'] = reg
                            if len(instr_stack) > 0:
                                instr1 = instr_stack.pop()
                                match instr1['opcode']:

                                    case Opcode.CMP:
                                        if instr1['arg1'] is None:
                                            instr1['arg1'] = instr['res_reg']
                                        elif instr1['arg2'] is None:
                                            instr1['arg2'] = instr['res_reg']
                                        instr1['res_reg'] = instr['res_reg']

                                    case Opcode.MOV:
                                        if instr1['arg2'] is None:
                                            instr1['arg2'] = instr['res_reg']
                                        instr1['res_reg'] = instr['res_reg']

                                    case Opcode.ADD | Opcode.SUB | Opcode.MUL | Opcode.DEV | Opcode.MOD:
                                        instr1['args'].append(instr['res_reg'])

                                    case Opcode.PRINTC | Opcode.PRINT:
                                        if instr1['arg1'] is None:
                                            instr1['arg1'] = instr['res_reg']
                                        instr1['res_reg'] = instr['res_reg']

                                instr_stack.append(instr1)
                            instr['term'] = instr['opcode'].value
                            code.append(instr)
                            instr_counter += 1

                        if instr['opcode'] is Opcode.CMP:
                            assert terms[pos + 1].word != ")", "Expected then block"
                            arg1 = instr['arg1']
                            arg2 = instr['arg2']
                            if isinstance(arg1, int):
                                reg = RegisterController.get_free_reg()
                                add_mov = {'opcode': Opcode.MOV, 'arg1': reg,
                                           'arg2': arg1, 'term': Opcode.MOV.value}
                                code.append(add_mov)
                                instr_counter += 1
                                instr['arg1'] = reg
                            if isinstance(arg2, int):
                                reg = RegisterController.get_free_reg()
                                add_mov = {'opcode': Opcode.MOV, 'arg1': reg,
                                           'arg2': arg2, 'term': Opcode.MOV.value}
                                code.append(add_mov)
                                instr_counter += 1
                                instr['arg2'] = reg

                            if re.fullmatch(r'r[0-5]', instr['arg1']):
                                RegisterController.free_reg(int(re.search(r'[0-5]', instr['arg1']).group(0)))
                            if re.fullmatch(r'r[0-5]', instr['arg2']):
                                RegisterController.free_reg(int(re.search(r'[0-5]', instr['arg2']).group(0)))

                            reg = RegisterController.get_free_reg()
                            RegisterController.free_reg(int(re.search(r'[0-5]', reg).group(0)))
                            instr['res_reg'] = reg
                            instr['term'] = instr['opcode'].value
                            code.append(instr)
                            instr_counter += 1
                            if len(instr_stack) > 0:
                                instr1 = instr_stack.pop()
                                if_jmp_stack.append([instr_counter, deep])
                                instr1['res_reg'] = reg
                                instr1['term'] = instr1['opcode'].value
                                code.append(instr1)
                                instr_counter += 1
                                if len(instr_stack) > 0:
                                    instr2 = instr_stack.pop()
                                    match instr2['opcode']:

                                        case Opcode.CMP:
                                            if instr2['arg1'] is None:
                                                instr2['arg1'] = instr1['res_reg']
                                            elif instr2['arg2'] is None:
                                                instr2['arg2'] = instr1['res_reg']
                                            instr2['res_reg'] = instr1['res_reg']

                                        case Opcode.MOV:
                                            if instr2['arg2'] is None:
                                                instr2['arg2'] = instr1['res_reg']
                                            instr2['res_reg'] = instr1['res_reg']

                                        case Opcode.ADD | Opcode.SUB | Opcode.MUL | Opcode.DEV | Opcode.MOD:
                                            instr2['args'].append(instr1['res_reg'])

                                        case Opcode.PRINT:
                                            if instr2['arg1'] is None:
                                                instr2['arg1'] = instr1['res_reg']
                                            instr2['res_reg'] = instr1['res_reg']
                                    instr_stack.append(instr2)
                                    instr_stack.append(instr1)
                                else:
                                    instr_stack.append(instr1)
                        else:
                            if len(if_jmp_stack) > 0:
                                if_jmp = if_jmp_stack.pop()
                                if if_jmp[1] == deep:
                                    if code[if_jmp[0] - VARS_SEG_SIZE]['arg1'] is None:
                                        if terms[pos + 1].word == "(":
                                            jmp_instr = {'opcode': Opcode.JMP, 'arg1': None, 'term': Opcode.JMP.value}
                                            jmp_stack.append(instr_counter)
                                            if_jmp_stack.append(if_jmp)
                                            code.append(jmp_instr)
                                            instr_counter += 1
                                            RegisterController.free_reg(
                                                int(re.search(r'[0-5]', instr['res_reg']).group(0)))
                                        code[if_jmp[0] - VARS_SEG_SIZE]['arg1'] = instr_counter
                                    else:
                                        assert terms[pos + 1].word == ")", "Too many blocks in if statement"
                                        jmp_addr = jmp_stack.pop()
                                        code[jmp_addr - VARS_SEG_SIZE]['arg1'] = instr_counter
                                else:
                                    if_jmp_stack.append(if_jmp)

                case "setvar":
                    instr_stack.append({'opcode': Opcode.MOV, 'arg1': None, 'arg2': None})
                case "var":
                    instr_stack.append({'opcode': Opcode.VAR, 'arg1': None, 'arg2': None})
                case "loop":
                    instr_stack.append({'opcode': Opcode.JMP, 'label': None, 'arg1': None})
                    jmp_stack.append([instr_counter, deep])
                case "if":
                    match terms[pos + 2].word:
                        case "=":
                            instr_stack.append({'opcode': Opcode.JNE, 'arg1': None})
                        case "!=":
                            instr_stack.append({'opcode': Opcode.JE, 'arg1': None})
                        case ">":
                            instr_stack.append({'opcode': Opcode.JLE, 'arg1': None})
                        case "<":
                            instr_stack.append({'opcode': Opcode.JGE, 'arg1': None})
                        case _:
                            assert False, "Unexpected operation after if"
                case "=" | "!=" | ">" | "<":
                    instr_stack.append({'opcode': Opcode.CMP, 'arg1': None, 'arg2': None})
                case "%":
                    instr_stack.append({'opcode': Opcode.MOD, 'args': []})
                case "*":
                    instr_stack.append({'opcode': Opcode.MUL, 'args': []})
                case "/":
                    instr_stack.append({'opcode': Opcode.DEV, 'args': []})
                case "-":
                    instr_stack.append({'opcode': Opcode.SUB, 'args': []})
                case "+":
                    instr_stack.append({'opcode': Opcode.ADD, 'args': []})
                case "print":
                    instr_stack.append({'opcode': Opcode.PRINT, 'arg1': None})
                case "printc":
                    instr_stack.append({'opcode': Opcode.PRINTC, 'arg1': None})
                case "printstr":
                    instr_stack.append({'opcode': Opcode.PRINTSTR, 'arg1': None})
                case "return-from":
                    instr_stack.append({'opcode': Opcode.JMPR, 'target_label': None, 'arg1': None})
                case "read":
                    instr_stack.append({'opcode': Opcode.READ, 'reg': None})
                case _:
                    instr = instr_stack.pop()
                    match instr['opcode']:
                        case Opcode.MOV:
                            if instr['arg1'] is None:
                                if re.fullmatch(r'[a-zA-Z]+', term.word):
                                    assert term.word in variables, "Undeclared var"
                                    instr['arg1'] = list(variables).index(term.word)
                                else:
                                    assert False, "Unexpected arg1 for setvar instruction"
                            elif instr['arg2'] is None:
                                if re.fullmatch(r'[a-zA-Z]+', term.word):
                                    assert term.word in variables, "Undeclared var " + term.word
                                    instr['arg2'] = list(variables).index(term.word)
                                elif re.fullmatch(r'(-?[1-9][0-9]*|0)', term.word):
                                    instr['arg2'] = term.word
                            else:
                                assert False, "Too many args for MOV"

                        case Opcode.VAR:
                            if instr['arg1'] is None:
                                assert re.fullmatch(r'[a-zA-Z]+', term.word), "Unexpected arg1 for DEFV instruction"
                                assert term.word not in variables, "Redefinition of " + term.word
                                variables[term.word] = 0
                                instr['arg1'] = term.word
                            elif instr['arg2'] is None:
                                if re.fullmatch(r'(-?[1-9][0-9]*|0)', term.word):
                                    variables[instr['arg1']] = int(term.word)
                                elif re.fullmatch(r"\"[^\"]*\"", term.word):
                                    variables[instr['arg1']] = term.word
                            else:
                                assert False, "Too many args for DEFV"

                        case Opcode.JMP:
                            assert instr['label'] is None and re.fullmatch(r'[a-zA-Z]+', term.word), "Unexpected symbol"
                            instr['label'] = term.word

                        case Opcode.ADD | Opcode.SUB | Opcode.MUL | Opcode.DEV | Opcode.MOD:
                            if re.fullmatch(r'[a-zA-Z]+', term.word):
                                assert term.word in variables, "Undeclared var " + term.word
                                instr['args'].append(list(variables).index(term.word))
                            elif re.fullmatch(r'(-?[1-9][0-9]*|0)', term.word):
                                instr['args'].append(term.word)

                        case Opcode.PRINT | Opcode.PRINTC:
                            assert instr['arg1'] is None, "To many arguments for PRINT"
                            if re.fullmatch(r'[a-zA-Z]+', term.word):
                                assert term.word in variables, "Undeclared var " + term.word
                                instr['arg1'] = list(variables).index(term.word)
                            elif re.fullmatch(r'([1-9][0-9]*|0)', term.word):
                                instr['arg1'] = term.word

                        case Opcode.CMP:
                            if instr['arg1'] is None:
                                if re.fullmatch(r'[a-zA-Z]+', term.word):
                                    assert term.word in variables, "Undeclared var " + term.word
                                    instr['arg1'] = list(variables).index(term.word)
                                elif re.fullmatch(r'(-?[1-9][0-9]*|0)', term.word):
                                    instr['arg1'] = term.word
                            elif instr['arg2'] is None:
                                if re.fullmatch(r'[a-zA-Z]+', term.word):
                                    assert term.word in variables, "Undeclared var " + term.word
                                    instr['arg2'] = list(variables).index(term.word)
                                elif re.fullmatch(r'(-?[1-9][0-9]*|0)', term.word):
                                    instr['arg2'] = term.word
                            else:
                                assert False, "Too many args for CMP"

                        case Opcode.JMPR:
                            assert instr['target_label'] is None, "Unexpected symbol"
                            assert re.fullmatch(r'[a-zA-Z]+', term.word), "Unexpected arg"
                            instr['target_label'] = term.word

                        case Opcode.PRINTSTR:
                            assert instr['arg1'] is None, "Too many args for printstr"
                            assert re.fullmatch(r"\"[^\"]*\"", term.word), "Unexpected arg"
                            if term.word not in variables:
                                addr = VARS_SEG_SIZE - STR_SEG_SIZE
                                for i in strings:
                                    addr += len(i)
                                # strings.append(re.search(r'[^\"]+', term.word).group(0))

                                handledStr = re.sub(r'["\x00]+$','',term.word.strip('"'))

                                strings.append(handledStr)
                                print("SS", len(handledStr))
                                variables[term.word] = addr
                            instr['arg1'] = '[' + str(list(variables).index(term.word)) + ']'
                    instr_stack.append(instr)
        code.append({'opcode': Opcode.HLT, 'term': Opcode.HLT.value})

        data = {'data': {}}
        vals = list(variables.values())
        for i, _ in enumerate(vals):
            data['data'][i] = vals[i]
        for i in strings:
            # Pascal string
            count = 0
            length = len(i)
            hex_string = hex(length)
            data['data'][VARS_SEG_SIZE - STR_SEG_SIZE + count] = hex_string

            count = 1

            for j in i:
                data['data'][VARS_SEG_SIZE - STR_SEG_SIZE + count] = j
                count += 1
        code.append(data)
        return code


def main(args):
    assert len(args) == 2, "Wrong arguments: translator.py <input_file> <target_file>"
    source, target = args

    with open(source, "rt", encoding="utf-8") as file:
        source = file.read()

    translator = Translator(source)
    code = translator.translate_into_opcode()
    print("source LoC:", len(source.split()), "code instr:", len(code) - 1)
    write_code(target, code)


if __name__ == '__main__':
    main(sys.argv[1:])
