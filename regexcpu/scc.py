"""DAA (Module 1.14 / 1.15) - Strongly Connected Components on the automaton graph.

* tarjan_scc    : single-pass iterative DFS with low-link values, O(V + E)
* kosaraju_scc  : two-pass DFS (used as an independent checker in the tests)
* analyze       : condensation DAG, topological order, live/dead states, loop detection

Why SCCs on a DFA?  A state is *useful* iff it is reachable from the start state AND
can reach an accepting state.  Tarjan emits SCCs in REVERSE topological order of the
condensation DAG, so one left-to-right pass over that list propagates the flag
"can reach an accepting state" without any further graph search.
"""
from collections import deque


def tarjan_scc(adj):
    """Return the list of SCCs (each a list of vertices) in reverse topological order."""
    n = len(adj)
    index, low = [-1] * n, [0] * n
    on_stack = [False] * n
    stack, sccs, counter = [], [], 0
    for root in range(n):
        if index[root] != -1:
            continue
        work = [(root, 0)]
        while work:
            v, i = work.pop()
            if i == 0:
                index[v] = low[v] = counter
                counter += 1
                stack.append(v)
                on_stack[v] = True
            descended = False
            for j in range(i, len(adj[v])):
                w = adj[v][j]
                if index[w] == -1:
                    work.append((v, j + 1))
                    work.append((w, 0))
                    descended = True
                    break
                if on_stack[w]:
                    low[v] = min(low[v], index[w])
            if descended:
                continue
            if low[v] == index[v]:          # v is the root of an SCC
                comp = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    comp.append(w)
                    if w == v:
                        break
                sccs.append(comp)
            if work:                         # return to the parent: propagate low-link
                u = work[-1][0]
                low[u] = min(low[u], low[v])
    return sccs


def kosaraju_scc(adj):
    """Two-pass algorithm: DFS finish order, then DFS on the transposed graph."""
    n = len(adj)
    seen, order = [False] * n, []
    for root in range(n):
        if seen[root]:
            continue
        seen[root] = True
        stack = [(root, 0)]
        while stack:
            v, i = stack.pop()
            if i < len(adj[v]):
                stack.append((v, i + 1))
                w = adj[v][i]
                if not seen[w]:
                    seen[w] = True
                    stack.append((w, 0))
            else:
                order.append(v)
    radj = [[] for _ in range(n)]
    for v in range(n):
        for w in adj[v]:
            radj[w].append(v)
    seen, sccs = [False] * n, []
    for root in reversed(order):
        if seen[root]:
            continue
        seen[root] = True
        comp, stack = [], [root]
        while stack:
            v = stack.pop()
            comp.append(v)
            for w in radj[v]:
                if not seen[w]:
                    seen[w] = True
                    stack.append(w)
        sccs.append(comp)
    return sccs


def reachable_from(adj, start):
    seen, q = {start}, deque([start])
    while q:
        v = q.popleft()
        for w in adj[v]:
            if w not in seen:
                seen.add(w)
                q.append(w)
    return seen


def analyze(adj, start, accepting):
    """Full SCC analysis of an automaton graph.

    Returns a dict with: sccs, comp_of, condensation (edge list), topo_order (SCC ids),
    reachable, live, useful, dead, cyclic_sccs, is_infinite.
    """
    sccs = tarjan_scc(adj)
    comp_of = {}
    for cid, comp in enumerate(sccs):
        for v in comp:
            comp_of[v] = cid
    cond = [set() for _ in sccs]
    for v in range(len(adj)):
        for w in adj[v]:
            if comp_of[v] != comp_of[w]:
                cond[comp_of[v]].add(comp_of[w])
    # Tarjan order = reverse topological: every successor SCC has a SMALLER id.
    live_comp = [False] * len(sccs)
    for cid, comp in enumerate(sccs):
        live_comp[cid] = any(v in accepting for v in comp) or any(live_comp[d] for d in cond[cid])
    live = {v for v in range(len(adj)) if live_comp[comp_of[v]]}
    reachable = reachable_from(adj, start)
    useful = live & reachable
    cyclic = [cid for cid, comp in enumerate(sccs)
              if len(comp) > 1 or comp[0] in adj[comp[0]]]
    infinite = any(any(v in useful for v in sccs[cid]) for cid in cyclic)
    return {
        "sccs": sccs,
        "comp_of": comp_of,
        "condensation": sorted((a, b) for a in range(len(sccs)) for b in cond[a]),
        "topo_order": list(range(len(sccs) - 1, -1, -1)),
        "reachable": reachable,
        "live": live,
        "useful": useful,
        "dead": set(range(len(adj))) - useful,
        "cyclic_sccs": cyclic,
        "is_infinite": infinite,
    }


def same_partition(a, b):
    """True if two SCC lists describe the same partition of the vertices."""
    return {frozenset(c) for c in a} == {frozenset(c) for c in b}


def finite_language(dfa, limit=200):
    """For a finite language (acyclic useful part) list the accepted strings via BFS by length."""
    out, frontier = [], [("", dfa.start)]
    for _ in range(dfa.n + 1):
        nxt = []
        for word, s in frontier:
            if s in dfa.accepting:
                out.append(word)
            for a in dfa.alphabet:
                t = dfa.delta[s].get(a)
                if t is not None:
                    nxt.append((word + a, t))
        frontier = nxt
        if not frontier or len(out) >= limit:
            break
    return sorted(out, key=lambda w: (len(w), w))[:limit]
