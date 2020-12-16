import cmd, sys
from unicorn import *
from keystone import Ks, KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN, KsError
from _const import *
from _isa import *

BASE_ADR = 0x1000
MEM_SIZE = 128

class Shell(cmd.Cmd):
    intro = 'Welcome to the Armv8-A A64 shell. Type help or ? to list commands.\n'
    prompt = '(A64) '
    file = None
    # Initiate Unicorn emulation
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    uc.mem_map(BASE_ADR, MEM_SIZE**2)
    uc.reg_write(REGISTERS["PC"], BASE_ADR + 4)

    # ------- instructions -------
    def default(self, line):
        cmd, arg, line = self.parseline(line)
        if cmd.upper() in ISA_SMID.keys() or cmd.upper() in ISA_BASE.keys():
            # Save environment
            regs = read_registers(self.uc)
            mem = self.uc.mem_read(BASE_ADR, MEM_SIZE)
            # Run instruction
            run(self.uc, line)
            # Check for changes
            diff_registers(self.uc, regs)
            diff_memory(self.uc, mem)
        elif cmd.upper() in REGISTERS.keys():
            arg = arg.strip(", ")
            if arg.lower() in ["", "x", "hex", "hexadecimal"]:
                print(F"{cmd}: 0x{self.uc.reg_read(REGISTERS[cmd.upper()]):x}")
            elif arg.lower() in ["d", "dec", "decimal"]:
                print(F"{cmd}: {self.uc.reg_read(REGISTERS[cmd.upper()]):d}")
            elif arg.lower() in ["b", "bin", "binary"]:
                print(F"{cmd}: {self.uc.reg_read(REGISTERS[cmd.upper()]):04b}")
            else:
                print(F"Unknown argument '{arg}'")
        elif cmd.upper() in BRANCHES:
            print("Branching instructions are not supported")
        elif line.endswith(":"):
            print("Labels are not supported")
        elif line.startswith("."):
            print("Directives are not supported")
        else:
            print(F"Unknown command or instruction '{cmd}'")

    # ------- commands -------
    def do_overvieuw(self, arg):
        'Show X0-X7, W0-W7 and 128 bytes of memory'
        uc = self.uc
        mem = uc.mem_read(BASE_ADR, 128)
        b = [mem[i:i+4].hex().upper() for i in range(0, 128, 4)]
        print("╔══════╡64-BIT REG╞══════╦══╡32-BIT REG╞══╦══════════════════╡MEMORY╞══════════════════╗")
        for i, j in zip(range(8), range(0, 32, 4)):
            print(F"║ X{i}: 0x{uc.reg_read(REGISTERS['X'+str(i)]):016x} ║" +
                  F" W{i}: 0x{uc.reg_read(REGISTERS['W'+str(i)]):08x} ║", end="")
            print(F" 0x{(BASE_ADR+j*4):x} {b[j]} {b[j+1]} {b[j+2]} {b[j+3]} ║")
        print("╚════════════════════════╩════════════════╩════════════════════════════════════════════╝")

    def do_write(self, arg):
        'Directly write to memory or registers'
        args = arg.replace(",", "").split(" ")
        if len(args) == 2:
            if not valid_number(args[1]):
                print("Invalid value")
            elif args[0].upper() in REGISTERS.keys():
                regs = read_registers(self.uc)
                value = int(args[1], 0)
                # Write value to register
                try:
                    self.uc.reg_write(REGISTERS[args[0].upper()], value)
                except UcError as ue:
                    print(ue)
                diff_registers(self.uc, regs)
            elif valid_number(args[0]):
                mem = self.uc.mem_read(BASE_ADR, MEM_SIZE)
                address = int(args[0].strip("[]"), 16)
                # Get Bytes
                if args[1].startswith("0x"):
                    args[1] += "0" if len(args[1])%2 != 0 else ""
                    value = bytes.fromhex(args[1][2:])
                else:
                    value = int(args[1], 0)
                    value = value.to_bytes((value.bit_length() + 7) // 8, 'big')
                # Write bytes to adress
                try:
                    self.uc.mem_write(address, value)
                except UcError as ue:
                    print(ue)
                diff_memory(self.uc, mem)
            else:
                print(F"'{args[0]}' is not recognized as a register or memory adress")

        else:
            print("Invalid arguments")

    def do_info(self, arg):
        'Display info about an instruction'
        if arg.upper() in ISA_BASE.keys():
            padding = max([len(i[1]) for i in ISA_BASE[arg.upper()]]) + len(arg) + 2
            width = max([len(i[0]) for i in ISA_BASE[arg.upper()]]) + 1
            print(" -- Base Instructions --")
            print("╔"+("═"*padding)+"═╦═"+("═"*width)+"╗")
            for i in ISA_BASE[arg.upper()]:
                print(F"║ {arg.upper()+' '+i[1]+' ': <{padding}}║ {i[0]: <{width}}║")
            print("╚"+("═"*padding)+"═╩═"+("═"*width)+"╝")
        if arg.upper() in ISA_SMID.keys():
            padding = max([len(i[1]) for i in ISA_SMID[arg.upper()]]) + len(arg) + 2
            width = max([len(i[0]) for i in ISA_SMID[arg.upper()]]) + 1
            print( " -- SIMD and Floating-point Instructions --")
            print("╔"+("═"*padding)+"═╦═"+("═"*width)+"╗")
            for i in ISA_SMID[arg.upper()]:
                print(F"║ {arg.upper()+' '+i[1]+' ': <{padding}}║ {i[0]: <{width}}║")
            print("╚"+("═"*padding)+"═╩═"+("═"*width)+"╝")
        if arg.upper() not in ISA_BASE.keys() and arg.upper() not in ISA_SMID.keys():
            print(F"Instruction '{arg}' not found.")

    def do_exit(self, arg):
        'Exit the program'
        return True

# ------- functions  -------

def run(uc, inp):
    try:
        ks = Ks(KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN)
        bytecode, _ = ks.asm(inp)
        uc.mem_write(BASE_ADR, bytes(bytecode))
        uc.emu_start(BASE_ADR, BASE_ADR + 4, 0, 1)
    except KsError as ke:
        print(ke)
    except UcError as ue:
        print(ue)
    except:
        print("Assemler error")

def read_registers(uc):
    regs = {}
    for i in REGISTERS.keys():
        regs[i] = uc.reg_read(REGISTERS[i])
    return(regs)

def diff_registers(uc, regs):
    new_regs = read_registers(uc)
    width = {"X":16, "W":8, "Q":32, "D":16, "S":8, "H":4, "B":2}
    for key in regs.keys():
        if new_regs[key] != regs[key]:
            w = width[key[0]] if not key.isalpha() else 8
            print(F"{key}: 0x{new_regs[key]:0{w}x}")

def diff_memory(uc, mem):
    new_mem = uc.mem_read(BASE_ADR, MEM_SIZE)
    b = [mem[i:i+4].hex().upper() for i in range(0, MEM_SIZE, 4)]
    n_b = [new_mem[i:i+4].hex().upper() for i in range(0, MEM_SIZE, 4)]
    for i in range(4, 32):
        if b[i] != n_b[i]:
            print(F"0x{(BASE_ADR+i*4):x} {n_b[i]} ")

def valid_number(num):
    try: int(num, 0)
    except: return False
    else: return True

if __name__ == '__main__':
    Shell().cmdloop()
