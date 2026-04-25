"""Drop and recreate the schema using Alembic. Local dev only."""
from __future__ import annotations

import subprocess
import sys


def main() -> None:
    print("Running: alembic downgrade base")
    r = subprocess.run(["alembic", "downgrade", "base"], check=False)
    if r.returncode != 0:
        sys.exit(r.returncode)
    print("Running: alembic upgrade head")
    r = subprocess.run(["alembic", "upgrade", "head"], check=False)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
