"""Unit + integration + fuzz tests.  Run:  python -m unittest discover -s tests -v"""
import os, random, re, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from regexcpu import compile_regex, run_all
from regexcpu.regex_parser import parse, postfix_string, RegexError
from regexcpu.nfa import regex_to_nfa
from regexcpu.dfa import subset_construction, complete, minimize
from regexcpu.scc import tarjan_scc, kosaraju_scc, same_partition, analyze, finite_language
from regexcpu.cpu import CPU, CPUError, encode, decode, disassemble
from regexcpu.assembler import assemble, AssemblerError


# ----------------------------------------------------------------------- FLAT
class TestParser(unittest.TestCase):
    def test_postfix(self):
        self.assertEqual(postfix_string(parse("ab|c")), "a b . c |")
        self.assertEqual(postfix_string(parse("(a|b)*abb")), "a b | * a . b . b .")
        self.assertEqual(postfix_string(parse("a+b?")), "a + b ? .")

    def test_class_expansion(self):
        self.assertEqual(postfix_string(parse("[a-c]")), "a b | c |")

    def test_empty_pattern_is_epsilon(self):
        self.assertTrue(compile_regex("").dfa_raw.accepts(""))

    def test_errors(self):
        for bad in ["(a", "a)", "*a", "a||b", "|a", "a|", "()", "[a", "[]", "a\\", ".", "[^a]", "[z-a]"]:
            with self.subTest(bad=bad):
                with self.assertRaises(RegexError):
                    parse(bad)

    def test_escape(self):
        self.assertTrue(compile_regex(r"a\*b").dfa_raw.accepts("a*b"))
        self.assertFalse(compile_regex(r"a\*b").dfa_raw.accepts("aab"))


class TestAutomata(unittest.TestCase):
    def test_nfa_known(self):
        n = regex_to_nfa("(a|b)*abb")
        self.assertTrue(n.accepts("abb")); self.assertTrue(n.accepts("babb"))
        self.assertFalse(n.accepts("ab")); self.assertFalse(n.accepts(""))

    def test_thompson_state_bound(self):          # Thompson NFA has at most 2 * |postfix| states
        for p in ["a", "a|b", "(a|b)*abb", "a+b?c*"]:
            self.assertLessEqual(regex_to_nfa(p).n, 2 * len(parse(p)))

    def test_minimal_sizes(self):
        self.assertEqual(compile_regex("(a|b)*abb").dfa_min.n, 4)       # textbook result
        self.assertEqual(compile_regex("a*").dfa_min.n, 1)              # one accepting self-loop
        self.assertEqual(compile_regex("a").dfa_min.n, 3)               # start, accept, trap

    def test_minimization_preserves_language_and_is_complete(self):
        c = compile_regex("(ab|a)*b?")
        self.assertTrue(c.dfa_min.is_complete())
        self.assertLessEqual(c.dfa_min.n, c.dfa_complete.n)
        for w in ["", "a", "ab", "aab", "abab", "b", "bb", "ba"]:
            self.assertEqual(c.dfa_raw.accepts(w), c.dfa_min.accepts(w), w)

    def test_subset_blowup_family(self):          # (a|b)*a(a|b)^n needs 2^(n+1) DFA states
        n = 4
        c = compile_regex("(a|b)*a" + "(a|b)" * n)
        self.assertEqual(c.dfa_min.n, 2 ** (n + 1))


# ------------------------------------------------------------------------ DAA
class TestSCC(unittest.TestCase):
    def test_known_graph(self):
        adj = [[1], [2], [0, 3], [4], [5], [3], [5, 7], [6], []]
        got = tarjan_scc(adj)
        self.assertTrue(same_partition(got, [[0, 1, 2], [3, 4, 5], [6, 7], [8]]))

    def test_reverse_topological_order(self):
        adj = [[1], [2], [], [0]]                 # 3 -> 0 -> 1 -> 2
        order = [c[0] for c in tarjan_scc(adj)]
        self.assertEqual(order, [2, 1, 0, 3])

    def test_self_loop_and_isolated(self):
        self.assertTrue(same_partition(tarjan_scc([[0], []]), [[0], [1]]))
        self.assertEqual(tarjan_scc([]), [])

    def test_tarjan_equals_kosaraju_random(self):
        rnd = random.Random(7)
        for _ in range(300):
            n = rnd.randint(1, 40)
            adj = [[rnd.randrange(n) for _ in range(rnd.randint(0, 3))] for _ in range(n)]
            self.assertTrue(same_partition(tarjan_scc(adj), kosaraju_scc(adj)))

    def test_deep_chain_no_recursion_error(self):
        n = 200_000
        adj = [[i + 1] for i in range(n - 1)] + [[]]
        self.assertEqual(len(tarjan_scc(adj)), n)

    def test_dead_state_detection(self):
        c = compile_regex("ab*")
        trap = [s for s in range(c.dfa_min.n) if not c.dfa_min.accepting & {s} and
                all(t == s for t in c.dfa_min.delta[s].values())]
        self.assertEqual(len(trap), 1)
        self.assertEqual(c.scc["dead"], set(trap))
        self.assertEqual(c.dfa.n, c.dfa_min.n - 1)

    def test_finiteness(self):
        self.assertTrue(compile_regex("a*").scc["is_infinite"])
        self.assertFalse(compile_regex("ab|cd?").scc["is_infinite"])
        self.assertEqual(finite_language(compile_regex("ab|cd?").dfa), ["c", "ab", "cd"])


# ------------------------------------------------------------------------ COA
class TestCPU(unittest.TestCase):
    def run_prog(self, src, inp=()):
        cpu = CPU(); cpu.load(assemble(src).words)
        return cpu, cpu.run(inp)

    def test_encode_decode_roundtrip(self):
        for op, rd, rs, imm in [("LDI", 3, 0, -1), ("LDX", 7, 5, 1234), ("JMP", 0, 0, 32767), ("ADD", 1, 2, 0)]:
            from regexcpu.cpu import OPCODES
            self.assertEqual(decode(encode(op, rd, rs, imm)), (OPCODES[op], rd, rs, imm))
        self.assertEqual(disassemble(encode("CMPI", 1, 0, -1)), "CMPI  R1, -1")

    def test_arithmetic_and_flags(self):
        cpu, r = self.run_prog("LDI R0, 6\nLDI R1, 7\nMUL R0, R1\nADDI R0, -2\nCMPI R0, 40\nJEQ ok\nREJECT\nok: ACCEPT")
        self.assertEqual(cpu.regs[0], 40); self.assertEqual(r.status, "ACCEPT")

    def test_addressing_modes(self):
        cpu, _ = self.run_prog("LDI R1, 2\nLD R0, d\nLDX R2, R1, d\nMOV R3, R0\nST R2, 200\nHLT\nd: .word 11, 22, 33")
        self.assertEqual((cpu.regs[0], cpu.regs[2], cpu.regs[3], cpu.mem[200]), (11, 33, 11, 33))

    def test_cycle_accounting(self):
        _, r = self.run_prog("LDI R0, 1\nLD R1, d\nMULI R0, 3\nHLT\nd: .word 5")
        self.assertEqual(r.instructions, 4)
        self.assertEqual(r.cycles, 5 + 6 + 7 + 5)

    def test_trace_has_all_phases(self):
        cpu = CPU(); cpu.load(assemble("LD R0, d\nHLT\nd: .word 9").words)
        rec = cpu.step(trace=True)
        joined = "\n".join(rec["micro"])
        for tag in ("T0", "T1", "T2", "T3", "T4", "T5"):
            self.assertIn(tag, joined)

    def test_errors(self):
        with self.assertRaises(AssemblerError): assemble("FOO R1")
        with self.assertRaises(AssemblerError): assemble("LDI R9, 1")
        with self.assertRaises(AssemblerError): assemble("x: NOP\nx: NOP")
        with self.assertRaises(AssemblerError): assemble("JMP nowhere")
        cpu = CPU(); cpu.load([0x7F000000])
        with self.assertRaises(CPUError): cpu.run([])
        cpu = CPU(); cpu.load([encode("LDI", 0, 0, 100), encode("LDX", 1, 0, 32767)])   # EA = 32867 > memory
        with self.assertRaises(CPUError): cpu.run([])

    def test_timeout(self):
        cpu = CPU(); cpu.load(assemble("l: JMP l").words)
        self.assertEqual(cpu.run([], max_cycles=1000).status, "TIMEOUT")


# ------------------------------------------------------------- end to end
class TestEndToEnd(unittest.TestCase):
    CASES = {
        r"(a|b)*abb": ["abb", "aabb", "ab", "", "babb", "abbb", "xabb"],
        r"[a-z][a-z0-9]*": ["a", "abc1", "1abc", "", "A", "z9z"],
        r"[0-9]+(\.[0-9]+)?": ["0", "12", "3.14", "3.", ".5", "1.2.3", "abc"],
        r"[a-z]+@[a-z]+\.(com|in|org)": ["me@site.com", "a@b.in", "me@site.net", "@x.com", "me@site.comm"],
        r"(0|1)*00": ["00", "100", "1000", "01", "", "0"],
        r"a?b?c?": ["", "a", "abc", "ac", "ca", "abcc"],
        r"ab|cd?": ["ab", "c", "cd", "abc", ""],
    }

    def test_cases_against_python_re(self):
        for pat, words in self.CASES.items():
            c = compile_regex(pat)
            for w in words:
                with self.subTest(pat=pat, word=w):
                    r = run_all(c, w)
                    self.assertTrue(r["agree"])
                    self.assertEqual(r["cpu"], re.fullmatch(pat, w) is not None)

    def test_unknown_symbol_is_rejected_by_cpu(self):
        r = run_all(compile_regex("ab*"), "a#")
        self.assertFalse(r["cpu"]); self.assertTrue(r["agree"])

    def test_cycles_grow_linearly(self):
        c = compile_regex("(a|b)*")
        cyc = [run_all(c, "ab" * n)["cycles"] for n in (10, 20, 30)]
        self.assertEqual(cyc[1] - cyc[0], cyc[2] - cyc[1])

    def test_fuzz_random_regexes(self):
        rnd = random.Random(2026)

        def gen(d):
            if d == 0 or rnd.random() < 0.25:
                return rnd.choice("abc")
            k = rnd.random()
            if k < 0.35: return gen(d - 1) + gen(d - 1)
            if k < 0.6: return "(" + gen(d - 1) + "|" + gen(d - 1) + ")"
            return "(" + gen(d - 1) + ")" + rnd.choice("*+?")

        checked = 0
        for _ in range(250):
            pat = gen(4)
            c = compile_regex(pat)
            for _ in range(12):
                w = "".join(rnd.choice("abc") for _ in range(rnd.randint(0, 8)))
                r = run_all(c, w)
                self.assertTrue(r["agree"], (pat, w))
                self.assertEqual(r["cpu"], re.fullmatch(pat, w) is not None, (pat, w))
                checked += 1
        self.assertEqual(checked, 3000)


if __name__ == "__main__":
    unittest.main()
