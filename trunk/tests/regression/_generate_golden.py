"""Generate golden-master reference outputs from the CURRENT code.

Run this once to freeze the baseline that the regression tests compare against::

    python tests/regression/_generate_golden.py

Re-run (and review the diff carefully) only when a change is *intended* to alter the
numerical results. The golden files capture current behavior of the dict-based API so
that later refactors (profile, powertrain, I/O) can be proven side-effect-free.

NOTE: ``trunk/Validation/JSONs`` is intentionally NOT used as the baseline: those files
were produced by an older battery API (``CellModel``/``BatteryHeating``) and do not
replay on the current code.
"""

import json
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))        # tests/ for _sample_configs
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))  # trunk/ for PhlyGreen

import _sample_configs as sc
from conftest import design_from_config

GOLDEN_DIR = os.path.join(HERE, "golden")

CASES = {
    "hybrid_parallel_atr": sc.hybrid_parallel_config,
    "traditional_atr": sc.traditional_config,
}


def main():
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    for name, config_fn in CASES.items():
        flags, kwargs = config_fn()
        aircraft = design_from_config(flags, kwargs)
        results = aircraft.results().to_dict()
        results.pop("extras", None)
        path = os.path.join(GOLDEN_DIR, f"{name}.json")
        with open(path, "w") as f:
            json.dump(results, f, indent=2, sort_keys=True)
        print(f"wrote {path}: WTO={results['WTO']:.3f}")


if __name__ == "__main__":
    main()
