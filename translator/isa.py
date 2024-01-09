"""
Типы данных для представления и сериализации/десериализации машинного кода.

Особенности:

- Машинный код сериализуется в список JSON.
- Один элемент списка -- одна инструкция.
- Индекс списка -- адрес инструкции.
"""
import json
from collections import namedtuple
from enum import Enum


class Opcode(str, Enum):
    """Opcode для ISA."""

    VAR = "var"
    JMP = "jmp"
    JMPR = "jmpr"
    HLT = "hlt"
    JNE = "jne"
    JE = "je"
    CMP = "cmp"
    PRINTINT = "printint"
    NOP = "nop"
    READ = "read"
    PRINTSTR = "printstr"
    JLE = "jle"
    JGE = "jge"
    PRINTC = "printc"
    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DEV = "dev"
    MOD = "mod"
    MOV = "mov"
class Term(namedtuple('Term', 'pos word')):
    """Описание выражения из исходного текста программы."""
    # сделано через класс, чтобы был docstring


def write_code(filename, code):
    """Записать машинный код в файл."""
    with open(filename, "w", encoding="utf-8") as file:
        file.write(json.dumps(code, indent=4))


def read_code(filename):
    """Прочесть машинный код из файла."""
    with open(filename, encoding="utf-8") as file:
        code = json.loads(file.read())
    return code
