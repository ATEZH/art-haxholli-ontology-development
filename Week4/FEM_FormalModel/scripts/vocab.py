# -*- coding: utf-8 -*-
"""
Class tree and vocabulary individuals, transcribed from OntologySpec v3 section 2.

Each CLASSES entry is:
    (name, parent, source_locator, epistemic_status, comment)

parent = None means subclass of owl:Thing.
source_locator = None means ontology scaffolding, which per the spec front matter is
    not a claim about the world; those entries carry epistemicStatus 'scaffolding'.

INDIVIDUALS entries are:
    (name, class_name, source_locator, comment)
"""

VERIFIED = "verified"
UNCERTAIN = "uncertain"
INFERRED = "inferred"
SCAFFOLDING = "scaffolding"
NAMED_ONLY = "named_only"

# ---------------------------------------------------------------------------
# Top-level classes
# ---------------------------------------------------------------------------
CLASSES = [
    ("Material", None, None, SCAFFOLDING,
     "Any substance participating in a flow: films, precursors, gases, targets, wet chemicals."),
    ("Dopant", None, "S1{I B, II B 1, II D}", VERIFIED,
     "A species substituted into the ferroelectric lattice to influence phase stability."),
    ("Phase_State", None, None, SCAFFOLDING,
     "The crystallographic state of a material. Instances are specific phases."),
    ("Defect", None, None, SCAFFOLDING,
     "A point or electronic defect affecting phase stability or trapping."),
    ("Layer_Stack", None, None, SCAFFOLDING,
     "An ordered assembly of layers forming a functional structure."),
    ("Layer_Slot", None, None, INFERRED,
     "REIFIED. One position in one stack. Carries layerIndex, the material occupying it, "
     "the role it plays there, and the as-fabricated thickness. Reified because role and "
     "thickness are properties of the position, not of the material: Si is a substrate in "
     "Flow A and a channel in Flow B1, and HZO is 9 nm in Flow B1 and 9.5 nm in Flow G."),
    ("Layer_Role", None, None, INFERRED,
     "The function a material serves at one position in one stack."),
    ("Artifact", None, None, INFERRED,
     "The physical specimen a Measurement points at. Distinguishing specimen types is what "
     "makes two measurements comparable or not."),
    ("Technology_Node", None, "S12a{P4}", VERIFIED,
     "A CMOS technology generation a flow targets."),
    ("Memory_Cell_Architecture", None, None, SCAFFOLDING,
     "A memory cell topology."),
    ("Array_Architecture", None, "S5", VERIFIED,
     "An arrangement of cells into an addressable array."),
    ("Process_Flow", None, None, SCAFFOLDING,
     "An ordered sequence of unit processes producing a stack or a device, as described by "
     "one source."),
    ("Unit_Process", None, None, SCAFFOLDING,
     "A single manufacturing or characterisation step within a flow."),
    ("Equipment", None, None, SCAFFOLDING,
     "A tool performing a unit process."),
    ("Capability", None, "S1{II A, II B, III}", VERIFIED,
     "A property of a deposition or etch technique that enables or precludes an architecture."),
    ("Measurement_Method", None, None, SCAFFOLDING,
     "A named characterisation technique."),
    ("Measurement", None, None, INFERRED,
     "REIFIED n-ary relation binding a value to a method, a property, a specimen and the "
     "conditions of measurement. A bare endurance figure on a material is misleading: S24's "
     "TiN device breaks down at 1e9 and its Ru device survives 1e10 under identical pulses."),
    ("Measured_Property", None, None, SCAFFOLDING,
     "A quantity that can be measured."),
    ("Degradation_Phenomenon", None, None, SCAFFOLDING,
     "A mechanism by which device performance degrades."),
]

# ---------------------------------------------------------------------------
# Material branch
# ---------------------------------------------------------------------------
CLASSES += [
    ("Substrate", "Material", "S1{II}", VERIFIED, None),
    ("Ferroelectric_Material", "Material", "S1{I B}", VERIFIED,
     "Every subclass is HfO2-family. Perovskite and other non-HfO2 ferroelectrics are out "
     "of scope by design, not absent for lack of evidence."),
    ("Undoped_HfO2", "Ferroelectric_Material", "S1{I B}", VERIFIED, None),
    ("Doped_HfO2", "Ferroelectric_Material", "S1{I B, II B 1}", VERIFIED, None),
    ("Hafnium_Zirconate", "Ferroelectric_Material", "S1{I}", VERIFIED,
     "'HZO' is a composition range, not a fixed formula. S24 measured Hf:Zr ~ 0.8 and still "
     "calls it HZO. Use hasNominalHfZrRatio; do not infer 50:50."),
    ("Doped_Hafnium_Zirconate", "Ferroelectric_Material", "S27, S6", VERIFIED, None),
    ("Hafnium_Aluminate", "Ferroelectric_Material", "S9{p.2}", VERIFIED, None),
    ("Electrode_Material", "Material", "S1{II A 2}", VERIFIED,
     "In polycrystalline MFM literature Ti/Pt is a contact pad, but in PLD and CSD "
     "literature Pt is a functional electrode. The distinction is carried by slotRole."),
    ("Dielectric_Layer_Material", "Material", None, SCAFFOLDING, None),
    ("Interfacial_Layer_Material", "Dielectric_Layer_Material", "S9, S10, S11", VERIFIED, None),
    ("Insertion_Layer_Material", "Dielectric_Layer_Material", "S1{II A 3}, S11", VERIFIED, None),
    ("Seed_Layer_Material", "Dielectric_Layer_Material", "S1{II A 3}", VERIFIED, None),
    ("Interface_Reaction_Product", "Dielectric_Layer_Material", "S1{II B 2}", VERIFIED,
     "TiO2 forms deliberately (pre-deposition O2) or parasitically (excess O3). "
     "HfN is the defect this prevents."),
    ("Channel_Material", "Material", "S5, S6", VERIFIED, None),
    ("Chemical_Precursor", "Material", "S1{II A 1}", VERIFIED, None),
    ("Hf_Precursor", "Chemical_Precursor", "S1{II A 1}", VERIFIED, None),
    ("Zr_Precursor", "Chemical_Precursor", "S1{II A 1}", VERIFIED, None),
    ("Dopant_Precursor", "Chemical_Precursor", "S1{Table I}", UNCERTAIN,
     "Listed in S1 Table I but none verified in a device flow. Treat as catalogue."),
    ("Electrode_Precursor", "Chemical_Precursor", "S23{2}, S24{2}", VERIFIED, None),
    ("Oxidant", "Material", "S1{II A 2}, S23{2}", VERIFIED, None),
    ("Process_Gas", "Material", "S1, S9, S10, S24", VERIFIED, None),
    ("Sputter_Target", "Material", "S1{II B, Table III}", VERIFIED, None),
    ("Wet_Chemical", "Material", "S1{II}, S10, S11", VERIFIED, None),
]

# ---------------------------------------------------------------------------
# Phase, defect, stack
# ---------------------------------------------------------------------------
CLASSES += [
    ("Amorphous", "Phase_State", "S1{II A 1}", VERIFIED, None),
    ("Crystalline_Phase", "Phase_State", "S1{I A}", VERIFIED, None),
    ("Point_Defect", "Defect", None, SCAFFOLDING, None),
    ("Electronic_Trap", "Defect", "S10{III D}", VERIFIED, None),
    ("MFM", "Layer_Stack", "S1{II}", VERIFIED, "metal-ferroelectric-metal"),
    ("MFIS", "Layer_Stack", "S9, S10, S11", VERIFIED,
     "metal-ferroelectric-insulator-semiconductor"),
    ("MIFIS", "Layer_Stack", "S11{II}", VERIFIED,
     "metal-insulator-ferroelectric-insulator-semiconductor"),
    ("MFMIS", "Layer_Stack", "S5, S6", VERIFIED,
     "metal-ferroelectric-metal-insulator-semiconductor"),
    ("Nanolaminate", "Layer_Stack", "S1{II A 3}", VERIFIED, None),
    ("Bilayer", "Layer_Stack", "S1{II A 3}", VERIFIED, None),
    ("Trilayer", "Layer_Stack", "S1{II A 3}", VERIFIED, None),
    ("Heterogeneous_Co_Doped_Stack", "Layer_Stack", "S9{p.2}", VERIFIED,
     "e.g. IL/HAO/HAO/HZO"),
]

# ---------------------------------------------------------------------------
# Artifact
# ---------------------------------------------------------------------------
CLASSES += [
    ("Blanket_Film", "Artifact", "S1, S9, S27", VERIFIED, "Unpatterned film on a wafer."),
    ("Patterned_Capacitor", "Artifact", "S12a, S23, S24", VERIFIED, "MFM or MIM test structure."),
    ("Single_Cell", "Artifact", "S10, S11, S12a", VERIFIED, "One FeFET or one 1T1C cell."),
    ("Array_Specimen", "Artifact", "S12a", VERIFIED,
     "An array measured as a unit. S12a measures a 1C capacitor and a 1T-1C array from the "
     "same wafer and reports they agree: two artifacts, one wafer."),
]

# ---------------------------------------------------------------------------
# Cell and array architecture
# ---------------------------------------------------------------------------
CLASSES += [
    ("Capacitor_Based_Cell", "Memory_Cell_Architecture", "S5", VERIFIED, None),
    ("FeCAP_1C", "Capacitor_Based_Cell", "S12a{Fig. 1b}", VERIFIED, None),
    ("FeRAM_1T1C_Charge_Sensed", "Capacitor_Based_Cell", "S5", VERIFIED, "destructive read"),
    ("FeRAM_1T1C_Capacitance_Sensed", "Capacitor_Based_Cell", "S5", VERIFIED,
     "non-destructive, under 2x ratio"),
    ("Transistor_Based_Cell", "Memory_Cell_Architecture", "S5", VERIFIED, None),
    ("FeFET_1T", "Transistor_Based_Cell", "S5", VERIFIED, None),
    ("FeMFET_1T1C", "Transistor_Based_Cell", "S5", VERIFIED, "MFMIS"),
    ("Hybrid_Cell", "Memory_Cell_Architecture", "S5", VERIFIED, None),
    ("FeRAM_2T1C", "Hybrid_Cell", "S5", VERIFIED, None),
    ("FeRAM_2TnC", "Hybrid_Cell", "S5", VERIFIED, "quasi-non-destructive readout"),
    ("FeRAM_1TnC", "Hybrid_Cell", "S5", VERIFIED, None),
    ("FTJ", "Memory_Cell_Architecture", "S1{I}, S27{p.1134}", NAMED_ONLY,
     "NAMED ONLY. Listed as an application of ferroelectric HfO2. No structure, sensing "
     "mechanism or performance data verified. Do not populate."),
    ("VC_FeNAND", "Array_Architecture", "S5", VERIFIED, "vertical channel"),
    ("HC_FeNAND", "Array_Architecture", "S5", VERIFIED, "horizontal channel"),
    ("Fe_AND", "Array_Architecture", "S5", VERIFIED, None),
    ("Stacking_Strategy", "Array_Architecture", "S5", VERIFIED, None),
    ("Parallel_Stacking", "Stacking_Strategy", "S5", VERIFIED,
     "lithography count roughly independent of layer count"),
    ("Sequential_Stacking", "Stacking_Strategy", "S5", VERIFIED,
     "lithography scales roughly linearly with layer count"),
]

# ---------------------------------------------------------------------------
# Unit processes
# ---------------------------------------------------------------------------
CLASSES += [
    ("Substrate_Preparation", "Unit_Process", None, SCAFFOLDING, None),
    ("Wet_Clean", "Substrate_Preparation", "S1, S10, S11", VERIFIED, None),
    ("Native_Oxide_Removal", "Substrate_Preparation", "S9{p.2}", VERIFIED, None),
    ("Pre_Deposition_Oxygen_Flow", "Substrate_Preparation", "S1{II B 2}", VERIFIED,
     "forms self-limiting TiO2"),
    ("Interfacial_Layer_Formation", "Unit_Process", None, SCAFFOLDING, None),
    ("Ozone_Oxidation", "Interfacial_Layer_Formation", "S10{II A}, S11{II}", VERIFIED,
     "O3, 300 C, in the ALD chamber"),
    ("Chemical_Oxidation_Plus_Nitridation", "Interfacial_Layer_Formation", "S9{p.2}", VERIFIED,
     "RTP in NH3, then O2/N2"),
    ("Deposition", "Unit_Process", None, SCAFFOLDING, None),
    ("ALD", "Deposition", "S1{II A}", VERIFIED, None),
    ("Thermal_ALD", "ALD", "S24{2}", VERIFIED, None),
    ("Plasma_Enhanced_ALD", "ALD", "S23{2}", VERIFIED, None),
    ("Radical_Enhanced_ALD", "ALD", "S24{2}", VERIFIED, "Ru from Ru(EtCp)2 + O*"),
    ("PVD", "Deposition", "S1{II B}", VERIFIED, None),
    ("Sputter_Deposition", "PVD", "S1{II B}", VERIFIED, None),
    ("Evaporation", "PVD", "S1{II}", VERIFIED, None),
    ("PLD", "Deposition", "S1{II C}", VERIFIED, None),
    ("CSD", "Deposition", "S1{II D}", VERIFIED, None),
    ("PECVD", "Deposition", "S24{2}", VERIFIED, "SiO2 insulation"),
    ("Thermal_Process", "Unit_Process", None, SCAFFOLDING, None),
    ("Crystallisation_Anneal", "Thermal_Process", "S1{II}, S9, S10, S11, S12a, S23", VERIFIED,
     "RTA/RTP"),
    ("Post_Metallisation_Anneal", "Thermal_Process", "S27{p.1134}", VERIFIED, "furnace, 1 h"),
    ("Dopant_Activation_Anneal", "Thermal_Process", "S10, S11", VERIFIED, "1050 C / 5 s"),
    ("Forming_Gas_Anneal", "Thermal_Process", "S10, S11", VERIFIED, "450 C, 5% H2 / 95% N2"),
    ("Retention_Bake", "Thermal_Process", "S24{3.3}", VERIFIED,
     "85 C diagnostic retention; 105 C fatigue recovery test"),
    ("Implantation", "Unit_Process", "S10, S11", VERIFIED, "channel doping; S/D formation"),
    ("Lithography", "Unit_Process", "S1{II}, S24{2}", VERIFIED, None),
    ("Etch", "Unit_Process", None, SCAFFOLDING, None),
    ("Wet_Etch", "Etch", "S1{II}", VERIFIED, None),
    ("Plasma_Etch", "Etch", "S24{2}", VERIFIED, None),
    ("BEOLProcess", "Unit_Process", "S12a{Fig. 1a}", VERIFIED, None),
    ("Isolation_Deposition", "BEOLProcess", "S12a{Fig. 1a}", VERIFIED, None),
    ("Via_Patterning_And_Etch", "BEOLProcess", "S12a{Fig. 1a}", VERIFIED, None),
    ("Metal_Deposition_And_Patterning", "BEOLProcess", "S12a{Fig. 1a}", VERIFIED, None),
    ("Contact_Formation", "Unit_Process", "S10, S24", VERIFIED, None),
    ("Characterisation", "Unit_Process", None, INFERRED,
     "A metrology or electrical test step, so that characterisation sits inside the flow "
     "ordering and can reach a Metrology_Tool or Electrical_Test_Tool through usesEquipment. "
     "Without it those tools are unreachable, since usesEquipment has domain Unit_Process."),
    ("Structural_Characterisation", "Characterisation", "S9, S24, S27", VERIFIED,
     "GIXRD, TEM, PED, ToF-SIMS"),
    ("Electrical_Characterisation", "Characterisation", "S10, S11, S23, S24", VERIFIED,
     "P-E, PUND, NDPU, IdVg, C-V"),
    ("Electrical_Conditioning", "Unit_Process", None, SCAFFOLDING, None),
    ("Wake_Up_Cycling", "Electrical_Conditioning", "S24{3.2}", UNCERTAIN,
     "Verified as an experimental preparation step, not as a production process step. "
     "Model as a conditioning step used before characterisation; do not assert it is in "
     "any manufacturing flow."),
]

# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------
CLASSES += [
    ("Deposition_Tool", "Equipment", "S1, S23, S24", VERIFIED, None),
    ("Thermal_Tool", "Equipment", "S1{II}, S9, S27", VERIFIED, None),
    ("Lithography_Tool", "Equipment", "S1{II}, S24{2}", UNCERTAIN,
     "No verified source names a specific exposure tool."),
    ("Etch_Tool", "Equipment", "S24{2}", VERIFIED, "plasma etcher"),
    ("Implant_Tool", "Equipment", "S10, S11", VERIFIED, "ion implanter"),
    ("Metrology_Tool", "Equipment", "S1, S9, S24, S27", VERIFIED, None),
    ("Electrical_Test_Tool", "Equipment", "S10, S24, S23", VERIFIED, None),
]

# ---------------------------------------------------------------------------
# Measured properties and degradation
# ---------------------------------------------------------------------------
CLASSES += [
    ("Polarisation_Property", "Measured_Property", None, SCAFFOLDING, None),
    ("Field_Property", "Measured_Property", None, SCAFFOLDING, None),
    ("Device_Property", "Measured_Property", None, SCAFFOLDING, None),
    ("Dielectric_Property", "Measured_Property", None, SCAFFOLDING, None),
    ("Reliability_Property", "Measured_Property", None, SCAFFOLDING, None),
    ("Structural_Property", "Measured_Property", None, SCAFFOLDING, None),
    ("Film_Level_Degradation", "Degradation_Phenomenon", None, INFERRED,
     "Attaches to a Layer_Stack."),
    ("Array_Level_Degradation", "Degradation_Phenomenon", None, INFERRED,
     "Attaches to an Array_Architecture. Before this split, exhibits had no domain that "
     "could carry Pass_Disturb."),
    ("Wake_Up", "Film_Level_Degradation", "S24{3.2}", VERIFIED, None),
    ("First_Stage_Wake_Up", "Wake_Up", "S24{3.2}", VERIFIED, None),
    ("Second_Stage_Wake_Up", "Wake_Up", "S24{3.2}", VERIFIED,
     "activates above 343 K at 1e7-1e8 cycles"),
    ("Wake_Up_Relaxation", "Film_Level_Degradation", "S23{4}", VERIFIED,
     "Vo driven back during idle at 0 V"),
    ("Fatigue", "Film_Level_Degradation", "S24{3.2}", VERIFIED, None),
    ("Imprint", "Film_Level_Degradation", "S23, S24", VERIFIED,
     "'Fluid imprint' reported by S6 as a distinct rapid mechanism under repeated "
     "non-destructive read. Trade press only; not modelled as a subclass."),
    ("Retention_Loss", "Film_Level_Degradation", "S24{3.3}", VERIFIED, None),
    ("Relaxation", "Retention_Loss", "S24{3.3}", VERIFIED, "ruled out in S24's devices"),
    ("Depolarisation_Loss", "Retention_Loss", "S24{3.3}", VERIFIED, None),
    ("Imprint_Driven_Loss", "Retention_Loss", "S24{3.3}", VERIFIED, None),
    ("Charge_Trapping", "Film_Level_Degradation", "S5, S10, S11", VERIFIED, None),
    ("Dielectric_Breakdown", "Film_Level_Degradation", "S24{3.2}", VERIFIED, None),
    ("Pass_Disturb", "Array_Level_Degradation", "S5", VERIFIED, "3D NAND strings"),
    ("Read_Disturb", "Array_Level_Degradation", "S5", VERIFIED,
     "accumulative switching in quasi-non-destructive readout"),
]

# ---------------------------------------------------------------------------
# Vocabulary individuals
# ---------------------------------------------------------------------------
INDIVIDUALS = []

def _batch(names, cls, src, comment=None):
    for n in names:
        INDIVIDUALS.append((n, cls, src, comment))

_batch(["Si_wafer", "Si_001", "Si_p_doped_heavy", "Si_3inch_10ohmcm",
        "Si_8inch_p_type", "SiO2_on_Si_PECVD", "Si_substrate"],
       "Substrate", "S1{II}, S9, S11, S23, S24, S27")
_batch(["HfO2"], "Undoped_HfO2", "S1{I B}")
_batch(["Si_HfO2", "Y_HfO2", "Sr_HfO2", "La_HfO2", "Gd_HfO2", "Al_HfO2",
        "N_HfO2", "Fe_HfO2", "Sc_HfO2", "Ge_HfO2"],
       "Doped_HfO2", "S1{I B, II B 1}")
_batch(["HZO"], "Hafnium_Zirconate", "S1{I}")
_batch(["La_HZO", "Al_codoped_HZO"], "Doped_Hafnium_Zirconate", "S27, S6")
_batch(["HAO"], "Hafnium_Aluminate", "S9{p.2}")
_batch(["TiN", "TaN", "Ru", "W", "Pt", "IrO2", "Al", "Ti_Pt_contact",
        "TiN_gate", "W_cap"],
       "Electrode_Material", "S1{II A 2}, S12a, S24")
_batch(["SiO2", "SiOx", "SiON", "SiO2_IL"], "Interfacial_Layer_Material", "S9, S10, S11")
_batch(["Al2O3"], "Insertion_Layer_Material", "S1{II A 3}, S11")
_batch(["HfO2_seed", "ZrO2_seed"], "Seed_Layer_Material", "S1{II A 3}")
_batch(["TiO2", "HfN"], "Interface_Reaction_Product", "S1{II B 2}")
_batch(["Si_bulk", "polySi", "IGZO"], "Channel_Material", "S5, S6")
_batch(["HfCl4", "TDMA_Hf", "TEMA_Hf", "CpHf_NMe2_3"], "Hf_Precursor", "S1{II A 1}")
_batch(["TDMA_Zr", "TEMA_Zr", "CpZr_NMe2_3"], "Zr_Precursor", "S1{II A 1}")
_batch(["TiCl4", "NH3_precursor", "Ru_EtCp_2"], "Electrode_Precursor", "S23{2}, S24{2}")
_batch(["H2O", "O3", "O2_gas", "O2_plasma", "H2O2"], "Oxidant", "S1{II A 2}, S23{2}")
_batch(["N2", "Ar", "O2", "NH3", "forming_gas_5H2_95N2", "SF6"],
       "Process_Gas", "S1, S9, S10, S24")
_batch(["HfO2_target", "ZrO2_target", "Hf_metal", "Y2O3_target", "HZO_target"],
       "Sputter_Target", "S1{II B, Table III}")
_batch(["SC1", "dilute_HF"], "Wet_Chemical", "S1{II}, S10, S11")
_batch(["Si4", "Y3", "Sr2", "La3", "Gd3", "Al3", "N3", "Zr4",
        "Fe3", "Sc", "Ge", "Ce", "Nd", "Sm", "Er", "Yb"],
       "Dopant", "S1{I B, II B 1, II D}")

# Phases are individuals, not classes: the causal properties relate individuals, and the
# instance document types them as such. See DECISIONS.md, D1.
_batch(["Orthorhombic_Pca21"], "Crystalline_Phase", "S1{I A}", "ferroelectric")
_batch(["Orthorhombic_Pbca"], "Crystalline_Phase", "S1{II E}", "non-ferroelectric")
_batch(["Tetragonal_P42nmc"], "Crystalline_Phase", "S1{I A}", "non-ferroelectric")
_batch(["Monoclinic_P21c"], "Crystalline_Phase", "S1{I A}", "non-ferroelectric, bulk-stable")
_batch(["Cubic_Fm3m"], "Crystalline_Phase", "S1{I A}", None)

_batch(["Oxygen_Vacancy"], "Point_Defect", "S1{I B, II A 2}", "stabilises o- and t-phase")
_batch(["Oxygen_Interstitial"], "Point_Defect", "S1{II A 2}", "removes barrier to m-phase")
_batch(["Metal_Vacancy"], "Point_Defect", "S10{III D}", "Hf, Zr: origin of deep traps")
_batch(["Et1", "Et2"], "Electronic_Trap", "S10{III D}")

_batch(["ALD_reactor", "PEALD_reactor", "REALD_reactor", "DC_magnetron_sputter",
        "RF_magnetron_sputter", "PLD_chamber", "PECVD_tool", "spin_coater",
        "Picosun_R200adv"],
       "Deposition_Tool", "S1, S23, S24")
_batch(["RTP_system", "furnace"], "Thermal_Tool", "S1{II}, S9, S27")
_batch(["GIXRD_diffractometer", "TEM", "HRTEM", "PED_ASTAR_system", "ToF_SIMS",
        "XPS", "EDS", "ARL_XTRA", "Titan3_G2", "DIGISTAR_P2010"],
       "Metrology_Tool", "S1, S9, S24, S27")
_batch(["probe_station", "ferroelectric_tester", "parameter_analyzer", "pulse_generator",
        "Keysight_B1500A", "Radiant_Precision_LC", "Summit_11000B_M", "F3000_Liryder"],
       "Electrical_Test_Tool", "S10, S24, S23")

_batch(["Conformality", "SubNanometreThicknessControl", "LineOfSight",
        "SelfLimitingGrowth", "HighDepositionRate", "LowCarbonContamination",
        "EtchSelectivityToHfO2", "EpitaxialGrowth"],
       "Capability", "S1{II A, II B, III}, S24{1}")

_batch(["PE_Hysteresis", "PUND", "NDPU", "Dynamic_IswE", "Small_Signal_CV", "QSCV",
        "Endurance_Cycling", "Retention_Measurement", "IdVg_Transfer",
        "Permittivity_From_Displacement_Current", "GIXRD_Phase_Analysis",
        "PED_Orientation_Mapping", "ToF_SIMS_Depth_Profiling"],
       "Measurement_Method", "S1, S9, S10, S23, S24, S27")

_batch(["remanent_polarisation_Pr", "double_remanent_2Pr", "switched_polarisation_Psw",
        "saturated_polarisation_Ps"], "Polarisation_Property", None)
_batch(["coercive_field_Ec", "coercive_voltage_Vc", "bias_field_Ebias",
        "depolarisation_field_Ed", "interfacial_field_EI", "built_in_field_Ebuilt_in",
        "breakdown_field"], "Field_Property", None)
_batch(["memory_window_MW", "threshold_voltage_Vth", "sense_margin", "bitline_voltage_VBL",
        "switching_speed", "on_current_Ion"], "Device_Property", None)
_batch(["relative_permittivity_k", "leakage_current_density"], "Dielectric_Property", None)
_batch(["endurance_cycles", "retention_time", "imprint_shift", "wakeup_magnitude",
        "trapped_charge_density"], "Reliability_Property", None)
_batch(["phase_fraction", "grain_size", "grain_aspect", "film_thickness",
        "carbon_impurity", "oxygen_vacancy_concentration", "growth_per_cycle",
        "film_density", "crystallographic_texture", "composition_ratio",
        "crystallisation_onset"], "Structural_Property", None)

_batch(["node_130nm"], "Technology_Node", "S12a{P4}")

# Layer roles: a closed vocabulary, and one of the few places where closing the world
# is correct, because the role set is a modelling decision rather than a claim.
LAYER_ROLES = ["substrate", "interfacial_layer", "insertion_layer", "seed_layer",
               "bottom_electrode", "ferroelectric_layer", "internal_electrode",
               "top_electrode", "gate_metal", "contact_pad", "channel"]
_batch(LAYER_ROLES, "Layer_Role", None)
