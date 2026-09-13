"""Validate every tracked Jupyter notebook without executing it."""

import subprocess
from pathlib import Path

import nbformat


def tracked_notebooks():
    output = subprocess.run(
        ["git", "ls-files", "*.ipynb"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [Path(line) for line in output.splitlines() if line]


def main():
    paths = tracked_notebooks()
    for path in paths:
        print(f"Checking {path}")
        if path.stat().st_size == 0:
            raise SystemExit(f"Empty notebook: {path}")
        with path.open(encoding="utf-8") as handle:
            notebook = nbformat.read(handle, as_version=4)
        nbformat.validate(notebook)
        if not notebook.cells:
            raise SystemExit(f"Notebook has no cells: {path}")
        if not any(getattr(cell, "source", "").strip() for cell in notebook.cells):
            raise SystemExit(f"Notebook has no meaningful cells: {path}")
    print(f"Validated {len(paths)} tracked notebooks.")


if __name__ == "__main__":
    main()
