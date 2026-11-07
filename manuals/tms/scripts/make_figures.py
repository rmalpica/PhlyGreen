"""Driver: regenerate the data (unless cached) and every figure of the TMS manual.

    cd trunk
    python ../manuals/tms/scripts/make_figures.py            # reuse data/tms_data.json if present
    python ../manuals/tms/scripts/make_figures.py --recompute  # re-run all designs (~8 min)
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import compute_data   # noqa: E402
import plots          # noqa: E402


def main():
    data = os.path.join(HERE, "..", "data", "tms_data.json")
    if "--recompute" in sys.argv or not os.path.exists(data):
        compute_data.main()
    plots.main()


if __name__ == "__main__":
    main()
