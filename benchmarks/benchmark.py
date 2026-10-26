"""Generate measurements + graphs used in the three reports.  python benchmarks/benchmark.py"""
import csv, os, random, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from regexcpu import compile_regex, run_all
from regexcpu.scc import tarjan_scc, kosaraju_scc
from regexcpu.pipeline import dot_graphs, run_on_cpu

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
plt.rcParams.update({"figure.figsize": (6.2, 4.0), "axes.grid": True, "grid.alpha": .3, "font.size": 10})


def save_csv(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)


def flat():
    rows = []
    for n in range(1, 10):
        pat = "(a|b)*a" + "(a|b)" * n
        t = time.perf_counter(); c = compile_regex(pat); dt = time.perf_counter() - t
        rows.append((n, c.nfa.n, c.dfa_raw.n, c.dfa_min.n, round(dt * 1000, 2)))
    save_csv("flat_blowup.csv", ["n", "nfa_states", "dfa_states", "min_dfa_states", "compile_ms"], rows)
    x = [r[0] for r in rows]
    plt.figure(); plt.semilogy(x, [r[1] for r in rows], "o-", label="ε-NFA (Thompson) – linear")
    plt.semilogy(x, [r[2] for r in rows], "s-", label="DFA (subset construction) – 2^(n+1)")
    plt.semilogy(x, [r[3] for r in rows], "^--", label="minimal DFA (Moore)")
    plt.xlabel("n  in  (a|b)*a(a|b)^n"); plt.ylabel("number of states (log scale)")
    plt.title("FLAT: regex → automata size"); plt.legend(); plt.tight_layout()
    plt.savefig(os.path.join(OUT, "flat_state_growth.png"), dpi=160); plt.close()
    return rows


def daa():
    rnd, rows = random.Random(1), []
    for v in (2_000, 5_000, 10_000, 20_000, 40_000, 80_000, 160_000):
        adj = [[rnd.randrange(v) for _ in range(3)] for _ in range(v)]
        e = sum(map(len, adj))
        best_t = best_k = 1e9
        for _ in range(3):
            t = time.perf_counter(); s1 = tarjan_scc(adj); best_t = min(best_t, time.perf_counter() - t)
            t = time.perf_counter(); s2 = kosaraju_scc(adj); best_k = min(best_k, time.perf_counter() - t)
        assert {frozenset(c) for c in s1} == {frozenset(c) for c in s2}
        rows.append((v, e, v + e, len(s1), round(best_t * 1000, 2), round(best_k * 1000, 2)))
    save_csv("daa_scc_scaling.csv", ["V", "E", "V+E", "sccs", "tarjan_ms", "kosaraju_ms"], rows)
    x = np.array([r[2] for r in rows]); yt = np.array([r[4] for r in rows]); yk = np.array([r[5] for r in rows])
    a, b = np.polyfit(x, yt, 1); r2 = 1 - ((yt - (a * x + b)) ** 2).sum() / ((yt - yt.mean()) ** 2).sum()
    plt.figure(); plt.plot(x, yt, "o-", label="Tarjan (1 pass)"); plt.plot(x, yk, "s-", label="Kosaraju (2 passes)")
    plt.plot(x, a * x + b, "k:", label=f"linear fit of Tarjan, R² = {r2:.4f}")
    plt.xlabel("V + E"); plt.ylabel("time (ms)"); plt.title("DAA: SCC running time is O(V + E)")
    plt.legend(); plt.tight_layout(); plt.savefig(os.path.join(OUT, "daa_scc_scaling.png"), dpi=160); plt.close()
    return rows, r2


def coa():
    c = compile_regex("(a|b)*abb")
    rows = []
    for n in range(0, 201, 10):
        r = run_all(c, "ab" * (n // 2) + "a" * (n % 2))
        rows.append((n, r["instructions"], r["cycles"], r["cpi"]))
    save_csv("coa_cycles.csv", ["input_len", "instructions", "cycles", "cpi"], rows)
    x = [r[0] for r in rows]
    fig, ax = plt.subplots(); ax.plot(x, [r[2] for r in rows], "o-", label="total clock cycles")
    ax.plot(x, [r[1] for r in rows], "s-", label="instructions executed")
    ax.set_xlabel("input length (symbols)"); ax.set_ylabel("count"); ax.set_title("COA: execution cost grows linearly")
    ax.legend(); fig.tight_layout(); fig.savefig(os.path.join(OUT, "coa_cycles.png"), dpi=160); plt.close(fig)
    res = run_on_cpu(c, "ab" * 50 + "abb")
    mix = sorted(res.mix.items(), key=lambda kv: -kv[1])
    plt.figure(); plt.bar([m[0] for m in mix], [m[1] for m in mix], color="#2f5bd8")
    plt.ylabel("times executed"); plt.title("COA: instruction mix, 103-symbol input")
    plt.tight_layout(); plt.savefig(os.path.join(OUT, "coa_instruction_mix.png"), dpi=160); plt.close()
    return rows, mix, res


def diagrams():
    for name, pat in (("abb", "(a|b)*abb"), ("fin", "ab|cd?")):
        for kind, dot in dot_graphs(compile_regex(pat)).items():
            base = os.path.join(OUT, "diagrams", f"{name}_{kind}")
            with open(base + ".dot", "w", encoding="utf-8") as f: f.write(dot)
            subprocess.run(["dot", "-Tpng", "-Gdpi=150", base + ".dot", "-o", base + ".png"], check=False)


if __name__ == "__main__":
    f = flat(); print("FLAT", f, flush=True)
    d, r2 = daa(); print("DAA", d, "R2=", r2, flush=True)
    c, mix, res = coa(); print("COA", c[:3], mix, res.cycles, res.instructions, flush=True)
    diagrams(); print("done ->", OUT)
