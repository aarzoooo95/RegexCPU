#!/usr/bin/env python3
"""RegexCPU command line interface.

  python main.py "(a|b)*abb" -t abb aabb ab          test strings through NFA/DFA/min-DFA/CPU
  python main.py "(a|b)*abb" -t abb --trace          show the fetch-decode-execute cycle trace
  python main.py "(a|b)*abb" --asm                   print the generated assembly + memory map
  python main.py "(a|b)*abb" --scc                   print the Tarjan SCC analysis
  python main.py "(a|b)*abb" --dot out_dir           write Graphviz .dot files
  python main.py --demo                              run the built-in demo patterns
  python main.py -i                                  interactive shell
"""
import argparse, os, sys
from regexcpu import compile_regex, run_all
from regexcpu.regex_parser import RegexError
from regexcpu.pipeline import dot_graphs, language_sample

DEMOS = [
    (r"(a|b)*abb", ["abb", "aabb", "babb", "ab", ""]),
    (r"[0-9]+(\.[0-9]+)?", ["42", "3.14", "3.", ".5"]),
    (r"[a-z]+@[a-z]+\.(com|in|org)", ["me@site.com", "a@b.in", "me@site.net"]),
    (r"ab|cd?", ["ab", "c", "cd", "abc"]),
]


def show_stats(c):
    st = c.stats()
    print(f"Pattern            : {st['pattern']}")
    print(f"Postfix            : {st['postfix']}")
    print(f"Alphabet           : {st['alphabet']}")
    print(f"epsilon-NFA        : {st['nfa_states']} states, {st['nfa_edges']} edges")
    print(f"DFA (subset)       : {st['dfa_states']} states")
    print(f"Complete DFA       : {st['dfa_complete_states']} states")
    print(f"Minimal DFA        : {st['min_dfa_states']} states")
    print(f"Tarjan SCCs        : {st['scc_count']} (largest {st['largest_scc']}, cyclic {st['cyclic_sccs']})")
    print(f"Dead states pruned : {st['dead_states'] or 'none'}")
    print(f"Language           : {'infinite' if st['is_infinite'] else 'finite -> ' + str(language_sample(c))}")
    print(f"CPU program        : {st['code_words']} code words + {st['data_words']} data words")


def show_scc(c):
    s = c.scc
    print("Tarjan output (reverse topological order of the condensation DAG):")
    for cid, comp in enumerate(s["sccs"]):
        tags = []
        if cid in s["cyclic_sccs"]: tags.append("cyclic")
        if any(v in c.dfa_min.accepting for v in comp): tags.append("accepting")
        if not any(v in s["useful"] for v in comp): tags.append("DEAD")
        print(f"  SCC {cid}: states {sorted(comp)} {' '.join(tags)}")
    print("Condensation edges:", s["condensation"] or "none")
    print("Dead states:", sorted(s["dead"]) or "none")


def show_trace(r):
    for rec in r["trace"]:
        print(f"[{rec['pc']:03d}] {rec['asm']:<22} cost={rec['cost']}  cycles={rec['cycles']}")
        for m in rec["micro"]:
            print("      " + m)
        print(f"      R = {rec['regs']}  Z={rec['z']} N={rec['n']}")


def test_strings(c, words, trace=False):
    print(f"\n{'input':<18}{'NFA':<7}{'DFA':<7}{'minDFA':<8}{'CPU':<8}{'instr':<7}{'cycles':<8}{'CPI':<7}agree")
    for w in words:
        r = run_all(c, w, trace=trace)
        yn = lambda b: "ACC" if b else "rej"
        print(f"{w!r:<18}{yn(r['nfa']):<7}{yn(r['dfa']):<7}{yn(r['min_dfa']):<8}{yn(r['cpu']):<8}"
              f"{r['instructions']:<7}{r['cycles']:<8}{r['cpi']:<7}{'OK' if r['agree'] else 'MISMATCH'}")
        if trace:
            print(); show_trace(r); print()


def main(argv=None):
    ap = argparse.ArgumentParser(description="RegexCPU - regex compiler running on a simulated CPU")
    ap.add_argument("pattern", nargs="?")
    ap.add_argument("-t", "--test", nargs="*", default=[], help="strings to test")
    ap.add_argument("--trace", action="store_true", help="print instruction-cycle trace")
    ap.add_argument("--asm", action="store_true")
    ap.add_argument("--scc", action="store_true")
    ap.add_argument("--dot", metavar="DIR")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("-i", "--interactive", action="store_true")
    a = ap.parse_args(argv)

    if a.demo:
        for pat, words in DEMOS:
            print("=" * 78); c = compile_regex(pat); show_stats(c); test_strings(c, words)
        return 0
    if a.interactive:
        print("RegexCPU interactive. Commands: type a regex, then strings. ':q' quits.")
        c = None
        while True:
            try:
                line = input("regex> " if c is None else f"[{c.pattern}] string (or new regex with ':r ...')> ")
            except EOFError:
                break
            if line.strip() == ":q": break
            try:
                if c is None or line.startswith(":r "):
                    c = compile_regex(line[3:] if line.startswith(":r ") else line); show_stats(c)
                else:
                    test_strings(c, [line])
            except RegexError as e:
                print("regex error:", e); c = None
        return 0
    if not a.pattern and a.pattern != "":
        ap.print_help(); return 1
    try:
        c = compile_regex(a.pattern)
    except RegexError as e:
        print("regex error:", e, file=sys.stderr); return 2
    show_stats(c)
    if a.scc: print(); show_scc(c)
    if a.asm:
        print("\n" + c.asm)
        print("Memory map (addr: word  source):")
        for addr, word, src in c.program.listing:
            print(f"  {addr:04d}: {word & 0xFFFFFFFF:08x}  {src.strip()}")
    if a.test: test_strings(c, a.test, trace=a.trace)
    if a.dot:
        os.makedirs(a.dot, exist_ok=True)
        for k, v in dot_graphs(c).items():
            with open(os.path.join(a.dot, f"{k}.dot"), "w", encoding="utf-8") as f: f.write(v)
        print(f"\nGraphviz files written to {a.dot}/ (render: dot -Tpng nfa.dot -o nfa.png)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
