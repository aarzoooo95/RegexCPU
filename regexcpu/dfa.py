"""FLAT (Modules 1.8-1.9, 2.7, 2.12) - subset construction, completion, minimisation."""
from collections import deque
from dataclasses import dataclass, field
from .nfa import NFA


@dataclass
class DFA:
    alphabet: list
    delta: list                      # delta[state] = {symbol: next_state}
    start: int
    accepting: set = field(default_factory=set)

    @property
    def n(self):
        return len(self.delta)

    @property
    def edge_count(self):
        return sum(len(d) for d in self.delta)

    def is_complete(self):
        return all(len(d) == len(self.alphabet) for d in self.delta)

    def accepts(self, text: str) -> bool:
        s = self.start
        for ch in text:
            s = self.delta[s].get(ch)
            if s is None:
                return False
        return s in self.accepting

    def adjacency(self):
        return [list(d.values()) for d in self.delta]


def subset_construction(nfa: NFA) -> DFA:
    """epsilon-NFA -> (partial) DFA. The empty subset is never created."""
    alphabet = nfa.alphabet
    start = nfa.eps_closure({nfa.start})
    ids, delta, order = {start: 0}, [{}], deque([start])
    accepting = set()
    while order:
        cur = order.popleft()
        cid = ids[cur]
        if nfa.accept in cur:
            accepting.add(cid)
        for a in alphabet:
            nxt = nfa.eps_closure(nfa.move(cur, a))
            if not nxt:
                continue
            if nxt not in ids:
                ids[nxt] = len(delta)
                delta.append({})
                order.append(nxt)
            delta[cid][a] = ids[nxt]
    return DFA(alphabet, delta, 0, accepting)


def complete(dfa: DFA) -> DFA:
    """Add an explicit trap (sink) state so every state has a move on every symbol."""
    if dfa.is_complete():
        return DFA(list(dfa.alphabet), [dict(d) for d in dfa.delta], dfa.start, set(dfa.accepting))
    trap = dfa.n
    delta = [dict(d) for d in dfa.delta] + [{}]
    for d in delta:
        for a in dfa.alphabet:
            d.setdefault(a, trap)
    return DFA(list(dfa.alphabet), delta, dfa.start, set(dfa.accepting))


def _renumber(dfa: DFA, keep=None) -> DFA:
    """BFS renumbering from start (deterministic ids); optionally drop states not in keep."""
    ids, order = {dfa.start: 0}, deque([dfa.start])
    delta = [{}]
    while order:
        s = order.popleft()
        for a in dfa.alphabet:
            t = dfa.delta[s].get(a)
            if t is None or (keep is not None and t not in keep):
                continue
            if t not in ids:
                ids[t] = len(ids)
                delta.append({})
                order.append(t)
            delta[ids[s]][a] = ids[t]
    return DFA(list(dfa.alphabet), delta, 0, {ids[s] for s in dfa.accepting if s in ids})


def minimize(dfa: DFA) -> DFA:
    """Moore partition refinement on a COMPLETE DFA. O(k * n^2) worst case."""
    assert dfa.is_complete(), "minimize() needs a complete DFA"
    block = [1 if s in dfa.accepting else 0 for s in range(dfa.n)]
    while True:
        sigs, new_block = {}, [0] * dfa.n
        for s in range(dfa.n):
            sig = (block[s],) + tuple(block[dfa.delta[s][a]] for a in dfa.alphabet)
            new_block[s] = sigs.setdefault(sig, len(sigs))
        if len(sigs) == len(set(block)):
            block = new_block
            break
        block = new_block
    k = max(block) + 1
    delta = [dict() for _ in range(k)]
    for s in range(dfa.n):
        for a in dfa.alphabet:
            delta[block[s]][a] = block[dfa.delta[s][a]]
    quotient = DFA(list(dfa.alphabet), delta, block[dfa.start],
                   {block[s] for s in dfa.accepting})
    return _renumber(quotient)


def trim(dfa: DFA, useful: set) -> DFA:
    """Keep only 'useful' states (reachable and able to reach an accepting state)."""
    return _renumber(dfa, keep=useful)


def to_table(dfa: DFA):
    """Flatten to the arrays stored in CPU memory: table[state*K + symbol] and accept[state]."""
    table = []
    for s in range(dfa.n):
        for a in dfa.alphabet:
            table.append(dfa.delta[s].get(a, -1))
    accept = [1 if s in dfa.accepting else 0 for s in range(dfa.n)]
    return table, accept


def dfa_to_dot(dfa: DFA, title="DFA", dead=frozenset()) -> str:
    lines = ['digraph DFA {', '  rankdir=LR; labelloc=t; label="%s";' % title,
             '  node [shape=circle, fontsize=11]; edge [fontsize=10];',
             '  __s [shape=point];', f'  __s -> q{dfa.start};']
    for s in range(dfa.n):
        attrs = []
        if s in dfa.accepting:
            attrs.append("shape=doublecircle")
        if s in dead:
            attrs.append('style=dashed, color=red, fontcolor=red')
        if attrs:
            lines.append(f'  q{s} [{", ".join(attrs)}];')
    for s in range(dfa.n):
        grouped = {}
        for a, t in dfa.delta[s].items():
            grouped.setdefault(t, []).append(a)
        for t, syms in grouped.items():
            lbl = ",".join(syms).replace('"', '\\"')
            lines.append(f'  q{s} -> q{t} [label="{lbl}"];')
    lines.append("}")
    return "\n".join(lines)
