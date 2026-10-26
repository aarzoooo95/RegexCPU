#!/usr/bin/env python3
"""Build the three per-subject submission ZIPs required by the portal.

    python package.py            (reads the name from student.json)

Output (in ./submission/):
    <Name>_COA_MicroProject.zip   <Name>_FLAT_MicroProject.zip   <Name>_DAA_MicroProject.zip
Each ZIP = full project + README.md (GitHub + deployed links) + that subject's report only.
"""
import json, os, re, zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SKIP_DIRS = {"__pycache__", ".git", "submission", ".venv"}
SUBJECTS = {"COA": "COA_Report", "FLAT": "FLAT_Report", "DAA": "DAA_Report"}


def main():
    cfg = json.load(open(os.path.join(ROOT, "student.json"), encoding="utf-8"))
    name = re.sub(r"[^A-Za-z0-9]+", "", cfg["name"].title()) or "StudentName"
    out = os.path.join(ROOT, "submission")
    os.makedirs(out, exist_ok=True)
    for subj, report in SUBJECTS.items():
        path = os.path.join(out, f"{name}_{subj}_MicroProject.zip")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for base, dirs, files in os.walk(ROOT):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for f in files:
                    full = os.path.join(base, f)
                    rel = os.path.relpath(full, ROOT)
                    if f.endswith((".zip", ".pyc")):
                        continue
                    if rel.startswith("reports" + os.sep) and f.endswith(("_Report.docx", "_Report.pdf")) \
                            and not f.startswith(report):
                        continue                      # keep only this subject's report
                    z.write(full, os.path.join("RegexCPU_MicroProject", rel))
        print("created", path)


if __name__ == "__main__":
    main()
