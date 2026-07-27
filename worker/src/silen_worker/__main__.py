"""`python -m silen_worker <command>` 진입점."""

import sys

from silen_worker.cli import main

if __name__ == "__main__":
    sys.exit(main())
