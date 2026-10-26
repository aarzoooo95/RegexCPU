"""COA (Module 2.1 / 2.3) - a small Von-Neumann CPU that models the INSTRUCTION CYCLE.

Registers : R0-R7 (general), PC, MAR, MDR, IR, flags Z and N
Memory    : 32768 words, instructions and data share one address space (Von Neumann)
Word      : 32-bit instruction  =  | opcode 8 | rd 4 | rs 4 | imm/addr 16 (signed) |

Addressing modes demonstrated
    immediate  LDI R0, 5          direct     LD  R1, 100
    register   MOV R2, R0         indexed    LDX R0, R2, table   (EA = R2 + table)

Instruction cycle (one call of CPU.step)
    T0 MAR <- PC                  T1 MDR <- M[MAR] ; PC <- PC + 1     T2 IR <- MDR
    T3 decode                     T4 execute (ALU / branch)           T5 memory access (LD/LDX/ST)
Cycle cost: fetch 3 + decode 1 + execute 1 = 5, +1 for a memory operand, +2 for multiply.
"""
from dataclasses import dataclass, field

MEM_WORDS = 32768
NUM_REGS = 8
MASK32 = 0xFFFFFFFF

OPCODES = {
    "NOP": 0, "LDI": 1, "LD": 2, "LDX": 3, "ST": 4, "MOV": 5, "ADD": 6, "ADDI": 7,
    "MUL": 8, "MULI": 9, "CMP": 10, "CMPI": 11, "JMP": 12, "JEQ": 13, "JNE": 14,
    "JLT": 15, "IN": 16, "ACCEPT": 17, "REJECT": 18, "HLT": 19,
}
MNEMONIC = {v: k for k, v in OPCODES.items()}

# operand pattern of each instruction: r = rd, s = rs, i = imm/addr
OPERANDS = {
    "NOP": "", "LDI": "ri", "LD": "ri", "LDX": "rsi", "ST": "si", "MOV": "rs",
    "ADD": "rs", "ADDI": "ri", "MUL": "rs", "MULI": "ri", "CMP": "rs", "CMPI": "ri",
    "JMP": "i", "JEQ": "i", "JNE": "i", "JLT": "i", "IN": "r", "ACCEPT": "",
    "REJECT": "", "HLT": "",
}
ADDRESSING = {"LDI": "immediate", "LD": "direct", "LDX": "indexed", "MOV": "register",
              "ST": "direct", "ADD": "register", "ADDI": "immediate", "MUL": "register",
              "MULI": "immediate", "CMP": "register", "CMPI": "immediate"}
CYCLES = {name: 5 for name in OPCODES}
for _m in ("LD", "LDX", "ST"):
    CYCLES[_m] = 6
for _m in ("MUL", "MULI"):
    CYCLES[_m] = 7


class CPUError(RuntimeError):
    """Illegal instruction, bad memory access or cycle-limit exceeded."""


def to_signed32(x: int) -> int:
    x &= MASK32
    return x - (1 << 32) if x & 0x80000000 else x


def encode(op: str, rd: int = 0, rs: int = 0, imm: int = 0) -> int:
    if not -32768 <= imm <= 32767:
        raise CPUError(f"immediate/address {imm} does not fit in 16 bits")
    return (OPCODES[op] << 24) | (rd << 20) | (rs << 16) | (imm & 0xFFFF)


def decode(word: int):
    op = (word >> 24) & 0xFF
    rd, rs = (word >> 20) & 0xF, (word >> 16) & 0xF
    imm = word & 0xFFFF
    if imm & 0x8000:
        imm -= 0x10000
    return op, rd, rs, imm


def disassemble(word: int) -> str:
    op, rd, rs, imm = decode(word)
    if op not in MNEMONIC:
        return f".word {word}"
    name = MNEMONIC[op]
    parts = []
    for c in OPERANDS[name]:
        parts.append({"r": f"R{rd}", "s": f"R{rs}", "i": str(imm)}[c])
    return f"{name:<6}{', '.join(parts)}".rstrip()


@dataclass
class RunResult:
    status: str                      # ACCEPT | REJECT | HALT | TIMEOUT
    cycles: int
    instructions: int
    trace: list = field(default_factory=list)
    mix: dict = field(default_factory=dict)

    @property
    def cpi(self):
        return self.cycles / self.instructions if self.instructions else 0.0


class CPU:
    def __init__(self, mem_words: int = MEM_WORDS):
        self.mem_words = mem_words
        self.reset()

    # ---- state ------------------------------------------------------------------
    def reset(self):
        self.mem = [0] * self.mem_words
        self.regs = [0] * NUM_REGS
        self.pc = self.mar = self.mdr = self.ir = 0
        self.z = self.n = False
        self.cycles = self.instructions = 0
        self.halted, self.status = False, None
        self.inp, self.inp_pos = [], 0
        self.mix = {}

    def load(self, words, base: int = 0):
        if base + len(words) > self.mem_words:
            raise CPUError(f"program of {len(words)} words does not fit in {self.mem_words}-word memory")
        self.mem[base:base + len(words)] = words

    def set_input(self, symbols):
        self.inp, self.inp_pos = list(symbols), 0

    def _read(self, addr: int) -> int:
        if not 0 <= addr < self.mem_words:
            raise CPUError(f"memory read out of range: {addr}")
        return self.mem[addr]

    # ---- one full instruction cycle ---------------------------------------------
    def step(self, trace: bool = False):
        if self.halted:
            raise CPUError("CPU is halted")
        micro = []
        pc0 = self.pc
        # FETCH
        self.mar = self.pc
        self.mdr = self._read(self.mar)
        self.pc += 1
        self.ir = self.mdr
        if trace:
            micro += [f"T0  MAR <- PC            (MAR = {pc0})",
                      f"T1  MDR <- M[MAR]; PC++  (MDR = {self.mdr:#010x}, PC = {self.pc})",
                      f"T2  IR  <- MDR"]
        # DECODE
        op, rd, rs, imm = decode(self.ir)
        if op not in MNEMONIC:
            raise CPUError(f"illegal opcode {op} at PC={pc0}")
        name = MNEMONIC[op]
        if trace:
            micro.append(f"T3  DECODE  opcode={name} rd=R{rd} rs=R{rs} imm={imm}"
                         + (f"  [{ADDRESSING[name]} addressing]" if name in ADDRESSING else ""))
        # EXECUTE (+ memory access / write-back)
        R = self.regs
        if name == "NOP":
            detail = "no operation"
        elif name == "LDI":
            R[rd] = imm
            detail = f"R{rd} <- {imm}"
        elif name == "LD":
            self.mar = imm
            self.mdr = self._read(self.mar)
            R[rd] = to_signed32(self.mdr)
            detail = f"MAR <- {imm}; MDR <- M[{imm}]; R{rd} <- {R[rd]}"
        elif name == "LDX":
            ea = R[rs] + imm
            self.mar = ea
            self.mdr = self._read(ea)
            R[rd] = to_signed32(self.mdr)
            detail = f"EA = R{rs}({R[rs] if rs != rd else '..'}) + {imm} = {ea}; R{rd} <- M[{ea}] = {R[rd]}"
        elif name == "ST":
            ea = imm
            if not 0 <= ea < self.mem_words:
                raise CPUError(f"memory write out of range: {ea}")
            self.mem[ea] = R[rs]
            detail = f"M[{ea}] <- R{rs} ({R[rs]})"
        elif name == "MOV":
            R[rd] = R[rs]
            detail = f"R{rd} <- R{rs} ({R[rs]})"
        elif name in ("ADD", "ADDI"):
            b = R[rs] if name == "ADD" else imm
            R[rd] = to_signed32(R[rd] + b)
            detail = f"R{rd} <- R{rd} + {b} = {R[rd]}"
        elif name in ("MUL", "MULI"):
            b = R[rs] if name == "MUL" else imm
            R[rd] = to_signed32(R[rd] * b)
            detail = f"R{rd} <- R{rd} * {b} = {R[rd]}"
        elif name in ("CMP", "CMPI"):
            b = R[rs] if name == "CMP" else imm
            diff = R[rd] - b
            self.z, self.n = diff == 0, diff < 0
            detail = f"R{rd}({R[rd]}) - {b} -> Z={int(self.z)} N={int(self.n)}"
        elif name == "JMP":
            self.pc = imm
            detail = f"PC <- {imm}"
        elif name in ("JEQ", "JNE", "JLT"):
            taken = {"JEQ": self.z, "JNE": not self.z, "JLT": self.n}[name]
            if taken:
                self.pc = imm
            detail = f"{'taken' if taken else 'not taken'}: PC = {self.pc}"
        elif name == "IN":
            if self.inp_pos < len(self.inp):
                R[rd] = self.inp[self.inp_pos]
                self.inp_pos += 1
            else:
                R[rd] = -1
            detail = f"R{rd} <- input symbol {R[rd]}"
        elif name in ("ACCEPT", "REJECT", "HLT"):
            self.halted = True
            self.status = name if name != "HLT" else "HALT"
            detail = f"halt, status = {self.status}"
        cost = CYCLES[name]
        self.cycles += cost
        self.instructions += 1
        self.mix[name] = self.mix.get(name, 0) + 1
        if not trace:
            return None
        micro.append(f"T4  EXECUTE {detail}")
        if name in ("LD", "LDX", "ST"):
            micro.append("T5  MEMORY ACCESS completed")
        return {
            "pc": pc0, "word": self.ir, "asm": disassemble(self.ir), "micro": micro,
            "regs": list(self.regs), "z": int(self.z), "n": int(self.n),
            "cost": cost, "cycles": self.cycles,
        }

    def run(self, symbols=(), max_cycles: int = 5_000_000, trace: bool = False,
            trace_limit: int = 100_000) -> RunResult:
        self.set_input(symbols)
        self.pc, self.halted, self.status = 0, False, None
        self.cycles = self.instructions = 0
        self.mix = {}
        log = []
        while not self.halted:
            if self.cycles > max_cycles:
                return RunResult("TIMEOUT", self.cycles, self.instructions, log, dict(self.mix))
            rec = self.step(trace=trace)
            if rec is not None and len(log) < trace_limit:
                log.append(rec)
        return RunResult(self.status, self.cycles, self.instructions, log, dict(self.mix))
