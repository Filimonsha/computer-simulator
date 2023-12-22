CSA Lab 3
Семенов Алексей P33102
## Вариант  
`lisp | risc | neum | hw | instr | struct | stream | port | prob5`  
## Язык программирования  
### Синтаксис  
    s-expr ::= list | s-expr s-expr  
    list ::= "(" function args")"  
    args ::=  word | number | list 
    function ::= math_operation | operation
    math_operation ::= "!=" | "*" | "+" | "-" | "/" | "%" | "=" | > | < 
    operation ::= var | setvar | loop | if | return-from | print | printstr | printc
    letter ::= "a" | "b" | ... | "z" | "A" | ... | "Z"
    word ::= letter | letter word
    digit ::= "1" | "2" | ... | "9" | "0"
    number ::= digit | digit number
* `var arg1 arg2` - объявляет переменную `arg1` и присваивает ей начальное значение `arg2`
* `setvar arg1 arg2` - присваивает объявленной переменной `arg1` новое значение `arg2`
* `loop <label>` - бесконечный цикл, может иметь свою метку `<label>` (опционально) 
* `return-from <target-label>` - безусловный переход на следующее выражение после выражения, на которое указывает целевая метка `<target-label>`
* `if (cond) (then block) (else block)` - оператор ветвления (else block - опционально)
* `+ | - | * | / | % arg1 arg2...<argn>` - арифметические операции над аргументами, минимальное кол-во аргументов: 2
* `!= | = | < | > arg1 arg2`- операторы сравнения, принимают два аргумента
* `printint arg` - вывод целого числа
* `printc arg` - вывод символа
* `printstr arg` - вывод строки
* Типы данных - целочисленные переменные, строки, константы
