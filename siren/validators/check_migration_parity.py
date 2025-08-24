import re
import sys
from pathlib import Path


def extract_objects_from_migrations(migrations_dir: Path) -> set[str]:
    """Extract created relational objects (tables, materialized views) from SQL migrations.

    The architecture doc may reference materialized views (e.g., mv_note_enriched). Treat them
    as required objects alongside tables for parity checking.
    """
    created_objects: set[str] = set()
    table_pattern = re.compile(
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([a-zA-Z0-9_\.]+)", re.IGNORECASE
    )
    mv_pattern_if = re.compile(
        r"CREATE\s+MATERIALIZED\s+VIEW\s+IF\s+NOT\s+EXISTS\s+([a-zA-Z0-9_\.]+)", re.IGNORECASE
    )
    mv_pattern = re.compile(r"CREATE\s+MATERIALIZED\s+VIEW\s+([a-zA-Z0-9_\.]+)", re.IGNORECASE)
    for sql_path in sorted(migrations_dir.glob("*.sql")):
        text = sql_path.read_text(encoding="utf-8", errors="ignore")
        for m in table_pattern.finditer(text):
            created_objects.add(m.group(1))
        for m in mv_pattern_if.finditer(text):
            created_objects.add(m.group(1))
        for m in mv_pattern.finditer(text):
            created_objects.add(m.group(1))
    return created_objects


def extract_v2_tables_from_architecture(arch_text: str) -> set[str]:
    want: set[str] = set()
    # V2 pattern: scan for lens_*.table_name patterns
    for m in re.finditer(r"\blens_(rel|sem|graph)\.([a-zA-Z0-9_]+)\b", arch_text):
        schema, table = m.groups()
        want.add(f"lens_{schema}.{table}")
    # Also scan for standalone table references in V2 context
    for m in re.finditer(r"\b(mv_[a-zA-Z0-9_]+)\b", arch_text):
        want.add(m.group(1))
    return want


def normalize(name: str) -> str:
    return name.split(".")[-1]


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    arch_path = root / "docs" / "architecture.md"
    migrations_dir = root / "migrations"

    if not arch_path.exists():
        print("No architecture.md found - skipping migration parity check")
        return 0

    arch_text = arch_path.read_text(encoding="utf-8")
    mig_objects = {normalize(t) for t in extract_objects_from_migrations(migrations_dir)}
    arch_tables = {normalize(t) for t in extract_v2_tables_from_architecture(arch_text)}

    # V2 validation: Check for lens schema tables when they're documented
    # For now, skip validation until V2 architecture.md is rebuilt
    if not arch_tables:
        print("Migration parity check: No V2 lens tables found in architecture.md")
        return 0

    interesting = arch_tables

    missing = interesting - mig_objects
    if missing:
        print("Migration parity check failed: missing tables in migrations:", sorted(missing))
        return 1
    print("Migration parity check OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
