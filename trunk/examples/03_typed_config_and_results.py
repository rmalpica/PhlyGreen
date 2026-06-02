"""Example 03 — Typed configuration, validation, and the two input styles.

PhlyGreen accepts inputs either as typed config objects (recommended: autocomplete +
validation) or as the legacy nested dictionaries. They are interchangeable, and configs
serialize losslessly to/from dicts. This example shows all three points.

Run it:
    cd trunk && python examples/03_typed_config_and_results.py
"""

import PhlyGreen as pg
from PhlyGreen.config import MissionConfig, ConfigError
from common import traditional_config, savefig


def main():
    # 1. Validation catches mistakes early, with a clear message.
    try:
        MissionConfig(range_mission=-10, range_diversion=220, beta_start=0.97,
                      payload_weight=4560, crew_weight=500)
    except ConfigError as e:
        print("Validation rejected a bad input:", e)

    # 2. Config <-> dict round-trip is lossless (the adapter the legacy API relies on).
    mission = MissionConfig(range_mission=750, range_diversion=220, beta_start=0.97,
                            payload_weight=4560, crew_weight=500)
    as_dict = mission.to_dict()
    print("\nMissionConfig as a legacy dict:", as_dict)
    assert MissionConfig.from_dict(as_dict).to_dict() == as_dict

    # 3. Design, then export the results as a plain dict (e.g. to JSON for a database).
    results = pg.run_design(traditional_config())   # the stateless one-call API
    print("\nResults as a dict:")
    for key, value in results.to_dict().items():
        if value is not None and not isinstance(value, dict):
            print(f"  {key:18s}: {value}")

    # 4. The AircraftResults dataclass is plot-friendly too — here a simple bar of the
    #    main mass groups straight from the returned object.
    _plot_results_bar(results)


def _plot_results_bar(results):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    groups = {
        "structure": results.WStructure, "powertrain": results.WPT,
        "fuel": results.Wf, "payload": results.WPayload, "crew": results.WCrew,
    }
    groups = {k: v for k, v in groups.items() if v}
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(list(groups), list(groups.values()), color="teal")
    ax.set_ylabel("mass [kg]"); ax.set_title(f"Mass groups (WTO {results.WTO:.0f} kg)")
    ax.grid(axis="y", alpha=0.3)
    print("\nFigures:")
    savefig(fig, "03_results_mass_groups.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
