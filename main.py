import sys

from expert_system.kb_verify import format_success, load_kb, verify_kb

if __name__ == "__main__":
    print(
        "Intelligent Medical Diagnosis Expert System - "
        f"setup OK (Python {sys.version.split()[0]})"
    )
    ok, errors, stats = verify_kb(load_kb())
    if not ok:
        for error in errors:
            print(f"ERROR: {error}")
        sys.exit(1)
    print(format_success(stats))
