"""Glue: regex -> NFA -> DFA -> complete -> minimal -> SCC trim -> assembly -> CPU."""
import time
from dataclasses import dataclass, field

from .regex_parser import parse, postfix_string
from .nfa import thompson, NFA
from .dfa import (DFA, subset_construction, complete, minimize, trim, dfa_to_dot,
                  to_table)
from .scc import analyze, finite_language
from .assembler import assemble, dfa_to_assembly, Program
from .cpu import CPU, CPUError


@dataclass
class Compiled:
    pattern: str
    postfix: list
    nfa: NFA
    dfa_raw: DFA
    dfa_complete: DFA
    dfa_min: DFA
    scc: dict
    dfa: DFA                     # trimmed minimal DFA that is loaded into the CPU
    asm: str
    program: Program
    timings: dict = field(default_factory=dict)

    @property
    def alphabet(self):
        return self.dfa.alphabet

    def symbols(self, text: str):
        idx = {a: i for i, a in enumerate(self.dfa.alphabet)}
        return [idx.get(ch, -2) for ch in text]

    def stats(self):
        s = self.scc
        return {
            "pattern": self.pattern,
            "postfix": postfix_string(self.postfix),
            "alphabet": self.alphabet,
            "nfa_states": self.nfa.n, "nfa_edges": self.nfa.edge_count,
            "dfa_states": self.dfa_raw.n,
            "dfa_complete_states": self.dfa_complete.n,
            "min_dfa_states": self.dfa_min.n,
            "scc_count": len(s["sccs"]),
            "largest_scc": max(len(c) for c in s["sccs"]),
            "cyclic_sccs": len(s["cyclic_sccs"]),
            "dead_states": sorted(s["dead"]),
            "final_states": self.dfa.n,
            "is_infinite": s["is_infinite"],
            "code_words": self.program.code_words,
            "data_words": self.program.data_words,
        }


def compile_regex(pattern: str) -> Compiled:
    t, timings = time.perf_counter(), {}

    def tick(name):
        nonlocal t
        now = time.perf_counter()
        timings[name] = now - t
        t = now

    postfix = parse(pattern);                         tick("parse")
    nfa = thompson(postfix);                          tick("thompson")
    raw = subset_construction(nfa);                   tick("subset")
    comp = complete(raw);                             tick("complete")
    mini = minimize(comp);                            tick("minimize")
    info = analyze(mini.adjacency(), mini.start, mini.accepting); tick("tarjan_scc")
    final = trim(mini, info["useful"]);               tick("trim")
    asm = dfa_to_assembly(final, pattern);            tick("codegen")
    program = assemble(asm);                          tick("assemble")
    return Compiled(pattern, postfix, nfa, raw, comp, mini, info, final, asm, program, timings)


def run_on_cpu(c: Compiled, text: str, trace: bool = False, max_cycles: int = 5_000_000):
    cpu = CPU()
    cpu.load(c.program.words)
    return cpu.run(c.symbols(text), max_cycles=max_cycles, trace=trace)


def run_all(c: Compiled, text: str, trace: bool = False):
    """Run one string through every engine and compare."""
    res = run_on_cpu(c, text, trace=trace)
    out = {
        "input": text,
        "nfa": c.nfa.accepts(text),
        "dfa": c.dfa_raw.accepts(text),
        "min_dfa": c.dfa_min.accepts(text),
        "cpu": res.status == "ACCEPT",
        "cpu_status": res.status,
        "cycles": res.cycles,
        "instructions": res.instructions,
        "cpi": round(res.cpi, 3),
        "trace": res.trace,
    }
    out["agree"] = len({out["nfa"], out["dfa"], out["min_dfa"], out["cpu"]}) == 1
    return out


def language_sample(c: Compiled, limit=20):
    """If the language is finite, list its words (uses the SCC analysis result)."""
    return None if c.scc["is_infinite"] else finite_language(c.dfa, limit)


def dot_graphs(c: Compiled):
    return {
        "nfa": __import__("regexcpu.nfa", fromlist=["x"]).nfa_to_dot(c.nfa, "ε-NFA (Thompson)"),
        "dfa": dfa_to_dot(c.dfa_raw, "DFA (subset construction)"),
        "min_dfa": dfa_to_dot(c.dfa_min, "Minimal complete DFA (red = dead states found by Tarjan)",
                              dead=c.scc["dead"]),
    }
