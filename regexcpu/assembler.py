"""COA - two-pass assembler and the DFA -> assembly code generator.

Syntax   label:  MNEMONIC op1, op2 [, op3]   ; comment        .word v1, v2, ...
Operands registers R0-R7, decimal / hex integers, or labels (resolved to addresses).
"""
import re
from dataclasses import dataclass
from .cpu import OPCODES, OPERANDS, encode, MEM_WORDS


class AssemblerError(ValueError):
    pass


@dataclass
class Program:
    words: list
    listing: list          # (address, word, source line)
    labels: dict
    code_words: int
    data_words: int
    source: str


_LABEL = re.compile(r"^\s*([A-Za-z_]\w*)\s*:\s*(.*)$")


def _parse_lines(source):
    items = []
    for lineno, raw in enumerate(source.splitlines(), 1):
        line = raw.split(";")[0].rstrip()
        label = None
        m = _LABEL.match(line)
        if m:
            label, line = m.group(1), m.group(2).strip()
        else:
            line = line.strip()
        items.append((lineno, raw.rstrip(), label, line))
    return items


def assemble(source: str) -> Program:
    items = _parse_lines(source)
    labels, addr = {}, 0
    # pass 1: addresses
    for lineno, raw, label, line in items:
        if label:
            if label in labels:
                raise AssemblerError(f"line {lineno}: duplicate label {label!r}")
            labels[label] = addr
        if not line:
            continue
        head = line.split(None, 1)
        if head[0].lower() == ".word":
            addr += len([x for x in head[1].split(",") if x.strip()]) if len(head) > 1 else 0
        else:
            addr += 1
    if addr > MEM_WORDS:
        raise AssemblerError("program too large for CPU memory")

    def value(tok, lineno):
        tok = tok.strip()
        if tok in labels:
            return labels[tok]
        try:
            return int(tok, 0)
        except ValueError:
            raise AssemblerError(f"line {lineno}: unknown operand {tok!r}")

    words, listing, code_words = [], [], 0
    first_data = None
    # pass 2: encode
    for lineno, raw, label, line in items:
        if not line:
            continue
        head = line.split(None, 1)
        mnem = head[0].upper()
        ops = [o.strip() for o in head[1].split(",")] if len(head) > 1 else []
        if head[0].lower() == ".word":
            if first_data is None:
                first_data = len(words)
            for tok in ops:
                if tok:
                    listing.append((len(words), value(tok, lineno), raw))
                    words.append(value(tok, lineno))
            continue
        if mnem not in OPCODES:
            raise AssemblerError(f"line {lineno}: unknown mnemonic {head[0]!r}")
        pattern = OPERANDS[mnem]
        if len(ops) != len(pattern):
            raise AssemblerError(f"line {lineno}: {mnem} expects {len(pattern)} operand(s)")
        rd = rs = imm = 0
        for kind, tok in zip(pattern, ops):
            if kind in "rs":
                m = re.fullmatch(r"[Rr]([0-7])", tok)
                if not m:
                    raise AssemblerError(f"line {lineno}: expected register, got {tok!r}")
                if kind == "r":
                    rd = int(m.group(1))
                else:
                    rs = int(m.group(1))
            else:
                imm = value(tok, lineno)
        word = encode(mnem, rd, rs, imm)
        listing.append((len(words), word, raw))
        words.append(word)
        code_words += 1
    return Program(words, listing, labels, code_words, len(words) - code_words, source)


def dfa_to_assembly(dfa, title="") -> str:
    """Generate the table-driven matcher program for a (trimmed) DFA.

    R0 = current state, R1 = input symbol class, R2 = table index, R3 = accept flag.
    The transition table lives in data memory; a missing transition is stored as -1.
    """
    from .dfa import to_table
    table, accept = to_table(dfa)
    k = len(dfa.alphabet)
    lines = [
        f"; ---- DFA matcher {('for ' + title) if title else ''}".rstrip(),
        f"; alphabet = {dfa.alphabet}   states = {dfa.n}   K = {k}",
        f"        LDI   R0, {dfa.start}        ; R0 = start state",
        "loop:   IN    R1               ; R1 = next symbol class (-1 end, -2 unknown)",
        "        CMPI  R1, -1",
        "        JEQ   done             ; end of input",
        "        JLT   reject           ; symbol not in alphabet",
        "        MOV   R2, R0",
        f"        MULI  R2, {k}               ; R2 = state * K",
        "        ADD   R2, R1           ; R2 = state * K + symbol",
        "        LDX   R0, R2, table    ; indexed addressing: R0 = M[R2 + table]",
        "        CMPI  R0, -1",
        "        JEQ   reject           ; dead transition",
        "        JMP   loop",
        "done:   LDX   R3, R0, accept   ; R3 = accept[state]",
        "        CMPI  R3, 1",
        "        JEQ   yes",
        "reject: REJECT",
        "yes:    ACCEPT",
    ]
    if table:
        for i in range(0, len(table), 16):
            lines.append(("table:  " if i == 0 else "        ") + ".word " + ", ".join(map(str, table[i:i + 16])))
    else:
        lines.append("table:  .word 0")
    lines.append("accept: .word " + ", ".join(map(str, accept)))
    return "\n".join(lines) + "\n"
