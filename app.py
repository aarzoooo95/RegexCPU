"""RegexCPU web app (Flask).   Local:  python app.py     Production:  gunicorn app:app"""
import os
from flask import Flask, jsonify, render_template, request

from regexcpu import compile_regex, run_all
from regexcpu.regex_parser import RegexError
from regexcpu.cpu import CPUError, disassemble
from regexcpu.pipeline import language_sample
from regexcpu.render import dfa_svg, nfa_svg

MAX_PATTERN, MAX_WORDS, MAX_WORD_LEN, TRACE_STEPS = 120, 25, 400, 60
app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/run")
def api_run():
    data = request.get_json(silent=True) or {}
    pattern = data.get("pattern", "")
    words = data.get("words", [])
    if not isinstance(pattern, str) or not isinstance(words, list):
        return jsonify(error="pattern must be a string and words a list"), 400
    if len(pattern) > MAX_PATTERN:
        return jsonify(error=f"pattern too long (max {MAX_PATTERN} characters)"), 400
    words = [str(w) for w in words][:MAX_WORDS]
    if any(len(w) > MAX_WORD_LEN for w in words):
        return jsonify(error=f"test string too long (max {MAX_WORD_LEN} characters)"), 400
    try:
        c = compile_regex(pattern)
    except RegexError as e:
        return jsonify(error=f"Regex error: {e}"), 400
    if c.dfa_raw.n > 600:
        return jsonify(error=f"DFA has {c.dfa_raw.n} states - too large for the online demo (max 600)"), 400
    results, first_trace = [], []
    try:
        for i, w in enumerate(words):
            r = run_all(c, w, trace=(i == 0))
            if i == 0:
                first_trace = r["trace"][:TRACE_STEPS]
            r.pop("trace")
            results.append(r)
    except CPUError as e:
        return jsonify(error=f"CPU error: {e}"), 400
    s = c.scc
    scc_rows = []
    for cid, comp in enumerate(s["sccs"]):
        tags = []
        if cid in s["cyclic_sccs"]: tags.append("cyclic")
        if any(v in c.dfa_min.accepting for v in comp): tags.append("accepting")
        if not any(v in s["useful"] for v in comp): tags.append("dead")
        scc_rows.append({"id": cid, "states": sorted(comp), "tags": tags})
    listing = [{"addr": a, "word": f"{w & 0xFFFFFFFF:08x}",
                "text": disassemble(w) if a < c.program.code_words else f".word {w}"}
               for a, w, _ in c.program.listing]
    return jsonify(
        stats=c.stats(), results=results, scc=scc_rows, asm=c.asm, listing=listing,
        language=language_sample(c), timings={k: round(v * 1000, 3) for k, v in c.timings.items()},
        trace=[{"pc": t["pc"], "asm": t["asm"], "micro": t["micro"], "regs": t["regs"],
                "z": t["z"], "n": t["n"], "cost": t["cost"], "cycles": t["cycles"]} for t in first_trace],
        svg={"nfa": nfa_svg(c.nfa) if c.nfa.n <= 120 else None, "min_dfa": dfa_svg(c.dfa_min, c.scc["dead"])
             if c.dfa_min.n <= 60 else None},
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
