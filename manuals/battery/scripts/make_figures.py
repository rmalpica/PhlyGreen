"""Produce every figure and data file of the battery manual.

Run from anywhere with the package installed (conda env ``phlygreen``):

    conda run -n phlygreen python manuals/battery/scripts/make_figures.py

Figures go to ``manuals/battery/figures/`` (vector PDF) and the quoted numbers to
``manuals/battery/data/*.json``. Total run time is a few minutes; the Class-II designs
dominate it.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fig_cell  # noqa: E402
import fig_class_ii_mission  # noqa: E402
import fig_sizing_studies  # noqa: E402


def main():
    for name, mod in (("cell model", fig_cell), ("Class-II mission", fig_class_ii_mission),
                      ("sizing studies", fig_sizing_studies)):
        t0 = time.time()
        print(f"[{name}]")
        mod.main()
        print(f"  done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
