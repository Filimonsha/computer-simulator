REGS_COUNT = 6
VARS_SEG_SIZE = 100
STR_SEG_SIZE = 50


class RegisterController:
    regs = []

    @staticmethod
    def init_regs():

        for _ in range(0, REGS_COUNT):
            RegisterController.regs.append(True)
        return RegisterController.regs

    @staticmethod
    def get_free_reg():
        for pos, reg in enumerate(RegisterController.regs):
            if reg:
                RegisterController.regs[pos] = False
                return "r" + str(pos)
        assert False, "All regs are busy"

    @staticmethod
    def free_reg( reg_number):
        RegisterController.regs[reg_number] = True
