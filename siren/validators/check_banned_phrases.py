import sys
from pathlib import Path

BANNED = [
    "docs-first",
    "no application code yet",
]


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    # V2: Check files that exist, gracefully handle missing ones
    candidate_files = [
        root / "README.md",
        root / "docs" / "api.md",
        root / "docs" / "architecture.md",
        root / "docs" / "development-workflow.md",
        root / "docs" / "v2_roadmap.md",
    ]
    files = [f for f in candidate_files if f.exists()]

    errors: list[str] = []
    for fp in files:
        try:
            text = fp.read_text(encoding="utf-8")
            for phrase in BANNED:
                if phrase in text:
                    errors.append(f"{fp}: contains banned phrase: '{phrase}'")
        except Exception as e:
            errors.append(f"{fp}: could not read file: {e}")

    if errors:
        print("Banned phrases check failed:\n" + "\n".join(errors))
        return 1
    print("Banned phrases check OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
