# -*- coding: utf-8 -*-
"""
The eight verified flows as ordered individuals, plus their stacks, specimens and
measurements.

Flows A and B1 are transcribed from InstanceFlows.tex, which carries them at full detail.
Flows B2 and C through G are transcribed from OntologySpec section 7, which gives the step
order and the parameters each source states, and no more. Where a source does not name the
deposition technique, the step individual is typed at the parent class (Deposition, PVD)
rather than guessed at, following the A3_FE_Deposition principle: typing at a subclass
would assert something no source said.

STEPS entries:
    (flow_id, index, local_name, class_name, source, data_props, obj_props)
"""

# ---------------------------------------------------------------------------
# (flow_id, individual, produces_stack, targets_node, source, comment)
# ---------------------------------------------------------------------------
FLOWS = [
    ("A",  "FlowA_LabMFM", "Stack_A_MFM", None, "S1{II, Fig. 3}",
     "Laboratory MFM coupon. Anneal before patterning."),
    ("B1", "FlowB1_GateLastFeFET", "Stack_B1_MFIS", None, "S10{II A}",
     "Gate-last silicon FeFET. The 1050 C activation precedes the ferroelectric existing."),
    ("B2", "FlowB2_GateLastFeFET_MIFIS", "Stack_B2_MIFIS", None, "S11{II}",
     "Gate-last FeFET with an Al2O3 interlayer."),
    ("C",  "FlowC_BEOL_FeRAM", "Stack_C_MIM", "node_130nm", "S12a{Fig. 1a}",
     "The only verified flow that patterns before annealing."),
    ("D",  "FlowD_MFIS_Capacitor", "Stack_D_MFIS", None, "S9{p.2}",
     "MFIS capacitors, not FeFETs. No patterning step described."),
    ("E",  "FlowE_FullALD_AutoAnneal", "Stack_E_MFM", None, "S24{2}",
     "No crystallisation anneal individual at all: crystallisation happens during the "
     "4 h ALD TiN top electrode deposition."),
    ("F",  "FlowF_MFM", "Stack_F_MFM", None, "S23{2}",
     "No patterning step described."),
    ("G",  "FlowG_LaHZO_MIM", "Stack_G_MIM", None, "S27{p.1134}",
     "No patterning step described."),
]

STEPS = [
    # ---- Flow A -----------------------------------------------------------
    ("A", 1, "A1_Substrate_Clean", "Wet_Clean", "S1", {}, {"hasInput": ["Si_substrate"]}),
    ("A", 2, "A2_BE_Sputter", "Sputter_Deposition", "S1", {},
     {"depositsMaterial": ["TiN"]}),
    ("A", 3, "A3_FE_Deposition", "Deposition", "S1", {}, {"depositsMaterial": ["HfO2"]}),
    ("A", 4, "A4_TE_Capping", "Sputter_Deposition", "S1", {}, {"depositsMaterial": ["TiN"]}),
    ("A", 5, "A5_Crystallisation_Anneal", "Crystallisation_Anneal",
     "S1{II} + Tables I, III, V", {},
     {"transformsPhase": ["Orthorhombic_Pca21"]}),
    ("A", 6, "A6_Patterned_Metal_Deposition", "Deposition", "S1{II} vs Fig. 3 caption", {},
     {"depositsMaterial": ["Ti_Pt_contact"]}),
    ("A", 7, "A7_SC1_Etch", "Wet_Etch", "S1", {}, {"etchesMaterial": ["TiN"]}),

    # ---- Flow B1 ----------------------------------------------------------
    ("B1", 1, "B1_1_As_Implant", "Implantation", "S10",
     {"hasImplantEnergy_keV": 40.0, "hasImplantDose_cm2": 4e15}, {}),
    ("B1", 2, "B1_2_Activation_Anneal", "Dopant_Activation_Anneal", "S10",
     {"hasProcessTemperature_C": 1050.0, "hasProcessDuration_s": 5.0},
     {"hasAmbient": ["N2"]}),
    ("B1", 3, "B1_3_dHF_Clean", "Wet_Clean", "S10", {}, {"hasInput": ["dilute_HF"]}),
    ("B1", 4, "B1_4_IL_Ozone_Oxidation", "Ozone_Oxidation", "S10",
     {"hasProcessTemperature_C": 300.0},
     {"usesOxidant": ["O3"], "usesEquipment": ["ALD_reactor"]}),
    ("B1", 5, "B1_5_HZO_ALD", "Thermal_ALD", "S10",
     {"hasProcessTemperature_C": 300.0},
     {"usesPrecursor": ["TEMA_Hf", "TEMA_Zr"], "usesOxidant": ["H2O"],
      "usesEquipment": ["ALD_reactor"], "depositsMaterial": ["HZO"]}),
    ("B1", 6, "B1_6_TiN_W_Sputter", "Sputter_Deposition", "S10", {},
     {"depositsMaterial": ["TiN", "W"]}),
    ("B1", 7, "B1_7_Crystallisation_Anneal", "Crystallisation_Anneal", "S10",
     {"hasProcessTemperature_C": 550.0, "hasProcessDuration_s": 60.0},
     {"hasAmbient": ["N2"]}),
    ("B1", 8, "B1_8_Gate_Formation", "Lithography", "S10", {}, {}),
    ("B1", 9, "B1_9_SD_Contact", "Contact_Formation", "S10", {},
     {"depositsMaterial": ["TiN", "Al"]}),
    ("B1", 10, "B1_10_Forming_Gas_Anneal", "Forming_Gas_Anneal", "S10",
     {"hasProcessTemperature_C": 450.0}, {"hasAmbient": ["forming_gas_5H2_95N2"]}),
    ("B1", 11, "B1_11_Electrical_Test", "Electrical_Characterisation", "S10{II A}", {},
     {"usesEquipment": ["Keysight_B1500A", "Radiant_Precision_LC"]}),

    # ---- Flow B2 ----------------------------------------------------------
    ("B2", 1, "B2_1_B_Implant", "Implantation", "S11", {}, {}),
    ("B2", 2, "B2_2_SD_Litho_As_Implant", "Implantation", "S11", {}, {}),
    ("B2", 3, "B2_3_Activation_Anneal", "Dopant_Activation_Anneal", "S11",
     {"hasProcessTemperature_C": 1050.0, "hasProcessDuration_s": 5.0}, {}),
    ("B2", 4, "B2_4_dHF_Clean", "Wet_Clean", "S11", {}, {"hasInput": ["dilute_HF"]}),
    ("B2", 5, "B2_5_IL_Ozone_Oxidation", "Ozone_Oxidation", "S11{II}",
     {"hasProcessTemperature_C": 300.0}, {"usesOxidant": ["O3"]}),
    ("B2", 6, "B2_6_HZO_Al2O3_ALD", "ALD", "S11{II}",
     {"hasProcessTemperature_C": 300.0},
     {"depositsMaterial": ["HZO", "Al2O3"]}),
    ("B2", 7, "B2_7_TiN_W_Deposition", "Deposition", "S11", {},
     {"depositsMaterial": ["TiN", "W"]}),
    ("B2", 8, "B2_8_Crystallisation_Anneal", "Crystallisation_Anneal", "S11{II}",
     {"hasProcessTemperature_C": 400.0, "hasProcessDuration_s": 60.0}, {}),
    ("B2", 9, "B2_9_Forming_Gas_Anneal", "Forming_Gas_Anneal", "S11",
     {"hasProcessTemperature_C": 450.0},
     {"hasAmbient": ["forming_gas_5H2_95N2"]}),

    # ---- Flow C -----------------------------------------------------------
    ("C", 1, "C1_FEOL", "Unit_Process", "S12a{Fig. 1a}", {}, {}),
    ("C", 2, "C2_M1_M6_Interconnect", "Metal_Deposition_And_Patterning", "S12a{Fig. 1a}",
     {}, {}),
    ("C", 3, "C3_TaN_BE_Deposition", "Deposition", "S12a{Fig. 1a}", {},
     {"depositsMaterial": ["TaN"]}),
    ("C", 4, "C4_HZO_ALD", "ALD", "S12a{Fig. 1a}", {}, {"depositsMaterial": ["HZO"]}),
    ("C", 5, "C5_TaN_TE_Deposition", "Deposition", "S12a{Fig. 1a}", {},
     {"depositsMaterial": ["TaN"]}),
    ("C", 6, "C6_Patterning_And_Etch", "Unit_Process", "S12a{Fig. 1a}", {}, {}),
    ("C", 7, "C7_Crystallisation_Anneal", "Crystallisation_Anneal", "S12a{Fig. 1a}",
     {"hasProcessTemperature_C": 500.0}, {}),
    ("C", 8, "C8_Isolation_Deposition", "Isolation_Deposition", "S12a{Fig. 1a}", {}, {}),
    ("C", 9, "C9_V6_Via", "Via_Patterning_And_Etch", "S12a{Fig. 1a}", {}, {}),
    ("C", 10, "C10_M7_Metal", "Metal_Deposition_And_Patterning", "S12a{Fig. 1a}", {}, {}),

    # ---- Flow D -----------------------------------------------------------
    ("D", 1, "D1_Native_Oxide_Removal", "Native_Oxide_Removal", "S9{p.2}", {}, {}),
    ("D", 2, "D2_Chemical_Oxidation", "Interfacial_Layer_Formation", "S9{p.2}", {}, {}),
    ("D", 3, "D3_NH3_RTP_Nitridation", "Chemical_Oxidation_Plus_Nitridation", "S9{p.2}",
     {}, {"usesProcessGas": ["NH3", "O2", "N2"]}),
    ("D", 4, "D4_HfO2_ALD", "ALD", "S9{p.2}", {"hasProcessTemperature_C": 250.0},
     {"depositsMaterial": ["HfO2"]}),
    ("D", 5, "D5_TiN_PVD", "PVD", "S9{p.2}", {}, {"depositsMaterial": ["TiN"]}),
    ("D", 6, "D6_RTP_Anneal", "Crystallisation_Anneal", "S9{p.2}",
     {"hasProcessTemperature_C": 800.0, "hasProcessDuration_s": 20.0}, {}),

    # ---- Flow E -----------------------------------------------------------
    ("E", 1, "E1_SiO2_W_Base", "PECVD", "S24{2}", {}, {"depositsMaterial": ["SiO2", "W"]}),
    ("E", 2, "E2_TiN_BE_ALD", "Thermal_ALD", "S24{2}",
     {"hasProcessTemperature_C": 400.0},
     {"depositsMaterial": ["TiN"], "usesPrecursor": ["TiCl4", "NH3_precursor"],
      "usesEquipment": ["Picosun_R200adv"]}),
    ("E", 3, "E3_HZO_ALD", "Thermal_ALD", "S24{2}",
     {"hasProcessTemperature_C": 240.0, "hasDepositionCycleCount": 65,
      "hasPulseTime_s": 0.1, "hasPurgeTime_s": 12.0},
     {"depositsMaterial": ["HZO"], "usesOxidant": ["H2O"],
      "usesEquipment": ["Picosun_R200adv"]}),
    ("E", 4, "E4_Ru_REALD", "Radical_Enhanced_ALD", "S24{2}", {},
     {"depositsMaterial": ["Ru"], "usesPrecursor": ["Ru_EtCp_2"]}),
    ("E", 5, "E5_TiN_TE_ALD", "Thermal_ALD", "S24{2}",
     {"hasProcessTemperature_C": 400.0, "hasProcessDuration_s": 14400.0,
      "isCrystallising": True},
     {"depositsMaterial": ["TiN"], "transformsPhase": ["Orthorhombic_Pca21"],
      "usesEquipment": ["Picosun_R200adv"]}),
    ("E", 6, "E6_Patterning", "Lithography", "S24{2}", {}, {}),
    ("E", 7, "E7_Plasma_Etch", "Plasma_Etch", "S24{2}", {},
     {"usesProcessGas": ["SF6", "Ar"], "etchesMaterial": ["TiN"]}),
    ("E", 8, "E8_Al_Pads", "Contact_Formation", "S24{2}", {},
     {"depositsMaterial": ["Al"]}),
    ("E", 9, "E9_Electrical_Test", "Electrical_Characterisation", "S24{2}", {},
     {"usesEquipment": ["Keysight_B1500A", "Summit_11000B_M"]}),

    # ---- Flow F -----------------------------------------------------------
    ("F", 1, "F1_Pre_Clean", "Wet_Clean", "S23{2}", {}, {}),
    ("F", 2, "F2_TiN_BE_ALD", "ALD", "S23{2}", {"hasProcessTemperature_C": 400.0},
     {"depositsMaterial": ["TiN"]}),
    ("F", 3, "F3_HZO_PEALD", "Plasma_Enhanced_ALD", "S23{2}",
     {"hasProcessTemperature_C": 270.0},
     {"depositsMaterial": ["HZO"], "usesOxidant": ["O2_plasma"]}),
    ("F", 4, "F4_TiN_TE_W_ALD", "ALD", "S23{2}", {},
     {"depositsMaterial": ["TiN", "W"]}),
    ("F", 5, "F5_Crystallisation_Anneal", "Crystallisation_Anneal", "S23{2}",
     {"hasProcessTemperature_C": 500.0, "hasProcessDuration_s": 60.0}, {}),

    # ---- Flow G -----------------------------------------------------------
    ("G", 1, "G1_TiN_BE_ALD", "ALD", "S27{p.1134}", {}, {"depositsMaterial": ["TiN"]}),
    ("G", 2, "G2_LaHZO_ALD", "ALD", "S27{p.1134}", {}, {"depositsMaterial": ["La_HZO"]}),
    ("G", 3, "G3_TiN_TE_ALD", "ALD", "S27{p.1134}", {}, {"depositsMaterial": ["TiN"]}),
    ("G", 4, "G4_PMA", "Post_Metallisation_Anneal", "S27{p.1134}",
     {"hasProcessTemperature_C": 400.0, "hasProcessDuration_s": 3600.0},
     {"hasAmbient": ["N2"]}),
    ("G", 5, "G5_PED_Analysis", "Structural_Characterisation", "S27{p.1134}", {},
     {"usesEquipment": ["Titan3_G2", "DIGISTAR_P2010"]}),
]

# ---------------------------------------------------------------------------
# Stacks. Each slot is (index, material, role, thickness_nm or None)
# ---------------------------------------------------------------------------
STACKS = [
    ("Stack_A_MFM", "MFM", "S1{II}", [
        (1, "Si_substrate", "substrate", None),
        (2, "SiO2", "interfacial_layer", None),
        (3, "TiN", "bottom_electrode", None),
        (4, "HfO2", "ferroelectric_layer", None),
        (5, "TiN", "top_electrode", None),
        (6, "Ti_Pt_contact", "contact_pad", None),
    ]),
    ("Stack_B1_MFIS", "MFIS", "S10{II A}", [
        (1, "Si_substrate", "channel", None),
        (2, "SiO2_IL", "interfacial_layer", 0.7),
        (3, "HZO", "ferroelectric_layer", 9.0),
        (4, "TiN_gate", "top_electrode", 10.0),
        (5, "W_cap", "gate_metal", 75.0),
    ]),
    ("Stack_B2_MIFIS", "MIFIS", "S11{II}", [
        (1, "Si_substrate", "channel", None),
        (2, "SiO2_IL", "interfacial_layer", None),
        (3, "HZO", "ferroelectric_layer", None),
        (4, "Al2O3", "insertion_layer", None),
        (5, "TiN", "top_electrode", None),
        (6, "W", "gate_metal", None),
    ]),
    ("Stack_C_MIM", "MFM", "S12a{Fig. 1a}", [
        (1, "TaN", "bottom_electrode", None),
        (2, "HZO", "ferroelectric_layer", 20.0),
        (3, "TaN", "top_electrode", None),
    ]),
    ("Stack_D_MFIS", "MFIS", "S9{p.2}", [
        (1, "Si_substrate", "channel", None),
        (2, "SiON", "interfacial_layer", None),
        (3, "HfO2", "ferroelectric_layer", None),
        (4, "TiN", "top_electrode", None),
    ]),
    ("Stack_E_MFM", "MFM", "S24{2}", [
        (1, "W", "substrate", None),
        (2, "TiN", "bottom_electrode", None),
        (3, "HZO", "ferroelectric_layer", 10.0),
        (4, "TiN", "top_electrode", None),
    ]),
    ("Stack_F_MFM", "MFM", "S23{2}", [
        (1, "TiN", "bottom_electrode", None),
        (2, "HZO", "ferroelectric_layer", None),
        (3, "TiN", "top_electrode", None),
        (4, "W", "gate_metal", None),
    ]),
    ("Stack_G_MIM", "MFM", "S27{p.1134}", [
        (1, "Si_substrate", "substrate", None),
        (2, "TiN", "bottom_electrode", 10.0),
        (3, "La_HZO", "ferroelectric_layer", 9.5),
        (4, "TiN", "top_electrode", 30.0),
    ]),
]

# ---------------------------------------------------------------------------
# Device individuals: (name, class, stack, source, data_props, obj_props)
# ---------------------------------------------------------------------------
DEVICES = [
    ("Cell_B1_FeFET", "FeFET_1T", "Stack_B1_MFIS", "S10",
     {"hasGateLength_um": 5.0, "hasGateWidth_um": 150.0},
     {"hasChannel": ["Si_bulk"]}),
    ("Cell_B2_FeFET", "FeFET_1T", "Stack_B2_MIFIS", "S11",
     {"hasGateLength_um": 5.0, "hasGateWidth_um": 150.0,
      "hasWriteVoltage_V": 5.5}, {}),
    ("Cell_C_FeRAM_1T1C", "FeRAM_1T1C_Charge_Sensed", "Stack_C_MIM", "S12a",
     {"hasArraySize_bit": 16384, "hasReferenceVoltage_V": 1.8}, {}),
]

# ---------------------------------------------------------------------------
# Specimens: (name, class, source, data_props, comment)
# ---------------------------------------------------------------------------
ARTIFACTS = [
    ("Artifact_B1_FeFET_L5_W150", "Single_Cell", "S10{II A}",
     {"hasSpecimenLabel": "MFIS FeFET, L=5 um, W=150 um"},
     "The physical thing S10 measured."),
    ("Artifact_B1_FeFET_cycled", "Single_Cell", "S10{III D}",
     {"hasSpecimenLabel": "same cell after endurance cycling",
      "hasCyclingHistory_cycles": 100000},
     "Same cell, later in its cycling history. A separate artifact individual is what "
     "keeps the pristine and cycled trap densities from overwriting each other."),
    ("Artifact_E_TiN_Capacitor", "Patterned_Capacitor", "S24{2}",
     {"hasSpecimenLabel": "TiN/HZO/TiN capacitor"}, None),
    ("Artifact_E_Ru_Capacitor", "Patterned_Capacitor", "S24{2}",
     {"hasSpecimenLabel": "TiN/HZO/Ru capacitor"}, None),
]

# ---------------------------------------------------------------------------
# Measurements: (name, method, property, artifact, source, data_props, comment)
# ---------------------------------------------------------------------------
MEASUREMENTS = [
    ("M_B1_Vth", "IdVg_Transfer", "threshold_voltage_Vth",
     "Artifact_B1_FeFET_L5_W150", "S10{II A}",
     {"hasVthConvention": "linear_extrapolation"},
     "S10 defines Vth by linear extrapolation; S11 by constant current on a near-identical "
     "stack. Recording the convention is one field and it closes the trap permanently."),
    ("M_B1_Trap_Density_initial", "QSCV", "trapped_charge_density",
     "Artifact_B1_FeFET_L5_W150", "S10{III D}",
     {"hasMeasuredValue": 1e14, "hasUnit": "cm-2"}, None),
    ("M_B1_Trap_Density_cycled", "QSCV", "trapped_charge_density",
     "Artifact_B1_FeFET_cycled", "S10{III D}",
     {"hasMeasuredValue": 3.6e14, "hasUnit": "cm-2"},
     "Two separate instances, not one value overwritten. This pair is why trap density "
     "cannot be a data property on Material."),
    ("M_E_TiN_Endurance", "Endurance_Cycling", "endurance_cycles",
     "Artifact_E_TiN_Capacitor", "S24{3.2}",
     {"hasEnduranceCycleCount": 1000000000, "hasPulseWidth_s": 3e-6,
      "hasAppliedVoltage_V": 3.0},
     "Breakdown at 1e9."),
    ("M_E_Ru_Endurance", "Endurance_Cycling", "endurance_cycles",
     "Artifact_E_Ru_Capacitor", "S24{3.2}",
     {"hasEnduranceCycleCount": 10000000000, "hasPulseWidth_s": 3e-6,
      "hasAppliedVoltage_V": 3.0},
     "Survives 1e10 under identical conditions to the TiN device. The pair is the whole "
     "argument for reifying Measurement."),
    ("M_G_Phase_Fraction", "PED_Orientation_Mapping", "phase_fraction",
     "Artifact_E_TiN_Capacitor", "S27{p.1134}",
     {"fractionMethod": "PED_mapping", "phasesLumped": "none"},
     "S27 finds tetragonal and monoclinic majority phases at 7.2 at.% La. Recorded with "
     "its method because o and t peaks overlap in GI-XRD and the fraction is not "
     "interpretable without it."),
]

# Which characterisation step produced which measurements
PRODUCES = [
    ("B1_11_Electrical_Test", ["M_B1_Vth", "M_B1_Trap_Density_initial",
                               "M_B1_Trap_Density_cycled"]),
    ("E9_Electrical_Test", ["M_E_TiN_Endurance", "M_E_Ru_Endurance"]),
    ("G5_PED_Analysis", ["M_G_Phase_Fraction"]),
]

# ---------------------------------------------------------------------------
# Causal assertions: (subject, property, object, source, status)
# ---------------------------------------------------------------------------
CAUSAL = [
    ("TiN", "stabilisesPhase", "Orthorhombic_Pca21", "S1{I A}", "verified"),
    ("Oxygen_Vacancy", "stabilisesPhase", "Orthorhombic_Pca21", "S1{I B, II A 2}", "verified"),
    ("Oxygen_Vacancy", "stabilisesPhase", "Tetragonal_P42nmc", "S1{I B, II A 2}", "verified"),
    ("Oxygen_Interstitial", "destabilisesPhase", "Orthorhombic_Pca21", "S1{II A 2}", "verified"),
    ("TiN", "scavengesOxygenFrom", "HfO2", "S1{II A 2}", "verified"),
    ("TaN", "scavengesOxygenFrom", "HfO2", "S1{II A 2}", "verified"),
    ("TiN", "scavengesOxygenFrom", "HZO", "S24{4}", "verified"),
    ("Ru", "scavengesOxygenFrom", "HZO", "S24{4}", "verified"),
    ("Zr4", "diffusesInto", "SiON", "S9{p.5}", "verified"),
    ("TiN", "templates", "HZO", "S27{p.1134}", "uncertain"),
    ("Conformality", "enables", "VC_FeNAND", "S1{II B}", "verified"),
    ("LineOfSight", "precludes", "VC_FeNAND", "S1{II B}", "verified"),
    ("EtchSelectivityToHfO2", "constrainsMaterialChoice", "Ru", "S24{1}", "uncertain"),
    ("Stack_E_MFM", "exhibits", "Fatigue", "S24{3.2}", "verified"),
    ("Stack_E_MFM", "exhibits", "Wake_Up", "S24{3.2}", "verified"),
    ("Stack_F_MFM", "exhibits", "Imprint", "S23{3.1}", "verified"),
    ("Stack_B1_MFIS", "exhibits", "Charge_Trapping", "S10", "verified"),
    ("VC_FeNAND", "exhibits", "Pass_Disturb", "S5", "verified"),
]

# Phase facts
PHASE_FACTS = [
    ("Orthorhombic_Pca21", {"hasSpaceGroup": "Pca21", "isFerroelectric": True,
                            "hasRelativeEnergy_meVperFU": 62.0}, "S1{I A, I B}"),
    ("Tetragonal_P42nmc", {"hasSpaceGroup": "P42/nmc", "isFerroelectric": False}, "S1{I A}"),
    ("Monoclinic_P21c", {"hasSpaceGroup": "P21/c", "isFerroelectric": False}, "S1{I A}"),
    ("Orthorhombic_Pbca", {"hasSpaceGroup": "Pbca", "isFerroelectric": False}, "S1{II E}"),
    ("Cubic_Fm3m", {"hasSpaceGroup": "Fm-3m", "isFerroelectric": False}, "S1{I A}"),
]

# Material facts (specified/nominal only, per the measured-versus-specified rule)
MATERIAL_FACTS = [
    ("HZO", {"hasNominalHfZrRatio": 1.0}, "S9{p.2}"),
    ("HAO", {"hasDopantRatio": "Al:Hf = 1:30"}, "S9{p.2}"),
    ("La_HZO", {"hasDopantConcentration_atPct": 7.2}, "S27{p.1134}"),
    ("HfO2", {"hasBandgap_eV": 5.6}, "S23{1}"),
]

# Uncertainty register cross-references: (entity, U-number)
UNCERTAINTY_REFS = [
    ("Wake_Up", "U1"), ("Fatigue", "U2"), ("Retention_Loss", "U3"),
    ("Charge_Trapping", "U4"), ("Seed_Layer_Material", "U6"),
    ("hasPermittivity_k", "U8"), ("Hafnium_Zirconate", "U10"),
    ("La_HZO", "U13"), ("Imprint", "U15"), ("hasVthConvention", "U16"),
    ("templates", "U17"), ("Wake_Up_Cycling", "U18"), ("FTJ", "U19"),
]
