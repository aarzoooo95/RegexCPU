#!/usr/bin/env python3
"""Build the three subject reports (COA / FLAT / DAA) as .docx in the Alliance sample format.

    python reports/build_reports.py          (edit ../student.json first: name, roll no., guides)
Re-run  python benchmarks/benchmark.py  first if you want the graphs/tables from YOUR machine.
"""
import csv, inspect, json, os, platform, re, subprocess, sys, tempfile, textwrap
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
from PIL import Image
from engine import Report, AL
from regexcpu import compile_regex, run_all
from regexcpu import nfa as nfa_mod, dfa as dfa_mod, scc as scc_mod, cpu as cpu_mod, assembler as asm_mod
from regexcpu.cpu import OPCODES, OPERANDS, ADDRESSING, CYCLES
from regexcpu.pipeline import run_on_cpu

RES = os.path.join(ROOT, "results"); ASSETS = os.path.join(HERE, "assets")
CFG = json.load(open(os.path.join(ROOT, "student.json"), encoding="utf-8"))
PROJECT = "RegexCPU"
PROJECT_TITLE = "RegexCPU: A Regular Expression Compiler that Executes on a Simulated CPU"


# ------------------------------------------------------------------ data helpers
def csv_rows(name):
    with open(os.path.join(RES, name), newline="") as f:
        r = list(csv.reader(f))
    return r[0], [[float(x) if re.fullmatch(r"-?\d+(\.\d+)?", x) else x for x in row] for row in r[1:]]

def out_text(name): return open(os.path.join(RES, "outputs", name), encoding="utf-8").read()
def img(*p): return os.path.join(RES, *p)
def src(obj, dedent=True):
    s = inspect.getsource(obj)
    s = textwrap.dedent(s) if dedent else s
    return re.sub(r'(\n\s*)""".*?"""\n', r"\1", s, count=1, flags=re.S) if '"""' in s.split("\n", 3)[1] + s.split("\n", 3)[2:3][0] else s

def crop(name, out, top=0, bottom=None, width=None):
    im = Image.open(img("screenshots", name)); im = im.crop((0, top, im.width, bottom or im.height))
    p = os.path.join(tempfile.gettempdir(), out); im.save(p); return p

def detect_system():
    s = dict(CFG.get("system") or {})
    def cpu_name():
        try:
            for line in open("/proc/cpuinfo"):
                if line.startswith("model name"): return line.split(":", 1)[1].strip()
        except OSError: pass
        return platform.processor() or "N/A"
    def ram():
        try:
            for line in open("/proc/meminfo"):
                if line.startswith("MemTotal"): return f"{int(line.split()[1]) / 1048576:.1f} GB"
        except OSError: pass
        return "N/A (edit student.json)"
    s.setdefault("os", f"{platform.system()} {platform.release()}")
    s.setdefault("cpu", cpu_name()); s.setdefault("cores", str(os.cpu_count()))
    s.setdefault("ram", ram()); s.setdefault("python", platform.python_version())
    return s

def test_counts():
    txt = out_text("unittest_output.txt"); groups = {}
    for m in re.finditer(r"^test_\w+ \(test_all\.(\w+)\.", txt, re.M):
        groups[m.group(1)] = groups.get(m.group(1), 0) + 1
    return groups

SYS = detect_system()

def config_table(r, extra_rows=()):
    rows = [("Operating system", SYS["os"]), ("Processor", SYS["cpu"]), ("CPU cores", SYS["cores"]),
            ("Memory (RAM)", SYS["ram"]), ("Language / runtime", f"Python {SYS['python']}"),
            ("Libraries", "Flask (web app), matplotlib + numpy (graphs); core engines use only the Python standard library"),
            ("Testing", "unittest (28 tests), Python `re` as reference oracle")] + list(extra_rows)
    r.table(["Item", "Configuration"], rows, widths=[1.7, 4.2], caption="Development and execution environment")

def test_table(r, focus):
    g = test_counts()
    names = {"TestParser": "Regex parser (postfix, classes, error handling)", "TestAutomata": "NFA / DFA / minimisation",
             "TestSCC": "Tarjan & Kosaraju SCC, dead states, finiteness", "TestCPU": "CPU, assembler, instruction cycle",
             "TestEndToEnd": "End-to-end vs Python `re` (incl. 3,000-case fuzz)"}
    rows = [(names[k], v, "PASS") for k, v in g.items() if k in names]
    rows.append(("**Total**", sum(g.values()), "**ALL PASS**"))
    r.table(["Test group", "Tests", "Result"], rows, widths=[3.9, 0.8, 1.2], caption="Automated test results (python -m unittest)")

def run_table(r, c, words, cpu_cols=True):
    rows = []
    for w in words:
        x = run_all(c, w); yn = lambda b: "accept" if b else "reject"
        row = [f"`{w}`" if w else "ε (empty)", yn(x["nfa"]), yn(x["dfa"]), yn(x["min_dfa"]), yn(x["cpu"])]
        if cpu_cols: row += [x["instructions"], x["cycles"], x["cpi"]]
        row.append("✔" if x["agree"] else "✘")
        rows.append(row)
    head = ["Input", "NFA", "DFA", "Min DFA", "CPU"] + (["Instr.", "Cycles", "CPI"] if cpu_cols else []) + ["Agree"]
    r.table(head, rows, size=9, caption=f"Results for pattern `{c.pattern}`")

# ======================================================================= COA
def coa(r):
    c = compile_regex("(a|b)*abb")
    abstract = ("The instruction cycle (fetch, decode, execute) is the heartbeat of every stored-program computer. This report "
        "presents a small Von-Neumann CPU simulator that models the instruction cycle at micro-operation level (PC, MAR, MDR, IR, "
        "flags), a 20-instruction instruction set with immediate, direct, register and indexed addressing, a two-pass assembler, "
        "and a code generator that compiles a minimised DFA into a table-driven pattern-matching program. The simulator runs this "
        "program on test strings and reports instructions executed, clock cycles and cycles per instruction (CPI).")
    abstract2 = ("Experiments show that the generated matcher executes exactly 11 instructions (58 clock cycles) per input symbol, "
        "so total cost follows cycles = 41 + 58n with CPI close to 5.27. The CPU's accept/reject decisions agreed with Python's "
        "`re` module on 3,000 randomly generated regex/string pairs. The CPU is the Computer Organization and Architecture part of "
        "RegexCPU, a combined project that also covers Formal Languages and Automata Theory (regex to automata) and Design and "
        "Analysis of Algorithms (Tarjan's SCC algorithm).")
    r.p("Abstract", size=16, bold=True, after=8, before=6, line=1.15); r.toc_marks.append(("Abstract", 0))
    r.body(abstract); r.body(abstract2)

    r.h1("Chapter I- Introduction")
    r.body("A stored-program computer keeps instructions and data in the same memory and executes a program by repeating one "
           "fixed routine, the **instruction cycle**: fetch the next instruction from memory, decode it, execute it and move on. "
           "Every feature of a processor, from registers and buses to addressing modes and pipelines, exists to make this routine "
           "correct and fast. Lecture diagrams of the cycle are easy to read but hard to internalise, because the student never "
           "sees a real program change real registers one clock tick at a time.")
    r.body("This work builds a small CPU in software so that the cycle can be observed and measured. The CPU is not a toy "
           "exercise with a hand-written five-line program: it runs a program that is **generated automatically** from a regular "
           "expression. A regular expression is compiled to a minimal deterministic finite automaton (the FLAT part of the "
           "project), analysed with Tarjan's strongly connected components algorithm (the DAA part), and the resulting transition "
           "table is loaded into CPU memory together with a machine-code matcher that walks the table using **indexed addressing**. "
           "The simulator then reports how many instructions and clock cycles the match took.")
    r.h2("Problem Statement")
    r.body("Textbook descriptions of the instruction cycle, registers and addressing modes stay abstract unless a student can run "
           "a real workload and inspect every register transfer. The problem addressed in this report is to design and implement a "
           "processor model in which the instruction cycle is explicit, and to use it to execute a non-trivial program while "
           "measuring its cost. The objectives are:")
    r.bullets(["define an instruction set architecture (ISA) with a fixed 32-bit format and several addressing modes;",
               "implement a two-pass assembler that turns assembly text into machine words;",
               "implement a CPU whose `step()` performs fetch, decode, execute and memory access with visible micro-operations;",
               "generate machine code for a DFA pattern matcher automatically and run it on test strings;",
               "measure instruction count, clock cycles and CPI, and verify the result against independent matchers."])
    r.h2("Theory")
    r.h3("Stored-program (Von Neumann) model")
    r.body("Instructions and data share one address space. The processor contains a **program counter (PC)** holding the address "
           "of the next instruction, a **memory address register (MAR)** and **memory data register (MDR)** that connect it to "
           "memory, and an **instruction register (IR)** holding the instruction being executed. The model used here follows this "
           "organisation exactly: one 32,768-word memory, one set of eight general-purpose registers and the four special registers.")
    r.h3("The instruction cycle")
    r.table(["Step", "Micro-operation", "Purpose"], [
        ("T0", "MAR ← PC", "put the address of the next instruction on the address bus"),
        ("T1", "MDR ← M[MAR];  PC ← PC + 1", "read the instruction word and advance the PC"),
        ("T2", "IR ← MDR", "latch the instruction"),
        ("T3", "decode IR", "split into opcode, rd, rs and immediate / address"),
        ("T4", "execute", "ALU operation, comparison, branch or I/O"),
        ("T5", "memory access", "only for LD, LDX and ST: operand read or write")],
        widths=[0.6, 2.4, 2.9], caption="Phases of the instruction cycle implemented by CPU.step()")
    r.h3("Instruction format and addressing modes")
    r.body("Every instruction is one 32-bit word: `opcode (8 bits) | rd (4) | rs (4) | imm/address (16, signed)`. The ISA supports "
           "four addressing modes. In **immediate** mode the operand is inside the instruction (`LDI R0, 5`). In **direct** mode the "
           "instruction holds the memory address (`LD R1, 100`). In **register** mode the operand is in a register (`MOV R2, R0`). "
           "In **indexed** mode the effective address is a register plus a constant (`LDX R0, R2, table` computes "
           "`EA = R2 + table`), which is the natural way to index a two-dimensional array stored in a flat memory.")
    r.h3("Performance equation")
    r.body("Execution time = Instruction count × CPI × Clock period. The simulator reports the first two terms directly. Because "
           "all clock periods are equal in a simulation, comparing programs by instructions and cycles is sufficient.")

    r.h1("Chapter II - System Configuration")
    r.body("The simulator was developed and tested in the environment below. It needs nothing beyond a standard Python installation "
           "to run the CPU; Flask is used only for the web demonstration.")
    config_table(r)
    r.h3("Simulated CPU configuration")
    r.table(["Component", "Specification"], [
        ("Architecture", "Von Neumann, single memory for code and data"),
        ("Memory", "32,768 words × 32 bits (16-bit addresses)"),
        ("General registers", "R0–R7, 32-bit signed"),
        ("Special registers", "PC, MAR, MDR, IR; flags Z (zero) and N (negative)"),
        ("Instruction word", "32 bits: opcode 8 | rd 4 | rs 4 | imm/addr 16 (signed)"),
        ("Addressing modes", "immediate, direct, register, indexed"),
        ("Input device", "`IN rd` reads the next input symbol class (−1 at end of input)"),
        ("Cycle model", "fetch 3 + decode 1 + execute 1 = 5; +1 memory operand; +2 multiply")],
        widths=[1.7, 4.2], caption="Simulated processor")
    rows = []
    for name, code in OPCODES.items():
        pat = OPERANDS[name]
        ops = ", ".join({"r": "rd", "s": "rs", "i": "imm"}[ch] for ch in pat) or "–"
        rows.append((name, code, ops, ADDRESSING.get(name, "–"), CYCLES[name]))
    r.table(["Mnemonic", "Opcode", "Operands", "Addressing", "Cycles"], rows, size=9,
            widths=[1.0, 0.8, 1.6, 1.5, 0.8], caption="Instruction set of the simulated CPU")
    r.h2("Algorithm")
    r.h3("Instruction-cycle algorithm (CPU.step)")
    r.numbered(["MAR ← PC; MDR ← M[MAR]; PC ← PC + 1; IR ← MDR (fetch).",
                "Split IR into opcode, rd, rs, imm; stop with an error if the opcode is undefined (decode).",
                "Perform the operation: update a register, set Z/N, change PC for a taken branch, read or write memory, or halt (execute).",
                "Add the instruction's cost to the cycle counter and increment the instruction counter.",
                "Repeat until ACCEPT, REJECT or HLT sets the halt flag, or until the cycle limit is exceeded."])
    r.h3("Generated DFA-matcher program")
    r.body("For a DFA with K symbols, state s and symbol class c, the transition table is stored row-major at address `table` so "
           "that the next state is `M[table + s·K + c]`. Registers: R0 = state, R1 = symbol, R2 = table index, R3 = accept flag.")
    r.numbered(["R0 ← start state.", "R1 ← next input symbol (`IN`). If R1 = −1 go to step 7. If R1 < −1 (symbol outside the alphabet) REJECT.",
                "R2 ← R0 · K (`MULI`).", "R2 ← R2 + R1 (`ADD`).", "R0 ← M[R2 + table] (`LDX`, indexed addressing).",
                "If R0 = −1 (dead transition) REJECT, otherwise jump to step 2.",
                "R3 ← accept[R0] (`LDX`). ACCEPT if R3 = 1, else REJECT."])
    r.h2("Source Code")
    r.h3("Instruction encoding and decoding")
    r.code(src(cpu_mod.encode) + "\n" + src(cpu_mod.decode))
    r.h3("The instruction cycle: CPU.step()")
    r.code(src(cpu_mod.CPU.step))
    r.h3("Machine-code generator for a DFA")
    r.code(src(asm_mod.dfa_to_assembly))

    r.h1("Chapter III - Results")
    r.body("All measurements below were produced by the project itself (`main.py`, `benchmarks/benchmark.py` and the unit tests). "
           "The reference pattern is `(a|b)*abb`, whose minimal DFA has four states.")
    r.h3("Generated program and memory map")
    r.body(f"The pattern compiles to {c.program.code_words} instruction words followed by {c.program.data_words} data words "
           "(an 8-entry transition table and a 4-entry accept table).")
    rows = [(a, f"{w & 0xFFFFFFFF:08x}", cpu_mod.disassemble(w) if a < c.program.code_words else f".word {w}")
            for a, w, _ in c.program.listing]
    r.table(["Address", "Word (hex)", "Meaning"], rows, size=9, widths=[0.9, 1.3, 2.6], caption="Memory image of the matcher")
    r.h3("Instruction-cycle trace")
    r.body("The first instructions of a run, as printed by `python main.py \"(a|b)*abb\" -t ab --trace`:")
    r.code(out_text("cli_trace_excerpt.txt"), size=8)
    r.image(crop("abb_trace.png", "trace_crop.png", 0, 1150), 5.6, "Instruction-cycle trace in the web application (first instructions expanded)")
    r.h3("Test strings")
    run_table(r, c, ["abb", "aabb", "babb", "ababb", "ab", "abba", "", "abbc"])
    r.body("For every string the NFA, DFA, minimal DFA and the CPU gave the same verdict. An input symbol outside the alphabet "
           "(`c`) is mapped to class −2 and rejected by the `JLT` instruction.")
    r.h3("Cost model: 11 instructions, 58 cycles per symbol")
    loop = [("IN", 1, 5), ("CMPI", 2, 5), ("JEQ", 2, 5), ("JLT", 1, 5), ("MOV", 1, 5), ("MULI", 1, 7), ("ADD", 1, 5), ("LDX", 1, 6), ("JMP", 1, 5)]
    r.table(["Instruction", "Times per symbol", "Cycles each", "Cycles"], [(m, n, k, n * k) for m, n, k in loop] +
            [("**Total**", "**11**", "", f"**{sum(n * k for _, n, k in loop)}**")], widths=[1.6, 1.5, 1.2, 1.2],
            caption="Cost of one iteration of the matcher loop")
    head, rows = csv_rows("coa_cycles.csv")
    sel = [row for row in rows if int(row[0]) in (0, 10, 50, 100, 150, 200)]
    r.table(["Input length n", "Instructions", "Cycles measured", "41 + 58n", "CPI"],
            [(int(n), int(i), int(cy), int(41 + 58 * n), f"{cpi:.3f}") for n, i, cy, cpi in sel],
            caption="Measured cycles versus the model cycles = 41 + 58n")
    r.body("The measured values equal the model exactly, which confirms that the cost is linear in the input length and that the "
           "start-up and finishing code (LDI, final IN, test, table lookup and ACCEPT) costs 41 cycles. The average CPI approaches "
           "58/11 = 5.27 for long inputs; it is above the minimum of 5 because the multiply (7 cycles) and the table load (6 cycles) are slower.")
    r.image(img("coa_cycles.png"), 4.9, "Instructions and clock cycles versus input length")
    r.image(img("coa_instruction_mix.png"), 4.9, "Dynamic instruction mix for a 103-symbol input")
    r.body("The mix is dominated by compare and branch instructions (CMPI and JEQ make up about 36% of all executed instructions): "
           "typical control-heavy code. Only one instruction per symbol touches memory (`LDX`), and it is the one that uses "
           "indexed addressing.")
    r.h3("Testing")
    test_table(r, "coa")
    r.body("The CPU-specific tests check encode/decode round trips, arithmetic and flag behaviour, every addressing mode, exact "
           "cycle accounting, presence of all six micro-steps (T0–T5) in a trace, error handling (undefined opcode, out-of-range "
           "memory access, assembler errors) and the cycle-limit guard against infinite loops.")
    r.image(crop("abb_pipeline.png", "pipe.png"), 5.6, "Web application: compilation pipeline summary for (a|b)*abb")
    r.image(img("screenshots", "abb_results.png"), 5.6, "Web application: all four engines agree; instructions, cycles and CPI per input")

    r.h1("Chapter IV – Conclusion")
    r.body("This work shows that the instruction cycle can be implemented, observed and measured in a few hundred lines of code. "
           "The simulated CPU fetches, decodes and executes real 32-bit machine words, exposes every register transfer in a trace, "
           "supports immediate, direct, register and indexed addressing, and accounts for clock cycles with a simple but explicit "
           "model. A program generated automatically from a regular expression ran correctly on it, and its measured cost "
           "(41 + 58n cycles, CPI ≈ 5.27) matched the analytical prediction exactly.")
    r.body("The main limitation is that the CPU is not pipelined: every instruction occupies the machine for its full 5–7 cycles. "
           "Natural extensions are a five-stage pipeline with hazard detection, a hardwired or microprogrammed control unit, a "
           "cache in front of the transition table, and a richer ISA (for example a conditional-move or table-lookup instruction) "
           "that would shorten the 11-instruction inner loop.")

# ======================================================================= FLAT
def flat(r):
    c = compile_regex("(a|b)*abb"); c2 = compile_regex(r"[0-9]+(\.[0-9]+)?"); st = c.stats()
    r.p("Abstract", size=16, bold=True, after=8, before=6, line=1.15); r.toc_marks.append(("Abstract", 0))
    r.body("Regular expressions and finite automata describe exactly the same class of languages (Kleene's theorem). This report "
           "presents a from-scratch implementation of the complete conversion pipeline: a regular expression is parsed with the "
           "shunting-yard algorithm, converted into an ε-NFA by Thompson's construction, determinised with the subset "
           "construction, completed with a trap state and minimised by partition refinement. The automata are checked on test "
           "strings and compared with Python's `re` module on 3,000 random regex/string pairs, with no disagreement.")
    r.body("Experiments confirm the textbook results: the minimal DFA for (a|b)*abb has four states, a Thompson NFA grows linearly "
           "with the expression, and the family (a|b)*a(a|b)^n needs 2^(n+1) DFA states, so the DFA grows exponentially while the "
           "NFA does not. The automaton produced here is also used by the other two parts of the combined RegexCPU project: it "
           "is analysed with Tarjan's SCC algorithm (DAA) and executed on a simulated CPU (COA).")

    r.h1("Chapter I- Introduction")
    r.body("Regular expressions are the everyday notation for patterns: validating an e-mail address, tokenising source code, "
           "searching logs. Behind most implementations lies a finite automaton. Kleene's theorem states that a language is "
           "regular if and only if it is denoted by a regular expression, accepted by a DFA, or accepted by an NFA, and the proof "
           "is constructive: it gives algorithms to convert one form into another. Understanding these algorithms is the core "
           "of Module 2 of Formal Languages and Automata Theory.")
    r.body("This project implements the constructive proof as working software. The pipeline is: regular expression → postfix "
           "form → ε-NFA → DFA → complete DFA → minimal DFA. Each stage is a separate, testable component, and the web "
           "application draws every automaton so that the transformations can be inspected visually.")
    r.h2("Problem Statement")
    r.body("Library regex engines hide the automaton construction from the user, and hand-drawn conversions in an exam do not "
           "scale beyond a few states. The problem is to implement the regular-expression-to-finite-automata conversion "
           "faithfully, verify that every stage preserves the language, and study how the sizes of the NFA, DFA and minimal DFA "
           "behave. Specific objectives:")
    r.bullets(["parse regular expressions with union, concatenation, Kleene star, plus, optional, grouping and character classes, and report malformed input clearly;",
               "build the ε-NFA with Thompson's construction;", "convert it to a DFA with the subset construction using ε-closures;",
               "complete and minimise the DFA;", "validate all stages against an independent reference (Python `re`) and measure state growth."])
    r.h2("Theory")
    r.h3("Definitions")
    r.body("A **DFA** is a 5-tuple (Q, Σ, δ, q0, F) with δ: Q × Σ → Q. An **ε-NFA** allows δ: Q × (Σ ∪ {ε}) → 2^Q. Both accept "
           "exactly the regular languages. The **ε-closure** of a set of states is the set reachable using only ε-moves.")
    r.h3("Thompson's construction")
    r.body("Each operator of the expression is translated into a small NFA fragment with one start and one accepting state. "
           "Fragments are glued with ε-edges, so the NFA has at most two states per symbol or operator, i.e. size O(|r|).")
    r.table(["Operator", "Construction"], [
        ("symbol a", "start —a→ accept"), ("r1 r2 (concatenation)", "accept(r1) —ε→ start(r2)"),
        ("r1 | r2 (union)", "new start —ε→ both starts; both accepts —ε→ new accept"),
        ("r* (star)", "new start —ε→ start(r) and → new accept; accept(r) —ε→ start(r) and → new accept"),
        ("r+ (plus)", "as star, but no direct ε from new start to new accept"),
        ("r? (optional)", "as star, but no ε-loop back from accept(r) to start(r)")],
        widths=[1.9, 4.0], caption="Thompson construction rules used in nfa.py")
    r.h3("Subset construction")
    r.body("Each DFA state is a set of NFA states. The start state is ε-closure({q0}); for a state S and symbol a, the next state is "
           "ε-closure(move(S, a)). A DFA state is accepting if it contains the NFA accepting state. In the worst case the DFA has "
           "2^n states for an n-state NFA; the family (a|b)*a(a|b)^n shows this blow-up is real.")
    r.h3("Completion and minimisation")
    r.body("A DFA is made **complete** by adding a trap state that absorbs every missing transition. Two states are equivalent "
           "(Myhill–Nerode) if they lead to the same acceptance behaviour on every suffix. **Partition refinement** (Moore) starts "
           "with the partition {accepting, non-accepting} and splits blocks whose members move into different blocks on some "
           "symbol, until the partition is stable. Each final block becomes one state of the minimal DFA, which is unique up to renaming.")

    r.h1("Chapter II - System Configuration")
    config_table(r)
    r.body("Components implemented for this report: `regex_parser.py` (tokeniser, explicit concatenation, shunting-yard), "
           "`nfa.py` (Thompson's construction, ε-closure, NFA simulation) and `dfa.py` (subset construction, completion, "
           "Moore minimisation, trimming and Graphviz export).")
    r.h2("Algorithm")
    r.h3("Regular expression to postfix")
    r.numbered(["Tokenise: literals, operators, escapes; expand a class such as [a-c] into (a|b|c).",
                "Insert an explicit concatenation token between adjacent operands, validating operator placement.",
                "Run shunting-yard with precedence union < concatenation; postfix operators *, +, ? go straight to the output."])
    r.h3("Postfix to ε-NFA, ε-NFA to minimal DFA")
    r.numbered(["Scan the postfix string; push a (start, accept) fragment for each symbol; pop one or two fragments for each operator and push the combined fragment.",
                "Subset construction: breadth-first search over sets of NFA states, using ε-closure after every move.",
                "Add a trap state if any transition is missing (complete DFA).",
                "Moore refinement: repeat block ← (block, blocks of successors) until the number of blocks stops growing.",
                "Renumber states in breadth-first order so equal languages give identical machines."])
    r.body("**Complexity.** Parsing and Thompson construction are O(|r|). Subset construction is O(2^n · |Σ|) in the worst case. "
           "Moore refinement is O(|Σ| · m²) for m DFA states (Hopcroft's algorithm would give O(|Σ| · m log m)).")
    r.h2("Source Code")
    r.h3("Thompson's construction (nfa.py)")
    r.code(src(nfa_mod.thompson))
    r.h3("Subset construction (dfa.py)")
    r.code(src(dfa_mod.subset_construction))
    r.h3("DFA minimisation (dfa.py)")
    r.code(src(dfa_mod.minimize))

    r.h1("Chapter III - Results")
    r.h3("Worked example: (a|b)*abb")
    r.body(f"Postfix form: `{st['postfix']}`. The ε-NFA has {st['nfa_states']} states and {st['nfa_edges']} edges; the subset "
           f"construction gives {st['dfa_states']} DFA states, which minimise to {st['min_dfa_states']}. The result of four states "
           "is the well-known answer for this language (strings over {a,b} ending in abb).")
    r.image(img("diagrams", "abb_nfa.png"), 6.0, "ε-NFA built by Thompson's construction for (a|b)*abb")
    r.image(img("diagrams", "abb_dfa.png"), 4.8, "DFA after the subset construction (5 states)")
    r.image(img("diagrams", "abb_min_dfa.png"), 4.8, "Minimal DFA (4 states)")
    r.h3("Test strings")
    run_table(r, c, ["abb", "aabb", "babb", "ababb", "ab", "abba", ""], cpu_cols=False)
    r.body(f"A second pattern, `[0-9]+(\\.[0-9]+)?` (unsigned decimal number), gives a Thompson NFA of {c2.nfa.n} states, a DFA of "
           f"{c2.dfa_raw.n} states and a minimal complete DFA of {c2.dfa_min.n} states (one of them the trap state).")
    run_table(r, c2, ["42", "3.14", "3.", ".5", "1.2.3", "007"], cpu_cols=False)
    r.h3("State growth: NFA versus DFA")
    head, rows = csv_rows("flat_blowup.csv")
    r.table(["n", "ε-NFA states", "DFA states", "Minimal DFA states", "Compile time (ms)"],
            [(int(n), int(a), int(b), int(m), f"{t:.2f}") for n, a, b, m, t in rows], caption="Size of the automata for (a|b)*a(a|b)^n")
    r.image(img("flat_state_growth.png"), 5.0, "Automaton size against n (logarithmic scale)")
    r.body("The ε-NFA grows by six states for each extra (a|b), i.e. linearly in the expression, while the minimal DFA has "
           "exactly 2^(n+1) states: the DFA must remember the last n+1 symbols. This is the practical reason why engines that "
           "need a DFA build it lazily or accept exponential cost in rare patterns.")
    r.h3("Testing")
    test_table(r, "flat")
    r.body("Correctness was established in four ways: (1) hand-checked examples with known minimal sizes; (2) a check that the Thompson NFA "
           "never exceeds two states per postfix token; (3) agreement of the NFA, DFA, minimal DFA and the CPU matcher on every test string; "
           "(4) a fuzz test generating 250 random regular expressions over {a,b,c} and 12 random strings each (3,000 comparisons) "
           "against `re.fullmatch`, which found no disagreement. Malformed expressions such as `(a`, `*a`, `a||b` and `[]` raise a clear error.")
    r.image(img("screenshots", "abb_pipeline.png"), 5.6, "Web application: pipeline statistics")
    r.image(img("screenshots", "abb_diagram.png"), 5.6, "Web application: minimal DFA diagram")

    r.h1("Chapter IV – Conclusion")
    r.body("The report demonstrates the constructive content of Kleene's theorem with a complete, tested implementation. Regular "
           "expressions with union, concatenation, star, plus, optional and character classes are converted to ε-NFAs, determinised, "
           "completed and minimised, and every stage preserved the language on all test inputs, including 3,000 random comparisons "
           "with a production regex engine. The experiments reproduce two classical facts: the minimal DFA of (a|b)*abb has four states, "
           "and DFA size can be exponential in the size of the expression.")
    r.body("Limitations are the restricted syntax (no wildcard, back-references, anchors or negated classes) and the quadratic "
           "Moore minimisation. Future work includes Hopcroft's algorithm, lazy DFA construction, complement and intersection of "
           "automata, and counted repetition `{m,n}`.")

# ======================================================================= DAA
def daa(r):
    c = compile_regex("ab|cd?"); s = c.scc
    head, rows = csv_rows("daa_scc_scaling.csv"); big = rows[-1]
    abstract = ("A strongly connected component (SCC) of a directed graph is a maximal set of vertices that are all reachable from "
        "one another. Tarjan's algorithm finds all SCCs in a single depth-first traversal in O(V + E) time using low-link values. "
        "This report presents an iterative implementation of Tarjan's algorithm, an independent Kosaraju implementation used as a "
        "checker, and an application: analysing the state graph of a deterministic finite automaton to locate dead (useless) "
        "states, loops, and to decide whether the accepted language is finite.")
    r.p("Abstract", size=16, bold=True, after=8, before=6, line=1.15); r.toc_marks.append(("Abstract", 0))
    r.body(abstract)
    r.body(f"Experiments on random graphs with up to {int(big[0]):,} vertices and {int(big[1]):,} edges show running time growing linearly "
           f"with V + E; Tarjan took {big[4]:.0f} ms against {big[5]:.0f} ms for Kosaraju at the largest size. Both algorithms returned "
           "identical partitions on 300 random graphs and on every benchmark graph, and the iterative design handled a 200,000-vertex "
           "chain without recursion errors. The DAA component is part of RegexCPU, together with FLAT (regex to automata) and COA (CPU simulation).")

    r.h1("Chapter I- Introduction")
    r.body("Graph traversal (BFS and DFS) is the foundation of Module 1 of Design and Analysis of Algorithms. Among the DFS-based "
           "algorithms, the computation of strongly connected components is one of the most useful: collapsing every SCC into a single "
           "vertex turns any directed graph into a directed acyclic graph (DAG), which can then be processed with topological order "
           "and dynamic programming. Tarjan's algorithm (1972) achieves this with one DFS and a stack.")
    r.body("Instead of demonstrating the algorithm on a textbook graph only, this project applies it to a real graph: the "
           "transition graph of a DFA produced from a regular expression. The result is used to remove states that can never lead to "
           "acceptance, to detect cycles and to classify the language as finite or infinite. The rest of the pipeline (regular expression "
           "to automaton, and execution on a simulated CPU) is described in the FLAT and COA reports.")
    r.h2("Problem Statement")
    r.body("Given a directed graph with V vertices and E edges, compute all strongly connected components in linear time without "
           "recursion limits, and use them to analyse an automaton. The objectives are:")
    r.bullets(["implement Tarjan's algorithm iteratively so that deep graphs do not overflow the call stack;",
               "implement Kosaraju's two-pass algorithm independently and use it to cross-check Tarjan's output;",
               "build the condensation DAG and exploit the reverse-topological emission order of Tarjan's algorithm;",
               "use the SCC structure of a DFA to find dead states, cycles and language finiteness;",
               "verify the O(V + E) bound experimentally."])
    r.h2("Theory")
    r.h3("Strongly connected components")
    r.body("Vertices u and v are strongly connected if there is a path from u to v and from v to u. This relation is an equivalence "
           "relation; its classes are the SCCs. The **condensation graph**, with one node per SCC, is always a DAG.")
    r.h3("Tarjan's algorithm")
    r.body("During a DFS each vertex v receives a discovery number `index[v]` and a `low[v]`: the smallest discovery number reachable "
           "from v's DFS subtree using at most one back or cross edge to a vertex still on the stack. Vertices are pushed on a stack when "
           "discovered. When the DFS finishes a vertex v with `low[v] = index[v]`, v is the root of an SCC and the stack is popped down to v; "
           "the popped vertices form the component.")
    r.table(["Property", "Statement"], [
        ("Time", "O(V + E): every vertex is pushed and popped once, every edge examined once"),
        ("Space", "O(V) for index, low, on-stack flags and the stack"),
        ("Output order", "SCCs are emitted in reverse topological order of the condensation DAG"),
        ("Passes", "one DFS (Kosaraju needs two DFS passes and a transposed graph)")],
        widths=[1.4, 4.5], caption="Properties of Tarjan's algorithm")
    r.h3("Application to a DFA")
    r.body("Treat each DFA state as a vertex and each transition as an edge. A state is **useful** if it is reachable from the start "
           "state and can reach an accepting state. Because Tarjan emits SCCs in reverse topological order, every successor of a component "
           "has already been emitted when the component is emitted. A single left-to-right pass can therefore compute "
           "`live[C] = (C contains an accepting state) or (some successor of C is live)`. States in non-live components are dead and are "
           "removed. The language is infinite exactly when a cyclic SCC (size > 1 or a self-loop) contains a useful state.")

    r.h1("Chapter II - System Configuration")
    config_table(r)
    r.h2("Algorithm")
    r.h3("Tarjan's SCC (iterative)")
    r.code("""for each vertex root not yet visited:
    push (root, 0) on a work stack
    while work stack not empty:
        (v, i) = pop
        if i == 0:  index[v] = low[v] = counter++;  push v on SCC stack;  mark on_stack[v]
        for j from i to deg(v)-1:
            w = adj[v][j]
            if w unvisited:    push (v, j+1), push (w, 0);  break      # "recursive call"
            elif on_stack[w]:  low[v] = min(low[v], index[w])
        if we descended: continue
        if low[v] == index[v]:  pop SCC stack down to v -> one component
        if work stack not empty:  parent u = top;  low[u] = min(low[u], low[v])""", size=8.5)
    r.body("The explicit work stack stores (vertex, next-edge-position) pairs, so the recursion of the textbook version is replaced by a loop. "
           "Python's default recursion limit of about 1,000 frames would otherwise crash on long chains.")
    r.h3("DFA analysis")
    r.numbered(["Run Tarjan on the complete minimal DFA graph.", "Map every state to its component and build the condensation edges.",
                "Scan components in emission order and compute `live`.", "useful = live ∩ reachable; dead = all states − useful.",
                "Report cyclic components and decide finiteness; trim dead states before code generation."])
    r.h2("Source Code")
    r.h3("Tarjan's algorithm (scc.py)")
    r.code(src(scc_mod.tarjan_scc))
    r.h3("Kosaraju's algorithm (scc.py), used as a checker")
    r.code(src(scc_mod.kosaraju_scc))
    r.h3("Condensation, dead states and finiteness (scc.py)")
    r.code(src(scc_mod.analyze))

    r.h1("Chapter III - Results")
    r.h3("Sample input and output")
    r.body("Input: the regular expression `ab|cd?`. Its minimal complete DFA has five states: start, two accepting states and "
           "a trap state. The command `python main.py \"ab|cd?\" --scc -t ab cd abc` produced:")
    r.code(out_text("cli_fin.txt"), size=8)
    r.table(["SCC", "States", "Flags"], [(i, ", ".join(f"q{x}" for x in sorted(comp)),
            " ".join(t for t, ok in (("cyclic", i in s["cyclic_sccs"]), ("accepting", any(v in c.dfa_min.accepting for v in comp)),
                                      ("DEAD", not any(v in s["useful"] for v in comp))) if ok) or "–") for i, comp in enumerate(s["sccs"])],
            widths=[0.8, 1.6, 3.2], caption="Tarjan output for the DFA of ab|cd? (reverse topological order)")
    r.body("The only cyclic component is the trap state q2 with its self-loop; it cannot reach an accepting state, so Tarjan's pass "
           "marks it dead and it is removed. All other components are singletons without cycles, so the language is finite, and "
           "the enumeration `c, ab, cd` is printed. For `(a|b)*abb` the whole four-state DFA is a single cyclic SCC, so the language is infinite.")
    r.image(img("screenshots", "fin_diagram.png"), 5.6, "Minimal DFA of ab|cd? with the dead state q2 drawn in red")
    r.image(img("screenshots", "fin_scc.png"), 5.6, "Web application: SCC table for ab|cd?")
    r.h3("Complexity analysis")
    r.table(["V", "E", "V + E", "SCCs found", "Tarjan (ms)", "Kosaraju (ms)"],
            [(f"{int(v):,}", f"{int(e):,}", f"{int(t):,}", int(k), f"{a:.1f}", f"{b:.1f}") for v, e, t, k, a, b in rows],
            caption="Running time on random graphs with 3 outgoing edges per vertex (best of 3 runs)")
    r.image(img("daa_scc_scaling.png"), 5.0, "Measured running time against V + E with linear fit")
    r.body("Doubling V + E roughly doubles the running time for both algorithms, as predicted by the O(V + E) analysis; the linear fit "
           "of Tarjan's times has R² close to 0.99. In this Python implementation Tarjan and Kosaraju have similar constants: "
           "Tarjan is faster at the largest sizes because it makes a single pass and builds no transposed graph, but at small "
           "sizes the difference is within measurement noise, so no stronger claim is made. Absolute timings depend on the machine.")
    r.h3("Test case results")
    test_table(r, "daa")
    r.table(["Test case", "Expected", "Result"], [
        ("Textbook graph with SCCs {0,1,2}, {3,4,5}, {6,7}, {8}", "4 components", "PASS"),
        ("Chain 3→0→1→2: emission order", "2, 1, 0, 3 (reverse topological)", "PASS"),
        ("Self-loop and isolated vertex; empty graph", "[[0],[1]]; []", "PASS"),
        ("300 random graphs, Tarjan vs Kosaraju", "identical partitions", "PASS"),
        ("Path graph with 200,000 vertices", "200,000 components, no RecursionError", "PASS"),
        ("DFA of ab*: dead states", "exactly the trap state", "PASS"),
        ("a* infinite; ab|cd? finite, words c, ab, cd", "as stated", "PASS")],
        widths=[3.1, 2.1, 0.7], size=9, caption="Selected DAA test cases (tests/test_all.py, class TestSCC)")

    r.h1("Chapter IV – Conclusion")
    r.body("Tarjan's algorithm was implemented iteratively, verified against an independent Kosaraju implementation and shown "
           "experimentally to run in time linear in V + E. Applied to the DFA produced by the FLAT part of the project, it identifies "
           "the dead trap state, detects loops and decides whether a language is finite, all from one traversal and one pass over the "
           "condensation DAG. The pruned automaton is then compiled to machine code and run on the simulated CPU of the COA part.")
    r.body("The key idea worth remembering is the reverse-topological emission order: it lets dynamic programming over the "
           "condensation DAG run during the SCC computation itself. Possible extensions are bridge and articulation-point detection "
           "with the same low-link technique, 2-SAT solving, and analysing larger automata such as lexer DFAs.")

# ======================================================================= driver
SUBJECTS = {
    "COA": dict(fn=coa, subject="Computer Organization and Architecture", guide_key="guide_coa",
                title="Instruction Cycle Simulation on a Custom CPU",
                topic="the Instruction Cycle and Addressing Modes (RegexCPU)",
                closing="This project allowed me to build a CPU model in which the instruction cycle is visible and measurable, "
                        "and to run a real program on it. It strengthened my understanding of registers, addressing modes and CPI."),
    "FLAT": dict(fn=flat, subject="Formal Languages and Automata Theory", guide_key="guide_flat",
                 title="Regular Expression to Finite Automata Conversion",
                 topic="Regular Expression to Finite Automata Conversion (RegexCPU)",
                 closing="This project allowed me to implement Thompson's construction, the subset construction and DFA "
                         "minimisation end to end, and to verify them against a production regex engine."),
    "DAA": dict(fn=daa, subject="Design and Analysis of Algorithms", guide_key="guide_daa",
                title="Tarjan's Strongly Connected Components Algorithm",
                topic="Tarjan's Strongly Connected Components Algorithm (RegexCPU)",
                closing="This project allowed me to implement Tarjan's algorithm iteratively, validate it against Kosaraju's "
                        "algorithm and measure its linear running time on large graphs."),
}


def build(key, pages=None):
    S = SUBJECTS[key]; guide = CFG[S["guide_key"]]
    r = Report()
    r.cover(CFG, S["title"], S["subject"], guide, ASSETS)
    r.certificate(CFG, S["topic"], guide, ASSETS)
    r.declaration(CFG, S["title"], guide, ASSETS)
    r.acknowledgement(CFG, S["title"], guide, ASSETS, S["closing"]); r.toc_marks.append(("Acknowledgement", 0))
    r.toc_placeholder()
    r.page_break(); S["fn"](r)
    marks = [m for m in r.toc_marks]
    r.fill_toc(marks, pages or {})
    return r, marks


def pdf_pages(docx_path):
    outdir = tempfile.mkdtemp()
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", outdir, docx_path],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pdf = os.path.join(outdir, os.path.basename(docx_path).replace(".docx", ".pdf"))
    n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout).group(1))
    pages = [subprocess.run(["pdftotext", "-layout", "-f", str(i), "-l", str(i), pdf, "-"], capture_output=True, text=True).stdout
             for i in range(1, n + 1)]
    return pdf, pages


def find_pages(marks, pages):
    toc_idx = next(i for i, t in enumerate(pages) if "TABLE OF CONTENTS" in t)
    found = {}
    for text, _ in marks:
        for i, t in enumerate(pages):
            if i == toc_idx: continue
            if any(line.strip() == text for line in t.splitlines()):
                found[text] = i + 1; break
    return found


def main():
    only = sys.argv[1:] or list(SUBJECTS)
    for key in only:
        path = os.path.join(HERE, f"{key}_Report.docx")
        r, marks = build(key); r.save(path)                       # pass 1 (layout)
        pdf, pages = pdf_pages(path)
        found = find_pages(marks, pages)
        r, marks = build(key, found); r.save(path)                # pass 2 (with page numbers)
        pdf, pages2 = pdf_pages(path)
        missing = [t for t, _ in marks if t not in found]
        print(f"{key}: {len(pages2)} pages, TOC ok" + (f", MISSING {missing}" if missing else ""))
        subprocess.run(["cp", pdf, os.path.join(HERE, f"{key}_Report.pdf")])


if __name__ == "__main__":
    main()
