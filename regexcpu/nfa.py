"""FLAT (Module 2.7) - Step 2: Thompson's construction  (postfix -> epsilon-NFA)."""
from collections import defaultdict
from .regex_parser import CHAR, ALT, STAR, PLUS, OPT, CAT, EPS, RegexError, parse

EPSILON = None  # label of an epsilon edge


class NFA:
    """epsilon-NFA with exactly one start and one accepting state."""

    def __init__(self):
        self.n = 0
        self.edges = defaultdict(list)   # state -> [(symbol | None, target)]
        self.start = 0
        self.accept = 0

    def new_state(self):
        self.n += 1
        return self.n - 1

    def add(self, src, sym, dst):
        self.edges[src].append((sym, dst))

    @property
    def alphabet(self):
        return sorted({s for es in self.edges.values() for s, _ in es if s is not EPSILON})

    @property
    def edge_count(self):
        return sum(len(v) for v in self.edges.values())

    def eps_closure(self, states):
        stack, seen = list(states), set(states)
        while stack:
            s = stack.pop()
            for sym, t in self.edges.get(s, ()):
                if sym is EPSILON and t not in seen:
                    seen.add(t)
                    stack.append(t)
        return frozenset(seen)

    def move(self, states, sym):
        return {t for s in states for a, t in self.edges.get(s, ()) if a == sym}

    def accepts(self, text: str) -> bool:
        cur = self.eps_closure({self.start})
        for ch in text:
            cur = self.eps_closure(self.move(cur, ch))
            if not cur:
                return False
        return self.accept in cur


def thompson(postfix) -> NFA:
    nfa, stack = NFA(), []
    for t in postfix:
        if t.kind == CHAR:
            s, a = nfa.new_state(), nfa.new_state()
            nfa.add(s, t.value, a)
            stack.append((s, a))
        elif t.kind == EPS:
            s, a = nfa.new_state(), nfa.new_state()
            nfa.add(s, EPSILON, a)
            stack.append((s, a))
        elif t.kind == CAT:
            if len(stack) < 2:
                raise RegexError("malformed expression")
            (s2, a2), (s1, a1) = stack.pop(), stack.pop()
            nfa.add(a1, EPSILON, s2)
            stack.append((s1, a2))
        elif t.kind == ALT:
            if len(stack) < 2:
                raise RegexError("malformed expression")
            (s2, a2), (s1, a1) = stack.pop(), stack.pop()
            s, a = nfa.new_state(), nfa.new_state()
            for x in (s1, s2):
                nfa.add(s, EPSILON, x)
            for x in (a1, a2):
                nfa.add(x, EPSILON, a)
            stack.append((s, a))
        elif t.kind in (STAR, PLUS, OPT):
            if not stack:
                raise RegexError("malformed expression")
            s1, a1 = stack.pop()
            s, a = nfa.new_state(), nfa.new_state()
            nfa.add(s, EPSILON, s1)
            nfa.add(a1, EPSILON, a)
            if t.kind in (STAR, OPT):
                nfa.add(s, EPSILON, a)          # skip the operand
            if t.kind in (STAR, PLUS):
                nfa.add(a1, EPSILON, s1)        # loop back
            stack.append((s, a))
    if len(stack) != 1:
        raise RegexError("malformed expression")
    nfa.start, nfa.accept = stack[0]
    return nfa


def regex_to_nfa(pattern: str) -> NFA:
    return thompson(parse(pattern))


def nfa_to_dot(nfa: NFA, title="epsilon-NFA") -> str:
    lines = ['digraph NFA {', '  rankdir=LR; labelloc=t; label="%s";' % title,
             '  node [shape=circle, fontsize=11]; edge [fontsize=10];',
             '  __s [shape=point];', f'  __s -> q{nfa.start};',
             f'  q{nfa.accept} [shape=doublecircle];']
    for s in range(nfa.n):
        for sym, t in nfa.edges.get(s, ()):
            lbl = "ε" if sym is EPSILON else sym.replace('"', '\\"')
            lines.append(f'  q{s} -> q{t} [label="{lbl}"];')
    lines.append("}")
    return "\n".join(lines)
