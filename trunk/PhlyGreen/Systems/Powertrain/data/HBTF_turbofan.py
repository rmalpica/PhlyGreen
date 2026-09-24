"""High-bypass turbofan pyCycle deck — *offline* map generator.

The turbofan counterpart of :mod:`.Single_spool_GT`. Running this module produces
``Turbofan_Universal_Map.csv``, which :mod:`..train_turbofan_surrogate` fits into the
artifact that :mod:`..turbofan_surrogate` loads at run time. pyCycle and OpenMDAO are needed
**only** here, never at run time.

What the map contains, and why
------------------------------
At each (altitude, Mach) the deck is solved twice: once at full throttle (``throttle_mode
'T4'``) to get the available thrust ``F_max``, and once in ``percent_thrust`` mode at each
fraction ``PC`` of it. Thrust fraction is therefore a *native* coordinate of the cycle, which
is what makes the map universal in engine size -- the same trick the turboshaft map plays with
power fraction.

Columns::

    Altitude_ft, Mach, ThrustFraction, Efficiency, TSFC, ThrustLapse,
    T3_K, P3_Pa, FAR, mdot_air3, mdot_inlet, BPR

``Efficiency`` is the **overall** efficiency ``eta_o = Fn*V / (mdot_f * LHV)``: the powertrain
graph normalises on propulsive power, so ``Pf/Pp = 1/eta_o`` is precisely a TSFC closure
(``TSFC = V/(eta_o*LHV)``). TSFC is carried alongside so results can be checked against
published engine data. ``ThrustLapse`` is ``F_max(h,M)/F_max_SLS``, giving a *fitted* thrust
lapse rather than an assumed one.

The last four columns are the combustor inlet state, in the schema
``emissions_pipeline/`` consumes. They cost nothing to export now and are exactly what a
turbofan emission-index surrogate needs later.

No size scaling is generated or applied: the turboshaft size-scaling exponent is fitted to
turboshaft SFC-vs-shaft-power data and does not describe turbofans.

Two different "reference conditions" -- do not confuse them
-----------------------------------------------------------
**1. The cycle design point: 35 000 ft / M 0.80, Fn_DES = 5900 lbf, T4_MAX = 2857 degR.**
This is where the engine's *geometry* is sized -- flow areas, mass flow, the component match.
Every other point in the map is an off-design solve against that frozen geometry. Designing at
cruise/top-of-climb is the standard convention for a transport turbofan, because that is where
the engine must produce thrust from the least air, so it sets the flow path; take-off is then a
hot, high-throttle off-design case limited by T4.

Designing instead at sea-level static would change the map, not just relabel it: the engine
would be flow-matched at sea level and would run further off-design at altitude, giving lower
component efficiency and a worse cruise TSFC. Since a transport burns most of its fuel in
cruise, that choice would bias mission fuel high. The trade is accuracy near the ground against
accuracy at altitude, and cruise is where the fuel is.

**2. The lapse normalisation: sea level, M 0.001.**
``ThrustLapse`` is F_max(h, M) / F00, and F00 is measured here, which is what makes
``EnergyConfig.turbofan_design_thrust`` mean the familiar sea-level-static rating (and what lets
``Powertrain.WeightPowertrain`` turn it into a mass through an installed thrust-to-weight).
This one IS just a convention: normalising at top of climb instead would give lapse values above
1 near the ground and would require the quoted "design thrust" to be read as a top-of-climb
rating. The *efficiency* map is unaffected either way, because its third coordinate is the
thrust fraction F/F_available(h, M), which is independent of the normalising reference -- and
that is also why one map serves engines of any size.

Cycle model
-----------
The ``HBTF`` / ``viewer`` definitions below are taken from pyCycle's
``example_cycles/high_bypass_turbofan.py`` (OpenMDAO/pyCycle, Apache-2.0) and vendored
unchanged, as ``Single_spool_GT.py`` vendors the turboshaft cycle. The design point is
CFM56-class: separate-flow 2-spool, BPR 5.105, fan PR 1.685, OPR ~30.

Toolchain: the shipped map was generated with **om-pycycle 4.4.0** (imports as ``pycycle``;
``pip install pycycle`` is a different, unrelated project) on openmdao 3.44.0, Python 3.12.
pyCycle is not part of OpenMDAO -- it is a separate library built on it, and it tracks
OpenMDAO's API closely, so both are pinned in ``requirements-dev.txt``. See ``README.md`` in
this folder for the full provenance and for what to re-check after regenerating.

Run with::

    python HBTF_turbofan.py          # ~45 min, resumable
"""

import os
import sys
import time

import numpy as np

import openmdao.api as om

import pycycle.api as pyc


class HBTF(pyc.Cycle):

    def initialize(self):
        # Initialize the model here by setting option variables such as a switch for design vs off-des cases
        self.options.declare('throttle_mode', default='T4', values=['T4', 'percent_thrust'])

        super().initialize()


    def setup(self):
        #Setup the problem by including all the relavant components here - comp, burner, turbine etc
        
        #Create any relavent short hands here:
        design = self.options['design']
        
        USE_TABULAR = False
        if USE_TABULAR: 
            self.options['thermo_method'] = 'TABULAR'
            self.options['thermo_data'] = pyc.AIR_JETA_TAB_SPEC
            FUEL_TYPE = 'FAR'
        else: 
            self.options['thermo_method'] = 'CEA'
            self.options['thermo_data'] = pyc.species_data.janaf
            FUEL_TYPE = 'Jet-A(g)'

        
        #Add subsystems to build the engine deck:
        self.add_subsystem('fc', pyc.FlightConditions())
        self.add_subsystem('inlet', pyc.Inlet())
        
        # Note variable promotion for the fan -- 
        # the LP spool speed and the fan speed are INPUTS that are promoted:
        # Note here that promotion aliases are used. Here Nmech is being aliased to LP_Nmech
        # check out: http://openmdao.org/twodocs/versions/latest/features/core_features/grouping_components/add_subsystem.html?highlight=alias
        self.add_subsystem('fan', pyc.Compressor(map_data=pyc.FanMap,
                                        bleed_names=[], map_extrap=True), promotes_inputs=[('Nmech','LP_Nmech')])
        self.add_subsystem('splitter', pyc.Splitter())
        self.add_subsystem('duct4', pyc.Duct())
        self.add_subsystem('lpc', pyc.Compressor(map_data=pyc.LPCMap,
                                        map_extrap=True),promotes_inputs=[('Nmech','LP_Nmech')])
        self.add_subsystem('duct6', pyc.Duct())
        self.add_subsystem('hpc', pyc.Compressor(map_data=pyc.HPCMap,
                                        bleed_names=['cool1','cool2','cust'], map_extrap=True),promotes_inputs=[('Nmech','HP_Nmech')])
        self.add_subsystem('bld3', pyc.BleedOut(bleed_names=['cool3','cool4']))
        self.add_subsystem('burner', pyc.Combustor(fuel_type=FUEL_TYPE))
        self.add_subsystem('hpt', pyc.Turbine(map_data=pyc.HPTMap,
                                        bleed_names=['cool3','cool4'], map_extrap=True),promotes_inputs=[('Nmech','HP_Nmech')])
        self.add_subsystem('duct11', pyc.Duct())
        self.add_subsystem('lpt', pyc.Turbine(map_data=pyc.LPTMap,
                                        bleed_names=['cool1','cool2'], map_extrap=True),promotes_inputs=[('Nmech','LP_Nmech')])
        self.add_subsystem('duct13', pyc.Duct())
        self.add_subsystem('core_nozz', pyc.Nozzle(nozzType='CV', lossCoef='Cv'))

        self.add_subsystem('byp_bld', pyc.BleedOut(bleed_names=['bypBld']))
        self.add_subsystem('duct15', pyc.Duct())
        self.add_subsystem('byp_nozz', pyc.Nozzle(nozzType='CV', lossCoef='Cv'))
        
        #Create shaft instances. Note that LP shaft has 3 ports! => no gearbox
        self.add_subsystem('lp_shaft', pyc.Shaft(num_ports=3),promotes_inputs=[('Nmech','LP_Nmech')])
        self.add_subsystem('hp_shaft', pyc.Shaft(num_ports=2),promotes_inputs=[('Nmech','HP_Nmech')])
        self.add_subsystem('perf', pyc.Performance(num_nozzles=2, num_burners=1))
    
        # Now use the explicit connect method to make connections -- connect(<from>, <to>)
        
        #Connect the inputs to perf group
        self.connect('inlet.Fl_O:tot:P', 'perf.Pt2')
        self.connect('hpc.Fl_O:tot:P', 'perf.Pt3')
        self.connect('burner.Wfuel', 'perf.Wfuel_0')
        self.connect('inlet.F_ram', 'perf.ram_drag')
        self.connect('core_nozz.Fg', 'perf.Fg_0')
        self.connect('byp_nozz.Fg', 'perf.Fg_1')
        
        #LP-shaft connections
        self.connect('fan.trq', 'lp_shaft.trq_0')
        self.connect('lpc.trq', 'lp_shaft.trq_1')
        self.connect('lpt.trq', 'lp_shaft.trq_2')
        #HP-shaft connections
        self.connect('hpc.trq', 'hp_shaft.trq_0')
        self.connect('hpt.trq', 'hp_shaft.trq_1')
        #Ideally expanding flow by conneting flight condition static pressure to nozzle exhaust pressure
        self.connect('fc.Fl_O:stat:P', 'core_nozz.Ps_exhaust')
        self.connect('fc.Fl_O:stat:P', 'byp_nozz.Ps_exhaust')
        
        #Create a balance component
        # Balances can be a bit confusing, here's some explanation -
        #   State Variables:
        #           (W)        Inlet mass flow rate to implictly balance thrust
        #                      LHS: perf.Fn  == RHS: Thrust requirement (set when TF is instantiated)
        #
        #           (FAR)      Fuel-air ratio to balance Tt4
        #                      LHS: burner.Fl_O:tot:T  == RHS: Tt4 target (set when TF is instantiated)
        #
        #           (lpt_PR)   LPT press ratio to balance shaft power on the low spool
        #           (hpt_PR)   HPT press ratio to balance shaft power on the high spool
        # Ref: look at the XDSM diagrams in the pyCycle paper and this:
        # http://openmdao.org/twodocs/versions/latest/features/building_blocks/components/balance_comp.html

        balance = self.add_subsystem('balance', om.BalanceComp())
        if design:
            balance.add_balance('W', units='lbm/s', eq_units='lbf')
            #Here balance.W is implicit state variable that is the OUTPUT of balance object
            self.connect('balance.W', 'fc.W') #Connect the output of balance to the relevant input
            self.connect('perf.Fn', 'balance.lhs:W')       #This statement makes perf.Fn the LHS of the balance eqn.
            self.promotes('balance', inputs=[('rhs:W', 'Fn_DES')])

            balance.add_balance('FAR', eq_units='degR', lower=1e-4, val=.017)
            self.connect('balance.FAR', 'burner.Fl_I:FAR')
            self.connect('burner.Fl_O:tot:T', 'balance.lhs:FAR')
            self.promotes('balance', inputs=[('rhs:FAR', 'T4_MAX')])
            
            # Note that for the following two balances the mult val is set to -1 so that the NET torque is zero
            balance.add_balance('lpt_PR', val=1.5, lower=1.001, upper=8,
                                eq_units='hp', use_mult=True, mult_val=-1)
            self.connect('balance.lpt_PR', 'lpt.PR')
            self.connect('lp_shaft.pwr_in_real', 'balance.lhs:lpt_PR')
            self.connect('lp_shaft.pwr_out_real', 'balance.rhs:lpt_PR')

            balance.add_balance('hpt_PR', val=1.5, lower=1.001, upper=8,
                                eq_units='hp', use_mult=True, mult_val=-1)
            self.connect('balance.hpt_PR', 'hpt.PR')
            self.connect('hp_shaft.pwr_in_real', 'balance.lhs:hpt_PR')
            self.connect('hp_shaft.pwr_out_real', 'balance.rhs:hpt_PR')

        else:
            
            #In OFF-DESIGN mode we need to redefine the balances:
            #   State Variables:
            #           (W)        Inlet mass flow rate to balance core flow area
            #                      LHS: core_nozz.Throat:stat:area == Area from DESIGN calculation 
            #
            #           (FAR)      Fuel-air ratio to balance Thrust req.
            #                      LHS: perf.Fn  == RHS: Thrust requirement (set when TF is instantiated)
            #
            #           (BPR)      Bypass ratio to balance byp. noz. area
            #                      LHS: byp_nozz.Throat:stat:area == Area from DESIGN calculation
            #
            #           (lp_Nmech)   LP spool speed to balance shaft power on the low spool
            #           (hp_Nmech)   HP spool speed to balance shaft power on the high spool

            if self.options['throttle_mode'] == 'T4': 
                balance.add_balance('FAR', val=0.017, lower=1e-4, eq_units='degR')
                self.connect('balance.FAR', 'burner.Fl_I:FAR')
                self.connect('burner.Fl_O:tot:T', 'balance.lhs:FAR')
                self.promotes('balance', inputs=[('rhs:FAR', 'T4_MAX')])

            elif self.options['throttle_mode'] == 'percent_thrust': 
                balance.add_balance('FAR', val=0.017, lower=1e-4, eq_units='lbf', use_mult=True)
                self.connect('balance.FAR', 'burner.Fl_I:FAR')
                self.connect('perf.Fn', 'balance.rhs:FAR')
                self.promotes('balance', inputs=[('mult:FAR', 'PC'), ('lhs:FAR', 'Fn_max')])


            balance.add_balance('W', units='lbm/s', lower=10., upper=1000., eq_units='inch**2')
            self.connect('balance.W', 'fc.W')
            self.connect('core_nozz.Throat:stat:area', 'balance.lhs:W')

            balance.add_balance('BPR', lower=2., upper=10., eq_units='inch**2')
            self.connect('balance.BPR', 'splitter.BPR')
            self.connect('byp_nozz.Throat:stat:area', 'balance.lhs:BPR')

            # Again for the following two balances the mult val is set to -1 so that the NET torque is zero
            balance.add_balance('lp_Nmech', val=1.5, units='rpm', lower=500., eq_units='hp', use_mult=True, mult_val=-1)
            self.connect('balance.lp_Nmech', 'LP_Nmech')
            self.connect('lp_shaft.pwr_in_real', 'balance.lhs:lp_Nmech')
            self.connect('lp_shaft.pwr_out_real', 'balance.rhs:lp_Nmech')

            balance.add_balance('hp_Nmech', val=1.5, units='rpm', lower=500., eq_units='hp', use_mult=True, mult_val=-1)
            self.connect('balance.hp_Nmech', 'HP_Nmech')
            self.connect('hp_shaft.pwr_in_real', 'balance.lhs:hp_Nmech')
            self.connect('hp_shaft.pwr_out_real', 'balance.rhs:hp_Nmech')
            
            # Specify the order in which the subsystems are executed:
            
            # self.set_order(['balance', 'fc', 'inlet', 'fan', 'splitter', 'duct4', 'lpc', 'duct6', 'hpc', 'bld3', 'burner', 'hpt', 'duct11',
            #                 'lpt', 'duct13', 'core_nozz', 'byp_bld', 'duct15', 'byp_nozz', 'lp_shaft', 'hp_shaft', 'perf'])
        
        # Set up all the flow connections:
        self.pyc_connect_flow('fc.Fl_O', 'inlet.Fl_I')
        self.pyc_connect_flow('inlet.Fl_O', 'fan.Fl_I')
        self.pyc_connect_flow('fan.Fl_O', 'splitter.Fl_I')
        self.pyc_connect_flow('splitter.Fl_O1', 'duct4.Fl_I')
        self.pyc_connect_flow('duct4.Fl_O', 'lpc.Fl_I')
        self.pyc_connect_flow('lpc.Fl_O', 'duct6.Fl_I')
        self.pyc_connect_flow('duct6.Fl_O', 'hpc.Fl_I')
        self.pyc_connect_flow('hpc.Fl_O', 'bld3.Fl_I')
        self.pyc_connect_flow('bld3.Fl_O', 'burner.Fl_I')
        self.pyc_connect_flow('burner.Fl_O', 'hpt.Fl_I')
        self.pyc_connect_flow('hpt.Fl_O', 'duct11.Fl_I')
        self.pyc_connect_flow('duct11.Fl_O', 'lpt.Fl_I')
        self.pyc_connect_flow('lpt.Fl_O', 'duct13.Fl_I')
        self.pyc_connect_flow('duct13.Fl_O','core_nozz.Fl_I')
        self.pyc_connect_flow('splitter.Fl_O2', 'byp_bld.Fl_I')
        self.pyc_connect_flow('byp_bld.Fl_O', 'duct15.Fl_I')
        self.pyc_connect_flow('duct15.Fl_O', 'byp_nozz.Fl_I')

        #Bleed flows:
        self.pyc_connect_flow('hpc.cool1', 'lpt.cool1', connect_stat=False)
        self.pyc_connect_flow('hpc.cool2', 'lpt.cool2', connect_stat=False)
        self.pyc_connect_flow('bld3.cool3', 'hpt.cool3', connect_stat=False)
        self.pyc_connect_flow('bld3.cool4', 'hpt.cool4', connect_stat=False)
        
        #Specify solver settings:
        newton = self.nonlinear_solver = om.NewtonSolver()
        newton.options['atol'] = 1e-8

        # set this very small, so it never activates and we rely on atol
        newton.options['rtol'] = 1e-99 
        newton.options['iprint'] = 2
        newton.options['maxiter'] = 50
        newton.options['solve_subsystems'] = True
        newton.options['max_sub_solves'] = 1000
        newton.options['reraise_child_analysiserror'] = False
        # ls = newton.linesearch = BoundsEnforceLS()
        ls = newton.linesearch = om.ArmijoGoldsteinLS()
        ls.options['maxiter'] = 3
        ls.options['rho'] = 0.75
        # ls.options['print_bound_enforce'] = True

        self.linear_solver = om.DirectSolver()

        super().setup()

def viewer(prob, pt, file=sys.stdout):
    """
    print a report of all the relevant cycle properties
    """

    if pt == 'DESIGN':
        MN = prob['DESIGN.fc.Fl_O:stat:MN']
        LPT_PR = prob['DESIGN.balance.lpt_PR']
        HPT_PR = prob['DESIGN.balance.hpt_PR']
        FAR = prob['DESIGN.balance.FAR']
    else:
        MN = prob[pt+'.fc.Fl_O:stat:MN']
        LPT_PR = prob[pt+'.lpt.PR']
        HPT_PR = prob[pt+'.hpt.PR']
        FAR = prob[pt+'.balance.FAR']

    summary_data = (MN, prob[pt+'.fc.alt'], prob[pt+'.inlet.Fl_O:stat:W'], prob[pt+'.perf.Fn'],
                        prob[pt+'.perf.Fg'], prob[pt+'.inlet.F_ram'], prob[pt+'.perf.OPR'],
                        prob[pt+'.perf.TSFC'], prob[pt+'.splitter.BPR'])

    print(file=file, flush=True)
    print(file=file, flush=True)
    print(file=file, flush=True)
    print("----------------------------------------------------------------------------", file=file, flush=True)
    print("                              POINT:", pt, file=file, flush=True)
    print("----------------------------------------------------------------------------", file=file, flush=True)
    print("                       PERFORMANCE CHARACTERISTICS", file=file, flush=True)
    print("    Mach      Alt       W      Fn      Fg    Fram     OPR     TSFC      BPR ", file=file, flush=True)
    print(" %7.5f  %7.1f %7.3f %7.1f %7.1f %7.1f %7.3f  %7.5f  %7.3f" %summary_data, file=file, flush=True)


    fs_names = ['fc.Fl_O', 'inlet.Fl_O', 'fan.Fl_O', 'splitter.Fl_O1', 'splitter.Fl_O2',
                'duct4.Fl_O', 'lpc.Fl_O', 'duct6.Fl_O', 'hpc.Fl_O', 'bld3.Fl_O', 'burner.Fl_O',
                'hpt.Fl_O', 'duct11.Fl_O', 'lpt.Fl_O', 'duct13.Fl_O', 'core_nozz.Fl_O', 'byp_bld.Fl_O',
                'duct15.Fl_O', 'byp_nozz.Fl_O']
    fs_full_names = [f'{pt}.{fs}' for fs in fs_names]
    pyc.print_flow_station(prob, fs_full_names, file=file)

    comp_names = ['fan', 'lpc', 'hpc']
    comp_full_names = [f'{pt}.{c}' for c in comp_names]
    pyc.print_compressor(prob, comp_full_names, file=file)

    pyc.print_burner(prob, [f'{pt}.burner'], file=file)

    turb_names = ['hpt', 'lpt']
    turb_full_names = [f'{pt}.{t}' for t in turb_names]
    pyc.print_turbine(prob, turb_full_names, file=file)

    noz_names = ['core_nozz', 'byp_nozz']
    noz_full_names = [f'{pt}.{n}' for n in noz_names]
    pyc.print_nozzle(prob, noz_full_names, file=file)

    shaft_names = ['hp_shaft', 'lp_shaft']
    shaft_full_names = [f'{pt}.{s}' for s in shaft_names]
    pyc.print_shaft(prob, shaft_full_names, file=file)

    bleed_names = ['hpc', 'bld3', 'byp_bld']
    bleed_full_names = [f'{pt}.{b}' for b in bleed_names]
    pyc.print_bleed(prob, bleed_full_names, file=file)



# ==============================================================================
# Multi-point model: one design point + a full-throttle and a part-power off-design
# point that share it. Fn_max flows from the full-throttle point into the part-power
# point, so 'PC' is literally the thrust fraction at that flight condition.
# ==============================================================================

_HEADER = ("Altitude_ft,Mach,ThrustFraction,Efficiency,TSFC,ThrustLapse,"
           "T3_K,P3_Pa,FAR,mdot_air3,mdot_inlet,BPR")

REF_FN_LBF = 5900.0      # design-point net thrust at 35 kft / M 0.8 (CFM56 class)
T4_MAX_DEGR = 2857.0
LHV_JPKG = 43.0e6        # Jet-A lower heating value, matching Single_spool_GT.py


class MPhbtf(pyc.MPCycle):

    def setup(self):

        self.pyc_add_pnt('DESIGN', HBTF(thermo_method='CEA'))

        self.set_input_defaults('DESIGN.inlet.MN', 0.751)
        self.set_input_defaults('DESIGN.fan.MN', 0.4578)
        self.set_input_defaults('DESIGN.splitter.BPR', 5.105)
        self.set_input_defaults('DESIGN.splitter.MN1', 0.3104)
        self.set_input_defaults('DESIGN.splitter.MN2', 0.4518)
        self.set_input_defaults('DESIGN.duct4.MN', 0.3121)
        self.set_input_defaults('DESIGN.lpc.MN', 0.3059)
        self.set_input_defaults('DESIGN.duct6.MN', 0.3563)
        self.set_input_defaults('DESIGN.hpc.MN', 0.2442)
        self.set_input_defaults('DESIGN.bld3.MN', 0.3000)
        self.set_input_defaults('DESIGN.burner.MN', 0.1025)
        self.set_input_defaults('DESIGN.hpt.MN', 0.3650)
        self.set_input_defaults('DESIGN.duct11.MN', 0.3063)
        self.set_input_defaults('DESIGN.lpt.MN', 0.4127)
        self.set_input_defaults('DESIGN.duct13.MN', 0.4463)
        self.set_input_defaults('DESIGN.byp_bld.MN', 0.4489)
        self.set_input_defaults('DESIGN.duct15.MN', 0.4589)
        self.set_input_defaults('DESIGN.LP_Nmech', 4666.1, units='rpm')
        self.set_input_defaults('DESIGN.HP_Nmech', 14705.7, units='rpm')

        self.pyc_add_cycle_param('burner.dPqP', 0.0540)
        self.pyc_add_cycle_param('core_nozz.Cv', 0.9933)
        self.pyc_add_cycle_param('byp_nozz.Cv', 0.9939)
        self.pyc_add_cycle_param('hpc.cool1:frac_W', 0.050708)
        self.pyc_add_cycle_param('hpc.cool1:frac_P', 0.5)
        self.pyc_add_cycle_param('hpc.cool1:frac_work', 0.5)
        self.pyc_add_cycle_param('hpc.cool2:frac_W', 0.020274)
        self.pyc_add_cycle_param('hpc.cool2:frac_P', 0.55)
        self.pyc_add_cycle_param('hpc.cool2:frac_work', 0.5)
        self.pyc_add_cycle_param('bld3.cool3:frac_W', 0.067214)
        self.pyc_add_cycle_param('bld3.cool4:frac_W', 0.101256)
        self.pyc_add_cycle_param('hpc.cust:frac_P', 0.5)
        self.pyc_add_cycle_param('hpc.cust:frac_work', 0.5)
        self.pyc_add_cycle_param('hpc.cust:frac_W', 0.0445)
        self.pyc_add_cycle_param('hpt.cool3:frac_P', 1.0)
        self.pyc_add_cycle_param('hpt.cool4:frac_P', 0.0)
        self.pyc_add_cycle_param('lpt.cool1:frac_P', 1.0)
        self.pyc_add_cycle_param('lpt.cool2:frac_P', 0.0)
        self.pyc_add_cycle_param('hp_shaft.HPX', 250.0, units='hp')

        self.od_pts = ['OD_full_pwr', 'OD_part_pwr']

        self.pyc_add_pnt('OD_full_pwr',
                         HBTF(design=False, thermo_method='CEA', throttle_mode='T4'))
        self.set_input_defaults('OD_full_pwr.fc.MN', 0.8)
        self.set_input_defaults('OD_full_pwr.fc.alt', 35000, units='ft')
        self.set_input_defaults('OD_full_pwr.fc.dTs', 0., units='degR')

        self.pyc_add_pnt('OD_part_pwr',
                         HBTF(design=False, thermo_method='CEA', throttle_mode='percent_thrust'))
        self.set_input_defaults('OD_part_pwr.fc.MN', 0.8)
        self.set_input_defaults('OD_part_pwr.fc.alt', 35000, units='ft')
        self.set_input_defaults('OD_part_pwr.fc.dTs', 0., units='degR')

        # This connection is what makes 'PC' a thrust FRACTION at the current condition.
        self.connect('OD_full_pwr.perf.Fn', 'OD_part_pwr.Fn_max')

        self.pyc_use_default_des_od_conns()
        self.pyc_connect_des_od('core_nozz.Throat:stat:area', 'balance.rhs:W')
        self.pyc_connect_des_od('byp_nozz.Throat:stat:area', 'balance.rhs:BPR')

        super().setup()


# ==============================================================================
# Envelope sweep -> Turbofan_Universal_Map.csv
# ==============================================================================

def _isa_delta(alt_ft):
    """ISA pressure ratio (troposphere), used only to scale the mass-flow guess."""
    t_r = max(518.67 - 3.566e-3 * alt_ft, 390.0)
    return (t_r / 518.67) ** 5.2561


def _set_guesses(prob, alt_ft=0.0):
    """(Re)seed the balances for a new flight condition.

    Off-design Newton solves are only as good as their starting point, and marching from a
    distant previous solution is what makes them fail silently: `run_model` does not raise on
    non-convergence, so a stalled solve returns whatever state it reached. Re-seeding from
    known-good values (with the corrected mass flow scaled by ambient pressure) at every new
    (altitude, Mach) keeps every solve close to a physical solution.
    """
    prob['DESIGN.balance.FAR'] = 0.025
    prob['DESIGN.balance.W'] = 100.
    prob['DESIGN.balance.lpt_PR'] = 4.0
    prob['DESIGN.balance.hpt_PR'] = 3.0
    prob['DESIGN.fc.balance.Pt'] = 5.2
    prob['DESIGN.fc.balance.Tt'] = 440.0
    for pt in ['OD_full_pwr', 'OD_part_pwr']:
        prob[pt + '.balance.FAR'] = 0.02467
        prob[pt + '.balance.W'] = 300. * _isa_delta(alt_ft)
        prob[pt + '.balance.BPR'] = 5.105
        prob[pt + '.balance.lp_Nmech'] = 5000.
        prob[pt + '.balance.hp_Nmech'] = 15000.
        prob[pt + '.hpt.PR'] = 3.
        prob[pt + '.lpt.PR'] = 4.
        prob[pt + '.fan.map.RlineMap'] = 2.0
        prob[pt + '.lpc.map.RlineMap'] = 2.0
        prob[pt + '.hpc.map.RlineMap'] = 2.0


def _state(prob, pt):
    """Overall efficiency, TSFC and the combustor inlet state at an off-design point."""
    g = lambda k, **kw: float(prob.get_val(f'{pt}.{k}', **kw)[0])

    fn_lbf = g('perf.Fn')
    mach = g('fc.Fl_O:stat:MN')
    # True airspeed from the freestream static temperature: a = sqrt(gamma R T).
    t_static_r = g('fc.Fl_O:stat:T')
    v_ms = mach * 20.0468 * np.sqrt(t_static_r / 1.8)

    wfuel_lbm_s = g('perf.Wfuel')
    mdot_f = wfuel_lbm_s * 0.45359237                      # kg/s
    fn_n = fn_lbf * 4.4482216153                           # N

    eta_o = fn_n * v_ms / max(mdot_f * LHV_JPKG, 1e-9)
    tsfc = mdot_f / max(fn_n, 1e-9)                        # kg/(N s)

    return dict(
        Fn_N=fn_n, Mach=mach, eta_o=eta_o, TSFC=tsfc,
        # Combustor inlet = compressor exit (station 3), for the Phase-2 emissions CRN.
        T3_K=g('bld3.Fl_O:tot:T') / 1.8,                   # degR -> K
        P3_Pa=g('bld3.Fl_O:tot:P') * 6894.757,             # psi -> Pa
        FAR=g('balance.FAR'),
        mdot_air3=g('bld3.Fl_O:stat:W') * 0.45359237,      # lbm/s -> kg/s
        # TOTAL ingested air (station 2, core + bypass) straight from the inlet, and the
        # bypass ratio that produced it. BPR is an off-design BALANCE variable here -- it is
        # solved against the bypass-nozzle throat area, bounded 2-10 -- so it moves across the
        # envelope and total flow cannot be recovered from the core flow and a fixed BPR.
        mdot_inlet=g('inlet.Fl_O:stat:W') * 0.45359237,    # lbm/s -> kg/s
        BPR=g('splitter.BPR'),
    )


def _load_existing(path):
    """Return ``(rows, done_keys)`` from a partially written map, or empty if there is none."""
    if not os.path.isfile(path):
        return [], set()
    try:
        data = np.loadtxt(path, delimiter=",", skiprows=1, ndmin=2)
    except Exception:
        return [], set()
    if data.size == 0:
        return [], set()
    rows = [list(r) for r in data]
    done = {(round(r[0], 3), round(r[1], 4), round(r[2], 4)) for r in rows}
    return rows, done


def _reject_reason(full, part, pc, fn_max_sls, eta, tsfc):
    """Return why this point must be rejected, or None if it is trustworthy.

    `prob.run_model()` does NOT raise when the off-design Newton solve stalls -- it returns
    whatever state it reached. Recording that silently produced thrust lapses above 1.0 and
    OPRs in the tens of thousands. So every point is checked against physics it must satisfy
    by construction before it is allowed into the map.
    """
    if not np.isfinite(eta) or not np.isfinite(tsfc):
        return "non-finite eta_o/TSFC"
    # The part-power point is solved in 'percent_thrust' mode against Fn_max from the
    # full-throttle point, so this identity holds exactly when the balance converged --
    # it is the most direct convergence test available.
    pc_actual = part['Fn_N'] / max(full['Fn_N'], 1e-9)
    if abs(pc_actual - pc) > 0.02:
        return f"thrust fraction did not converge (asked {pc:.2f}, got {pc_actual:.3f})"
    # Thrust cannot exceed the sea-level-static value.
    lapse = full['Fn_N'] / fn_max_sls
    if not (0.02 < lapse <= 1.02):
        return f"unphysical thrust lapse {lapse:.3f}"
    # Compressor exit pressure must stay in a sane OPR band for this cycle.
    opr = part['P3_Pa'] / 101325.0
    if not (5.0 < opr < 60.0):
        return f"unphysical OPR {opr:.0f}"
    if not (0.05 < eta < 0.65):
        return f"eta_o {eta:.3f} out of range"
    return None


# The flight envelope is not a rectangle, and sweeping it as one is what makes a turbofan
# deck look unreliable. Mach 0.2 at 39,000 ft is not a condition any aircraft flies: the
# engine is effectively windmilling, OPR collapses to 3-5 and the off-design Newton solve
# has no physical solution to find. Each Mach therefore carries the altitudes where it is
# actually flown -- low Mach near the ground, high Mach only at altitude.
ENVELOPE = [
    # Each Mach carries the altitudes at which it is actually flown: low Mach near the ground,
    # high Mach only at altitude. The columns are marched bottom-up with a warm start, so the
    # altitude steps are also the continuation path that gets the high points to converge.
    #
    # This is the set that CONVERGES, not the set that was attempted. A denser grid was tried
    # (M 0.80 at every altitude; M 0.75 at 32 500 ft; M 0.85 at 25 000 ft) and the off-design
    # balance would not hold there even with a warm start and a re-seeded retry; `_reject_reason`
    # refuses those rather than record unconverged states. M 0.80 is bracketed by the
    # well-covered 0.75 and 0.85 columns.
    #
    # Note the high-Mach columns are SPLIT into a low and a high segment. Each entry gets fresh
    # guesses at its first altitude, and that matters: marching M 0.75 up from sea level diverges
    # at 20 000 ft (the part-power balance runs away to a negative thrust fraction), whereas
    # starting a fresh segment at 20 000 ft walks cleanly to 35 000 ft. The split is the
    # continuation path, not cosmetic -- merging these entries breaks the cruise columns.
    # For the same reason M 0.85 carries a 25 000 ft step: without it the 20 -> 30 kft jump is
    # too large and the column stops at 20 000 ft.
    (0.20, [0., 5000., 10000.]),
    (0.30, [0., 5000., 10000., 15000.]),
    (0.40, [0., 5000., 10000., 15000., 20000.]),
    (0.50, [0., 10000., 15000., 20000., 25000.]),
    (0.60, [0., 10000., 15000., 20000., 25000., 30000.]),
    (0.70, [0., 10000.]),
    (0.70, [20000., 25000., 30000., 32500.]),
    (0.75, [0., 10000.]),
    (0.75, [20000., 25000., 30000., 35000.]),
    (0.85, [10000.]),
    (0.85, [20000., 25000., 30000., 35000.]),
]

# Ceiling of the map. Above ~35,000 ft this deck's off-design solve stops converging: the
# part-power balance loses its thrust target and the validator rejects the result rather than
# record it. 35,000 ft covers the cruise regime of the aircraft class the deck describes, so
# the map stops there deliberately instead of shipping unconverged points.
#
# Consequence to keep in mind: TurbofanResponseSurface clips its inputs to this box, so a
# requirement evaluated above 35,000 ft (a service ceiling, say) reads the 35,000 ft thrust
# lapse. That *overestimates* available thrust there, making such a constraint optimistic.
# Keep ceiling requirements at or below 35,000 ft, or extend the deck first.


def generate_map(envelope=None, pcs=None, out_path=None, resume=True):
    """Sweep the flight envelope and write the universal turbofan map.

    Marches in **altitude at constant Mach**, warm-starting each solve from the previous
    one: consecutive points then differ by a small altitude step, which is a far gentler
    continuation path than jumping across the envelope. A failed point is retried once from
    re-seeded guesses before it is given up on.
    """
    # ``resume=False`` still avoids duplicate rows, but re-solves points that are already
    # recorded. That matters because the continuation chain is what makes the hard, high
    # altitude points converge: skipping the solve at 10,000 and 20,000 ft leaves the solver
    # cold when it reaches 30,000, and the column fails from there up.
    envelope = ENVELOPE if envelope is None else envelope
    pcs = np.array([0.30, 0.55, 0.80, 0.90, 1.00]) if pcs is None else pcs
    out_path = out_path or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "Turbofan_Universal_Map.csv")

    prob = om.Problem()
    prob.model = MPhbtf()
    prob.setup(check=False)

    prob.set_val('DESIGN.fan.PR', 1.685);  prob.set_val('DESIGN.fan.eff', 0.8948)
    prob.set_val('DESIGN.lpc.PR', 1.935);  prob.set_val('DESIGN.lpc.eff', 0.9243)
    prob.set_val('DESIGN.hpc.PR', 9.369);  prob.set_val('DESIGN.hpc.eff', 0.8707)
    prob.set_val('DESIGN.hpt.eff', 0.8888)
    prob.set_val('DESIGN.lpt.eff', 0.8996)
    prob.set_val('DESIGN.fc.alt', 35000., units='ft')
    prob.set_val('DESIGN.fc.MN', 0.8)
    prob.set_val('DESIGN.T4_MAX', T4_MAX_DEGR, units='degR')
    prob.set_val('DESIGN.Fn_DES', REF_FN_LBF, units='lbf')
    prob.set_val('OD_full_pwr.T4_MAX', T4_MAX_DEGR, units='degR')
    prob.set_val('OD_part_pwr.PC', 1.0)

    _set_guesses(prob, alt_ft=0.0)
    prob.set_solver_print(level=-1)

    # Reference for the thrust lapse: full-throttle thrust at sea level, essentially static.
    # Anchoring here (rather than at whichever point happens to run first) is what makes
    # 'Turbofan Design Thrust' mean the familiar SLS rating F00. M is 0.001 rather than 0
    # because the deck does not converge at a true standstill -- the same reason the PW127
    # pipeline drops its Mach 0 point.
    #
    # It is cached beside the map: it is a property of the cycle, not of the sweep, so a
    # resumed run should not spend a minute re-deriving it before it can add a single point.
    # The reference solve is ALWAYS run, even when the value is cached, because it does two
    # jobs: it measures F00, and it leaves the Newton solver warm at a converged sea-level
    # state. Skipping it on a cached run makes the first Mach column start cold, and that
    # column then fails to converge at all.
    ref_path = os.path.splitext(out_path)[0] + "_F00.txt"
    cached = None
    if os.path.isfile(ref_path):
        try:
            cached = float(open(ref_path).read().strip())
        except Exception:
            cached = None

    prob['OD_full_pwr.fc.alt'] = 0.0
    prob['OD_full_pwr.fc.MN'] = 0.001
    prob['OD_part_pwr.fc.alt'] = 0.0
    prob['OD_part_pwr.fc.MN'] = 0.001
    prob['OD_part_pwr.PC'] = 1.0
    prob.run_model()
    measured = _state(prob, 'OD_full_pwr')['Fn_N']

    # Prefer the cached value so the lapse column stays identical across runs (a re-measured
    # F00 can differ in the last digits and would silently rescale the whole map).
    fn_max_sls = cached if cached else measured
    if not cached:
        with open(ref_path, "w") as fh:
            fh.write(repr(fn_max_sls))
    print(f"Reference SLS thrust F00 = {fn_max_sls/1000:.1f} kN "
          f"({fn_max_sls/4.4482216153:.0f} lbf)"
          + (" [cached]" if cached else ""), flush=True)
    _set_guesses(prob, alt_ft=0.0)

    # Resume support. Each point is an independent off-design solve and the sweep is long,
    # so a run that is interrupted (or a grid that is extended later) should not start over.
    # Completed points are keyed on the exact (alt, Mach, PC) triple.
    rows, done = _load_existing(out_path)
    if rows:
        print(f"Resuming: {len(rows)} points already in {os.path.basename(out_path)}",
              flush=True)
    failures = 0
    t0 = time.time()

    for mach, alt_list in envelope:
        # New Mach column: start from clean guesses at its lowest altitude, then march up.
        _set_guesses(prob, alt_ft=alt_list[0])
        for alt in alt_list:
            if resume and all((round(float(alt), 3), round(float(mach), 4),
                               round(float(pc), 4)) in done for pc in pcs):
                continue
            prob['OD_full_pwr.fc.alt'] = alt
            prob['OD_full_pwr.fc.MN'] = mach
            prob['OD_part_pwr.fc.alt'] = alt
            prob['OD_part_pwr.fc.MN'] = mach

            for pc in pcs:
                key = (round(float(alt), 3), round(float(mach), 4), round(float(pc), 4))
                if resume and key in done:
                    continue
                prob['OD_part_pwr.PC'] = pc

                # Try warm-started first; on failure re-seed and try once more.
                for attempt in (0, 1):
                    if attempt == 1:
                        _set_guesses(prob, alt_ft=alt)
                        prob['OD_part_pwr.PC'] = pc
                    try:
                        prob.run_model()
                        full = _state(prob, 'OD_full_pwr')
                        part = _state(prob, 'OD_part_pwr')
                    except Exception as exc:
                        if attempt == 1:
                            failures += 1
                            print(f"  [ ! ] alt={alt:6.0f} M={mach:.2f} PC={pc:.2f} did not "
                                  f"converge ({type(exc).__name__})", flush=True)
                        continue

                    eta, tsfc = part['eta_o'], part['TSFC']
                    bad = _reject_reason(full, part, pc, fn_max_sls, eta, tsfc)
                    if bad:
                        if attempt == 1:
                            failures += 1
                            print(f"  [ x ] alt={alt:6.0f} M={mach:.2f} PC={pc:.2f} "
                                  f"rejected: {bad}", flush=True)
                        continue

                    if key in done:
                        break          # already recorded; this solve only warmed the chain
                    rows.append([alt, mach, pc, eta, tsfc, full['Fn_N'] / fn_max_sls,
                                 part['T3_K'], part['P3_Pa'], part['FAR'], part['mdot_air3'],
                                 part['mdot_inlet'], part['BPR']])
                    done.add(key)
                    with open(out_path, "w") as fh:
                        fh.write(_HEADER + "\n")
                        np.savetxt(fh, np.array(rows), delimiter=",")
                    print(f"  [{len(rows):3d}] alt={alt:6.0f} M={mach:.2f} PC={pc:.2f} "
                          f"eta_o={eta:.4f} TSFC={tsfc*3600*9.80665:.4f} lb/lbf/h",
                          flush=True)
                    break

        print(f"--- M {mach:.2f} column done ({len(rows)} points so far) ---", flush=True)

    np.savetxt(out_path, np.array(rows), delimiter=",", header=_HEADER, comments="")
    print(f"\nRun time: {(time.time()-t0)/60:.1f} min")
    print(f"SUCCESS: {out_path} written ({len(rows)} points, {failures} rejected).")
    return out_path


if __name__ == "__main__":
    generate_map()
