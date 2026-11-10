"""FLOPS nacelle mass (Aviary ``nacelle.py``), imperial units."""

from .sizing_inputs import sls_thrust_per_engine_lbf


class Nacelle:

    def __init__(self, aircraft, input):
        self.aircraft = aircraft
        self.input = input

    def NacelleMass(self):
        """Total nacelle mass [lb] of all engines: 0.25 * D * L * T^0.36 per nacelle, with D and
        L the average nacelle diameter and length [ft] and T the SLS thrust per engine [lbf],
        times the nacelle count (the engine count, plus 0.5 for a centreline engine when the
        count is odd)."""
        num_eng = self.input['ENGINE']['N_ENGINES']
        avg_diam = self.input['NACELLE']['AVG_DIAM']
        avg_length = self.input['NACELLE']['AVG_LENGTH']
        thrust = sls_thrust_per_engine_lbf(self.aircraft, self.input)
        scaler = self.input['NACELLE']['SCALER']

        nacelle_count = num_eng + (num_eng % 2) * 0.5

        self.nacellemass = 0.25 * nacelle_count * avg_diam * avg_length * thrust**0.36 * scaler

        return None
