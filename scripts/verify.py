"""Single entrypoint for Idea Vending Machine production verification."""

from __future__ import annotations

import compileall
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def check_python_compiles() -> None:
    targets = [ROOT / "app.py", ROOT / "src", ROOT / "tests", ROOT / "scripts"]
    for target in targets:
        if target.is_dir():
            ok = compileall.compile_dir(target, quiet=1, force=True)
        else:
            ok = compileall.compile_file(target, quiet=1, force=True)
        if not ok:
            fail(f"Python compilation failed for {target.relative_to(ROOT)}")
    print("PASS: Python compilation")


def check_forbidden_frontend_sinks() -> None:
    source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    forbidden = ["innerHTML", "outerHTML", "document.write("]
    hits = [token for token in forbidden if token in source]
    if hits:
        fail(f"forbidden frontend sink(s): {', '.join(hits)}")
    print("PASS: frontend sink guard")


def run_tests() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-v"],
        cwd=ROOT,
        check=False,
    )
    if completed.returncode != 0:
        fail("unit/integration tests")
    print("PASS: unit/integration tests")


def main() -> None:
    print("Idea Vending Machine Production Gate")
    check_python_compiles()
    check_forbidden_frontend_sinks()
    run_tests()
    print("GREEN WITH EVIDENCE")


if __name__ == "__main__":
    main()
