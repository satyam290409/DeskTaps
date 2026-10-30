"""Allow running TapDeck with `python -m tapdeck`."""

import sys

from tapdeck.main import main

if __name__ == "__main__":
    sys.exit(main())
