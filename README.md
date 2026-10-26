# RegexCPU – a regular-expression compiler that runs on a simulated CPU

**Micro Project – Computer Organization & Architecture · Formal Language & Automata Theory · Design & Analysis of Algorithms**

| Link | URL |
|---|---|
| GitHub repository | https://github.com/YOUR-USERNAME/RegexCPU  *(replace before submitting)* |
| Deployed application | https://YOUR-APP.onrender.com  *(replace before submitting)* |

## What it does
You type a regular expression. RegexCPU

1. **parses** it (shunting-yard) and builds an **ε-NFA** with Thompson's construction — *FLAT*
2. converts it to a **DFA** (subset construction), completes it and **minimises** it (Moore) — *FLAT*
3. runs **Tarjan's SCC algorithm** on the DFA graph to find dead states, loops and whether the
   language is finite, then prunes the dead states — *DAA*
4. **compiles** the DFA to assembly for a custom 32-bit CPU, assembles it into machine code and
   **executes it on a CPU simulator that models the fetch-decode-execute cycle**, counting
   instructions and clock cycles (CPI) — *COA*

Every string is checked by four engines (NFA, DFA, minimal DFA, CPU). They must agree, and the
test-suite also compares them with Python's `re` on 3,000 random regex/string pairs.

## Selected concepts (one per subject, per the micro-project rules)
| Subject | Module | Concept | Where in the code |
|---|---|---|---|
| FLAT | Module 2 | Regular Expression → Finite Automata conversion (with NFA→DFA and DFA minimisation) | `regexcpu/regex_parser.py`, `nfa.py`, `dfa.py` |
| DAA  | Module 1 | Tarjan's Strongly Connected Components algorithm (DFS, low-link, O(V+E)) | `regexcpu/scc.py` |
| COA  | Module 2 | The Instruction Cycle (+ addressing modes) on a simulated CPU | `regexcpu/cpu.py`, `assembler.py` |

## Run it
```bash
pip install -r requirements.txt

python main.py --demo                          # demo patterns
python main.py "(a|b)*abb" -t abb aabb ab      # test strings through all four engines
python main.py "(a|b)*abb" -t ab --trace      # fetch-decode-execute trace
python main.py "ab|cd?" --scc                  # Tarjan SCC analysis (finds the dead state)
python main.py "(a|b)*abb" --asm               # generated assembly + memory map
python app.py                                  # web app on http://localhost:5000
python -m unittest discover -s tests -v        # 28 tests (incl. 3,000-case fuzz test)
```
Supported regex syntax: literals, `|` `*` `+` `?` `( )`, classes like `[a-z0-9]`, and `\x` escapes.

## Project layout
```
main.py                CLI                          app.py + templates/   Flask web app
regexcpu/              regex_parser · nfa · dfa  (FLAT) | scc (DAA) | cpu · assembler (COA)
                       pipeline (glue) · render (SVG diagrams)
tests/test_all.py      28 unit / integration / fuzz tests
benchmarks/            benchmark.py -> results/*.png|csv (graphs used in the reports)
reports/               build_reports.py + the three subject reports (.docx)
student.json           your name / roll no. / guide names used by the reports
package.py             builds the 3 per-subject submission ZIPs
```

## CPU in one paragraph
Von-Neumann machine, 32,768-word memory, registers R0–R7, PC, MAR, MDR, IR and Z/N flags. A 32-bit
instruction is `opcode(8) | rd(4) | rs(4) | imm(16)`. Addressing modes: immediate, direct, register
and indexed (`LDX R0, R2, table` → `R0 = M[R2 + table]`). One instruction costs 5 cycles
(3 fetch + 1 decode + 1 execute), +1 for a memory operand, +2 for multiply. The generated matcher
executes 11 instructions (58 cycles) per input symbol, so run time is `41 + 58·n` cycles.

DEPLOYED LINK--> https://regexcpu.onrender.com/
GITHUB LINK--> https://github.com/aarzoooo95/RegexCPU.git