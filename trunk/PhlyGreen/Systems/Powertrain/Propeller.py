import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Units as Units
import PhlyGreen.Utilities.Speed as Speed
from .utils_propeller import _unint, _biquad, Act_Factor_arr, AFCPC, AFCTC, CL_arr, CPEC, CTEC, BL_P_corr_table, PF_CLI_arr, CP_CLi_table, cli_arr_len, ang_arr_len, XPCLI, XTCLI, CP_Angle_table, Blade_angle_table, CT_Angle_table, advance_ratio_array, BL_T_corr_table, TF_CLI_arr, CT_CLi_table, advance_ratio_array2, mach_corr_table, mach_tip_corr_arr, num_blades_arr, comp_mach_CT_arr

class Propeller:

    def __init__(self, aircraft):
        self.aircraft = aircraft

    def SetInput(self):

        self.diam_prop = Units.mToft(self.aircraft.PropellerInput['Propeller Diameter'])
        self.RPM_prop = self.aircraft.PropellerInput['RPM'] 
        self.n_engines = self.aircraft.PropellerInput['N_ENGINES']
        self.V_tip = self.RPM_prop * self.diam_prop * np.pi / 60.
        self.n_blades = self.aircraft.PropellerInput['N_BLADES']
        self.activity_factor = self.aircraft.PropellerInput['ACTIVITY_FACTOR']
        self.cli = self.aircraft.PropellerInput['INTEGRATED_LIFT_COEFFICIENT']

        return None
    
    def ComputePropEfficiency(self,Altitude,Velocity,ShaftPower):

        # CHECK THAT VELOCITY IS TAS m/s
        # Shaft Power [hp]
        # Diameter [ft]

        Velocity = Units.mToft(Velocity)
        AdvanceRatio = np.pi * Velocity / self.V_tip
        DensityRatio = ISA.atmosphere.RHOstd(Altitude,self.aircraft.constraint.DISA) /ISA.atmosphere.Rho_sls
        PowerCoeff = Units.wTohp(ShaftPower/self.n_engines)*10e10/(2*6966) / DensityRatio / (self.V_tip**3 * self.diam_prop**2)
        TipMach = self.V_tip/Units.mToft(ISA.atmosphere.astd(Altitude))

        num_blades = self.n_blades

        act_factor = self.activity_factor
        cli = self.cli

        # TODO verify this works with multiple engine models (i.e. prop mission is
        #      properly slicing these inputs)
        # ensure num_blades is an int, so it can be used as array index later
        try:
            len(num_blades)
        except TypeError:
            num_blades = int(num_blades)
        else:
            num_blades = int(num_blades[0])

        ichck = 0
        run_flag = 0
        xft = 1.0
        AF_adj_CP = np.zeros(7)  # AFCP: an AF adjustment of CP to be assigned
        AF_adj_CT = np.zeros(7)  # AFCT: an AF adjustment of CT to be assigned
        CTT = np.zeros(7)
        BLL = np.zeros(7)
        BLLL = np.zeros(7)
        PXCLI = np.zeros(7)
        XFFT = np.zeros(6)
        CTG = np.zeros(11)
        CTG1 = np.zeros(11)
        TXCLI = np.zeros(6)
        CTTT = np.zeros(4)
        XXXFT = np.zeros(4)

        for k in range(2):
            AF_adj_CP[k], run_flag = _unint(Act_Factor_arr, AFCPC[k], act_factor)
            AF_adj_CT[k], run_flag = _unint(Act_Factor_arr, AFCTC[k], act_factor)
        for k in range(2, 7):
            AF_adj_CP[k] = AF_adj_CP[1]
            AF_adj_CT[k] = AF_adj_CT[1]
        if (AdvanceRatio <= 0.5):
            AFCTE = 2.*AdvanceRatio * \
                (AF_adj_CT[1] - AF_adj_CT[0]) + AF_adj_CT[0]
        else:
            AFCTE = AF_adj_CT[1]

        # bounding J (advance ratio) for setting up interpolation
        if (AdvanceRatio <= 1.0):
            J_begin = 0
            J_end = 3
        elif (AdvanceRatio <= 1.5):
            J_begin = 1
            J_end = 4
        elif (AdvanceRatio <= 2.0):
            J_begin = 2
            J_end = 5
        else:
            J_begin = 3
            J_end = 6

        CL_tab_idx_begin = 0  # NCLT
        CL_tab_idx_end = 0  # NCLTT
        # flag that given lift coeff (cli) does not fall on a node point of CL_arr
        CL_tab_idx_flg = 0  # NCL_flg
        ifnd = 0

        power_coefficient = PowerCoeff
        for ii in range(6):
            cl_idx = ii
            if (abs(cli - CL_arr[ii]) <= 0.0009):
                ifnd = 1
                break
        if (ifnd == 0):
            if (cli <= 0.6):
                CL_tab_idx_begin = 0
                CL_tab_idx_end = 3
            elif (cli <= 0.7):
                CL_tab_idx_begin = 1
                CL_tab_idx_end = 4
            else:
                CL_tab_idx_begin = 2
                CL_tab_idx_end = 5
        else:
            CL_tab_idx_begin = cl_idx
            CL_tab_idx_end = cl_idx
            # flag that given lift coeff (cli) falls on a node point of CL_arr
            CL_tab_idx_flg = 1

        lmod = (num_blades % 2) + 1
        if (lmod == 1):
            nbb = 1
            idx_blade = int(num_blades / 2)
            # even number of blades idx_blade = 1 if 2 blades;
            #                       idx_blade = 2 if 4 blades;
            #                       idx_blade = 3 if 6 blades;
            #                       idx_blade = 4 if 8 blades.
            idx_blade = idx_blade - 1
        else:
            nbb = 4
            # odd number of blades
            idx_blade = 0  # start from first blade

        for ibb in range(nbb):
            # nbb = 1 even number of blades. No interpolation needed
            # nbb = 4 odd number of blades. So, interpolation done
            #       using 4 sets of even J (advance ratio) interpolation
            for kdx in range(J_begin, J_end+1):
                CP_Eff = power_coefficient*AF_adj_CP[kdx]
                PBL, run_flag = _unint(CPEC, BL_P_corr_table[idx_blade], CP_Eff)
                # PBL = number of blades correction for power_coefficient
                CPE1 = CP_Eff*PBL*PF_CLI_arr[kdx]
                CL_tab_idx = CL_tab_idx_begin
                for kl in range(CL_tab_idx_begin, CL_tab_idx_end+1):
                    CPE1X = CPE1
                    if (CPE1 < CP_CLi_table[CL_tab_idx][0]):
                        CPE1X = CP_CLi_table[CL_tab_idx][0]
                    cli_len = cli_arr_len[CL_tab_idx]
                    PXCLI[kl], run_flag = _unint(
                        CP_CLi_table[CL_tab_idx][:cli_len], XPCLI[CL_tab_idx], CPE1X)
                    if (run_flag == 1):
                        ichck = ichck + 1
                    # if verbosity:
                    #     if (run_flag == 1):
                        #     warnings.warn(
                        #         f"Mach = {inputs[Dynamic.Atmosphere.MACH][i_node]}\n"
                        #         f"VTMACH = {inputs['tip_mach'][i_node]}\n"
                        #         f"J = {inputs['advance_ratio'][i_node]}\n"
                        #         f"power_coefficient = {power_coefficient}\n"
                        #         f"CP_Eff = {CP_Eff}"
                        #     )
                        # if (kl == 4 and CPE1 < 0.010):
                        #     print(
                        #         f"Extrapolated data is being used for CLI=.6--CPE1,PXCLI,L= , {CPE1},{PXCLI[kl]},{idx_blade}   Suggest inputting CLI=.5")
                        # if (kl == 5 and CPE1 < 0.010):
                        #     print(
                        #         f"Extrapolated data is being used for CLI=.7--CPE1,PXCLI,L= , {CPE1},{PXCLI[kl]},{idx_blade}   Suggest inputting CLI=.5")
                        # if (kl == 6 and CPE1 < 0.010):
                        #     print(
                        #         f"Extrapolated data is being used for CLI=.8--CPE1,PXCLI,L= , {CPE1},{PXCLI[kl]},{idx_blade}   Suggest inputting CLI=.5")
                    NERPT = 1
                    CL_tab_idx = CL_tab_idx+1
                if (CL_tab_idx_flg != 1):
                    PCLI, run_flag = _unint(
                        CL_arr[CL_tab_idx_begin:CL_tab_idx_begin+4], PXCLI[CL_tab_idx_begin:CL_tab_idx_begin+4], cli)
                else:
                    PCLI = PXCLI[CL_tab_idx_begin]
                    # PCLI = CLI adjustment to power_coefficient
                CP_Eff = CP_Eff*PCLI  # the effective CP at baseline point for kdx
                ang_len = ang_arr_len[kdx]
                BLL[kdx], run_flag = _unint(
                    # blade angle at baseline point for kdx
                    CP_Angle_table[idx_blade][kdx][:ang_len],
                    Blade_angle_table[kdx],
                    CP_Eff,
                )
                try:
                    CTT[kdx], run_flag = _unint(
                        # thrust coeff at baseline point for kdx
                        Blade_angle_table[kdx][:ang_len], CT_Angle_table[idx_blade][kdx][:ang_len], BLL[kdx])
                except:
                    raise Exception(
                        "interp failed for CTT (thrust coefficient) in hamilton_standard.py")
                if run_flag > 1:
                    NERPT = 2
                    print(
                        f"ERROR IN PROP. PERF.-- NERPT={NERPT}, run_flag={run_flag}"
                    )

            BLLL[ibb], run_flag = _unint(
                advance_ratio_array[J_begin:J_begin+4], BLL[J_begin:J_begin+4], AdvanceRatio)
            ang_blade = BLLL[ibb]
            CTTT[ibb], run_flag = _unint(
                advance_ratio_array[J_begin:J_begin+4], CTT[J_begin:J_begin+4], AdvanceRatio)

            # make extra correction. CTG is an "error" function, and the iteration (loop counter = "IL") tries to drive CTG/CT to 0
            # ERR_CT = CTG1[il]/CTTT[ibb], where CTG1 =CT_Eff - CTTT(IBB).
            CTG[0] = .100
            CTG[1] = .200
            TFCLII, run_flag = _unint(
                advance_ratio_array, TF_CLI_arr, AdvanceRatio)
            NCTG = 10
            ifnd1 = 0
            ifnd2 = 0
            for il in range(NCTG):
                ct = CTG[il]
                CT_Eff = CTG[il]*AFCTE
                TBL, run_flag = _unint(CTEC, BL_T_corr_table[idx_blade], CT_Eff)
                # TBL = number of blades correction for thrust_coefficient
                CTE1 = CT_Eff*TBL*TFCLII
                CL_tab_idx = CL_tab_idx_begin
                for kl in range(CL_tab_idx_begin, CL_tab_idx_end+1):
                    CTE1X = CTE1
                    if (CTE1 < CT_CLi_table[CL_tab_idx][0]):
                        CTE1X = CT_CLi_table[CL_tab_idx][0]
                    cli_len = cli_arr_len[CL_tab_idx]
                    TXCLI[kl], run_flag = _unint(
                        CT_CLi_table[CL_tab_idx][:cli_len], XTCLI[CL_tab_idx][:cli_len], CTE1X)
                    NERPT = 5
                    if (run_flag == 1):
                        # off lower bound only.
                        print(
                            f"ERROR IN PROP. PERF.-- NERPT={NERPT}, "
                            f"run_flag={run_flag}, il={il}, kl = {kl}"
                        )
                    if (AdvanceRatio != 0.0):
                        ZMCRT, run_flag = _unint(
                            advance_ratio_array2, mach_corr_table[CL_tab_idx], AdvanceRatio)
                        DMN = Speed.TAS2Mach(Units.ftTom(Velocity),Altitude) - ZMCRT
                    else:
                        ZMCRT = mach_tip_corr_arr[CL_tab_idx]
                        DMN = TipMach - ZMCRT
                    XFFT[kl] = 1.0  # compressibility tip loss factor
                    if (DMN > 0.0):
                        CTE2 = CT_Eff*TXCLI[kl]*TBL
                        XFFT[kl], run_flag = _biquad(comp_mach_CT_arr, 1, DMN, CTE2)
                    CL_tab_idx = CL_tab_idx + 1
                if (CL_tab_idx_flg != 1):
                    # cli = inputs[Aircraft.Engine.Propeller.INTEGRATED_LIFT_COEFFICIENT][0]
                    TCLII, run_flag = _unint(
                        CL_arr[CL_tab_idx_begin:CL_tab_idx_begin+4], TXCLI[CL_tab_idx_begin:CL_tab_idx_begin+4], cli)
                    xft, run_flag = _unint(
                        CL_arr[CL_tab_idx_begin:CL_tab_idx_begin+4], XFFT[CL_tab_idx_begin:CL_tab_idx_begin+4], cli)
                else:
                    TCLII = TXCLI[CL_tab_idx_begin]
                    xft = XFFT[CL_tab_idx_begin]
                ct = CTG[il]
                CT_Eff = CTG[il]*AFCTE*TCLII
                CTG1[il] = CT_Eff - CTTT[ibb]
                if (abs(CTG1[il]/CTTT[ibb]) < 0.001):
                    ifnd1 = 1
                    break
                if (il > 0):
                    CTG[il+1] = -CTG1[il-1] * \
                        (CTG[il] - CTG[il-1])/(CTG1[il] - CTG1[il-1]) + CTG[il-1]
                    if (CTG[il+1] <= 0):
                        ifnd2 = 1
                        break

            if (ifnd1 == 0 and ifnd2 == 0):
                raise ValueError(
                    "Integrated design cl adjustment not working properly for ct "
                    f"definition (ibb={ibb})"
                )
            if (ifnd1 == 0 and ifnd2 == 1):
                ct = 0.0
            CTTT[ibb] = ct
            XXXFT[ibb] = xft
            idx_blade = idx_blade + 1

        if (nbb != 1):
            # interpolation by the number of blades if odd number
            ang_blade, run_flag = _unint(
                num_blades_arr, BLLL[:4], num_blades)
            ct, run_flag = _unint(num_blades_arr, CTTT, num_blades)
            xft, run_flag = _unint(num_blades_arr, XXXFT, num_blades)

        # NOTE this could be handled via the metamodel comps (extrapolate flag)
        if ichck > 0:
            print(f"  table look-up error = {ichck} (if you go outside the tables.)")

        ThrustCoeff = ct
        comp_tip_loss_factor = xft

        eta_prop = AdvanceRatio*ThrustCoeff*comp_tip_loss_factor/PowerCoeff

        # print('Velocity: ', Velocity)
        # print('SHP: ',  Units.wTohp(ShaftPower/self.n_engines))
        # print('tipspd: ', self.V_tip)
        # print('Tip Mach: ', TipMach)
        # print('Advance Ratio: ', AdvanceRatio)
        # print('Thrust Coeff: ', ThrustCoeff)
        # print('Power Coeff: ', PowerCoeff)
        # print('Comp Loss Factor: ', comp_tip_loss_factor)
        # print('Propeller Efficiency: ', eta_prop)
        # print('--'*20) 


        return eta_prop