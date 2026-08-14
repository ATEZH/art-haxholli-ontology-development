# -*- coding: utf-8 -*-
"""
Object and data properties, transcribed from OntologySpec v3 sections 3 and 4.

OBJECT_PROPERTIES entries:
    (name, domain, range, characteristics, source_locator, status, comment)

domain/range are either a class name, or a list of class names meaning owl:unionOf.
None means the property is left undeclared on that side, which the spec does not do
anywhere; the verifier checks for it.

characteristics is a list drawn from:
    transitive, symmetric, asymmetric, reflexive, irreflexive, functional,
    inverse_functional
"""

from vocab import VERIFIED, UNCERTAIN, INFERRED, SCAFFOLDING

OBJECT_PROPERTIES = [
    # -- process ordering -----------------------------------------------------
    ("belongsToFlow", "Unit_Process", "Process_Flow", [], None, SCAFFOLDING,
     "Required on every Unit_Process individual. Without it, precedes produces "
     "contradictions between Flow C and the rest."),
    ("directlyPrecedes", "Unit_Process", "Unit_Process", ["asymmetric", "irreflexive"],
     None, SCAFFOLDING,
     "Immediate ordering within one flow. Deliberately NOT transitive; precedes is the "
     "transitive property."),
    ("precedes", "Unit_Process", "Unit_Process",
     ["transitive"], None, SCAFFOLDING,
     "Transitive closure of directlyPrecedes, scoped by flow. Asserted only between steps "
     "sharing a belongsToFlow value. "
     "NOTE: the specification asked for transitive AND asymmetric AND irreflexive. That "
     "combination is illegal in OWL 2 DL: asymmetry and irreflexivity may only be declared "
     "on simple properties, and a transitive property is by definition non-simple. HermiT "
     "rejects the ontology outright rather than reporting an inconsistency. Transitivity is "
     "the useful half, so it is kept. Acyclicity is enforced at generation time and would "
     "belong in SHACL, not OWL. directlyPrecedes is simple and keeps both characteristics."),
    ("flowProducesArchitecture", "Process_Flow",
     ["Memory_Cell_Architecture", "Layer_Stack"], [], None, SCAFFOLDING,
     "Flow C produces FeRAM_1T1C; Flow E produces MFM; Flow B1 produces MFIS."),
    ("flowTargetsNode", "Process_Flow", "Technology_Node", [], "S12a{P4}", VERIFIED,
     "Flow C targets 130 nm."),

    # -- process composition --------------------------------------------------
    ("hasInput", "Unit_Process", ["Material", "Artifact"], [], None, SCAFFOLDING, None),
    ("hasOutput", "Unit_Process", ["Material", "Artifact"], [], None, SCAFFOLDING, None),
    ("usesEquipment", "Unit_Process", "Equipment", [], "S24{2}", VERIFIED,
     "Many-to-many. One ALD reactor serves electrode and ferroelectric deposition in S24."),
    ("usesPrecursor", "Deposition", "Chemical_Precursor", [], None, SCAFFOLDING, None),
    ("usesOxidant", "Deposition", "Oxidant", [], None, SCAFFOLDING, None),
    ("usesProcessGas", "Unit_Process", "Process_Gas", [], None, SCAFFOLDING,
     "Covers carrier, sputter, anneal ambient and etch gases."),
    ("usesTarget", "Sputter_Deposition", "Sputter_Target", [], None, SCAFFOLDING, None),
    ("depositsMaterial", "Deposition", "Material", [], None, SCAFFOLDING, None),
    ("etchesMaterial", "Etch", "Material", [], "S24{2}", VERIFIED, None),
    ("hasAmbient", "Thermal_Process", "Process_Gas", [], "S1{II B 2}", VERIFIED,
     "N2 recommended over O2."),

    # -- structure ------------------------------------------------------------
    ("hasSlot", "Layer_Stack", "Layer_Slot", [], None, INFERRED,
     "Ordered via the slot's layerIndex. Replaces the earlier hasLayer / "
     "hasLayerAtPosition pair."),
    ("slotMaterial", "Layer_Slot", "Material", ["functional"], None, INFERRED,
     "One slot holds exactly one material."),
    ("slotRole", "Layer_Slot", "Layer_Role", ["functional"], "S1{II}", INFERRED,
     "The function the material serves here. Pt is an Electrode_Material by class but a "
     "contact_pad by role in an MFM coupon and a bottom_electrode by role in a PLD stack."),
    ("hasElectrode", "Layer_Stack", "Electrode_Material", [], None, INFERRED,
     "DERIVED, not asserted by hand. Shortcut for the material of a slot whose slotRole is "
     "an electrode role. The slot is authoritative."),
    ("hasTopElectrode", "Layer_Stack", "Electrode_Material", [], None, INFERRED,
     "Derived. rdfs:subPropertyOf hasElectrode."),
    ("hasBottomElectrode", "Layer_Stack", "Electrode_Material", [], None, INFERRED,
     "Derived. rdfs:subPropertyOf hasElectrode."),
    ("hasInterfacialLayer", "Layer_Stack", "Interfacial_Layer_Material", [], None, INFERRED,
     "Derived, from slotRole = interfacial_layer."),
    ("hasFerroelectricLayer", "Layer_Stack", "Ferroelectric_Material", [], None, INFERRED,
     "Derived, from slotRole = ferroelectric_layer."),
    ("hasChannel", "Memory_Cell_Architecture", "Channel_Material", [], None, SCAFFOLDING, None),
    ("usesStack", "Memory_Cell_Architecture", "Layer_Stack", [], "S5", VERIFIED,
     "FeFET_1T uses MFIS; FeMFET_1T1C uses MFMIS."),
    ("hasDopant", "Ferroelectric_Material", "Dopant", [], None, SCAFFOLDING, None),
    ("hasPhase", ["Material", "Layer_Stack"], "Phase_State", [], "S27{Fig. 1a}", UNCERTAIN,
     "Films are phase mixtures, so this is a simplification. Non-functional, and absence of "
     "a phase assertion never denies the phase. A quantified fraction is a Measurement."),
    ("arrangedAs", "Memory_Cell_Architecture", "Array_Architecture", [], None, SCAFFOLDING, None),
    ("usesStackingStrategy", "Array_Architecture", "Stacking_Strategy", [], None,
     SCAFFOLDING, None),

    # -- causal ---------------------------------------------------------------
    # Deliberately no characteristics on any of these: they are experimentally
    # inferred, hold under conditions, and are multiply realised.
    ("stabilisesPhase", ["Material", "Defect"], "Phase_State", [], "S1{I A, I B, II A 2}",
     VERIFIED, None),
    ("destabilisesPhase", ["Material", "Defect"], "Phase_State", [], "S1{II A 2}",
     VERIFIED, None),
    ("transformsPhase", "Unit_Process", "Phase_State", [], "S24{2}", VERIFIED,
     "Domain is Unit_Process, not Thermal_Process. In Flow E an ALD electrode deposition "
     "performs the transformation."),
    ("scavengesOxygenFrom", "Electrode_Material", "Ferroelectric_Material", [],
     "S1{II A 2}, S24{4}", VERIFIED,
     "TiN and TaN scavenge; IrO2 does not and degrades ferroelectricity; Ru scavenges less "
     "than TiN."),
    ("diffusesInto", ["Dopant", "Material"], "Material", [], "S9{p.5}", VERIFIED,
     "Zr4 diffuses into SiON, degrading the interfacial layer."),
    ("templates", "Material", "Material", [], "S27{p.1134}", UNCERTAIN,
     "t-phase grains sit within 5 degrees of both TiN layers, suggesting near-epitaxial "
     "growth during PMA. S27 says 'may be some kind of': implied, not demonstrated."),
    ("exhibits", ["Layer_Stack", "Memory_Cell_Architecture", "Array_Architecture"],
     "Degradation_Phenomenon", [], None, SCAFFOLDING,
     "Domain includes Array_Architecture: Pass_Disturb is a 3D NAND string phenomenon and "
     "had no possible subject before."),
    ("mitigatedBy", "Degradation_Phenomenon", ["Unit_Process", "Material"], [],
     "S24{3.2}, S1{II A 3}", VERIFIED, None),
    ("enables", "Capability", ["Array_Architecture", "Memory_Cell_Architecture"], [],
     "S1{II B}", VERIFIED, None),
    ("precludes", "Capability", ["Array_Architecture", "Memory_Cell_Architecture"], [],
     "S1{II B}", VERIFIED,
     "LineOfSight precludes the 3D capacitor. Previously stated only in prose on enables."),
    ("requiresCapability", ["Unit_Process", "Array_Architecture"], "Capability", [],
     None, SCAFFOLDING, None),
    ("constrainsMaterialChoice", "Capability", "Material", [], "S24{1}", UNCERTAIN,
     "Ru selected partly because a dry plasma etch selective to HfO2 exists for it: stated "
     "as a motivation, not a demonstrated constraint."),

    # -- measurement and evidence --------------------------------------------
    ("hasMeasurement", ["Artifact", "Layer_Stack", "Memory_Cell_Architecture"],
     "Measurement", [], None, SCAFFOLDING, None),
    ("measurementMethod", "Measurement", "Measurement_Method", ["functional"], None,
     SCAFFOLDING, None),
    ("measuresProperty", "Measurement", "Measured_Property", ["functional"], None,
     SCAFFOLDING, None),
    ("measuredOn", "Measurement", "Artifact", ["functional"], "S12a{P5}", VERIFIED,
     "Distinguish blanket film, patterned capacitor, single cell and array. S12a measures "
     "both 1C and 1T-1C and reports they agree."),
    ("producesMeasurement", "Characterisation", "Measurement", [], None, INFERRED,
     "Links the characterisation step to what it produced. A characterisation is a "
     "Unit_Process, so it also carries belongsToFlow and its position in the ordering."),
]

# ---------------------------------------------------------------------------
# Data properties
#   (name, domain, xsd_type, source_locator, status, comment, oneof_values)
# ---------------------------------------------------------------------------
XSD_DOUBLE = "double"
XSD_INT = "int"
XSD_LONG = "long"
XSD_STRING = "string"
XSD_BOOL = "boolean"

DATA_PROPERTIES = [
    # -- Measurement ----------------------------------------------------------
    ("hasMeasuredValue", "Measurement", XSD_DOUBLE, None, SCAFFOLDING,
     "Renamed from hasValue: owl:hasValue is a reserved OWL construct and the name "
     "collides on sight even across namespaces.", None),
    ("hasUnit", "Measurement", XSD_STRING, None, SCAFFOLDING, None, None),
    ("hasAppliedVoltage_V", "Measurement", XSD_DOUBLE, None, SCAFFOLDING, None, None),
    ("hasAppliedField_MVcm", "Measurement", XSD_DOUBLE, None, SCAFFOLDING, None, None),
    ("hasFrequency_Hz", "Measurement", XSD_DOUBLE, None, SCAFFOLDING, None, None),
    ("hasPulseWidth_s", "Measurement", XSD_DOUBLE, None, SCAFFOLDING, None, None),
    ("hasIntervalTime_s", "Measurement", XSD_DOUBLE, "S23{2}", VERIFIED, None, None),
    ("hasTemperature_C", "Measurement", XSD_DOUBLE, None, SCAFFOLDING, None, None),
    ("hasEnduranceCycleCount", "Measurement", XSD_LONG, None, SCAFFOLDING,
     "Renamed from hasCycleCount, which was also declared on Unit_Process with a different "
     "range and an unrelated meaning.", None),
    ("hasBakeTime_min", "Measurement", XSD_DOUBLE, "S24{3.3}", VERIFIED, None, None),
    ("hasWaveform", "Measurement", XSD_STRING, None, SCAFFOLDING, None,
     ["PUND", "NDPU", "triangle", "square", "trapezoidal"]),
    ("hasVthConvention", "Measurement", XSD_STRING, "S10{II A}, S11{II}", VERIFIED,
     "S10 uses linear extrapolation, S11 constant current, on near-identical stacks. "
     "Memory windows are not comparable without this field.",
     ["linear_extrapolation", "constant_current"]),
    ("hasPolarisationStateType", "Measurement", XSD_STRING, "S24{3.3}", VERIFIED, None,
     ["SS", "NSS", "OS"]),
    ("fractionMethod", "Measurement", XSD_STRING, "S24{3.1}, S9{p.3}, S27", VERIFIED,
     "Moved from Phase_State. A phase fraction without its method is not interpretable.",
     ["GIXRD_intensity_ratio", "PED_mapping", "k_value_inference"]),
    ("phasesLumped", "Measurement", XSD_STRING, "S24{3.1}", VERIFIED,
     "Moved from Phase_State. o and t peaks overlap in GI-XRD, so many sources quantify m "
     "only and lump o+t.", ["o+t", "none"]),

    # -- Unit_Process ---------------------------------------------------------
    ("hasProcessTemperature_C", "Unit_Process", XSD_DOUBLE, "S1, S9, S10, S11", VERIFIED,
     "Verified range 150 to 1050.", None),
    ("hasProcessDuration_s", "Unit_Process", XSD_DOUBLE, "S10, S24", VERIFIED,
     "Verified range 1 to 14400.", None),
    ("hasProcessPressure_mbar", "Unit_Process", XSD_DOUBLE, "S1 Tables III, IV", VERIFIED,
     None, None),
    ("hasBasePressure_mbar", "Unit_Process", XSD_DOUBLE, "S1", VERIFIED, None, None),
    ("hasGasFlow_sccm", "Unit_Process", XSD_DOUBLE, "S1{II B 2}", VERIFIED, None, None),
    ("hasPulseTime_s", "Unit_Process", XSD_DOUBLE, "S24{2}", VERIFIED, None, None),
    ("hasPurgeTime_s", "Unit_Process", XSD_DOUBLE, "S24{2}", VERIFIED, None, None),
    ("hasOxidantDoseTime_s", "Unit_Process", XSD_DOUBLE, "S1{II A 2}", VERIFIED,
     "Optimum 1 to 5.", None),
    ("hasDepositionCycleCount", "Unit_Process", XSD_INT, "S24{2}", VERIFIED,
     "65 supercycles for about 10 nm HZO.", None),
    ("hasGrowthPerCycle_nm", "Unit_Process", XSD_DOUBLE, "S1{II A 1}", VERIFIED, None, None),
    ("hasCoolingRate_Cps", "Unit_Process", XSD_DOUBLE, "S1{I C}", VERIFIED, None, None),
    ("hasImplantEnergy_keV", "Unit_Process", XSD_DOUBLE, "S10, S11", VERIFIED, None, None),
    ("hasImplantDose_cm2", "Unit_Process", XSD_DOUBLE, "S10, S11", VERIFIED, None, None),
    ("isCrystallising", "Unit_Process", XSD_BOOL, "S24{2}", VERIFIED,
     "True for E5, an ALD deposition that crystallises the film without a separate anneal.",
     None),
    ("hasStepIndex", "Unit_Process", XSD_INT, None, SCAFFOLDING,
     "A convenience key, not the authoritative ordering. belongsToFlow with "
     "directlyPrecedes is what the model asserts.", None),

    # -- Layer_Slot -----------------------------------------------------------
    ("layerIndex", "Layer_Slot", XSD_INT, None, INFERRED,
     "1 at the bottom, ascending upward.", None),
    ("hasSlotThickness_nm", "Layer_Slot", XSD_DOUBLE, "S9, S10, S11, S12a, S23, S24, S27",
     VERIFIED,
     "Was hasFilmThickness_nm on Material. Moved because the same material individual "
     "appears in stacks of different thickness: HZO at 9 nm in Flow B1 and 9.5 nm in Flow G.",
     None),

    # -- Material (specified and nominal only) --------------------------------
    ("hasNominalHfZrRatio", "Material", XSD_DOUBLE, "S9{p.2}", VERIFIED,
     "The nominal 1:1. S24's measured 0.8 is a Measurement, not this property.", None),
    ("hasDopantConcentration_atPct", "Material", XSD_DOUBLE,
     "S27{p.1134}, S1 Table III", VERIFIED, None, None),
    ("hasDopantConcentration_molPct", "Material", XSD_DOUBLE, "S1{II B 1, II D}", VERIFIED,
     None, None),
    ("hasDopantRatio", "Material", XSD_STRING, "S9{p.2}", VERIFIED, "e.g. Al:Hf = 1:30", None),
    ("hasBandgap_eV", "Material", XSD_DOUBLE, "S1{I}, S23{1}", VERIFIED, None, None),

    # -- Phase_State ----------------------------------------------------------
    ("hasSpaceGroup", "Phase_State", XSD_STRING, "S1{I A}", VERIFIED, None, None),
    ("isFerroelectric", "Phase_State", XSD_BOOL, "S1{I A}", VERIFIED,
     "True only for Pca21, and for the contested R3m.", None),
    ("hasRelativeEnergy_meVperFU", "Phase_State", XSD_DOUBLE, "S1{I B}", VERIFIED, None, None),
    ("hasTransformationBarrier_meVperFU", "Phase_State", XSD_DOUBLE, "S1{I C}", VERIFIED,
     None, None),
    ("hasPermittivity_k", "Phase_State", XSD_DOUBLE, "S24, S23", UNCERTAIN,
     "DISPUTED. Both figures are secondary citations of Park-group work; neither S23 nor "
     "S24 measured phase permittivities directly. See U8.", None),

    # -- Artifact -------------------------------------------------------------
    ("hasSpecimenLabel", "Artifact", XSD_STRING, None, SCAFFOLDING, None, None),
    ("hasCyclingHistory_cycles", "Artifact", XSD_LONG, "S24, S10", VERIFIED,
     "What separates S10's pristine and cycled trap-density figures without either "
     "overwriting the other.", None),

    # -- Memory_Cell_Architecture --------------------------------------------
    ("hasCellArea_um2", "Memory_Cell_Architecture", XSD_DOUBLE, "S6", UNCERTAIN,
     "0.009 for the TSMC OS FeFET, trade press only.", None),
    ("hasCapacitorDiameter_um", "Memory_Cell_Architecture", XSD_DOUBLE, "S12a{P4}",
     VERIFIED, None, None),
    ("hasContactPadArea_cm2", "Memory_Cell_Architecture", XSD_DOUBLE, "S24{2}", VERIFIED,
     None, None),
    ("hasGateLength_um", "Memory_Cell_Architecture", XSD_DOUBLE, "S10, S11", VERIFIED,
     None, None),
    ("hasGateWidth_um", "Memory_Cell_Architecture", XSD_DOUBLE, "S10, S11", VERIFIED,
     None, None),
    ("hasArraySize_bit", "Memory_Cell_Architecture", XSD_INT, "S12a", VERIFIED, None, None),
    ("hasBitlineLength_bit", "Memory_Cell_Architecture", XSD_INT, "S12a{P6}", VERIFIED,
     None, None),
    ("hasWriteVoltage_V", "Memory_Cell_Architecture", XSD_DOUBLE, "S11{III}", VERIFIED,
     None, None),
    ("hasReferenceVoltage_V", "Memory_Cell_Architecture", XSD_DOUBLE, "S12a{P6}", VERIFIED,
     None, None),
]

# ---------------------------------------------------------------------------
# Annotation properties, declared before everything else.
# ---------------------------------------------------------------------------
ANNOTATION_PROPERTIES = [
    ("sourceLocator",
     "The per-entity source tag, e.g. S1{II A 2} meaning source S1, section II A 2. "
     "Repeatable: an entity may be attested by several sources."),
    ("epistemicStatus",
     "One of: verified, uncertain, inferred, scaffolding, named_only. Formalises the "
     "UNCERTAIN and INFERRED markers and the untagged-scaffolding rule from the "
     "specification front matter."),
    ("uncertaintyRef",
     "Points an entity at its entry in the uncertainty register, e.g. U13."),
    ("contradictedBy",
     "Marks an entity whose own source contradicts itself, naming the source."),
    ("scopeNote",
     "Records what a class deliberately excludes."),
]
