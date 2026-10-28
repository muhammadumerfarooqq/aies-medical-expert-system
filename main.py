import sys

from expert_system import cli
from expert_system.kb_verify import format_success, load_kb, verify_kb

if __name__ == "__main__":
    # Never crash on characters such as the en dash in a Windows console.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = cli.parse_args()
    print(
        "Intelligent Medical Diagnosis Expert System - "
        f"setup OK (Python {sys.version.split()[0]})"
    )
    kb = load_kb()
    ok, errors, stats = verify_kb(kb)
    if not ok:
        for error in errors:
            print(f"ERROR: {error}")
        sys.exit(1)
    print(format_success(stats))
    sys.exit(cli.run(kb, args))
