"""Build the code deliverable without unrelated working files."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT: Path = Path(__file__).resolve().parent
# Keep only runnable deliverables and evidence used by the report. TODO:
FILES: tuple[str, ...] = (
    "scraper.py",
    "README.md",
    "tests/test_scraper.py",
    "evidence/live-run.jsonl",
    "evidence/run-context.txt",
    "evidence/checks-typed.txt",
)


def main() -> None:
    """Package required files and any supplied task3 artifacts. TODO:

    Fail if a required file is missing. The optional task3 directory is
    included when present, excluding hidden files, bytecode and symlinks.
    """
    files: list[Path] = []
    for name in FILES:
        path = ROOT / name
        if not path.is_file():
            raise SystemExit(f"Missing required file: {name}")
        files.append(path)

    artifact_dir = ROOT / "task3"
    if artifact_dir.is_dir() and not artifact_dir.is_symlink():
        # Restrict automatic additions to the team's Task 3 artifacts. TODO:
        for path in sorted(artifact_dir.rglob("*")):
            relative = path.relative_to(ROOT)
            if (
                path.is_file()
                and not path.is_symlink()
                and ROOT in path.resolve().parents
                and not any(part.startswith(".") or part == "__pycache__"
                            for part in relative.parts)
                and path.suffix.lower() not in (".pyc", ".pyo")
            ):
                files.append(path)

    target = ROOT / "deliverables" / "cits5501-phase2-code.zip"
    target.parent.mkdir(exist_ok=True)
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, arcname=path.relative_to(ROOT).as_posix())
    print(target)
    print(f"Included {len(files)} files.")
    if not artifact_dir.is_dir() or artifact_dir.is_symlink():
        print("No optional task3 directory included.")


if __name__ == "__main__":
    main()
