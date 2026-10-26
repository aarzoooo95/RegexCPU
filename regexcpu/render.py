"""Dependency-free SVG drawing of automata (used by the web app; no Graphviz needed).

Layered left-to-right layout (BFS depth from the start state), quadratic-Bezier edges,
double circles for accepting states, red dashed circles for dead states.
"""
from collections import deque
from html import escape

R = 17          # node radius
GAP_X, GAP_Y = 96, 70


def _layout(n, edges, start):
    adj = {}
    for u, v, _ in edges:
        adj.setdefault(u, []).append(v)
    depth, q = {start: 0}, deque([start])
    while q:
        u = q.popleft()
        for v in adj.get(u, []):
            if v not in depth:
                depth[v] = depth[u] + 1
                q.append(v)
    last = max(depth.values(), default=0)
    for s in range(n):                       # unreachable states go in an extra column
        depth.setdefault(s, last + 1)
    cols = {}
    for s in sorted(depth, key=lambda s: (depth[s], s)):
        cols.setdefault(depth[s], []).append(s)
    tallest = max(len(c) for c in cols.values())
    pos = {}
    for d, members in cols.items():
        for i, s in enumerate(members):
            y = 100 + (tallest - len(members)) * GAP_Y / 2 + i * GAP_Y
            pos[s] = (60 + d * GAP_X, y)
    width = 40 + (max(cols) + 1) * GAP_X
    height = 190 + (tallest - 1) * GAP_Y
    return pos, width, height


def compress_labels(labels):
    """['0','1','2','3','a'] -> '0-3,a'  (runs of 3+ consecutive single characters)."""
    singles = sorted({l for l in labels if len(l) == 1}, key=ord)
    others = sorted({l for l in labels if len(l) != 1})
    parts, i = [], 0
    while i < len(singles):
        j = i
        while j + 1 < len(singles) and ord(singles[j + 1]) == ord(singles[j]) + 1:
            j += 1
        if j - i >= 2:
            parts.append(f"{singles[i]}-{singles[j]}")
        else:
            parts.extend(singles[i:j + 1])
        i = j + 1
    return ",".join(parts + others)


def graph_svg(n, edges, start, accepting=(), dead=(), prefix="q"):
    """edges: iterable of (u, v, label)."""
    merged = {}
    for u, v, lbl in edges:
        merged.setdefault((u, v), []).append(lbl)
    edge_list = [(u, v, compress_labels(ls)) for (u, v), ls in merged.items()]
    pos, width, height = _layout(n, edge_list, start)
    pairs = set(merged)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
           f'width="{width}" height="{height}" font-family="monospace" font-size="12" '
           f'role="img" aria-label="automaton diagram">',
           '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
           'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" '
           'fill="currentColor"/></marker></defs>',
           '<g fill="none" stroke="currentColor" stroke-width="1.3" color="inherit">']
    labels = []
    for u, v, lbl in edge_list:
        x1, y1 = pos[u]; x2, y2 = pos[v]
        if u == v:
            out.append(f'<path d="M{x1-9},{y1-R+3} C{x1-30},{y1-R-38} {x1+30},{y1-R-38} {x1+9},{y1-R+3}" '
                       f'marker-end="url(#arr)"/>')
            labels.append((x1, y1 - R - 31, lbl))
            continue
        dx, dy = x2 - x1, y2 - y1
        dist = (dx * dx + dy * dy) ** 0.5 or 1
        nx, ny = -dy / dist, dx / dist
        back = (v, u) in pairs or pos[v][0] <= pos[u][0]
        bend = 0.28 * dist if back else 0.0
        if back and (v, u) in pairs and pos[v][0] > pos[u][0]:
            bend = 0.18 * dist
        cx, cy = (x1 + x2) / 2 + nx * bend, (y1 + y2) / 2 + ny * bend
        def trim(px, py, qx, qy):                     # move (px,py) to the circle boundary toward q
            ddx, ddy = qx - px, qy - py
            d = (ddx * ddx + ddy * ddy) ** 0.5 or 1
            return px + ddx / d * R, py + ddy / d * R
        sx, sy = trim(x1, y1, cx, cy)
        ex, ey = trim(x2, y2, cx, cy)
        out.append(f'<path d="M{sx:.1f},{sy:.1f} Q{cx:.1f},{cy:.1f} {ex:.1f},{ey:.1f}" marker-end="url(#arr)"/>')
        labels.append((0.25 * sx + 0.5 * cx + 0.25 * ex, 0.25 * sy + 0.5 * cy + 0.25 * ey - 4, lbl))
    out.append('</g>')
    # start arrow
    sx, sy = pos[start]
    out.append(f'<path d="M{sx-R-26},{sy} L{sx-R-1},{sy}" stroke="currentColor" stroke-width="1.3" '
               f'marker-end="url(#arr)"/>')
    for s in range(n):
        x, y = pos[s]
        is_dead = s in dead
        stroke = "#d03b3b" if is_dead else "currentColor"
        dash = ' stroke-dasharray="4 3"' if is_dead else ""
        out.append(f'<circle cx="{x}" cy="{y}" r="{R}" fill="none" stroke="{stroke}" stroke-width="1.5"{dash}/>')
        if s in accepting:
            out.append(f'<circle cx="{x}" cy="{y}" r="{R-4}" fill="none" stroke="{stroke}" stroke-width="1.3"/>')
        out.append(f'<text x="{x}" y="{y+4}" text-anchor="middle" fill="{stroke}">{prefix}{s}</text>')
    for x, y, lbl in labels:
        out.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" font-size="11" '
                   f'fill="currentColor" paint-order="stroke" stroke="var(--bg,#fff)" stroke-width="3">'
                   f'{escape(lbl)}</text>')
    out.append("</svg>")
    return "".join(out)


def dfa_svg(dfa, dead=()):
    edges = [(s, t, a) for s in range(dfa.n) for a, t in dfa.delta[s].items()]
    return graph_svg(dfa.n, edges, dfa.start, dfa.accepting, dead)


def nfa_svg(nfa):
    edges = [(s, t, "ε" if a is None else a) for s in range(nfa.n) for a, t in nfa.edges.get(s, ())]
    return graph_svg(nfa.n, edges, nfa.start, {nfa.accept}, ())
