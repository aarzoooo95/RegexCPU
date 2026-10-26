"""RegexCPU - a regular-expression compiler that runs on a simulated CPU.

FLAT : regex -> epsilon-NFA -> DFA -> minimal DFA          (regex_parser, nfa, dfa)
DAA  : Tarjan's strongly-connected-components analysis      (scc)
COA  : instruction-cycle CPU simulator + assembler          (cpu, assembler)
"""
from .pipeline import compile_regex, run_all  # noqa: F401

__version__ = "1.0.0"
