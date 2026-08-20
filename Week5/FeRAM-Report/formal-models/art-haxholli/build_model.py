#!/usr/bin/env python3
"""Build the ALD HfO2 Deposition OWL 2 DL ontology from ``claim_ledger.xlsx``.

The program constructs the Chapter 3 schema, the fixed BS3 worked-route
population, coverage assessments, process variables, and optional report-derived
window and gap scaffolds.  Run it with Python 3.11 or newer, for example::

    python build_ontology.py --ledger claim_ledger.xlsx --sheet "Corrected Ledger" --out ald_hfo2.ttl --report-date 2026-08-20 --run-cq

It writes canonical LongTurtle to ``--out`` and a UTF-8 validation report to
``--verification-report`` (by default, beside the Turtle file).  RDFLib checks,
round-trip comparison, graph-shape checks, and competency questions are
structural validation; only release mode with ROBOT's OWL 2 DL profile check and
HermiT reasoning is external release verification.  The BS3 claims are a
second-hand ledger transcription associated with Tsai et al. (2022); this build
does not independently reverify them against the publication.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Sequence

import openpyxl
import pandas as pd
import rdflib
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS, XSD


LOGGER = logging.getLogger("build_ontology")

ONTOLOGY_IRI = URIRef(
    "https://github.com/OPXHS/Ontologies-Development/ontology/ald-hfo2"
)
ALD = Namespace(f"{ONTOLOGY_IRI}#")
PROJECT_PREFIX = str(ALD)
REPORT_REPOSITORY_IRI = URIRef("https://github.com/OPXHS/Ontologies-Development")
TSAI_DOI_IRI = URIRef("https://doi.org/10.1021/acsaelm.1c01321")

LEDGER_SHEET = "Corrected Ledger"
COVERAGE_SHEET = "Output 3 - Coverage"
LEDGER_ROW_COUNT = 754
BS3_CAVEAT = (
    "recorded in Berine dataset from Tsai 2022; not independently verified "
    "against the source"
)
WINDOW_SCAFFOLD_NOTE = (
    "Window evidence derives from non-BS3 claims that are not instantiated in "
    "this build; no numeric bounds are asserted."
)
REPORT_GAP_SOURCE = "Section 3.12, Table 3.7"
REPORT_GAP_NOTE = (
    "Unreported in the worked-route summary; do not fill from another configuration."
)
TRANSFER_BLOCK_TEXT = "delivery mode and line temperatures unreported"
THERMAL_MATCH_RATIONALE = (
    "The 500 C, 30 s, N2 RTP tuple matches a non-BS3 TiN/HZO/TiN "
    "post-metallization route documented in report reference choi2022chamber; "
    "agreement is corroboration, not evidence of preference."
)
NECESSARY_ORDER_RATIONALE = (
    "Bottom-electrode formation precedes HZO deposition in every ledger route "
    "that states this relation; no ledger claim reverses it."
)

LEDGER_COLUMNS = (
    "claim_id",
    "source_id",
    "locator",
    "target",
    "field",
    "value",
    "unit",
    "condition",
    "anchor",
    "note",
    "helper_target",
    "helper_source",
    "claim_id_original",
    "extraction_batch",
)

EXPECTED_SOURCE_COUNTS = {
    "S1": 43,
    "S2": 107,
    "S3": 43,
    "S4": 79,
    "S5": 69,
    "S6": 51,
    "S7": 61,
    "S8": 42,
    "S9": 51,
    "S10": 57,
    "S11": 46,
    "S13": 17,
    "S14": 63,
    "BS3": 25,
}

TARGETS = (
    "flow/surface-preclean",
    "flow/interface-prep",
    "flow/electrode-integration",
    "flow/hf-precursor-pulse",
    "flow/first-purge",
    "flow/co-reactant-pulse",
    "flow/second-purge",
    "flow/cycle-repetition",
    "flow/post-deposition-treatment",
    "flow/electrical-qualification",
    "param/thickness-growth-per-cycle",
    "param/conformality-uniformity",
    "param/polarization-coercive-field",
    "param/leakage-current",
    "param/defect-density-reliability",
    "metrology/film-thickness-uniformity",
    "metrology/crystalline-phase",
    "metrology/hysteresis-reliability",
    "metrology/leakage-breakdown",
    "metrology/interface-defect",
    "input-condition",
    "materials-equipment",
    "unassigned",
)

FIELDS = (
    "parameter_value",
    "metrology_technique",
    "limitation",
    "composition",
    "electrode_material",
    "film_thickness",
    "cycle_structure",
    "precursor",
    "interface_layer",
    "uniformity_result",
    "electrode_method",
    "anneal_temperature",
    "co_reactant",
    "anneal_sequence",
    "deposition_temperature",
    "anneal_ambient",
    "tool_name",
    "electrode_thickness",
    "anneal_time",
    "clean_chemistry",
    "pulse_time",
    "growth_per_cycle",
    "reactor_type",
    "precursor_source_temperature",
    "plasma_power",
    "seed_layer",
    "wafer_size",
    "line_temperature",
    "chamber_pressure",
    "carrier_gas",
    "purge_time",
)

UNIT_IRI_NAMES = {
    "nm": "Unit_nm",
    "uC/cm2": "Unit_uC_cm2",
    "cycles": "Unit_cycles",
    "C": "Unit_C",
    "%": "Unit_percent",
    "s": "Unit_s",
    "MV/cm": "Unit_MV_cm",
    "V": "Unit_V",
    "ns": "Unit_ns",
    "W": "Unit_W",
    "uC m-2 K-1": "Unit_uC_m_minus2_K_minus1",
    "eV": "Unit_eV",
    "mTorr": "Unit_mTorr",
    "A/cycle": "Unit_A_cycle",
    "deg": "Unit_deg",
    "um2": "Unit_um2",
    "supercycles": "Unit_supercycles",
    "us": "Unit_us",
    "um": "Unit_um",
    "Hz": "Unit_Hz",
    "K": "Unit_K",
    "GPa": "Unit_GPa",
    "A": "Unit_A",
    "kHz": "Unit_kHz",
    "A/cm2": "Unit_A_cm2",
    "orders of magnitude": "Unit_orders_of_magnitude",
    "sccm": "Unit_sccm",
    "fJ": "Unit_fJ",
    "Gbit": "Unit_Gbit",
    "kV/cm": "Unit_kV_cm",
    "pm/V": "Unit_pm_V",
    "nJ": "Unit_nJ",
    "ps": "Unit_ps",
    "dB": "Unit_dB",
    "meV": "Unit_meV",
    "eV*Angstrom": "Unit_eV_Angstrom",
    "fJ/bit": "Unit_fJ_bit",
    "W/cm2": "Unit_W_cm2",
    "C/s": "Unit_C_s",
    "cm-1": "Unit_cm_minus1",
    "kV": "Unit_kV",
    "g/m3": "Unit_g_m3",
    "min": "Unit_min",
    "ohm": "Unit_ohm",
    "ohm/sq": "Unit_ohm_sq",
    "MHz": "Unit_MHz",
    "cm2": "Unit_cm2",
    "mA": "Unit_mA",
    "mm": "Unit_mm",
    "ms": "Unit_ms",
    "g/Nm3": "Unit_g_Nm3",
    "fold": "Unit_fold",
}

EXPECTED_BS3_TARGETS = {
    **{f"BS3-{index:03d}": "flow/electrode-integration" for index in range(1, 7)},
    "BS3-007": "input-condition",
    "BS3-008": "input-condition",
    **{f"BS3-{index:03d}": "flow/hf-precursor-pulse" for index in range(9, 14)},
    "BS3-014": "flow/cycle-repetition",
    "BS3-015": "flow/co-reactant-pulse",
    "BS3-016": "flow/electrode-integration",
    "BS3-017": "flow/electrode-integration",
    **{f"BS3-{index:03d}": "unassigned" for index in range(18, 23)},
    **{
        f"BS3-{index:03d}": "flow/post-deposition-treatment"
        for index in range(23, 26)
    },
}

EXPECTED_BS3_CONTENT = {
    "BS3-001": ("electrode_material", "TiN used as bottom electrode", ""),
    "BS3-002": ("electrode_thickness", "bottom TiN electrode thickness 15", "nm"),
    "BS3-003": ("parameter_value", "sputter power 100", "W"),
    "BS3-004": ("parameter_value", "Ar flow 50", "sccm"),
    "BS3-005": ("parameter_value", "N2 flow 3", "sccm"),
    "BS3-006": ("parameter_value", "sputter chamber pressure 2.5", "mTorr"),
    "BS3-007": ("composition", "Hf0.5Zr0.5O2", ""),
    "BS3-008": ("film_thickness", "10", "nm"),
    "BS3-009": ("deposition_temperature", "250", "C"),
    "BS3-010": ("precursor", "TEMAH", ""),
    "BS3-011": ("precursor_source_temperature", "TEMAH source temperature 90", "C"),
    "BS3-012": ("precursor", "TEMAZ", ""),
    "BS3-013": ("precursor_source_temperature", "TEMAZ source temperature 110", "C"),
    "BS3-014": ("cycle_structure", "HfO2:ZrO2 cycle ratio 1:1", ""),
    "BS3-015": ("co_reactant", "oxidant not reported for this route", ""),
    "BS3-016": ("electrode_material", "TiN used as top electrode", ""),
    "BS3-017": ("electrode_thickness", "top TiN electrode thickness 15", "nm"),
    "BS3-018": (
        "parameter_value",
        "photolithography used for capacitor pattern definition",
        "",
    ),
    "BS3-019": (
        "limitation",
        "detailed lithography parameters not reported for this route",
        "",
    ),
    "BS3-020": ("clean_chemistry", "NH4OH:H2O2:H2O wet etchant", ""),
    "BS3-021": ("clean_chemistry", "NH4OH:H2O2:H2O etchant ratio 1:1:5", ""),
    "BS3-022": ("parameter_value", "wet etch temperature 60", "C"),
    "BS3-023": ("anneal_temperature", "crystallization anneal at 500", "C"),
    "BS3-024": ("anneal_time", "anneal duration 30", "s"),
    "BS3-025": ("anneal_ambient", "N2", ""),
}

THIN_BARE_EXPECTED = {
    "input-condition": (7, 3, "thin"),
    "flow/surface-preclean": (7, 6, "thin"),
    "flow/first-purge": (3, 1, "thin"),
    "flow/second-purge": (1, 1, "bare"),
    "unassigned": (8, 2, "thin"),
}

QUANTITY_CLAIM_IDS = (
    "BS3-002",
    "BS3-003",
    "BS3-004",
    "BS3-005",
    "BS3-006",
    "BS3-008",
    "BS3-009",
    "BS3-011",
    "BS3-013",
    "BS3-014",
    "BS3-017",
    "BS3-021",
    "BS3-022",
    "BS3-023",
    "BS3-024",
)
RATIO_CLAIM_IDS = ("BS3-014", "BS3-021")

EXPECTED_PARSED_VALUES: dict[str, Decimal | str] = {
    "BS3-002": Decimal("15"),
    "BS3-003": Decimal("100"),
    "BS3-004": Decimal("50"),
    "BS3-005": Decimal("3"),
    "BS3-006": Decimal("2.5"),
    "BS3-008": Decimal("10"),
    "BS3-009": Decimal("250"),
    "BS3-011": Decimal("90"),
    "BS3-013": Decimal("110"),
    "BS3-014": "1:1",
    "BS3-017": Decimal("15"),
    "BS3-021": "1:1:5",
    "BS3-022": Decimal("60"),
    "BS3-023": Decimal("500"),
    "BS3-024": Decimal("30"),
}

EXPECTED_HANDLER_EFFECTS = {
    "BS3-001": "bottom_material",
    "BS3-002": "quantity",
    "BS3-003": "quantity",
    "BS3-004": "ar_flow",
    "BS3-005": "n2_flow",
    "BS3-006": "quantity",
    "BS3-007": "hzo_material",
    "BS3-008": "quantity",
    "BS3-009": "quantity",
    "BS3-010": "temah",
    "BS3-011": "quantity_hf",
    "BS3-012": "temaz",
    "BS3-013": "quantity_zr",
    "BS3-014": "ratio_cycle",
    "BS3-015": "co_reactant_gap",
    "BS3-016": "top_material",
    "BS3-017": "quantity",
    "BS3-018": "photolithography",
    "BS3-019": "lithography_gap",
    "BS3-020": "etchant",
    "BS3-021": "ratio_etchant",
    "BS3-022": "quantity",
    "BS3-023": "quantity",
    "BS3-024": "quantity",
    "BS3-025": "anneal_ambient",
}

ROUTE_INSTANCE_IDS = (
    "Instance_BS3_002",
    "Instance_BS3_003",
    "Instance_BS3_004",
    "Instance_BS3_005",
    "Instance_BS3_006",
    "Instance_BS3_008",
    "Instance_BS3_009",
    "Instance_BS3_011",
    "Instance_BS3_013",
    "Instance_BS3_014",
    "Instance_BS3_017",
    "Instance_BS3_021",
    "Instance_BS3_022",
    "Instance_BS3_Thermal_Treatment_Tuple",
)

QUANTITY_VARIABLE_MAP = {
    "BS3-002": "Variable_Electrode_Thickness",
    "BS3-003": "Variable_Sputter_Power",
    "BS3-004": "Variable_Gas_Flow_Rate",
    "BS3-005": "Variable_Gas_Flow_Rate",
    "BS3-006": "Variable_Bottom_Electrode_Sputter_Pressure",
    "BS3-008": "Variable_Film_Thickness",
    "BS3-009": "Variable_Deposition_Temperature",
    "BS3-011": "Variable_Precursor_Source_Temperature",
    "BS3-013": "Variable_Precursor_Source_Temperature",
    "BS3-014": "Variable_Cycle_Ratio",
    "BS3-017": "Variable_Electrode_Thickness",
    "BS3-021": "Variable_Etchant_Ratio",
    "BS3-022": "Variable_Wet_Etch_Temperature",
    "BS3-023": "Variable_Anneal_Temperature",
    "BS3-024": "Variable_Anneal_Duration",
}

QUANTITY_OPERATION_MAP = {
    "BS3-002": "Op_01_Bottom_Electrode_Formation",
    "BS3-003": "Op_01_Bottom_Electrode_Formation",
    "BS3-004": "Op_01_Bottom_Electrode_Formation",
    "BS3-005": "Op_01_Bottom_Electrode_Formation",
    "BS3-006": "Op_01_Bottom_Electrode_Formation",
    "BS3-008": "Op_02_ALD_Film_Formation",
    "BS3-009": "Op_02_ALD_Film_Formation",
    "BS3-011": "Op_02a_Hf_Precursor_Dose",
    "BS3-013": "Op_02b_Zr_Precursor_Dose",
    "BS3-014": "Op_02d_Cycle_Repetition",
    "BS3-017": "Op_03_Top_Electrode_Formation",
    "BS3-021": "Op_05_Wet_Etch",
    "BS3-022": "Op_05_Wet_Etch",
    "BS3-023": "Op_06_Crystallization_Anneal",
    "BS3-024": "Op_06_Crystallization_Anneal",
}

MEASUREMENT_TBOX_SCAFFOLD_CLASSES = (
    "Characterization_Method",
    "Electrical_Test_Method",
    "Measurement_Result",
    "Specimen",
    "Measurand",
)

MEASUREMENT_TBOX_SCAFFOLD_NOTE = (
    "TBox-only scaffolding in the BS3 build; no measurement or electrical-test "
    "individuals are created because the BS3 ledger contains no measurement-result evidence."
)

SHARED_INDIVIDUAL_CLAIMS = {
    "Route_BS3_Tsai2022": tuple(f"BS3-{index:03d}" for index in range(1, 26)),
    "Step_01_Bottom_Electrode": tuple(f"BS3-{index:03d}" for index in range(1, 7)),
    "Step_02_HZO_Deposition": tuple(f"BS3-{index:03d}" for index in range(7, 16)),
    "Step_03_Top_Electrode": ("BS3-016", "BS3-017"),
    "Step_04_Photolithography": ("BS3-018", "BS3-019"),
    "Step_05_Wet_Etch": ("BS3-020", "BS3-021", "BS3-022"),
    "Step_06_Crystallization_Anneal": ("BS3-023", "BS3-024", "BS3-025"),
    "Op_01_Bottom_Electrode_Formation": tuple(
        f"BS3-{index:03d}" for index in range(1, 7)
    ),
    "Op_02_ALD_Film_Formation": tuple(f"BS3-{index:03d}" for index in range(7, 16)),
    "Op_02a_Hf_Precursor_Dose": ("BS3-010", "BS3-011"),
    "Op_02b_Zr_Precursor_Dose": ("BS3-012", "BS3-013"),
    "Op_02c_Co_Reactant_Dose": ("BS3-015",),
    "Op_02d_Cycle_Repetition": ("BS3-014",),
    "Op_03_Top_Electrode_Formation": ("BS3-016", "BS3-017"),
    "Op_04_Photolithography": ("BS3-018", "BS3-019"),
    "Op_05_Wet_Etch": ("BS3-020", "BS3-021", "BS3-022"),
    "Op_06_Crystallization_Anneal": ("BS3-023", "BS3-024", "BS3-025"),
    "Stack_BS3_TiN_HZO_TiN": ("BS3-001", "BS3-007", "BS3-016"),
    "Layer_BS3_Bottom_TiN": ("BS3-001", "BS3-002"),
    "Layer_BS3_HZO": ("BS3-007", "BS3-008"),
    "Layer_BS3_Top_TiN": ("BS3-016", "BS3-017"),
    "TiN": ("BS3-001", "BS3-016"),
    "HZO_Hf05Zr05O2": ("BS3-007",),
    "TEMAH": ("BS3-010",),
    "TEMAZ": ("BS3-012",),
    "Ar": ("BS3-004",),
    "N2": ("BS3-005", "BS3-025"),
    "NH4OH_H2O2_H2O_Etchant": ("BS3-020",),
}

CASE_PRESERVING_TOKENS = {
    "ALD",
    "Ar",
    "BS3",
    "FeFET",
    "Hf",
    "HfO2",
    "HZO",
    "HZO_Hf05Zr05O2",
    "MFM",
    "N2",
    "NH4OH",
    "NH4OH_H2O2_H2O",
    "PUND",
    "RTP",
    "TEMAH",
    "TEMAZ",
    "TiN",
    "Zr",
}
ENTITY_RE = re.compile(r"^[A-Z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*$")
PROPERTY_RE = re.compile(r"^[a-z][A-Za-z0-9]*$")
STEP_POSITION_RE = re.compile(r"(?<!\w)step\s+([1-6])\s+of\s+6(?!\w)", re.IGNORECASE)
INTEGER_RE = re.compile(r"^[+-]?\d+$")
NON_NEGATIVE_INTEGER_RE = re.compile(r"^\d+$")
POSITIVE_INTEGER_RE = re.compile(r"^[1-9]\d*$")
DECIMAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
RATIO_RE = re.compile(r"^\d+(?::\d+)+$")


class ValidationError(RuntimeError):
    """Raised after one validation phase has reported all of its violations."""


@dataclass(frozen=True)
class ClaimRow:
    """One normalized ledger row with source text preserved."""

    claim_id: str
    source_id: str
    locator: str
    target: str
    field: str
    value: str
    unit: str
    condition: str
    anchor: str
    note: str
    helper_target: str
    helper_source: str
    claim_id_original: str
    extraction_batch: int


@dataclass(frozen=True)
class CoverageRow:
    """One reconciled controlled coverage record."""

    target: str
    row_count: int
    distinct_source_count: int
    coverage: str


@dataclass(frozen=True)
class ClaimHandler:
    """Fail-fast contract and extraction rule for one BS3 claim."""

    claim_id: str
    expected_target: str
    expected_field: str
    expected_value: str
    expected_unit: str
    effect: str
    quantity_label: str = ""
    parse_prefix: str = ""
    ratio_prefix: str = ""


@dataclass(frozen=True)
class StepSpec:
    """Authoritative route-step specification."""

    index: int
    step_local: str
    label: str
    description: str
    operation_local: str
    operation_class: str
    module_scope: str
    claim_ids: Sequence[str]
    handlers: Sequence[ClaimHandler]


@dataclass(frozen=True)
class GapSpec:
    """Specification for one report-derived evidence gap."""

    local_name: str
    concerns_local: str
    quantity_kind_field: str
    statement: str


@dataclass(frozen=True)
class VariableSpec:
    """Specification for one documented process variable."""

    local_name: str
    variable_class: str
    rationale: str


@dataclass(frozen=True)
class WindowSpec:
    """Specification for a non-numeric report-derived literature window."""

    local_name: str
    label: str
    condition_text: str


@dataclass(frozen=True)
class CompetencyQuestion:
    """An executable competency question with an exact normalized result contract."""

    number: int
    question: str
    sparql: str
    expected_rows: Sequence[Sequence[str]]


@dataclass(frozen=True)
class BuildOptions:
    """Immutable inputs that affect graph population or validation."""

    report_date: date
    generation_timestamp: datetime
    ledger_path: Path
    ledger_sha256: str
    sheet_name: str
    window_scaffold: bool
    report_derived_gaps: bool
    strict: bool
    release: bool
    coverage_rows: Sequence[CoverageRow]


@dataclass(frozen=True)
class BuildCounts:
    """Summary entity counts for the completed graph."""

    triples: int
    classes: int
    object_properties: int
    data_properties: int
    annotation_properties: int
    named_individuals: int
    claims: int
    quantities: int
    route_instances: int
    evidence_gaps: int
    windows: int
    coverage_assessments: int


def entity_name(*parts: str) -> str:
    """Create or validate a class/individual local name with curated case preservation."""

    if len(parts) == 1 and ENTITY_RE.fullmatch(parts[0]):
        return parts[0]
    tokens: list[str] = []
    for part in parts:
        tokens.extend(token for token in re.split(r"[^A-Za-z0-9]+", part) if token)
    if not tokens:
        raise ValidationError("Cannot construct an entity name from empty input")
    rendered = [
        token if token in CASE_PRESERVING_TOKENS else token[:1].upper() + token[1:].lower()
        for token in tokens
    ]
    result = "_".join(rendered)
    if not ENTITY_RE.fullmatch(result):
        raise ValidationError(f"Invalid class/individual local name: {result!r}")
    return result


def property_name(*parts: str) -> str:
    """Create or validate a lower-camel-case property local name with no underscore."""

    if len(parts) == 1 and PROPERTY_RE.fullmatch(parts[0]):
        return parts[0]
    tokens: list[str] = []
    for part in parts:
        tokens.extend(token for token in re.split(r"[^A-Za-z0-9]+", part) if token)
    if not tokens:
        raise ValidationError("Cannot construct a property name from empty input")
    first = tokens[0][:1].lower() + tokens[0][1:]
    result = first + "".join(
        token if token in CASE_PRESERVING_TOKENS else token[:1].upper() + token[1:]
        for token in tokens[1:]
    )
    if not PROPERTY_RE.fullmatch(result) or "_" in result:
        raise ValidationError(f"Invalid property local name: {result!r}")
    return result


def E(local_name: str) -> URIRef:
    """Return a validated project class or individual IRI."""

    return ALD[entity_name(local_name)]


def P(local_name: str) -> URIRef:
    """Return a validated project property IRI."""

    return ALD[property_name(local_name)]


def local_name(term: URIRef) -> str:
    """Return the local part of a project IRI."""

    text = str(term)
    return text[len(PROJECT_PREFIX) :] if text.startswith(PROJECT_PREFIX) else text


def target_local(target: str) -> str:
    """Map a controlled target string to its stable individual local name."""

    return entity_name("Target", *re.split(r"[/\-]", target))


def target_suffix(target: str) -> str:
    """Map a target string to the suffix used by its coverage assessment."""

    return entity_name(*re.split(r"[/\-]", target))


def field_local(field: str) -> str:
    """Map a controlled ledger field to its quantity-kind individual."""

    return entity_name("Field", *field.split("_"))


def claim_local(claim_id: str) -> str:
    """Map a BS3 claim identifier to its stable individual local name."""

    match = re.fullmatch(r"BS3-(\d{3})", claim_id)
    if match is None:
        raise ValidationError(f"Invalid BS3 claim identifier: {claim_id!r}")
    return entity_name(f"Claim_BS3_{match.group(1)}")


def quantity_local(claim_id: str) -> str:
    """Map a BS3 claim identifier to its quantity individual local name."""

    return entity_name(claim_local(claim_id).replace("Claim_", "Qty_", 1))


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 digest of a file without changing it."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_cell(value: object) -> str:
    """Convert a pandas cell to source text without introducing float formatting."""

    if value is None or pd.isna(value):
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        return format(value, "f")
    raise ValidationError(
        f"Unexpected non-text cell type {type(value).__name__}; load with dtype=str"
    )


def parse_numeric(raw_value: str, required_prefix: str) -> Decimal:
    """Strip only a declared prefix and parse the complete remainder as Decimal."""

    if not raw_value.startswith(required_prefix):
        raise ValidationError(
            f"Value {raw_value!r} does not begin with required prefix {required_prefix!r}"
        )
    token = raw_value[len(required_prefix) :]
    if not DECIMAL_RE.fullmatch(token):
        raise ValidationError(f"Value remainder is not a complete decimal token: {token!r}")
    try:
        return Decimal(token)
    except InvalidOperation as exc:
        raise ValidationError(f"Invalid decimal token: {token!r}") from exc


def decimal_literal(value: Decimal) -> Literal:
    """Return an xsd:decimal literal whose lexical form survives Turtle round trips."""

    lexical = format(value, "f")
    if "." not in lexical:
        lexical += ".0"
    return Literal(lexical, datatype=XSD.decimal, normalize=False)


def parse_ratio(raw_value: str, required_prefix: str) -> str:
    """Strip a declared prefix and require a complete colon-delimited integer ratio."""

    if not raw_value.startswith(required_prefix):
        raise ValidationError(
            f"Value {raw_value!r} does not begin with ratio prefix {required_prefix!r}"
        )
    token = raw_value[len(required_prefix) :]
    if not RATIO_RE.fullmatch(token):
        raise ValidationError(f"Value remainder is not a complete ratio token: {token!r}")
    return token


def parse_step_position(condition: str) -> int:
    """Parse the unique ``step N of 6`` fragment in a BS3 condition."""

    matches = STEP_POSITION_RE.findall(condition)
    if len(matches) != 1:
        raise ValidationError(
            f"Condition must contain exactly one 'step N of 6' fragment: {condition!r}"
        )
    return int(matches[0])


def _raise_phase(phase: str, violations: Sequence[str]) -> None:
    """Log all violations for one phase, then raise once."""

    if not violations:
        return
    for violation in violations:
        LOGGER.error("%s: %s", phase, violation)
    raise ValidationError(f"{phase} failed with {len(violations)} violation(s)")


def load_ledger(path: Path, sheet_name: str) -> Sequence[ClaimRow]:
    """Load and validate the exact ledger contract before graph construction."""

    if sheet_name != LEDGER_SHEET:
        raise ValidationError(
            f"--sheet must be {LEDGER_SHEET!r}; forbidden sheets are not valid inputs"
        )
    if not path.is_file():
        raise ValidationError(f"Ledger does not exist: {path}")
    excel = pd.ExcelFile(path, engine="openpyxl")
    required_sheets = {LEDGER_SHEET, COVERAGE_SHEET}
    missing_sheets = sorted(required_sheets - set(excel.sheet_names))
    if missing_sheets:
        raise ValidationError(f"Missing required sheet(s): {missing_sheets}")
    frame = pd.read_excel(
        path,
        sheet_name=sheet_name,
        engine="openpyxl",
        dtype=str,
        keep_default_na=False,
    )
    violations: list[str] = []
    if tuple(str(column) for column in frame.columns) != LEDGER_COLUMNS:
        violations.append(
            f"header order {tuple(frame.columns)!r} does not equal {LEDGER_COLUMNS!r}"
        )
    if len(frame.index) != LEDGER_ROW_COUNT:
        violations.append(f"row count {len(frame.index)} does not equal {LEDGER_ROW_COUNT}")
    if tuple(str(column) for column in frame.columns) != LEDGER_COLUMNS:
        _raise_phase("ledger input contract", violations)

    rows: list[ClaimRow] = []
    required_nonempty = (
        "claim_id",
        "source_id",
        "locator",
        "target",
        "field",
        "value",
        "condition",
        "anchor",
        "claim_id_original",
        "extraction_batch",
    )
    for index, record in frame.iterrows():
        values = {column: normalized_cell(record[column]) for column in LEDGER_COLUMNS}
        excel_row = index + 2
        for column in required_nonempty:
            if values[column] == "":
                violations.append(f"row {excel_row} has empty required column {column}")
        batch_text = values["extraction_batch"]
        if not NON_NEGATIVE_INTEGER_RE.fullmatch(batch_text):
            violations.append(
                f"row {excel_row} extraction_batch is not an integer: {batch_text!r}"
            )
            batch = -1
        else:
            batch = int(batch_text)
        rows.append(
            ClaimRow(
                claim_id=values["claim_id"],
                source_id=values["source_id"],
                locator=values["locator"],
                target=values["target"],
                field=values["field"],
                value=values["value"],
                unit=values["unit"],
                condition=values["condition"],
                anchor=values["anchor"],
                note=values["note"],
                helper_target=values["helper_target"],
                helper_source=values["helper_source"],
                claim_id_original=values["claim_id_original"],
                extraction_batch=batch,
            )
        )

    source_counts = Counter(row.source_id for row in rows)
    if dict(sorted(source_counts.items())) != dict(sorted(EXPECTED_SOURCE_COUNTS.items())):
        violations.append(
            f"source counts {dict(sorted(source_counts.items()))!r} do not equal contract"
        )
    observed_targets = {row.target for row in rows}
    if observed_targets != set(TARGETS):
        violations.append(
            f"target vocabulary mismatch; missing={sorted(set(TARGETS)-observed_targets)}, "
            f"extra={sorted(observed_targets-set(TARGETS))}"
        )
    observed_fields = {row.field for row in rows}
    if observed_fields != set(FIELDS):
        violations.append(
            f"field vocabulary mismatch; missing={sorted(set(FIELDS)-observed_fields)}, "
            f"extra={sorted(observed_fields-set(FIELDS))}"
        )
    observed_units = {row.unit for row in rows if row.unit != ""}
    if observed_units != set(UNIT_IRI_NAMES):
        violations.append(
            f"unit vocabulary mismatch; missing={sorted(set(UNIT_IRI_NAMES)-observed_units)}, "
            f"extra={sorted(observed_units-set(UNIT_IRI_NAMES))}"
        )
    claim_ids = [row.claim_id for row in rows]
    duplicates = sorted(claim_id for claim_id, count in Counter(claim_ids).items() if count > 1)
    if duplicates:
        violations.append(f"duplicate global claim_id values: {duplicates}")

    bs3_rows = sorted((row for row in rows if row.source_id == "BS3"), key=lambda row: row.claim_id)
    expected_ids = {f"BS3-{index:03d}" for index in range(1, 26)}
    actual_ids = {row.claim_id for row in bs3_rows}
    if len(bs3_rows) != 25 or actual_ids != expected_ids:
        violations.append(
            f"BS3 claim set mismatch; count={len(bs3_rows)}, "
            f"missing={sorted(expected_ids-actual_ids)}, extra={sorted(actual_ids-expected_ids)}"
        )
    for row in bs3_rows:
        expected_field, expected_value, expected_unit = EXPECTED_BS3_CONTENT.get(
            row.claim_id, ("", "", "")
        )
        expected = (
            EXPECTED_BS3_TARGETS.get(row.claim_id),
            expected_field,
            expected_value,
            expected_unit,
        )
        actual = (row.target, row.field, row.value, row.unit)
        if actual != expected:
            violations.append(f"{row.claim_id} content {actual!r} does not equal {expected!r}")
        if row.claim_id_original != row.claim_id:
            violations.append(
                f"{row.claim_id} claim_id_original is {row.claim_id_original!r}"
            )
        if row.extraction_batch != 1:
            violations.append(f"{row.claim_id} extraction_batch is {row.extraction_batch}")
        if BS3_CAVEAT not in row.note:
            violations.append(f"{row.claim_id} is missing the mandatory second-hand caveat")
        try:
            parse_step_position(row.condition)
        except ValidationError as exc:
            violations.append(f"{row.claim_id}: {exc}")
    _raise_phase("ledger input contract", violations)
    return tuple(sorted(rows, key=lambda row: row.claim_id))


def load_and_reconcile_coverage(path: Path, rows: Sequence[ClaimRow]) -> Sequence[CoverageRow]:
    """Load only controlled target rows and reconcile them to the ledger."""

    frame = pd.read_excel(
        path,
        sheet_name=COVERAGE_SHEET,
        engine="openpyxl",
        dtype=str,
        keep_default_na=False,
    )
    required_columns = ("target", "row count", "distinct source count", "coverage")
    violations: list[str] = []
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValidationError(f"Coverage sheet missing required columns: {missing}")
    selected = frame[frame.iloc[:, 0].isin(TARGETS)]
    coverage_rows: list[CoverageRow] = []
    for index, record in selected.iterrows():
        target = normalized_cell(record["target"])
        row_text = normalized_cell(record["row count"])
        source_text = normalized_cell(record["distinct source count"])
        grade = normalized_cell(record["coverage"])
        if not NON_NEGATIVE_INTEGER_RE.fullmatch(row_text):
            violations.append(f"coverage row {index+2} row count is not an integer: {row_text!r}")
            row_count = -1
        else:
            row_count = int(row_text)
        if not NON_NEGATIVE_INTEGER_RE.fullmatch(source_text):
            violations.append(
                f"coverage row {index+2} distinct source count is not an integer: {source_text!r}"
            )
            source_count = -1
        else:
            source_count = int(source_text)
        if grade not in {"well-covered", "thin", "bare"}:
            violations.append(f"coverage row {index+2} has invalid grade {grade!r}")
        coverage_rows.append(CoverageRow(target, row_count, source_count, grade))

    counts = Counter(row.target for row in coverage_rows)
    if set(counts) != set(TARGETS) or any(count != 1 for count in counts.values()):
        violations.append(f"coverage targets are not exactly once each: {dict(sorted(counts.items()))}")
    for coverage in coverage_rows:
        matching = [row for row in rows if row.target == coverage.target]
        recomputed = (len(matching), len({row.source_id for row in matching}))
        recorded = (coverage.row_count, coverage.distinct_source_count)
        if recorded != recomputed:
            violations.append(
                f"{coverage.target} coverage counts {recorded} do not equal recomputed {recomputed}"
            )
    if sum(row.row_count for row in coverage_rows) != LEDGER_ROW_COUNT:
        violations.append(
            f"coverage row-count sum is {sum(row.row_count for row in coverage_rows)}, "
            f"expected {LEDGER_ROW_COUNT}"
        )
    thin_bare = {
        row.target: (row.row_count, row.distinct_source_count, row.coverage)
        for row in coverage_rows
        if row.coverage in {"thin", "bare"}
    }
    if thin_bare != THIN_BARE_EXPECTED:
        violations.append(f"thin/bare target set mismatch: {thin_bare!r}")
    _raise_phase("coverage input contract", violations)
    return tuple(sorted(coverage_rows, key=lambda row: row.target))


def _handler(
    claim_id: str,
    effect: str,
    quantity_label: str = "",
    parse_prefix: str = "",
    ratio_prefix: str = "",
) -> ClaimHandler:
    """Create a handler from the exact content and target contracts."""

    field, value, unit = EXPECTED_BS3_CONTENT[claim_id]
    return ClaimHandler(
        claim_id=claim_id,
        expected_target=EXPECTED_BS3_TARGETS[claim_id],
        expected_field=field,
        expected_value=value,
        expected_unit=unit,
        effect=effect,
        quantity_label=quantity_label,
        parse_prefix=parse_prefix,
        ratio_prefix=ratio_prefix,
    )


BS3_ROUTE_SPEC: Sequence[StepSpec] = (
    StepSpec(
        1,
        "Step_01_Bottom_Electrode",
        "Bottom TiN electrode formation by sputtering",
        "Bottom TiN electrode formation by sputtering.",
        "Op_01_Bottom_Electrode_Formation",
        "Bottom_Electrode_Formation",
        "Scope_In_Module",
        tuple(f"BS3-{index:03d}" for index in range(1, 7)),
        (
            _handler("BS3-001", "bottom_material"),
            _handler(
                "BS3-002",
                "quantity",
                "bottom TiN electrode thickness",
                "bottom TiN electrode thickness ",
            ),
            _handler("BS3-003", "quantity", "sputter power", "sputter power "),
            _handler("BS3-004", "ar_flow", "Ar flow", "Ar flow "),
            _handler("BS3-005", "n2_flow", "N2 flow", "N2 flow "),
            _handler(
                "BS3-006",
                "quantity",
                "sputter chamber pressure",
                "sputter chamber pressure ",
            ),
        ),
    ),
    StepSpec(
        2,
        "Step_02_HZO_Deposition",
        "Composite HZO formation by ALD",
        "Composite HZO film formation by alternating Hf and Zr precursor doses.",
        "Op_02_ALD_Film_Formation",
        "ALD_Film_Formation",
        "Scope_In_Module",
        tuple(f"BS3-{index:03d}" for index in range(7, 16)),
        (
            _handler("BS3-007", "hzo_material"),
            _handler("BS3-008", "quantity", "HZO film thickness", ""),
            _handler("BS3-009", "quantity", "deposition temperature", ""),
            _handler("BS3-010", "temah"),
            _handler(
                "BS3-011",
                "quantity_hf",
                "TEMAH source temperature",
                "TEMAH source temperature ",
            ),
            _handler("BS3-012", "temaz"),
            _handler(
                "BS3-013",
                "quantity_zr",
                "TEMAZ source temperature",
                "TEMAZ source temperature ",
            ),
            _handler(
                "BS3-014",
                "ratio_cycle",
                "HfO2:ZrO2 cycle ratio",
                ratio_prefix="HfO2:ZrO2 cycle ratio ",
            ),
            _handler("BS3-015", "co_reactant_gap"),
        ),
    ),
    StepSpec(
        3,
        "Step_03_Top_Electrode",
        "Top TiN electrode formation by sputtering",
        "Top TiN electrode formation by sputtering.",
        "Op_03_Top_Electrode_Formation",
        "Top_Electrode_Formation",
        "Scope_In_Module",
        ("BS3-016", "BS3-017"),
        (
            _handler("BS3-016", "top_material"),
            _handler(
                "BS3-017",
                "quantity",
                "top TiN electrode thickness",
                "top TiN electrode thickness ",
            ),
        ),
    ),
    StepSpec(
        4,
        "Step_04_Photolithography",
        "Photolithography",
        "Photolithography retained only to preserve the reported route order.",
        "Op_04_Photolithography",
        "Photolithography",
        "Scope_Out_Of_Module",
        ("BS3-018", "BS3-019"),
        (
            _handler("BS3-018", "photolithography"),
            _handler("BS3-019", "lithography_gap"),
        ),
    ),
    StepSpec(
        5,
        "Step_05_Wet_Etch",
        "Wet chemical etching",
        "Wet chemical etching retained only to preserve the reported route order.",
        "Op_05_Wet_Etch",
        "Wet_Etch",
        "Scope_Out_Of_Module",
        ("BS3-020", "BS3-021", "BS3-022"),
        (
            _handler("BS3-020", "etchant"),
            _handler(
                "BS3-021",
                "ratio_etchant",
                "etchant ratio",
                ratio_prefix="NH4OH:H2O2:H2O etchant ratio ",
            ),
            _handler(
                "BS3-022",
                "quantity",
                "wet etch temperature",
                "wet etch temperature ",
            ),
        ),
    ),
    StepSpec(
        6,
        "Step_06_Crystallization_Anneal",
        "Crystallization RTP anneal after metallization",
        "Crystallization rapid thermal anneal after top-electrode metallization.",
        "Op_06_Crystallization_Anneal",
        "Post_Metallization_Anneal",
        "Scope_In_Module",
        ("BS3-023", "BS3-024", "BS3-025"),
        (
            _handler(
                "BS3-023",
                "quantity",
                "crystallization anneal temperature",
                "crystallization anneal at ",
            ),
            _handler("BS3-024", "quantity", "anneal duration", "anneal duration "),
            _handler("BS3-025", "anneal_ambient"),
        ),
    ),
)

REPORT_GAP_SPECS: Sequence[GapSpec] = (
    GapSpec(
        "Gap_Report_Step_01_Tool_Identity",
        "Op_01_Bottom_Electrode_Formation",
        "tool_name",
        "bottom-electrode tool identity unreported",
    ),
    GapSpec(
        "Gap_Report_Step_02_Metal_Precursor_Pulse_Timings",
        "Op_02_ALD_Film_Formation",
        "pulse_time",
        "Hf and Zr precursor pulse timings unreported",
    ),
    GapSpec(
        "Gap_Report_Step_02_Co_Reactant_Pulse_Timing",
        "Op_02c_Co_Reactant_Dose",
        "pulse_time",
        "co-reactant pulse timing unreported",
    ),
    GapSpec(
        "Gap_Report_Step_02_Purge_Operations_And_Timings",
        "Op_02_ALD_Film_Formation",
        "purge_time",
        "first and second purge operations and timings not documented for this route",
    ),
    GapSpec(
        "Gap_Report_Step_02_Delivery_Mode",
        "Op_02_ALD_Film_Formation",
        "parameter_value",
        "precursor delivery mode unreported",
    ),
    GapSpec(
        "Gap_Report_Step_02_Line_Temperatures",
        "Op_02_ALD_Film_Formation",
        "line_temperature",
        "line temperatures unreported",
    ),
    GapSpec(
        "Gap_Report_Step_02_Chamber_Pressure",
        "Op_02_ALD_Film_Formation",
        "chamber_pressure",
        "ALD chamber pressure unreported",
    ),
    GapSpec(
        "Gap_Report_Step_02_Cycle_Count",
        "Op_02d_Cycle_Repetition",
        "cycle_structure",
        "ALD cycle count unreported",
    ),
    GapSpec(
        "Gap_Report_Step_03_Sputter_Conditions",
        "Op_03_Top_Electrode_Formation",
        "parameter_value",
        "position-specific top-electrode sputter conditions unreported",
    ),
    GapSpec(
        "Gap_Report_Step_06_Ramp_Rate",
        "Op_06_Crystallization_Anneal",
        "anneal_sequence",
        "anneal ramp rate unreported",
    ),
)

VARIABLE_SPECS: Sequence[VariableSpec] = (
    VariableSpec(
        "Variable_Anneal_Temperature",
        "First_Order_Variable",
        "The report identifies anneal temperature as a first-order crystallization control.",
    ),
    VariableSpec(
        "Variable_Anneal_Placement",
        "First_Order_Variable",
        "The report treats anneal placement relative to metallization as first-order context.",
    ),
    VariableSpec(
        "Variable_Deposition_Temperature",
        "First_Order_Variable",
        "The report identifies deposition temperature as a first-order film-formation control.",
    ),
    VariableSpec(
        "Variable_Precursor_Purge_Duration",
        "First_Order_Variable",
        "The report identifies precursor and purge duration as first-order exposure controls.",
    ),
    VariableSpec(
        "Variable_Electrode_Material_And_Oxygen_Affinity",
        "First_Order_Variable",
        "The report treats electrode material and oxygen affinity as first-order interface controls.",
    ),
    VariableSpec(
        "Variable_Oxidant_Exposure",
        "First_Order_Variable",
        "The report identifies oxidant exposure as a first-order chemistry control.",
    ),
    VariableSpec(
        "Variable_Top_Electrode_Deposition_Pressure",
        "First_Order_Variable",
        "The first-order classification is specific to top-electrode deposition pressure.",
    ),
    VariableSpec(
        "Variable_Precursor_Source_Temperature",
        "Second_Order_Variable",
        "The report classifies precursor source temperature as a second-order delivery control.",
    ),
    VariableSpec(
        "Variable_ALD_Chamber_Pressure",
        "Second_Order_Variable",
        "The report classifies ALD chamber pressure as a second-order reactor control.",
    ),
    VariableSpec(
        "Variable_Sputter_Power",
        "Second_Order_Variable",
        "The report classifies sputter power as a second-order electrode-formation control.",
    ),
    VariableSpec(
        "Variable_Cycle_Or_Supercycle_Count",
        "Second_Order_Variable",
        "The report classifies cycle or supercycle count as a second-order architecture control.",
    ),
    VariableSpec(
        "Variable_Gas_Flow_Rate",
        "Unclassified_Variable",
        "The supplied evidence does not justify a first- or second-order classification for gas flow rate.",
    ),
    VariableSpec(
        "Variable_Anneal_Ambient_Independent",
        "Unclassified_Variable",
        "The supplied evidence does not isolate anneal ambient as an independent ordered variable.",
    ),
    VariableSpec(
        "Variable_Precursor_Delivery_Mode",
        "Unclassified_Variable",
        "The route does not report enough delivery detail for an ordered classification.",
    ),
    VariableSpec(
        "Variable_Electrode_Thickness",
        "Unclassified_Variable",
        "The supplied evidence does not justify an ordered classification for electrode thickness.",
    ),
    VariableSpec(
        "Variable_Film_Thickness",
        "Unclassified_Variable",
        "The supplied evidence does not justify an ordered classification for film thickness.",
    ),
    VariableSpec(
        "Variable_Bottom_Electrode_Sputter_Pressure",
        "Unclassified_Variable",
        "Bottom-electrode pressure is not assigned the position-specific top-electrode classification.",
    ),
    VariableSpec(
        "Variable_Cycle_Ratio",
        "Unclassified_Variable",
        "The supplied evidence does not justify an ordered classification for cycle ratio.",
    ),
    VariableSpec(
        "Variable_Etchant_Ratio",
        "Unclassified_Variable",
        "The out-of-module etchant ratio is retained without an ordered classification.",
    ),
    VariableSpec(
        "Variable_Wet_Etch_Temperature",
        "Unclassified_Variable",
        "The out-of-module wet-etch temperature is retained without an ordered classification.",
    ),
    VariableSpec(
        "Variable_Anneal_Duration",
        "Unclassified_Variable",
        "The supplied evidence does not justify an independent ordered classification for anneal duration.",
    ),
)

WINDOW_SPECS: Sequence[WindowSpec] = (
    WindowSpec(
        "Window_Electrode_Thickness_Envelope",
        "Electrode thickness literature envelope",
        "Conditioned literature envelope for electrode thickness; configuration matching is required.",
    ),
    WindowSpec(
        "Window_Sputter_Power_Envelope",
        "Sputter power literature envelope",
        "Conditioned literature envelope for sputter power in electrode formation.",
    ),
    WindowSpec(
        "Window_Sputter_Pressure_Envelope",
        "Sputter pressure literature envelope",
        "Conditioned literature envelope for reported electrode sputter pressures.",
    ),
    WindowSpec(
        "Window_Film_Thickness",
        "Film thickness literature window",
        "Conditioned literature window for HfO2-family ferroelectric film thickness.",
    ),
    WindowSpec(
        "Window_Deposition_Temperature",
        "Deposition temperature literature window",
        "Conditioned literature window for ALD deposition temperature.",
    ),
    WindowSpec(
        "Window_Precursor_Source_Temperature",
        "Precursor source temperature literature window",
        "Conditioned literature window for precursor source temperature and delivery context.",
    ),
    WindowSpec(
        "Window_Cycle_Ratio",
        "Cycle ratio literature window",
        "Conditioned literature window for HfO2-to-ZrO2 cycle architecture.",
    ),
    WindowSpec(
        "Window_Thermal_Treatment_Tuple",
        "Thermal treatment tuple literature window",
        "Conditioned literature comparison for anneal temperature, duration, ambient, and route placement.",
    ),
)

WINDOW_ASSESSMENTS: Sequence[tuple[str, str, str | None, str | None]] = (
    ("Instance_BS3_002", "Window_Assessment_Inside", "insideWindow", "Window_Electrode_Thickness_Envelope"),
    ("Instance_BS3_003", "Window_Assessment_Inside", "insideWindow", "Window_Sputter_Power_Envelope"),
    ("Instance_BS3_004", "Window_Assessment_No_Window_Available", None, None),
    ("Instance_BS3_005", "Window_Assessment_No_Window_Available", None, None),
    ("Instance_BS3_006", "Window_Assessment_Extends", "extendsWindow", "Window_Sputter_Pressure_Envelope"),
    ("Instance_BS3_008", "Window_Assessment_Inside", "insideWindow", "Window_Film_Thickness"),
    ("Instance_BS3_009", "Window_Assessment_Inside", "insideWindow", "Window_Deposition_Temperature"),
    ("Instance_BS3_011", "Window_Assessment_Inside", "insideWindow", "Window_Precursor_Source_Temperature"),
    ("Instance_BS3_013", "Window_Assessment_Beyond", "beyondWindow", "Window_Precursor_Source_Temperature"),
    ("Instance_BS3_014", "Window_Assessment_Inside", "insideWindow", "Window_Cycle_Ratio"),
    ("Instance_BS3_017", "Window_Assessment_Inside", "insideWindow", "Window_Electrode_Thickness_Envelope"),
    ("Instance_BS3_021", "Window_Assessment_Not_Assessed", None, None),
    ("Instance_BS3_022", "Window_Assessment_Not_Assessed", None, None),
    (
        "Instance_BS3_Thermal_Treatment_Tuple",
        "Window_Assessment_Exact_Independent_Match",
        "exactIndependentMatch",
        "Window_Thermal_Treatment_Tuple",
    ),
)

CLASS_HIERARCHY: Sequence[tuple[str, str | None]] = (
    ("Process_Element", None),
    ("Process_Operation", "Process_Element"),
    ("Pre_Deposition_Operation", "Process_Operation"),
    ("Surface_Preclean", "Pre_Deposition_Operation"),
    ("Interface_Preparation", "Pre_Deposition_Operation"),
    ("Seed_Layer_Formation", "Interface_Preparation"),
    ("Interlayer_Formation", "Interface_Preparation"),
    ("Electrode_Integration_Operation", "Process_Operation"),
    ("Bottom_Electrode_Formation", "Electrode_Integration_Operation"),
    ("Top_Electrode_Formation", "Electrode_Integration_Operation"),
    ("Capping_Layer_Formation", "Electrode_Integration_Operation"),
    ("Contact_Metallization", "Electrode_Integration_Operation"),
    ("ALD_Film_Formation", "Process_Operation"),
    ("Metal_Precursor_Dose", "ALD_Film_Formation"),
    ("Hf_Precursor_Dose", "Metal_Precursor_Dose"),
    ("Zr_Precursor_Dose", "Metal_Precursor_Dose"),
    ("First_Purge", "ALD_Film_Formation"),
    ("Co_Reactant_Dose", "ALD_Film_Formation"),
    ("Second_Purge", "ALD_Film_Formation"),
    ("Cycle_Repetition", "ALD_Film_Formation"),
    ("Thermal_Treatment_Operation", "Process_Operation"),
    ("Post_Deposition_Anneal", "Thermal_Treatment_Operation"),
    ("Post_Metallization_Anneal", "Thermal_Treatment_Operation"),
    ("Forming_Gas_Anneal", "Thermal_Treatment_Operation"),
    ("Electrical_Qualification_Operation", "Process_Operation"),
    ("Non_Module_Operation", "Process_Operation"),
    ("Photolithography", "Non_Module_Operation"),
    ("Wet_Etch", "Non_Module_Operation"),
    ("Route_Step", "Process_Element"),
    ("Process_Route", None),
    ("Material", None),
    ("Substrate", "Material"),
    ("Layer", "Material"),
    ("Ferroelectric_Layer", "Layer"),
    ("Electrode_Layer", "Layer"),
    ("Seed_Layer", "Layer"),
    ("Interlayer_Dielectric", "Layer"),
    ("Interfacial_Oxide_Layer", "Layer"),
    ("Device_Stack", "Material"),
    ("MFM_Capacitor", "Device_Stack"),
    ("Superlattice_Stack", "Device_Stack"),
    ("Trilayer_Stack", "Device_Stack"),
    ("FeFET_Gate_Stack", "Device_Stack"),
    ("Chemical", "Material"),
    ("Electrode_Material", "Chemical"),
    ("Film_Material", "Chemical"),
    ("Metal_Precursor", "Chemical"),
    ("Hf_Precursor", "Metal_Precursor"),
    ("Zr_Precursor", "Metal_Precursor"),
    ("Co_Reactant", "Chemical"),
    ("Thermal_Oxidant", "Co_Reactant"),
    ("Plasma_Oxidant", "Co_Reactant"),
    ("Process_Gas", "Chemical"),
    ("Sputter_Gas", "Process_Gas"),
    ("Purge_Gas", "Process_Gas"),
    ("Carrier_Gas", "Process_Gas"),
    ("Anneal_Ambient", "Chemical"),
    ("Cleaning_Chemistry", "Chemical"),
    ("Etchant", "Chemical"),
    ("Crystalline_Phase", None),
    ("Orthorhombic_Phase", "Crystalline_Phase"),
    ("Monoclinic_Phase", "Crystalline_Phase"),
    ("Tetragonal_Phase", "Crystalline_Phase"),
    ("Cubic_Phase", "Crystalline_Phase"),
    ("Amorphous_Phase", "Crystalline_Phase"),
    ("Equipment", None),
    ("Deposition_Equipment", "Equipment"),
    ("Deposition_Reactor", "Deposition_Equipment"),
    ("Thermal_ALD_Reactor", "Deposition_Reactor"),
    ("Plasma_Enhanced_ALD_Reactor", "Deposition_Reactor"),
    ("Crossflow_Reactor", "Deposition_Reactor"),
    ("Showerhead_Reactor", "Deposition_Reactor"),
    ("Laminar_Flow_Reactor", "Deposition_Reactor"),
    ("Sputtering_System", "Deposition_Equipment"),
    ("Annealing_Equipment", "Equipment"),
    ("Rapid_Thermal_Processor", "Annealing_Equipment"),
    ("Furnace", "Annealing_Equipment"),
    ("Metrology_Instrument", "Equipment"),
    ("Characterization_Method", None),
    ("Diffraction_Method", "Characterization_Method"),
    ("Microscopy_Method", "Characterization_Method"),
    ("Spectroscopy_Method", "Characterization_Method"),
    ("Depth_Profiling_Method", "Characterization_Method"),
    ("Thickness_Metrology", "Characterization_Method"),
    ("Electrical_Test_Method", "Characterization_Method"),
    ("Hysteresis_Measurement", "Electrical_Test_Method"),
    ("PUND_Measurement", "Electrical_Test_Method"),
    ("Endurance_Cycling", "Electrical_Test_Method"),
    ("Wake_Up_Cycling", "Electrical_Test_Method"),
    ("Retention_Test", "Electrical_Test_Method"),
    ("Leakage_Measurement", "Electrical_Test_Method"),
    ("Breakdown_Test", "Electrical_Test_Method"),
    ("Measurement_Result", None),
    ("Specimen", None),
    ("Capacitor_Specimen", "Specimen"),
    ("Wafer_Specimen", "Specimen"),
    ("Reference_Piece", "Specimen"),
    ("Cross_Section_Lamella", "Specimen"),
    ("Measurand", None),
    ("Process_Parameter", "Measurand"),
    ("Thickness_Growth_Per_Cycle", "Process_Parameter"),
    ("Conformality_Uniformity", "Process_Parameter"),
    ("Device_Property", "Measurand"),
    ("Polarization_Coercive_Field", "Device_Property"),
    ("Leakage_Current", "Device_Property"),
    ("Defect_Density_Reliability", "Device_Property"),
    ("Process_Variable", None),
    ("First_Order_Variable", "Process_Variable"),
    ("Second_Order_Variable", "Process_Variable"),
    ("Unclassified_Variable", "Process_Variable"),
    ("Quantity_Value", None),
    ("Point_Value", "Quantity_Value"),
    ("Range_Value", "Quantity_Value"),
    ("Ratio_Value", "Quantity_Value"),
    ("Qualitative_Value", "Quantity_Value"),
    ("Evidence_Item", None),
    ("Claim", "Evidence_Item"),
    ("Source", "Evidence_Item"),
    ("Source_Record", "Source"),
    ("Source_Document", "Source"),
    ("Evidence_Object", "Evidence_Item"),
    ("Literature_Window", "Evidence_Object"),
    ("Route_Instance", "Evidence_Object"),
    ("Evidence_Gap", "Evidence_Item"),
    ("Coverage_Assessment", "Evidence_Item"),
    ("Limitation", None),
    ("Evidence_Limitation", "Limitation"),
    ("Process_Capability_Limitation", "Limitation"),
    ("Quantity_Kind", None),
    ("Target_Category", None),
    ("Unit", None),
    ("Module_Scope", None),
    ("Coverage_Grade", None),
    ("Evidence_Status", None),
    ("Confidence_Level", None),
    ("Window_Assessment_Status", None),
)

REPORT_SECTION_MAP: dict[str, str] = {
    "Surface_Preclean": "3.3",
    "Interface_Preparation": "3.4",
    "Electrode_Integration_Operation": "3.5",
    "ALD_Film_Formation": "3.6",
    "Metal_Precursor_Dose": "3.6.1",
    "Hf_Precursor_Dose": "3.6.1",
    "Zr_Precursor_Dose": "3.6.1",
    "First_Purge": "3.6.2",
    "Co_Reactant_Dose": "3.6.3",
    "Second_Purge": "3.6.4",
    "Cycle_Repetition": "3.6.5",
    "Thermal_Treatment_Operation": "3.7",
    "Post_Deposition_Anneal": "3.7",
    "Post_Metallization_Anneal": "3.7",
    "Deposition_Reactor": "3.8",
    "Process_Variable": "3.10",
    "Characterization_Method": "3.11",
    "MFM_Capacitor": "3.12",
    "Evidence_Gap": "3.13.3",
    "Coverage_Assessment": "3.13.3",
}

DR_MAPPINGS: dict[str, tuple[str, str, str]] = {}
# Example for external curation:
# DR_MAPPINGS["ALD_Film_Formation"] = ("https://example.org/dr-class", "closeMatch", "Curator-reviewed scope match.")

OBJECT_PROPERTY_SPECS: Sequence[tuple[str, str | URIRef, str | URIRef]] = (
    ("hasStep", "Process_Route", "Route_Step"),
    ("stepOf", "Route_Step", "Process_Route"),
    ("realizesOperation", "Route_Step", "Process_Operation"),
    ("operationRealizedBy", "Process_Operation", "Route_Step"),
    ("hasSubOperation", "Process_Operation", "Process_Operation"),
    ("subOperationOf", "Process_Operation", "Process_Operation"),
    ("precedes", "Route_Step", "Route_Step"),
    ("directlyPrecedes", "Route_Step", "Route_Step"),
    ("necessarilyPrecedes", "Route_Step", "Route_Step"),
    ("routeScopedPrecedes", "Route_Step", "Route_Step"),
    ("hasInput", "Process_Operation", "Material"),
    ("hasOutput", "Process_Operation", "Material"),
    ("usesChemical", "Process_Operation", "Chemical"),
    ("usesPrecursor", "Process_Operation", "Metal_Precursor"),
    ("usesCoReactant", "Process_Operation", "Co_Reactant"),
    ("usesPurgeGas", "Process_Operation", "Purge_Gas"),
    ("usesCarrierGas", "Process_Operation", "Carrier_Gas"),
    ("usesSputterGas", "Process_Operation", "Sputter_Gas"),
    ("usesAnnealAmbient", "Process_Operation", "Anneal_Ambient"),
    ("usesEtchant", "Process_Operation", "Etchant"),
    ("usesCleaningChemistry", "Process_Operation", "Cleaning_Chemistry"),
    ("performedWith", "Process_Operation", "Equipment"),
    ("hasQuantity", OWL.Thing, "Quantity_Value"),
    ("hasProcessParameterValue", "Process_Operation", "Quantity_Value"),
    ("hasObservedValue", "Route_Instance", "Quantity_Value"),
    ("observedInRoute", "Route_Instance", "Process_Route"),
    ("observedAtStep", "Route_Instance", "Route_Step"),
    ("hasUnit", "Quantity_Value", "Unit"),
    ("hasQuantityKind", "Quantity_Value", "Quantity_Kind"),
    ("hasClaimField", "Claim", "Quantity_Kind"),
    ("hasTargetCategory", "Claim", "Target_Category"),
    ("concernsVariable", "Quantity_Value", "Process_Variable"),
    ("assessesTarget", "Coverage_Assessment", "Target_Category"),
    ("hasModuleScope", "Process_Element", "Module_Scope"),
    ("producesLayer", "Process_Operation", "Layer"),
    ("hasLayer", "Device_Stack", "Layer"),
    ("hasBottomElectrode", "Device_Stack", "Electrode_Layer"),
    ("hasTopElectrode", "Device_Stack", "Electrode_Layer"),
    ("hasFerroelectricLayer", "Device_Stack", "Ferroelectric_Layer"),
    ("madeOfChemical", "Layer", "Chemical"),
    ("hasPhase", "Material", "Crystalline_Phase"),
    ("measuredBy", "Measurement_Result", "Characterization_Method"),
    ("hasMeasurand", "Measurement_Result", "Measurand"),
    ("measuredOn", "Measurement_Result", "Specimen"),
    ("hasResultValue", "Measurement_Result", "Quantity_Value"),
    ("representsStack", "Specimen", "Device_Stack"),
    ("correspondsToProcessVariable", "Measurand", "Process_Variable"),
    ("assertedBy", OWL.Thing, "Claim"),
    ("hasSource", "Claim", "Source_Record"),
    ("documentedIn", OWL.Thing, "Source_Document"),
    ("transcribesDocument", "Source_Record", "Source_Document"),
    ("hasEvidenceStatus", "Claim", "Evidence_Status"),
    ("hasConfidence", "Claim", "Confidence_Level"),
    ("gapConcerns", "Evidence_Gap", OWL.Thing),
    ("gapQuantityKind", "Evidence_Gap", "Quantity_Kind"),
    ("hasCoverageGrade", "Coverage_Assessment", "Coverage_Grade"),
    ("comparedWithWindow", "Route_Instance", "Literature_Window"),
    ("insideWindow", "Route_Instance", "Literature_Window"),
    ("atWindowEdge", "Route_Instance", "Literature_Window"),
    ("extendsWindow", "Route_Instance", "Literature_Window"),
    ("beyondWindow", "Route_Instance", "Literature_Window"),
    ("exactIndependentMatch", "Route_Instance", "Literature_Window"),
    ("hasWindowAssessment", "Route_Instance", "Window_Assessment_Status"),
    ("constrainedBy", OWL.Thing, "Limitation"),
)

OBJECT_INVERSES = (
    ("hasStep", "stepOf"),
    ("realizesOperation", "operationRealizedBy"),
    ("hasSubOperation", "subOperationOf"),
)

OBJECT_SUBPROPERTIES = (
    ("directlyPrecedes", "precedes"),
    ("necessarilyPrecedes", "precedes"),
    ("routeScopedPrecedes", "precedes"),
    ("usesPrecursor", "usesChemical"),
    ("usesCoReactant", "usesChemical"),
    ("usesPurgeGas", "usesChemical"),
    ("usesCarrierGas", "usesChemical"),
    ("usesSputterGas", "usesChemical"),
    ("usesAnnealAmbient", "usesChemical"),
    ("usesEtchant", "usesChemical"),
    ("usesCleaningChemistry", "usesChemical"),
    ("hasProcessParameterValue", "hasQuantity"),
    ("hasBottomElectrode", "hasLayer"),
    ("hasTopElectrode", "hasLayer"),
    ("hasFerroelectricLayer", "hasLayer"),
    ("insideWindow", "comparedWithWindow"),
    ("atWindowEdge", "comparedWithWindow"),
    ("extendsWindow", "comparedWithWindow"),
    ("beyondWindow", "comparedWithWindow"),
    ("exactIndependentMatch", "insideWindow"),
    ("exactIndependentMatch", "comparedWithWindow"),
)

FUNCTIONAL_OBJECT_PROPERTIES = {
    "observedInRoute",
    "observedAtStep",
    "hasUnit",
    "hasQuantityKind",
    "hasClaimField",
    "hasTargetCategory",
    "concernsVariable",
    "assessesTarget",
    "hasModuleScope",
    "hasBottomElectrode",
    "hasTopElectrode",
    "hasFerroelectricLayer",
    "hasSource",
    "hasEvidenceStatus",
    "hasConfidence",
    "gapQuantityKind",
    "hasCoverageGrade",
    "hasWindowAssessment",
}

DATA_PROPERTY_SPECS: Sequence[tuple[str, str | URIRef, URIRef]] = (
    ("claimId", "Claim", XSD.string),
    ("claimIdOriginal", "Claim", XSD.string),
    ("sourceId", "Source_Record", XSD.string),
    ("locatorText", "Claim", XSD.string),
    ("rawValueText", OWL.Thing, XSD.string),
    ("rawUnitText", "Quantity_Value", XSD.string),
    ("conditionText", "Claim", XSD.string),
    ("anchorText", "Claim", XSD.string),
    ("noteText", "Claim", XSD.string),
    ("extractionBatch", "Claim", XSD.integer),
    ("helperTargetText", "Claim", XSD.string),
    ("helperSourceText", "Claim", XSD.string),
    ("secondHandTranscription", "Claim", XSD.boolean),
    ("numericValue", "Point_Value", XSD.decimal),
    ("minValue", "Range_Value", XSD.decimal),
    ("maxValue", "Range_Value", XSD.decimal),
    ("ratioExpression", "Ratio_Value", XSD.string),
    ("qualitativeStatement", "Qualitative_Value", XSD.string),
    ("quantityLabel", "Quantity_Value", XSD.string),
    ("stepIndex", "Route_Step", XSD.positiveInteger),
    ("stepDescription", "Route_Step", XSD.string),
    ("gapStatement", "Evidence_Gap", XSD.string),
    ("doNotInferNote", "Evidence_Gap", XSD.string),
    ("windowConditionText", "Literature_Window", XSD.string),
    ("contributingSourceCount", "Literature_Window", XSD.nonNegativeInteger),
    ("claimCount", "Source_Record", XSD.nonNegativeInteger),
    ("coverageRowCount", "Coverage_Assessment", XSD.nonNegativeInteger),
    ("coverageSourceCount", "Coverage_Assessment", XSD.nonNegativeInteger),
    ("variableOrderRationale", "Process_Variable", XSD.string),
    ("transferBlockedBy", "Route_Instance", XSD.string),
    ("scaffoldNote", "Literature_Window", XSD.string),
    ("derivedFromReport", "Evidence_Gap", XSD.string),
    ("sourceFileSha256", "Source_Document", XSD.string),
    ("inputSheetName", "Source_Document", XSD.string),
)

FUNCTIONAL_DATA_PROPERTIES = {
    "claimId",
    "claimIdOriginal",
    "sourceId",
    "locatorText",
    "rawUnitText",
    "conditionText",
    "anchorText",
    "noteText",
    "extractionBatch",
    "helperTargetText",
    "helperSourceText",
    "secondHandTranscription",
    "numericValue",
    "minValue",
    "maxValue",
    "ratioExpression",
    "qualitativeStatement",
    "quantityLabel",
    "stepIndex",
    "stepDescription",
    "gapStatement",
    "doNotInferNote",
    "windowConditionText",
    "contributingSourceCount",
    "claimCount",
    "coverageRowCount",
    "coverageSourceCount",
    "variableOrderRationale",
    "transferBlockedBy",
    "scaffoldNote",
    "derivedFromReport",
    "sourceFileSha256",
    "inputSheetName",
}

PROJECT_ANNOTATION_PROPERTIES = (
    "reportSection",
    "reportTable",
    "drMappingIRI",
    "drMappingRelation",
    "drMappingRationale",
    "openWorldNote",
    "generationTimestamp",
    "ledgerRowCount",
    "assertionRationale",
    "assertionSource",
)

STANDARD_ANNOTATION_PROPERTIES = (
    RDFS.label,
    RDFS.comment,
    SKOS.definition,
    SKOS.scopeNote,
    DCTERMS.title,
    DCTERMS.creator,
    DCTERMS.issued,
    DCTERMS.identifier,
    DCTERMS.source,
    DCTERMS.created,
)

ENUMERATIONS: dict[str, Sequence[str]] = {
    "Module_Scope": (
        "Scope_In_Module",
        "Scope_Out_Of_Module",
        "Scope_Upstream_Boundary",
        "Scope_Downstream_Boundary",
    ),
    "Coverage_Grade": (
        "Coverage_Well_Covered",
        "Coverage_Thin",
        "Coverage_Bare",
    ),
    "Evidence_Status": (
        "Evidence_Status_Directly_Reported",
        "Evidence_Status_Open_Gap",
        "Evidence_Status_Corroborated",
        "Evidence_Status_Single_Source",
        "Evidence_Status_Range",
        "Evidence_Status_Inferred",
    ),
    "Confidence_Level": (
        "Confidence_High",
        "Confidence_Medium",
        "Confidence_Low",
        "Confidence_Open",
    ),
    "Window_Assessment_Status": (
        "Window_Assessment_Inside",
        "Window_Assessment_At_Edge",
        "Window_Assessment_Extends",
        "Window_Assessment_Beyond",
        "Window_Assessment_Exact_Independent_Match",
        "Window_Assessment_No_Window_Available",
        "Window_Assessment_Not_Assessed",
    ),
}

TOP_LEVEL_DISJOINT = (
    "Process_Element",
    "Process_Route",
    "Material",
    "Crystalline_Phase",
    "Equipment",
    "Characterization_Method",
    "Evidence_Item",
    "Quantity_Value",
    "Measurement_Result",
    "Specimen",
    "Measurand",
    "Process_Variable",
    "Limitation",
)

PHASE_DISJOINT = (
    "Orthorhombic_Phase",
    "Monoclinic_Phase",
    "Tetragonal_Phase",
    "Cubic_Phase",
    "Amorphous_Phase",
)

SCHEMA_SOME_RESTRICTIONS = (
    (
        "Hf_Precursor_Dose",
        "usesPrecursor",
        "Hf_Precursor",
        "hf_precursor_dose_precursor",
    ),
    (
        "Zr_Precursor_Dose",
        "usesPrecursor",
        "Zr_Precursor",
        "zr_precursor_dose_precursor",
    ),
    (
        "Bottom_Electrode_Formation",
        "producesLayer",
        "Electrode_Layer",
        "bottom_electrode_output",
    ),
    (
        "Top_Electrode_Formation",
        "producesLayer",
        "Electrode_Layer",
        "top_electrode_output",
    ),
    (
        "ALD_Film_Formation",
        "producesLayer",
        "Ferroelectric_Layer",
        "ald_film_output",
    ),
    (
        "Post_Metallization_Anneal",
        "usesAnnealAmbient",
        "Anneal_Ambient",
        "post_metallization_anneal_ambient",
    ),
    (
        "Measurement_Result",
        "measuredBy",
        "Characterization_Method",
        "measurement_result_method",
    ),
    (
        "Measurement_Result",
        "assertedBy",
        "Claim",
        "measurement_result_provenance",
    ),
    (
        "Specimen",
        "representsStack",
        "Device_Stack",
        "specimen_represented_stack",
    ),
    (
        "Process_Parameter",
        "correspondsToProcessVariable",
        "Process_Variable",
        "process_parameter_variable",
    ),
)

MEASUREMENT_CARDINALITY_RESTRICTIONS = (
    (
        "Measurement_Result",
        "hasMeasurand",
        1,
        "Measurand",
        "measurement_result_measurand",
    ),
    (
        "Measurement_Result",
        "hasResultValue",
        1,
        "Quantity_Value",
        "measurement_result_value",
    ),
    (
        "Measurement_Result",
        "measuredOn",
        1,
        "Specimen",
        "measurement_result_specimen",
    ),
)

ROUTE_STEP_LOCALS = tuple(spec.step_local for spec in BS3_ROUTE_SPEC)
OPERATION_LOCALS = (
    "Op_01_Bottom_Electrode_Formation",
    "Op_02_ALD_Film_Formation",
    "Op_02a_Hf_Precursor_Dose",
    "Op_02b_Zr_Precursor_Dose",
    "Op_02c_Co_Reactant_Dose",
    "Op_02d_Cycle_Repetition",
    "Op_03_Top_Electrode_Formation",
    "Op_04_Photolithography",
    "Op_05_Wet_Etch",
    "Op_06_Crystallization_Anneal",
)
STACK_LAYER_LOCALS = (
    "Layer_BS3_Bottom_TiN",
    "Layer_BS3_HZO",
    "Layer_BS3_Top_TiN",
)


def bind_namespaces(graph: Graph) -> None:
    """Bind every required namespace to a stable prefix."""

    graph.bind("ald", ALD, override=True)
    graph.bind("owl", OWL, override=True)
    graph.bind("rdf", RDF, override=True)
    graph.bind("rdfs", RDFS, override=True)
    graph.bind("xsd", XSD, override=True)
    graph.bind("skos", SKOS, override=True)
    graph.bind("dcterms", DCTERMS, override=True)


def readable_label(local: str) -> str:
    """Render a stable English label without changing curated acronym casing."""

    return local.replace("_", " ")


def _class_or_standard(value: str | URIRef) -> URIRef:
    """Resolve a project class name or retain a standard class/datatype IRI."""

    return value if isinstance(value, URIRef) else E(value)


def add_rdf_list(graph: Graph, values: Sequence[URIRef], identifier: str) -> URIRef | BNode:
    """Add a finite, deterministic RDF list and return its head."""

    if not values:
        return RDF.nil
    nodes = [BNode(f"{identifier}_{index:03d}") for index in range(len(values))]
    for index, (node, value) in enumerate(zip(nodes, values, strict=True)):
        graph.add((node, RDF.first, value))
        graph.add((node, RDF.rest, nodes[index + 1] if index + 1 < len(nodes) else RDF.nil))
    return nodes[0]


def add_all_different(graph: Graph, locals_: Sequence[str], identifier: str) -> None:
    """Declare a required group of named individuals pairwise different."""

    node = BNode(f"all_different_{identifier}")
    graph.add((node, RDF.type, OWL.AllDifferent))
    graph.add(
        (
            node,
            OWL.distinctMembers,
            add_rdf_list(graph, [E(local) for local in locals_], f"different_{identifier}"),
        )
    )


def add_all_disjoint_classes(graph: Graph, locals_: Sequence[str], identifier: str) -> None:
    """Declare a required all-disjoint class group."""

    node = BNode(f"all_disjoint_{identifier}")
    graph.add((node, RDF.type, OWL.AllDisjointClasses))
    graph.add(
        (
            node,
            OWL.members,
            add_rdf_list(graph, [E(local) for local in locals_], f"disjoint_{identifier}"),
        )
    )


def add_individual(
    graph: Graph,
    local: str,
    class_local: str,
    label: str | None = None,
    additional_types: Sequence[str] = (),
) -> URIRef:
    """Declare and type one project named individual."""

    individual = E(local)
    graph.add((individual, RDF.type, OWL.NamedIndividual))
    graph.add((individual, RDF.type, E(class_local)))
    for additional_type in additional_types:
        graph.add((individual, RDF.type, E(additional_type)))
    graph.add((individual, RDFS.label, Literal(label or readable_label(local), lang="en")))
    return individual


def add_some_values_restriction(
    graph: Graph,
    class_local: str,
    property_local: str,
    target_class_local: str,
    identifier: str,
) -> None:
    """Add a named-class existential restriction on an object property."""

    node = BNode(f"restriction_{identifier}")
    graph.add((node, RDF.type, OWL.Restriction))
    graph.add((node, OWL.onProperty, P(property_local)))
    graph.add((node, OWL.someValuesFrom, E(target_class_local)))
    graph.add((E(class_local), RDFS.subClassOf, node))


def add_qualified_cardinality_restriction(
    graph: Graph,
    class_local: str,
    property_local: str,
    cardinality: int,
    target_class_local: str,
    identifier: str,
) -> None:
    """Add a named-class qualified-cardinality restriction on a simple object property."""

    node = BNode(f"restriction_{identifier}")
    graph.add((node, RDF.type, OWL.Restriction))
    graph.add((node, OWL.onProperty, P(property_local)))
    graph.add((node, OWL.qualifiedCardinality, Literal(cardinality, datatype=XSD.nonNegativeInteger)))
    graph.add((node, OWL.onClass, E(target_class_local)))
    graph.add((E(class_local), RDFS.subClassOf, node))


def build_tbox(graph: Graph) -> None:
    """Build the reusable schema, controlled vocabularies, and OWL axioms."""

    for class_local, parent_local in CLASS_HIERARCHY:
        class_iri = E(class_local)
        label = readable_label(class_local)
        graph.add((class_iri, RDF.type, OWL.Class))
        graph.add((class_iri, RDFS.label, Literal(label, lang="en")))
        graph.add(
            (
                class_iri,
                SKOS.definition,
                Literal(f"{label} is a concept used in the ALD HfO2 deposition model.", lang="en"),
            )
        )
        if parent_local is not None:
            graph.add((class_iri, RDFS.subClassOf, E(parent_local)))
        section = REPORT_SECTION_MAP.get(class_local)
        if section is not None:
            graph.add((class_iri, P("reportSection"), Literal(section)))

    for class_local, (mapping_iri, relation, rationale) in sorted(DR_MAPPINGS.items()):
        if class_local not in {local for local, _ in CLASS_HIERARCHY}:
            raise ValidationError(f"DR mapping names undeclared class {class_local!r}")
        graph.add((E(class_local), P("drMappingIRI"), URIRef(mapping_iri)))
        graph.add((E(class_local), P("drMappingRelation"), Literal(relation)))
        graph.add((E(class_local), P("drMappingRationale"), Literal(rationale)))

    for property_local, domain, range_ in OBJECT_PROPERTY_SPECS:
        property_iri = P(property_local)
        label = re.sub(r"(?<!^)([A-Z])", r" \1", property_local).lower()
        graph.add((property_iri, RDF.type, OWL.ObjectProperty))
        graph.add((property_iri, RDFS.label, Literal(label, lang="en")))
        graph.add(
            (
                property_iri,
                SKOS.definition,
                Literal(f"Relates its domain subject to the stated {label} object.", lang="en"),
            )
        )
        graph.add((property_iri, RDFS.domain, _class_or_standard(domain)))
        graph.add((property_iri, RDFS.range, _class_or_standard(range_)))
        if property_local in FUNCTIONAL_OBJECT_PROPERTIES:
            graph.add((property_iri, RDF.type, OWL.FunctionalProperty))
    graph.add((P("precedes"), RDF.type, OWL.TransitiveProperty))
    for left, right in OBJECT_INVERSES:
        graph.add((P(left), OWL.inverseOf, P(right)))
    for child, parent in OBJECT_SUBPROPERTIES:
        graph.add((P(child), RDFS.subPropertyOf, P(parent)))

    for property_local, domain, range_ in DATA_PROPERTY_SPECS:
        property_iri = P(property_local)
        label = re.sub(r"(?<!^)([A-Z])", r" \1", property_local).lower()
        graph.add((property_iri, RDF.type, OWL.DatatypeProperty))
        graph.add((property_iri, RDFS.label, Literal(label, lang="en")))
        graph.add(
            (
                property_iri,
                SKOS.definition,
                Literal(f"Records the {label} literal for its domain subject.", lang="en"),
            )
        )
        graph.add((property_iri, RDFS.domain, _class_or_standard(domain)))
        graph.add((property_iri, RDFS.range, range_))
        if property_local in FUNCTIONAL_DATA_PROPERTIES:
            graph.add((property_iri, RDF.type, OWL.FunctionalProperty))

    for property_local in PROJECT_ANNOTATION_PROPERTIES:
        property_iri = P(property_local)
        label = re.sub(r"(?<!^)([A-Z])", r" \1", property_local).lower()
        graph.add((property_iri, RDF.type, OWL.AnnotationProperty))
        graph.add((property_iri, RDFS.label, Literal(label, lang="en")))
        graph.add(
            (
                property_iri,
                SKOS.definition,
                Literal(f"Annotates ontology resources with {label} information.", lang="en"),
            )
        )
    for property_iri in STANDARD_ANNOTATION_PROPERTIES:
        graph.add((property_iri, RDF.type, OWL.AnnotationProperty))

    for enum_class, member_locals in ENUMERATIONS.items():
        for member_local in member_locals:
            member = add_individual(graph, member_local, enum_class)
            graph.add((member, P("documentedIn"), E("Report_Chapter_3")))
        enum_node = BNode(f"enumeration_{enum_class}")
        graph.add((enum_node, RDF.type, OWL.Class))
        graph.add(
            (
                enum_node,
                OWL.oneOf,
                add_rdf_list(
                    graph,
                    [E(member) for member in member_locals],
                    f"enumeration_members_{enum_class}",
                ),
            )
        )
        graph.add((E(enum_class), OWL.equivalentClass, enum_node))
        add_all_different(graph, member_locals, f"enum_{enum_class}")

    variable_partition = (
        "First_Order_Variable",
        "Second_Order_Variable",
        "Unclassified_Variable",
    )
    union_node = BNode("process_variable_covering_union")
    graph.add((union_node, RDF.type, OWL.Class))
    graph.add(
        (
            union_node,
            OWL.unionOf,
            add_rdf_list(
                graph,
                [E(local) for local in variable_partition],
                "process_variable_union_members",
            ),
        )
    )
    graph.add((E("Process_Variable"), OWL.equivalentClass, union_node))
    add_all_disjoint_classes(graph, variable_partition, "process_variable_partition")

    add_all_disjoint_classes(graph, TOP_LEVEL_DISJOINT, "top_level")
    add_all_disjoint_classes(graph, PHASE_DISJOINT, "crystalline_phases")
    for left, right in (
        ("Bottom_Electrode_Formation", "Top_Electrode_Formation"),
        ("Post_Deposition_Anneal", "Post_Metallization_Anneal"),
        ("Evidence_Gap", "Process_Capability_Limitation"),
        ("Literature_Window", "Route_Instance"),
        ("Electrode_Layer", "Ferroelectric_Layer"),
        ("Contact_Metallization", "Bottom_Electrode_Formation"),
        ("Contact_Metallization", "Top_Electrode_Formation"),
    ):
        graph.add((E(left), OWL.disjointWith, E(right)))
    graph.add(
        (
            E("Evidence_Gap"),
            RDFS.comment,
            Literal(
                "An evidence gap records unavailable reporting and is distinct from a physical process-capability limitation.",
                lang="en",
            ),
        )
    )
    graph.add(
        (
            E("Contact_Metallization"),
            RDFS.comment,
            Literal(
                "Contact metallization is distinct from bottom- and top-electrode formation even when materials overlap.",
                lang="en",
            ),
        )
    )
    for class_local in MEASUREMENT_TBOX_SCAFFOLD_CLASSES:
        graph.add(
            (
                E(class_local),
                RDFS.comment,
                Literal(MEASUREMENT_TBOX_SCAFFOLD_NOTE, lang="en"),
            )
        )

    add_all_different(graph, ROUTE_STEP_LOCALS, "route_steps")
    add_all_different(graph, OPERATION_LOCALS, "route_operations")
    add_all_different(graph, STACK_LAYER_LOCALS, "stack_layers")

    add_qualified_cardinality_restriction(
        graph, "Route_Step", "stepOf", 1, "Process_Route", "route_step_route"
    )
    add_qualified_cardinality_restriction(
        graph,
        "Route_Step",
        "realizesOperation",
        1,
        "Process_Operation",
        "route_step_operation",
    )
    add_qualified_cardinality_restriction(
        graph,
        "Quantity_Value",
        "hasQuantityKind",
        1,
        "Quantity_Kind",
        "quantity_kind",
    )
    add_qualified_cardinality_restriction(
        graph,
        "Route_Instance",
        "observedInRoute",
        1,
        "Process_Route",
        "route_instance_route",
    )
    add_qualified_cardinality_restriction(
        graph,
        "Route_Instance",
        "observedAtStep",
        1,
        "Route_Step",
        "route_instance_step",
    )
    for (
        class_local,
        property_local,
        target_class_local,
        identifier,
    ) in SCHEMA_SOME_RESTRICTIONS:
        add_some_values_restriction(
            graph,
            class_local,
            property_local,
            target_class_local,
            identifier,
        )
    for (
        class_local,
        property_local,
        cardinality,
        target_class_local,
        identifier,
    ) in MEASUREMENT_CARDINALITY_RESTRICTIONS:
        add_qualified_cardinality_restriction(
            graph,
            class_local,
            property_local,
            cardinality,
            target_class_local,
            identifier,
        )

    for target in TARGETS:
        individual = add_individual(graph, target_local(target), "Target_Category", target)
        graph.add((individual, P("documentedIn"), E("Ledger_Claim_Ledger")))
    for field in FIELDS:
        individual = add_individual(
            graph, field_local(field), "Quantity_Kind", field.replace("_", " ")
        )
        graph.add((individual, P("documentedIn"), E("Ledger_Claim_Ledger")))
    for symbol, unit_local in UNIT_IRI_NAMES.items():
        individual = add_individual(graph, unit_local, "Unit", symbol)
        graph.add((individual, P("documentedIn"), E("Ledger_Claim_Ledger")))


def build_documents_and_source_registry(
    graph: Graph, rows: Sequence[ClaimRow], options: BuildOptions
) -> None:
    """Build ontology metadata, source documents, and all source registry records."""

    graph.add((ONTOLOGY_IRI, RDF.type, OWL.Ontology))
    graph.add(
        (
            ONTOLOGY_IRI,
            DCTERMS.title,
            Literal("ALD HfO2 Deposition ontology for HfO2-based FeRAM production", lang="en"),
        )
    )
    graph.add((ONTOLOGY_IRI, DCTERMS.created, Literal(options.report_date, datatype=XSD.date)))
    timestamp_text = options.generation_timestamp.astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    graph.add(
        (
            ONTOLOGY_IRI,
            P("generationTimestamp"),
            Literal(timestamp_text, datatype=XSD.dateTimeStamp),
        )
    )
    graph.add((ONTOLOGY_IRI, P("ledgerRowCount"), Literal(LEDGER_ROW_COUNT, datatype=XSD.integer)))
    for note in (
        "Domain and range axioms infer types under the open-world semantics and are not closed-world validation constraints.",
        "Unreported values remain unknown; an evidence gap does not assert physical absence or a negative process fact.",
        "Literature windows are conditioned evidence summaries, not production windows, recommendations, or transferable recipes.",
    ):
        graph.add((ONTOLOGY_IRI, P("openWorldNote"), Literal(note, lang="en")))
    graph.add((ONTOLOGY_IRI, DCTERMS.source, E("Ledger_Claim_Ledger")))
    graph.add((ONTOLOGY_IRI, DCTERMS.source, E("Report_Chapter_3")))

    ledger_document = add_individual(
        graph, "Ledger_Claim_Ledger", "Source_Document", "Claim ledger"
    )
    graph.add((ledger_document, DCTERMS.title, Literal("claim_ledger.xlsx")))
    graph.add((ledger_document, P("inputSheetName"), Literal(LEDGER_SHEET)))
    graph.add((ledger_document, P("sourceFileSha256"), Literal(options.ledger_sha256)))

    report_document = add_individual(
        graph, "Report_Chapter_3", "Source_Document", "HfO2 FeRAM Production System Chapter 3"
    )
    graph.add(
        (
            report_document,
            DCTERMS.title,
            Literal("HfO2 FeRAM Production System — Chapter 3: ALD HfO2 Deposition"),
        )
    )
    graph.add((report_document, DCTERMS.source, REPORT_REPOSITORY_IRI))
    graph.add((report_document, DCTERMS.created, Literal(options.report_date, datatype=XSD.date)))

    publication = add_individual(
        graph, "Document_Tsai_2022", "Source_Document", "Tsai et al. 2022 publication"
    )
    graph.add(
        (
            publication,
            DCTERMS.creator,
            Literal(
                "Shih-Hao Tsai; Zihang Fang; Xinghua Wang; Umesh Chand; Chun-Kuei Chen; "
                "Sonu Hooda; Maheswari Sivan; Jieming Pan; Evgeny Zamburg; Aaron Voon-Yew Thean"
            ),
        )
    )
    graph.add(
        (
            publication,
            DCTERMS.title,
            Literal("Stress-Memorized HZO for High-Performance Ferroelectric Field-Effect Memtransistor"),
        )
    )
    graph.add(
        (
            publication,
            RDFS.comment,
            Literal("ACS Applied Electronic Materials, volume 4, issue 4, pages 1642–1650, 2022."),
        )
    )
    graph.add((publication, DCTERMS.issued, Literal("2022", datatype=XSD.gYear)))
    graph.add((publication, DCTERMS.identifier, Literal("10.1021/acsaelm.1c01321")))
    graph.add((publication, DCTERMS.source, TSAI_DOI_IRI))

    source_counts = Counter(row.source_id for row in rows)
    for source_id in sorted(EXPECTED_SOURCE_COUNTS):
        source = add_individual(graph, entity_name("Source", source_id), "Source_Record", source_id)
        graph.add((source, P("sourceId"), Literal(source_id)))
        graph.add((source, P("claimCount"), Literal(source_counts[source_id], datatype=XSD.nonNegativeInteger)))
        graph.add((source, P("documentedIn"), ledger_document))
        if source_id == "BS3":
            graph.add((source, P("transcribesDocument"), publication))
            graph.add(
                (
                    source,
                    RDFS.comment,
                    Literal(
                        "Ledger source record for BS3; the ontology build did not independently reverify the transcription against the publication.",
                        lang="en",
                    ),
                )
            )
        else:
            graph.add(
                (
                    source,
                    SKOS.scopeNote,
                    Literal(
                        "Declared for source-registry completeness; claims are not instantiated in this build.",
                        lang="en",
                    ),
                )
            )


def _status_and_confidence(note: str, claim_id: str) -> tuple[str, str]:
    """Extract exactly one controlled evidence-status and confidence token."""

    status_matches = re.findall(r"Berine evidence status:\s*([^;]+);", note)
    confidence_matches = re.findall(r"confidence:\s*([^.;]+)[.;]", note)
    if len(status_matches) != 1 or len(confidence_matches) != 1:
        raise ValidationError(
            f"{claim_id} must contain exactly one evidence status and confidence token"
        )
    status_map = {
        "Directly reported": "Evidence_Status_Directly_Reported",
        "Open gap": "Evidence_Status_Open_Gap",
    }
    confidence_map = {"High": "Confidence_High", "Open": "Confidence_Open"}
    status = status_map.get(status_matches[0])
    confidence = confidence_map.get(confidence_matches[0])
    if status is None or confidence is None:
        raise ValidationError(
            f"{claim_id} has unknown status/confidence tokens "
            f"{status_matches[0]!r}/{confidence_matches[0]!r}"
        )
    return status, confidence


def build_claims(graph: Graph, rows: Sequence[ClaimRow]) -> None:
    """Create exactly the 25 universal BS3 claim reifications."""

    for row in sorted((item for item in rows if item.source_id == "BS3"), key=lambda item: item.claim_id):
        status_local, confidence_local = _status_and_confidence(row.note, row.claim_id)
        claim = add_individual(graph, claim_local(row.claim_id), "Claim", row.claim_id)
        graph.add((claim, P("claimId"), Literal(row.claim_id)))
        graph.add((claim, P("claimIdOriginal"), Literal(row.claim_id_original)))
        graph.add((claim, P("hasSource"), E("Source_BS3")))
        graph.add((claim, P("documentedIn"), E("Ledger_Claim_Ledger")))
        graph.add((claim, P("locatorText"), Literal(row.locator)))
        graph.add((claim, P("hasTargetCategory"), E(target_local(row.target))))
        graph.add((claim, P("hasClaimField"), E(field_local(row.field))))
        graph.add((claim, P("rawValueText"), Literal(row.value)))
        graph.add((claim, P("conditionText"), Literal(row.condition)))
        graph.add((claim, P("anchorText"), Literal(row.anchor)))
        graph.add((claim, P("noteText"), Literal(row.note)))
        graph.add((claim, P("helperTargetText"), Literal(row.helper_target)))
        graph.add((claim, P("helperSourceText"), Literal(row.helper_source)))
        graph.add(
            (claim, P("extractionBatch"), Literal(row.extraction_batch, datatype=XSD.integer))
        )
        graph.add((claim, P("hasEvidenceStatus"), E(status_local)))
        graph.add((claim, P("hasConfidence"), E(confidence_local)))
        graph.add((claim, P("secondHandTranscription"), Literal(True, datatype=XSD.boolean)))


def validate_route_spec(rows: Sequence[ClaimRow], route_spec: Sequence[StepSpec]) -> None:
    """Cross-check every handler and step condition before any BS3 ABox is added."""

    violations: list[str] = []
    bs3 = {row.claim_id: row for row in rows if row.source_id == "BS3"}
    spec_ids = [claim_id for spec in route_spec for claim_id in spec.claim_ids]
    handler_ids = [handler.claim_id for spec in route_spec for handler in spec.handlers]
    expected_ids = {f"BS3-{index:03d}" for index in range(1, 26)}
    if len(route_spec) != 6 or tuple(spec.index for spec in route_spec) != tuple(range(1, 7)):
        violations.append("route specification does not have exactly indexed steps 1 through 6")
    if Counter(spec_ids) != Counter(expected_ids):
        violations.append(f"route claim consumption is not exactly once: {Counter(spec_ids)!r}")
    if Counter(handler_ids) != Counter(expected_ids):
        violations.append(f"handler claim consumption is not exactly once: {Counter(handler_ids)!r}")
    if set(bs3) != expected_ids:
        violations.append("ledger BS3 set differs from the authoritative route specification")
    for spec in route_spec:
        if tuple(handler.claim_id for handler in spec.handlers) != spec.claim_ids:
            violations.append(f"step {spec.index} handler order differs from claim tuple")
        for handler in spec.handlers:
            row = bs3.get(handler.claim_id)
            if row is None:
                violations.append(f"missing ledger row for {handler.claim_id}")
                continue
            expected = (
                handler.expected_target,
                handler.expected_field,
                handler.expected_value,
                handler.expected_unit,
            )
            actual = (row.target, row.field, row.value, row.unit)
            if actual != expected:
                violations.append(f"{row.claim_id} handler contract {expected!r} != ledger {actual!r}")
            if handler.effect != EXPECTED_HANDLER_EFFECTS.get(handler.claim_id):
                violations.append(
                    f"{row.claim_id} handler effect {handler.effect!r} is not the exact required effect"
                )
            try:
                if parse_step_position(row.condition) != spec.index:
                    violations.append(
                        f"{row.claim_id} condition step does not equal authoritative step {spec.index}"
                    )
                parsed: Decimal | str | None = None
                if handler.claim_id in RATIO_CLAIM_IDS:
                    parsed = parse_ratio(row.value, handler.ratio_prefix)
                elif handler.claim_id in QUANTITY_CLAIM_IDS:
                    parsed = parse_numeric(row.value, handler.parse_prefix)
                if parsed is not None and parsed != EXPECTED_PARSED_VALUES[handler.claim_id]:
                    violations.append(
                        f"{row.claim_id} parsed result {parsed!r} does not equal "
                        f"{EXPECTED_PARSED_VALUES[handler.claim_id]!r}"
                    )
            except ValidationError as exc:
                violations.append(f"{row.claim_id}: {exc}")
    _raise_phase("BS3 route specification", violations)


def annotate_axiom(
    graph: Graph,
    source: URIRef,
    predicate: URIRef,
    target: URIRef,
    rationale: str,
    assertion_source: URIRef,
) -> None:
    """Annotate one asserted object-property triple with a proper OWL axiom record."""

    key = "|".join((str(source), str(predicate), str(target)))
    identifier = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    axiom = BNode(f"axiom_{identifier}")
    graph.add((axiom, RDF.type, OWL.Axiom))
    graph.add((axiom, OWL.annotatedSource, source))
    graph.add((axiom, OWL.annotatedProperty, predicate))
    graph.add((axiom, OWL.annotatedTarget, target))
    graph.add((axiom, P("assertionRationale"), Literal(rationale, lang="en")))
    graph.add((axiom, P("assertionSource"), assertion_source))


def build_variables(graph: Graph) -> None:
    """Create report-documented variable descriptors and their order rationales."""

    for spec in sorted(VARIABLE_SPECS, key=lambda item: item.local_name):
        variable = add_individual(graph, spec.local_name, spec.variable_class)
        graph.add((variable, P("variableOrderRationale"), Literal(spec.rationale)))
        graph.add((variable, P("documentedIn"), E("Report_Chapter_3")))


def _quantity_handler_map(route_spec: Sequence[StepSpec]) -> dict[str, tuple[StepSpec, ClaimHandler]]:
    """Return the authoritative claim-to-step-and-handler lookup."""

    return {
        handler.claim_id: (step, handler)
        for step in route_spec
        for handler in step.handlers
    }


def build_route_and_handlers(
    graph: Graph, rows: Sequence[ClaimRow], route_spec: Sequence[StepSpec]
) -> None:
    """Build the exact BS3 route, materials, quantities, instances, and ledger gaps."""

    row_by_id = {row.claim_id: row for row in rows if row.source_id == "BS3"}
    handler_map = _quantity_handler_map(route_spec)
    route = add_individual(
        graph,
        "Route_BS3_Tsai2022",
        "Process_Route",
        "TiN/HZO/TiN MFM capacitor route (Tsai et al. 2022)",
    )
    graph.add((route, P("reportSection"), Literal("3.12")))
    graph.add((route, P("reportTable"), Literal("3.7")))
    graph.add(
        (
            route,
            RDFS.comment,
            Literal(
                "One literature-route instantiation; it is not a recommendation, reference flow, production recipe, or production process window.",
                lang="en",
            ),
        )
    )

    for spec in route_spec:
        step = add_individual(graph, spec.step_local, "Route_Step", spec.label)
        operation = add_individual(
            graph, spec.operation_local, spec.operation_class, readable_label(spec.operation_local)
        )
        graph.add((route, P("hasStep"), step))
        graph.add((step, P("stepOf"), route))
        graph.add((step, P("stepIndex"), Literal(spec.index, datatype=XSD.positiveInteger)))
        graph.add((step, P("stepDescription"), Literal(spec.description)))
        graph.add((step, P("hasModuleScope"), E(spec.module_scope)))
        graph.add((operation, P("hasModuleScope"), E(spec.module_scope)))
        graph.add((step, P("realizesOperation"), operation))
        graph.add((operation, P("operationRealizedBy"), step))
        if spec.index in {4, 5}:
            scope_comment = Literal(
                "Retained only to preserve route order; patterning is not owned by this module or elsewhere in the report.",
                lang="en",
            )
            graph.add((step, RDFS.comment, scope_comment))
            graph.add((operation, RDFS.comment, scope_comment))

    composite = E("Op_02_ALD_Film_Formation")
    for sub_local, class_local in (
        ("Op_02a_Hf_Precursor_Dose", "Hf_Precursor_Dose"),
        ("Op_02b_Zr_Precursor_Dose", "Zr_Precursor_Dose"),
        ("Op_02c_Co_Reactant_Dose", "Co_Reactant_Dose"),
        ("Op_02d_Cycle_Repetition", "Cycle_Repetition"),
    ):
        suboperation = add_individual(graph, sub_local, class_local)
        graph.add((composite, P("hasSubOperation"), suboperation))
        graph.add((suboperation, P("subOperationOf"), composite))

    for left_spec, right_spec in zip(route_spec[:-1], route_spec[1:], strict=True):
        graph.add((E(left_spec.step_local), P("directlyPrecedes"), E(right_spec.step_local)))
    graph.add(
        (
            E("Step_01_Bottom_Electrode"),
            P("necessarilyPrecedes"),
            E("Step_02_HZO_Deposition"),
        )
    )
    annotate_axiom(
        graph,
        E("Step_01_Bottom_Electrode"),
        P("necessarilyPrecedes"),
        E("Step_02_HZO_Deposition"),
        NECESSARY_ORDER_RATIONALE,
        E("Report_Chapter_3"),
    )
    for left_local, right_local in (
        ("Step_02_HZO_Deposition", "Step_03_Top_Electrode"),
        ("Step_03_Top_Electrode", "Step_04_Photolithography"),
        ("Step_04_Photolithography", "Step_05_Wet_Etch"),
        ("Step_05_Wet_Etch", "Step_06_Crystallization_Anneal"),
    ):
        graph.add((E(left_local), P("routeScopedPrecedes"), E(right_local)))

    stack = add_individual(
        graph, "Stack_BS3_TiN_HZO_TiN", "MFM_Capacitor", "BS3 TiN/HZO/TiN stack"
    )
    bottom_layer = add_individual(
        graph, "Layer_BS3_Bottom_TiN", "Electrode_Layer", "BS3 bottom TiN electrode"
    )
    hzo_layer = add_individual(
        graph, "Layer_BS3_HZO", "Ferroelectric_Layer", "BS3 HZO ferroelectric layer"
    )
    top_layer = add_individual(
        graph, "Layer_BS3_Top_TiN", "Electrode_Layer", "BS3 top TiN electrode"
    )
    tin = add_individual(graph, "TiN", "Electrode_Material", "TiN")
    hzo = add_individual(graph, "HZO_Hf05Zr05O2", "Film_Material", "Hf0.5Zr0.5O2")
    temah = add_individual(graph, "TEMAH", "Hf_Precursor", "TEMAH")
    temaz = add_individual(graph, "TEMAZ", "Zr_Precursor", "TEMAZ")
    argon = add_individual(graph, "Ar", "Sputter_Gas", "Ar")
    nitrogen = add_individual(
        graph, "N2", "Sputter_Gas", "N2", additional_types=("Anneal_Ambient",)
    )
    etchant = add_individual(
        graph,
        "NH4OH_H2O2_H2O_Etchant",
        "Etchant",
        "NH4OH:H2O2:H2O wet etchant",
    )

    graph.add((stack, P("hasBottomElectrode"), bottom_layer))
    graph.add((stack, P("hasFerroelectricLayer"), hzo_layer))
    graph.add((stack, P("hasTopElectrode"), top_layer))
    graph.add((bottom_layer, P("madeOfChemical"), tin))
    graph.add((hzo_layer, P("madeOfChemical"), hzo))
    graph.add((top_layer, P("madeOfChemical"), tin))
    graph.add((E("Op_01_Bottom_Electrode_Formation"), P("producesLayer"), bottom_layer))
    graph.add((E("Op_02_ALD_Film_Formation"), P("producesLayer"), hzo_layer))
    graph.add((E("Op_03_Top_Electrode_Formation"), P("producesLayer"), top_layer))
    graph.add((E("Op_02a_Hf_Precursor_Dose"), P("usesPrecursor"), temah))
    graph.add((E("Op_02b_Zr_Precursor_Dose"), P("usesPrecursor"), temaz))
    graph.add((E("Op_01_Bottom_Electrode_Formation"), P("usesSputterGas"), argon))
    graph.add((E("Op_01_Bottom_Electrode_Formation"), P("usesSputterGas"), nitrogen))
    graph.add((E("Op_05_Wet_Etch"), P("usesEtchant"), etchant))
    graph.add((E("Op_06_Crystallization_Anneal"), P("usesAnnealAmbient"), nitrogen))

    for claim_id in QUANTITY_CLAIM_IDS:
        row = row_by_id[claim_id]
        _, handler = handler_map[claim_id]
        quantity_class = "Ratio_Value" if claim_id in RATIO_CLAIM_IDS else "Point_Value"
        quantity = add_individual(
            graph,
            quantity_local(claim_id),
            quantity_class,
            handler.quantity_label,
            additional_types=("Quantity_Value",),
        )
        graph.add((quantity, P("hasQuantityKind"), E(field_local(row.field))))
        graph.add((quantity, P("quantityLabel"), Literal(handler.quantity_label)))
        graph.add((quantity, P("rawValueText"), Literal(row.value)))
        graph.add((quantity, P("rawUnitText"), Literal(row.unit)))
        graph.add((quantity, P("assertedBy"), E(claim_local(claim_id))))
        graph.add((quantity, P("concernsVariable"), E(QUANTITY_VARIABLE_MAP[claim_id])))
        if quantity_class == "Ratio_Value":
            graph.add(
                (
                    quantity,
                    P("ratioExpression"),
                    Literal(parse_ratio(row.value, handler.ratio_prefix)),
                )
            )
        else:
            graph.add(
                (
                    quantity,
                    P("numericValue"),
                    decimal_literal(parse_numeric(row.value, handler.parse_prefix)),
                )
            )
            graph.add((quantity, P("hasUnit"), E(UNIT_IRI_NAMES[row.unit])))
        operation_local = QUANTITY_OPERATION_MAP[claim_id]
        graph.add((E(operation_local), P("hasProcessParameterValue"), quantity))

    for claim_id in QUANTITY_CLAIM_IDS:
        if claim_id in {"BS3-023", "BS3-024"}:
            continue
        step_spec, _ = handler_map[claim_id]
        instance_local = f"Instance_BS3_{claim_id[-3:]}"
        instance = add_individual(graph, instance_local, "Route_Instance")
        graph.add((instance, P("hasObservedValue"), E(quantity_local(claim_id))))
        graph.add((instance, P("observedInRoute"), route))
        graph.add((instance, P("observedAtStep"), E(step_spec.step_local)))
        graph.add((instance, P("assertedBy"), E(claim_local(claim_id))))

    thermal_instance = add_individual(
        graph,
        "Instance_BS3_Thermal_Treatment_Tuple",
        "Route_Instance",
        "BS3 thermal treatment tuple",
    )
    for claim_id in ("BS3-023", "BS3-024"):
        graph.add((thermal_instance, P("hasObservedValue"), E(quantity_local(claim_id))))
    graph.add((thermal_instance, P("observedInRoute"), route))
    graph.add(
        (
            thermal_instance,
            P("observedAtStep"),
            E("Step_06_Crystallization_Anneal"),
        )
    )
    for claim_id in ("BS3-023", "BS3-024", "BS3-025"):
        graph.add((thermal_instance, P("assertedBy"), E(claim_local(claim_id))))

    for gap_claim_id, concerns_local in (
        ("BS3-015", "Op_02c_Co_Reactant_Dose"),
        ("BS3-019", "Op_04_Photolithography"),
    ):
        row = row_by_id[gap_claim_id]
        gap = add_individual(graph, f"Gap_{gap_claim_id.replace('-', '_')}", "Evidence_Gap")
        graph.add((gap, P("gapConcerns"), E(concerns_local)))
        graph.add((gap, P("gapQuantityKind"), E(field_local(row.field))))
        graph.add((gap, P("gapStatement"), Literal(row.value)))
        graph.add((gap, P("doNotInferNote"), Literal(row.note)))
        graph.add((gap, P("assertedBy"), E(claim_local(gap_claim_id))))

    graph.add((E("Instance_BS3_013"), P("transferBlockedBy"), Literal(TRANSFER_BLOCK_TEXT)))

    for individual_local, claim_ids in sorted(SHARED_INDIVIDUAL_CLAIMS.items()):
        individual = E(individual_local)
        if (individual, RDF.type, OWL.NamedIndividual) not in graph:
            raise ValidationError(f"Shared provenance target was not built: {individual_local}")
        for claim_id in claim_ids:
            graph.add((individual, P("assertedBy"), E(claim_local(claim_id))))


def build_window_scaffold(graph: Graph, enabled: bool) -> None:
    """Build optional non-numeric literature windows and exact assessments."""

    if not enabled:
        for instance_local in ROUTE_INSTANCE_IDS:
            graph.add(
                (
                    E(instance_local),
                    P("hasWindowAssessment"),
                    E("Window_Assessment_Not_Assessed"),
                )
            )
        return

    for spec in WINDOW_SPECS:
        window = add_individual(graph, spec.local_name, "Literature_Window", spec.label)
        graph.add((window, P("documentedIn"), E("Report_Chapter_3")))
        graph.add((window, P("windowConditionText"), Literal(spec.condition_text)))
        graph.add((window, P("scaffoldNote"), Literal(WINDOW_SCAFFOLD_NOTE)))

    for instance_local, assessment_local, relation_local, window_local in WINDOW_ASSESSMENTS:
        instance = E(instance_local)
        graph.add((instance, P("hasWindowAssessment"), E(assessment_local)))
        if relation_local is not None and window_local is not None:
            window = E(window_local)
            graph.add((instance, P(relation_local), window))
            if relation_local == "exactIndependentMatch":
                annotate_axiom(
                    graph,
                    instance,
                    P(relation_local),
                    window,
                    THERMAL_MATCH_RATIONALE,
                    E("Report_Chapter_3"),
                )


def build_report_derived_gaps(graph: Graph, enabled: bool) -> None:
    """Create the exact optional set of report-derived evidence gaps."""

    if not enabled:
        return
    for spec in REPORT_GAP_SPECS:
        gap = add_individual(graph, spec.local_name, "Evidence_Gap")
        graph.add((gap, P("gapConcerns"), E(spec.concerns_local)))
        graph.add((gap, P("gapQuantityKind"), E(field_local(spec.quantity_kind_field))))
        graph.add((gap, P("gapStatement"), Literal(spec.statement)))
        graph.add((gap, P("derivedFromReport"), Literal(REPORT_GAP_SOURCE)))
        graph.add((gap, P("documentedIn"), E("Report_Chapter_3")))
        graph.add((gap, P("doNotInferNote"), Literal(REPORT_GAP_NOTE)))


def coverage_grade_local(grade: str) -> str:
    """Map a controlled coverage grade to its enumeration member."""

    mapping = {
        "well-covered": "Coverage_Well_Covered",
        "thin": "Coverage_Thin",
        "bare": "Coverage_Bare",
    }
    try:
        return mapping[grade]
    except KeyError as exc:
        raise ValidationError(f"Unknown controlled coverage grade: {grade!r}") from exc


def build_coverage(graph: Graph, coverage_rows: Sequence[CoverageRow]) -> None:
    """Create one reconciled coverage assessment for every controlled target."""

    for row in sorted(coverage_rows, key=lambda item: item.target):
        assessment = add_individual(
            graph,
            entity_name("Coverage", "Assessment", target_suffix(row.target)),
            "Coverage_Assessment",
            f"Coverage assessment for {row.target}",
        )
        graph.add((assessment, P("assessesTarget"), E(target_local(row.target))))
        graph.add(
            (
                assessment,
                P("coverageRowCount"),
                Literal(row.row_count, datatype=XSD.nonNegativeInteger),
            )
        )
        graph.add(
            (
                assessment,
                P("coverageSourceCount"),
                Literal(row.distinct_source_count, datatype=XSD.nonNegativeInteger),
            )
        )
        graph.add((assessment, P("hasCoverageGrade"), E(coverage_grade_local(row.coverage))))
        graph.add((assessment, P("documentedIn"), E("Ledger_Claim_Ledger")))


def build_graph(rows: Sequence[ClaimRow], options: BuildOptions) -> Graph:
    """Construct one complete graph from already validated in-memory inputs."""

    validate_route_spec(rows, BS3_ROUTE_SPEC)
    graph = Graph()
    bind_namespaces(graph)
    build_tbox(graph)
    build_documents_and_source_registry(graph, rows, options)
    build_claims(graph, rows)
    build_variables(graph)
    build_route_and_handlers(graph, rows, BS3_ROUTE_SPEC)
    build_window_scaffold(graph, options.window_scaffold)
    build_report_derived_gaps(graph, options.report_derived_gaps)
    build_coverage(graph, options.coverage_rows)
    return graph


def rdf_list_values(graph: Graph, head: URIRef | BNode) -> Sequence[URIRef | BNode | Literal]:
    """Read one finite, well-formed RDF list or raise a structural error."""

    if head == RDF.nil:
        return ()
    values: list[URIRef | BNode | Literal] = []
    seen: set[URIRef | BNode] = set()
    node: URIRef | BNode = head
    while node != RDF.nil:
        if node in seen:
            raise ValidationError(f"cyclic RDF list at {node}")
        seen.add(node)
        first_values = list(graph.objects(node, RDF.first))
        rest_values = list(graph.objects(node, RDF.rest))
        if len(first_values) != 1 or len(rest_values) != 1:
            raise ValidationError(
                f"malformed RDF list node {node}: first={len(first_values)}, rest={len(rest_values)}"
            )
        values.append(first_values[0])
        rest = rest_values[0]
        if rest != RDF.nil and not isinstance(rest, (URIRef, BNode)):
            raise ValidationError(f"RDF list rest is not a resource at {node}: {rest}")
        node = rest  # type: ignore[assignment]
    return tuple(values)


def subclass_ancestors(graph: Graph) -> dict[URIRef, set[URIRef]]:
    """Compute transitive named-superclass closure, ignoring anonymous restrictions."""

    classes = {
        subject
        for subject in graph.subjects(RDF.type, OWL.Class)
        if isinstance(subject, URIRef)
    }
    direct: dict[URIRef, set[URIRef]] = {class_: set() for class_ in classes}
    for child, parent in graph.subject_objects(RDFS.subClassOf):
        if isinstance(child, URIRef) and isinstance(parent, URIRef):
            direct.setdefault(child, set()).add(parent)
    closure: dict[URIRef, set[URIRef]] = {}
    for class_ in classes:
        visited: set[URIRef] = set()
        stack = list(direct.get(class_, set()))
        while stack:
            parent = stack.pop()
            if parent in visited:
                continue
            visited.add(parent)
            stack.extend(direct.get(parent, set()) - visited)
        closure[class_] = visited
    return closure


def named_individuals(graph: Graph) -> set[URIRef]:
    """Return all explicitly declared project named individuals."""

    return {
        subject
        for subject in graph.subjects(RDF.type, OWL.NamedIndividual)
        if isinstance(subject, URIRef) and str(subject).startswith(PROJECT_PREFIX)
    }


def instances_of(graph: Graph, class_local: str) -> set[URIRef]:
    """Return explicitly named individuals typed into a class through named closure."""

    target = E(class_local)
    closure = subclass_ancestors(graph)
    result: set[URIRef] = set()
    for individual in named_individuals(graph):
        direct_types = {
            type_
            for type_ in graph.objects(individual, RDF.type)
            if isinstance(type_, URIRef) and type_ != OWL.NamedIndividual
        }
        if target in direct_types or any(target in closure.get(type_, set()) for type_ in direct_types):
            result.add(individual)
    return result


def _single_values(graph: Graph, subject: URIRef, predicate: URIRef) -> set[URIRef | Literal | BNode]:
    """Return the direct values of one subject/predicate pair as a set."""

    return set(graph.objects(subject, predicate))


def _expected_provenance() -> dict[str, Sequence[str]]:
    """Return the complete exact assertedBy contract for ledger-derived individuals."""

    expected = dict(SHARED_INDIVIDUAL_CLAIMS)
    for claim_id in QUANTITY_CLAIM_IDS:
        expected[quantity_local(claim_id)] = (claim_id,)
    for claim_id in QUANTITY_CLAIM_IDS:
        if claim_id not in {"BS3-023", "BS3-024"}:
            expected[f"Instance_BS3_{claim_id[-3:]}"] = (claim_id,)
    expected["Instance_BS3_Thermal_Treatment_Tuple"] = (
        "BS3-023",
        "BS3-024",
        "BS3-025",
    )
    expected["Gap_BS3_015"] = ("BS3-015",)
    expected["Gap_BS3_019"] = ("BS3-019",)
    return expected


def _validate_population(
    graph: Graph, rows: Sequence[ClaimRow], options: BuildOptions
) -> None:
    """Validate exact BS3 population and source-column preservation."""

    violations: list[str] = []
    bs3_rows = {row.claim_id: row for row in rows if row.source_id == "BS3"}
    claims = instances_of(graph, "Claim")
    expected_claims = {E(claim_local(claim_id)) for claim_id in bs3_rows}
    if claims != expected_claims:
        violations.append(
            f"claim individuals mismatch; missing={sorted(map(local_name, expected_claims-claims))}, "
            f"extra={sorted(map(local_name, claims-expected_claims))}"
        )
    for claim_id, row in sorted(bs3_rows.items()):
        claim = E(claim_local(claim_id))
        status_local, confidence_local = _status_and_confidence(row.note, claim_id)
        expected_values: Sequence[tuple[URIRef, set[URIRef | Literal]]] = (
            (P("claimId"), {Literal(row.claim_id)}),
            (P("claimIdOriginal"), {Literal(row.claim_id_original)}),
            (P("hasSource"), {E("Source_BS3")}),
            (P("documentedIn"), {E("Ledger_Claim_Ledger")}),
            (P("locatorText"), {Literal(row.locator)}),
            (P("hasTargetCategory"), {E(target_local(row.target))}),
            (P("hasClaimField"), {E(field_local(row.field))}),
            (P("rawValueText"), {Literal(row.value)}),
            (P("conditionText"), {Literal(row.condition)}),
            (P("anchorText"), {Literal(row.anchor)}),
            (P("noteText"), {Literal(row.note)}),
            (P("helperTargetText"), {Literal(row.helper_target)}),
            (P("helperSourceText"), {Literal(row.helper_source)}),
            (P("extractionBatch"), {Literal(row.extraction_batch, datatype=XSD.integer)}),
            (P("hasEvidenceStatus"), {E(status_local)}),
            (P("hasConfidence"), {E(confidence_local)}),
            (P("secondHandTranscription"), {Literal(True, datatype=XSD.boolean)}),
        )
        for predicate, expected in expected_values:
            actual = _single_values(graph, claim, predicate)
            if actual != expected:
                violations.append(
                    f"{claim_id} {local_name(predicate)} values {actual!r} do not equal {expected!r}"
                )
        if claim_id in QUANTITY_CLAIM_IDS:
            actual_units = _single_values(graph, E(quantity_local(claim_id)), P("rawUnitText"))
            if actual_units != {Literal(row.unit)}:
                violations.append(f"{claim_id} source unit was not preserved on its quantity")
        elif row.unit != "":
            violations.append(f"{claim_id} has a nonempty unit but no required quantity")

    non_bs3_claims = [
        individual
        for individual in claims
        if not local_name(individual).startswith("Claim_BS3_")
    ]
    if non_bs3_claims:
        violations.append(f"non-BS3 claims exist: {sorted(map(local_name, non_bs3_claims))}")

    expected_category_sets = {
        "Process_Route": {"Route_BS3_Tsai2022"},
        "Route_Step": set(ROUTE_STEP_LOCALS),
        "Process_Operation": set(OPERATION_LOCALS),
        "Device_Stack": {"Stack_BS3_TiN_HZO_TiN"},
        "Layer": set(STACK_LAYER_LOCALS),
        "Chemical": {
            "TiN",
            "HZO_Hf05Zr05O2",
            "TEMAH",
            "TEMAZ",
            "Ar",
            "N2",
            "NH4OH_H2O2_H2O_Etchant",
        },
        "Quantity_Value": {quantity_local(claim_id) for claim_id in QUANTITY_CLAIM_IDS},
        "Route_Instance": set(ROUTE_INSTANCE_IDS),
    }
    for class_local, expected_locals in expected_category_sets.items():
        actual_locals = {local_name(individual) for individual in instances_of(graph, class_local)}
        if actual_locals != expected_locals:
            violations.append(
                f"{class_local} population mismatch; missing={sorted(expected_locals-actual_locals)}, "
                f"extra={sorted(actual_locals-expected_locals)}"
            )
    gaps = {local_name(individual) for individual in instances_of(graph, "Evidence_Gap")}
    expected_gaps = {"Gap_BS3_015", "Gap_BS3_019"}
    if options.report_derived_gaps:
        expected_gaps.update(spec.local_name for spec in REPORT_GAP_SPECS)
    if gaps != expected_gaps:
        violations.append(f"Evidence_Gap population mismatch: {sorted(gaps)}")
    windows = {local_name(individual) for individual in instances_of(graph, "Literature_Window")}
    expected_windows = {spec.local_name for spec in WINDOW_SPECS} if options.window_scaffold else set()
    if windows != expected_windows:
        violations.append(f"Literature_Window population mismatch: {sorted(windows)}")
    coverage = instances_of(graph, "Coverage_Assessment")
    if len(coverage) != 23:
        violations.append(f"coverage assessment count is {len(coverage)}, expected 23")
    if instances_of(graph, "First_Purge") or instances_of(graph, "Second_Purge"):
        violations.append("BS3 purge operation individual exists")
    if instances_of(graph, "Thermal_Oxidant") or instances_of(graph, "Plasma_Oxidant"):
        violations.append("BS3 oxidant individual exists")
    if any(graph.triples((None, P("usesCoReactant"), None))):
        violations.append("usesCoReactant assertion exists for BS3")
    for class_local in (
        "Measurement_Result",
        "Specimen",
        "Measurand",
        "Characterization_Method",
    ):
        individuals = instances_of(graph, class_local)
        if individuals:
            violations.append(
                f"unsupported {class_local} individuals exist: "
                f"{sorted(map(local_name, individuals))}"
            )
    _raise_phase("input and population validation", violations)


def _validate_naming_and_declarations(graph: Graph) -> None:
    """Validate naming, explicit declarations, predicate kinds, and standard allowlist."""

    violations: list[str] = []
    declaration_types = {
        "class": OWL.Class,
        "object": OWL.ObjectProperty,
        "data": OWL.DatatypeProperty,
        "annotation": OWL.AnnotationProperty,
        "individual": OWL.NamedIndividual,
    }
    declarations: dict[str, set[URIRef]] = {}
    for kind, type_iri in declaration_types.items():
        declarations[kind] = {
            subject
            for subject in graph.subjects(RDF.type, type_iri)
            if isinstance(subject, URIRef) and str(subject).startswith(PROJECT_PREFIX)
        }
    for class_ in declarations["class"]:
        if not ENTITY_RE.fullmatch(local_name(class_)):
            violations.append(f"invalid class local name {local_name(class_)!r}")
    for individual in declarations["individual"]:
        if not ENTITY_RE.fullmatch(local_name(individual)):
            violations.append(f"invalid individual local name {local_name(individual)!r}")
    for kind in ("object", "data", "annotation"):
        for property_ in declarations[kind]:
            if not PROPERTY_RE.fullmatch(local_name(property_)) or "_" in local_name(property_):
                violations.append(f"invalid {kind} property local name {local_name(property_)!r}")

    all_project_declarations: dict[URIRef, list[str]] = defaultdict(list)
    for kind, terms in declarations.items():
        for term in terms:
            all_project_declarations[term].append(kind)
    for term, kinds in all_project_declarations.items():
        if len(kinds) > 1:
            violations.append(f"{local_name(term)} declared in multiple entity kinds: {kinds}")

    expected_properties = (
        {P(local) for local, _, _ in OBJECT_PROPERTY_SPECS}
        | {P(local) for local, _, _ in DATA_PROPERTY_SPECS}
        | {P(local) for local in PROJECT_ANNOTATION_PROPERTIES}
    )
    used_project_predicates = {
        predicate
        for _, predicate, _ in graph
        if isinstance(predicate, URIRef) and str(predicate).startswith(PROJECT_PREFIX)
    }
    if used_project_predicates - expected_properties:
        violations.append(
            "undeclared project predicates used: "
            + repr(sorted(map(local_name, used_project_predicates - expected_properties)))
        )
    for predicate in used_project_predicates:
        kinds = [
            kind
            for kind in ("object", "data", "annotation")
            if predicate in declarations[kind]
        ]
        if len(kinds) != 1:
            violations.append(f"predicate {local_name(predicate)} has property kinds {kinds}")

    standard_allowlist = {
        RDF.type,
        RDF.first,
        RDF.rest,
        RDFS.label,
        RDFS.comment,
        RDFS.subClassOf,
        RDFS.subPropertyOf,
        RDFS.domain,
        RDFS.range,
        SKOS.definition,
        SKOS.scopeNote,
        DCTERMS.title,
        DCTERMS.creator,
        DCTERMS.issued,
        DCTERMS.identifier,
        DCTERMS.source,
        DCTERMS.created,
        OWL.inverseOf,
        OWL.equivalentClass,
        OWL.oneOf,
        OWL.unionOf,
        OWL.members,
        OWL.distinctMembers,
        OWL.disjointWith,
        OWL.onProperty,
        OWL.someValuesFrom,
        OWL.qualifiedCardinality,
        OWL.onClass,
        OWL.annotatedSource,
        OWL.annotatedProperty,
        OWL.annotatedTarget,
    }
    used_standard = {
        predicate
        for _, predicate, _ in graph
        if isinstance(predicate, URIRef) and not str(predicate).startswith(PROJECT_PREFIX)
    }
    unexpected_standard = used_standard - standard_allowlist
    if unexpected_standard:
        violations.append(f"standard predicates outside allowlist: {sorted(map(str, unexpected_standard))}")

    for subject, class_ in graph.subject_objects(RDF.type):
        if isinstance(class_, URIRef) and str(class_).startswith(PROJECT_PREFIX):
            if class_ not in declarations["class"]:
                violations.append(f"undeclared project class in type assertion: {local_name(class_)}")
            if isinstance(subject, URIRef) and str(subject).startswith(PROJECT_PREFIX):
                if subject not in declarations["individual"]:
                    violations.append(
                        f"undeclared project individual in type assertion: {local_name(subject)}"
                    )

    actual_unit_iris = {
        individual
        for individual in instances_of(graph, "Unit")
    }
    expected_unit_iris = {E(local) for local in UNIT_IRI_NAMES.values()}
    if actual_unit_iris != expected_unit_iris:
        violations.append("unit individual IRIs differ from UNIT_IRI_NAMES")
    _raise_phase("naming and declaration validation", violations)


def _validate_provenance_and_quantities(graph: Graph, options: BuildOptions) -> None:
    """Validate exact provenance, value forms, units, variables, and typed literals."""

    violations: list[str] = []
    expected_provenance = _expected_provenance()
    actual_subjects = {
        local_name(subject)
        for subject in graph.subjects(P("assertedBy"), None)
        if isinstance(subject, URIRef)
    }
    if actual_subjects != set(expected_provenance):
        violations.append(
            f"assertedBy subject set mismatch; missing={sorted(set(expected_provenance)-actual_subjects)}, "
            f"extra={sorted(actual_subjects-set(expected_provenance))}"
        )
    for individual_local, claim_ids in sorted(expected_provenance.items()):
        actual = {
            local_name(claim)
            for claim in graph.objects(E(individual_local), P("assertedBy"))
            if isinstance(claim, URIRef)
        }
        expected = {claim_local(claim_id) for claim_id in claim_ids}
        if actual != expected:
            violations.append(
                f"{individual_local} assertedBy {sorted(actual)} does not equal {sorted(expected)}"
            )

    report_gap_locals = {spec.local_name for spec in REPORT_GAP_SPECS}
    for gap_local in report_gap_locals:
        if options.report_derived_gaps:
            gap = E(gap_local)
            if any(graph.objects(gap, P("assertedBy"))):
                violations.append(f"report-derived gap {gap_local} has assertedBy")
            if _single_values(graph, gap, P("documentedIn")) != {E("Report_Chapter_3")}:
                violations.append(f"report-derived gap {gap_local} lacks report provenance")

    scaffold_locals: set[str] = set()
    scaffold_locals.update(target_local(target) for target in TARGETS)
    scaffold_locals.update(field_local(field) for field in FIELDS)
    scaffold_locals.update(UNIT_IRI_NAMES.values())
    scaffold_locals.update(member for members in ENUMERATIONS.values() for member in members)
    scaffold_locals.update(spec.local_name for spec in VARIABLE_SPECS)
    scaffold_locals.update(
        entity_name("Coverage", "Assessment", target_suffix(row.target))
        for row in options.coverage_rows
    )
    if options.window_scaffold:
        scaffold_locals.update(spec.local_name for spec in WINDOW_SPECS)
    if options.report_derived_gaps:
        scaffold_locals.update(report_gap_locals)
    for scaffold_local in sorted(scaffold_locals):
        if not any(graph.objects(E(scaffold_local), P("documentedIn"))):
            violations.append(f"non-claim scaffold {scaffold_local} lacks documentedIn")

    quantities = instances_of(graph, "Quantity_Value")
    for quantity in sorted(quantities, key=local_name):
        q_local = local_name(quantity)
        claim_id = q_local.replace("Qty_", "").replace("_", "-")
        numeric = list(graph.objects(quantity, P("numericValue")))
        ratios = list(graph.objects(quantity, P("ratioExpression")))
        qualitative = list(graph.objects(quantity, P("qualitativeStatement")))
        forms = len(numeric) + len(ratios) + len(qualitative)
        if forms != 1:
            violations.append(f"{q_local} has {forms} value forms")
        direct_types = set(graph.objects(quantity, RDF.type))
        if E("Point_Value") in direct_types:
            if len(numeric) != 1 or ratios or qualitative:
                violations.append(f"{q_local} Point_Value form is invalid")
            if len(list(graph.objects(quantity, P("hasUnit")))) != 1:
                violations.append(f"{q_local} numeric quantity does not have exactly one unit")
        if E("Ratio_Value") in direct_types:
            if len(ratios) != 1 or numeric or qualitative:
                violations.append(f"{q_local} Ratio_Value form is invalid")
            if _single_values(graph, quantity, P("rawUnitText")) != {Literal("")}:
                violations.append(f"{q_local} ratio rawUnitText is not the empty string")
            if any(graph.objects(quantity, P("hasUnit"))):
                violations.append(f"{q_local} ratio unexpectedly has a unit")
        if len(list(graph.objects(quantity, P("concernsVariable")))) != 1:
            violations.append(f"{q_local} does not concern exactly one variable")
        observers = list(graph.subjects(P("hasObservedValue"), quantity))
        if len(observers) != 1:
            violations.append(f"{q_local} is observed by {len(observers)} route instances")
        if claim_id not in QUANTITY_CLAIM_IDS:
            violations.append(f"unexpected quantity identifier {q_local}")

    expected_parameter_edges = {
        (operation_local, quantity_local(claim_id))
        for claim_id, operation_local in QUANTITY_OPERATION_MAP.items()
    }
    actual_parameter_edges = {
        (local_name(operation), local_name(quantity))
        for operation, quantity in graph.subject_objects(P("hasProcessParameterValue"))
        if isinstance(operation, URIRef) and isinstance(quantity, URIRef)
    }
    if actual_parameter_edges != expected_parameter_edges:
        violations.append(
            "hasProcessParameterValue edges differ; "
            f"expected={sorted(expected_parameter_edges)}, "
            f"actual={sorted(actual_parameter_edges)}"
        )
    if any(graph.triples((None, P("hasQuantity"), None))):
        violations.append(
            "direct hasQuantity assertion exists; operation parameters must use "
            "hasProcessParameterValue"
        )

    for range_value in instances_of(graph, "Range_Value"):
        mins = list(graph.objects(range_value, P("minValue")))
        maxs = list(graph.objects(range_value, P("maxValue")))
        if not mins and not maxs:
            violations.append(f"{local_name(range_value)} Range_Value has no bound")
        if mins and maxs and Decimal(str(mins[0])) > Decimal(str(maxs[0])):
            violations.append(f"{local_name(range_value)} has minValue greater than maxValue")

    datatype_checks: dict[URIRef, tuple[re.Pattern[str], str]] = {
        XSD.decimal: (DECIMAL_RE, "decimal"),
        XSD.integer: (INTEGER_RE, "integer"),
        XSD.nonNegativeInteger: (NON_NEGATIVE_INTEGER_RE, "nonNegativeInteger"),
        XSD.positiveInteger: (POSITIVE_INTEGER_RE, "positiveInteger"),
        XSD.gYear: (re.compile(r"^-?\d{4,}$"), "gYear"),
    }
    for _, _, literal in graph:
        if not isinstance(literal, Literal) or literal.datatype is None:
            continue
        if literal.datatype in datatype_checks:
            pattern, label = datatype_checks[literal.datatype]
            if not pattern.fullmatch(str(literal)):
                violations.append(f"invalid xsd:{label} lexical form {str(literal)!r}")
        elif literal.datatype == XSD.boolean and str(literal) not in {"true", "false", "1", "0"}:
            violations.append(f"invalid xsd:boolean lexical form {str(literal)!r}")
        elif literal.datatype == XSD.date:
            try:
                date.fromisoformat(str(literal))
            except ValueError:
                violations.append(f"invalid xsd:date lexical form {str(literal)!r}")
        elif literal.datatype == XSD.dateTimeStamp:
            try:
                datetime.fromisoformat(str(literal).replace("Z", "+00:00"))
            except ValueError:
                violations.append(f"invalid xsd:dateTimeStamp lexical form {str(literal)!r}")
    _raise_phase("provenance and quantity validation", violations)


def _direct_edge_set(graph: Graph, predicate_local: str) -> set[tuple[str, str]]:
    """Return project-local pairs for one direct object-property predicate."""

    return {
        (local_name(subject), local_name(object_))
        for subject, object_ in graph.subject_objects(P(predicate_local))
        if isinstance(subject, URIRef) and isinstance(object_, URIRef)
    }


def _reachable(edges: set[tuple[str, str]], start: str, goal: str) -> bool:
    """Return whether a directed path exists in a finite local-name edge set."""

    adjacency: dict[str, set[str]] = defaultdict(set)
    for left, right in edges:
        adjacency[left].add(right)
    seen: set[str] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node == goal:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency[node] - seen)
    return False


def _validate_route_shape(graph: Graph) -> None:
    """Validate order, realization, scope, stack roles, and functional multiplicities."""

    violations: list[str] = []
    route_steps = {
        local_name(step)
        for step in graph.objects(E("Route_BS3_Tsai2022"), P("hasStep"))
        if isinstance(step, URIRef)
    }
    if route_steps != set(ROUTE_STEP_LOCALS):
        violations.append(f"route hasStep set is {sorted(route_steps)}")
    step_indices: dict[int, str] = {}
    for spec in BS3_ROUTE_SPEC:
        values = list(graph.objects(E(spec.step_local), P("stepIndex")))
        if len(values) != 1:
            violations.append(f"{spec.step_local} has {len(values)} stepIndex values")
        else:
            index = int(str(values[0]))
            if index in step_indices:
                violations.append(f"duplicate step index {index}")
            step_indices[index] = spec.step_local
        if _single_values(graph, E(spec.step_local), P("realizesOperation")) != {
            E(spec.operation_local)
        }:
            violations.append(f"{spec.step_local} realizes unexpected operation")
    if set(step_indices) != set(range(1, 7)):
        violations.append(f"step index set is {sorted(step_indices)}")

    expected_direct = {
        (left.step_local, right.step_local)
        for left, right in zip(BS3_ROUTE_SPEC[:-1], BS3_ROUTE_SPEC[1:], strict=True)
    }
    actual_direct = _direct_edge_set(graph, "directlyPrecedes")
    if actual_direct != expected_direct:
        violations.append(f"directlyPrecedes edge set is {sorted(actual_direct)}")
    incoming = Counter(right for _, right in actual_direct)
    outgoing = Counter(left for left, _ in actual_direct)
    if any(count > 1 for count in incoming.values()) or any(count > 1 for count in outgoing.values()):
        violations.append("directlyPrecedes has a branch")
    for left, right in actual_direct:
        if _reachable(actual_direct, right, left):
            violations.append(f"directlyPrecedes cycle includes {left} and {right}")
            break
    expected_necessary = {("Step_01_Bottom_Electrode", "Step_02_HZO_Deposition")}
    if _direct_edge_set(graph, "necessarilyPrecedes") != expected_necessary:
        violations.append("necessarilyPrecedes edge set differs from the exact contract")
    expected_scoped = {
        ("Step_02_HZO_Deposition", "Step_03_Top_Electrode"),
        ("Step_03_Top_Electrode", "Step_04_Photolithography"),
        ("Step_04_Photolithography", "Step_05_Wet_Etch"),
        ("Step_05_Wet_Etch", "Step_06_Crystallization_Anneal"),
    }
    if _direct_edge_set(graph, "routeScopedPrecedes") != expected_scoped:
        violations.append("routeScopedPrecedes edge set differs from the exact contract")

    suboperations = {
        local_name(operation)
        for operation in graph.objects(E("Op_02_ALD_Film_Formation"), P("hasSubOperation"))
        if isinstance(operation, URIRef)
    }
    expected_suboperations = {
        "Op_02a_Hf_Precursor_Dose",
        "Op_02b_Zr_Precursor_Dose",
        "Op_02c_Co_Reactant_Dose",
        "Op_02d_Cycle_Repetition",
    }
    if suboperations != expected_suboperations:
        violations.append(f"ALD suboperation set is {sorted(suboperations)}")
    if not _reachable(
        actual_direct, "Step_03_Top_Electrode", "Step_06_Crystallization_Anneal"
    ):
        violations.append("step 3 does not reach step 6 through directlyPrecedes")

    for spec in BS3_ROUTE_SPEC:
        expected_scope = {E(spec.module_scope)}
        for subject_local in (spec.step_local, spec.operation_local):
            if _single_values(graph, E(subject_local), P("hasModuleScope")) != expected_scope:
                violations.append(f"{subject_local} has incorrect module scope")

    stack = E("Stack_BS3_TiN_HZO_TiN")
    expected_roles = {
        "hasBottomElectrode": E("Layer_BS3_Bottom_TiN"),
        "hasFerroelectricLayer": E("Layer_BS3_HZO"),
        "hasTopElectrode": E("Layer_BS3_Top_TiN"),
    }
    for predicate_local, expected_layer in expected_roles.items():
        if _single_values(graph, stack, P(predicate_local)) != {expected_layer}:
            violations.append(f"stack {predicate_local} role is incorrect")
    layer_materials = {
        "Layer_BS3_Bottom_TiN": "TiN",
        "Layer_BS3_HZO": "HZO_Hf05Zr05O2",
        "Layer_BS3_Top_TiN": "TiN",
    }
    for layer_local, material_local in layer_materials.items():
        if _single_values(graph, E(layer_local), P("madeOfChemical")) != {E(material_local)}:
            violations.append(f"{layer_local} material is incorrect")

    functional_properties = (
        [P(local) for local in FUNCTIONAL_OBJECT_PROPERTIES]
        + [P(local) for local in FUNCTIONAL_DATA_PROPERTIES]
    )
    for predicate in functional_properties:
        subjects = set(graph.subjects(predicate, None))
        for subject in subjects:
            values = set(graph.objects(subject, predicate))
            if len(values) > 1:
                violations.append(
                    f"functional property {local_name(predicate)} has {len(values)} values on {subject}"
                )
    _raise_phase("route and graph-shape validation", violations)


def _disjoint_pairs(graph: Graph) -> set[frozenset[URIRef]]:
    """Expand pairwise and AllDisjointClasses axioms to unordered named-class pairs."""

    pairs: set[frozenset[URIRef]] = set()
    for left, right in graph.subject_objects(OWL.disjointWith):
        if isinstance(left, URIRef) and isinstance(right, URIRef):
            pairs.add(frozenset((left, right)))
    for node in graph.subjects(RDF.type, OWL.AllDisjointClasses):
        member_heads = list(graph.objects(node, OWL.members))
        if len(member_heads) != 1 or not isinstance(member_heads[0], (URIRef, BNode)):
            continue
        try:
            members = [
                member
                for member in rdf_list_values(graph, member_heads[0])
                if isinstance(member, URIRef)
            ]
        except ValidationError:
            continue
        for index, left in enumerate(members):
            for right in members[index + 1 :]:
                pairs.add(frozenset((left, right)))
    return pairs


def _has_some_values_restriction(
    graph: Graph,
    class_local: str,
    property_local: str,
    target_class_local: str,
) -> bool:
    """Return whether a named class has the requested existential restriction."""

    return any(
        (restriction, RDF.type, OWL.Restriction) in graph
        and (restriction, OWL.onProperty, P(property_local)) in graph
        and (restriction, OWL.someValuesFrom, E(target_class_local)) in graph
        for restriction in graph.objects(E(class_local), RDFS.subClassOf)
    )


def _has_qualified_cardinality_restriction(
    graph: Graph,
    class_local: str,
    property_local: str,
    cardinality: int,
    target_class_local: str,
) -> bool:
    """Return whether a named class has the requested exact qualified cardinality."""

    cardinality_literal = Literal(cardinality, datatype=XSD.nonNegativeInteger)
    return any(
        (restriction, RDF.type, OWL.Restriction) in graph
        and (restriction, OWL.onProperty, P(property_local)) in graph
        and (restriction, OWL.qualifiedCardinality, cardinality_literal) in graph
        and (restriction, OWL.onClass, E(target_class_local)) in graph
        for restriction in graph.objects(E(class_local), RDFS.subClassOf)
    )


def _validate_owl_structure(graph: Graph) -> None:
    """Run supplementary OWL 2 DL structural and disjointness checks."""

    violations: list[str] = []
    for child_local, parent_local in OBJECT_SUBPROPERTIES:
        if (P(child_local), RDFS.subPropertyOf, P(parent_local)) not in graph:
            violations.append(
                f"missing object subproperty axiom {child_local} subPropertyOf {parent_local}"
            )
    for (
        class_local,
        property_local,
        target_class_local,
        _,
    ) in SCHEMA_SOME_RESTRICTIONS:
        if not _has_some_values_restriction(
            graph,
            class_local,
            property_local,
            target_class_local,
        ):
            violations.append(
                f"missing existential restriction {class_local} {property_local} some "
                f"{target_class_local}"
            )
    for (
        class_local,
        property_local,
        cardinality,
        target_class_local,
        _,
    ) in MEASUREMENT_CARDINALITY_RESTRICTIONS:
        if not _has_qualified_cardinality_restriction(
            graph,
            class_local,
            property_local,
            cardinality,
            target_class_local,
        ):
            violations.append(
                f"missing cardinality restriction {class_local} {property_local} exactly "
                f"{cardinality} {target_class_local}"
            )
    scaffold_note = Literal(MEASUREMENT_TBOX_SCAFFOLD_NOTE, lang="en")
    for class_local in MEASUREMENT_TBOX_SCAFFOLD_CLASSES:
        if (E(class_local), RDFS.comment, scaffold_note) not in graph:
            violations.append(f"{class_local} lacks the BS3 TBox-scaffold annotation")
    closure = subclass_ancestors(graph)
    disjoint = _disjoint_pairs(graph)
    for pair in disjoint:
        if len(pair) != 2:
            violations.append(f"degenerate disjointness pair: {pair}")
            continue
        left, right = tuple(pair)
        if right in closure.get(left, set()) or left in closure.get(right, set()):
            violations.append(
                f"class is both subclass-related and disjoint: {local_name(left)}, {local_name(right)}"
            )

    for individual in named_individuals(graph):
        direct_types = {
            type_
            for type_ in graph.objects(individual, RDF.type)
            if isinstance(type_, URIRef)
            and type_ != OWL.NamedIndividual
            and str(type_).startswith(PROJECT_PREFIX)
        }
        entailed_types = set(direct_types)
        for type_ in direct_types:
            entailed_types.update(closure.get(type_, set()))
        for pair in disjoint:
            if pair.issubset(entailed_types):
                violations.append(
                    f"{local_name(individual)} is typed into disjoint classes "
                    f"{sorted(local_name(class_) for class_ in pair)}"
                )

    list_predicates = (OWL.oneOf, OWL.unionOf, OWL.members, OWL.distinctMembers)
    for predicate in list_predicates:
        for subject, head in graph.subject_objects(predicate):
            if not isinstance(head, (URIRef, BNode)):
                violations.append(f"{predicate} list head on {subject} is not a resource")
                continue
            try:
                rdf_list_values(graph, head)
            except ValidationError as exc:
                violations.append(f"{predicate} list on {subject}: {exc}")

    expected_enum_sets = {
        enum_class: {E(member) for member in members}
        for enum_class, members in ENUMERATIONS.items()
    }
    for enum_class, expected_members in expected_enum_sets.items():
        equivalent_nodes = list(graph.objects(E(enum_class), OWL.equivalentClass))
        one_of_sets: list[set[URIRef | BNode | Literal]] = []
        for node in equivalent_nodes:
            for head in graph.objects(node, OWL.oneOf):
                if isinstance(head, (URIRef, BNode)):
                    try:
                        one_of_sets.append(set(rdf_list_values(graph, head)))
                    except ValidationError:
                        pass
        if one_of_sets != [expected_members]:
            violations.append(f"{enum_class} oneOf members are not exact")

    union_nodes = list(graph.objects(E("Process_Variable"), OWL.equivalentClass))
    expected_union = {
        E("First_Order_Variable"),
        E("Second_Order_Variable"),
        E("Unclassified_Variable"),
    }
    union_sets: list[set[URIRef | BNode | Literal]] = []
    for node in union_nodes:
        for head in graph.objects(node, OWL.unionOf):
            if isinstance(head, (URIRef, BNode)):
                try:
                    union_sets.append(set(rdf_list_values(graph, head)))
                except ValidationError:
                    pass
    if union_sets != [expected_union]:
        violations.append("Process_Variable covering union is not exact")

    expected_all_different = [
        {E(member) for member in members} for members in ENUMERATIONS.values()
    ] + [
        {E(member) for member in ROUTE_STEP_LOCALS},
        {E(member) for member in OPERATION_LOCALS},
        {E(member) for member in STACK_LAYER_LOCALS},
    ]
    actual_all_different: list[set[URIRef | BNode | Literal]] = []
    for node in graph.subjects(RDF.type, OWL.AllDifferent):
        heads = list(graph.objects(node, OWL.distinctMembers))
        if len(heads) == 1 and isinstance(heads[0], (URIRef, BNode)):
            try:
                actual_all_different.append(set(rdf_list_values(graph, heads[0])))
            except ValidationError:
                pass
    if Counter(frozenset(group) for group in actual_all_different) != Counter(
        frozenset(group) for group in expected_all_different
    ):
        violations.append("owl:AllDifferent groups do not match the exact expected groups")

    if len(instances_of(graph, "Target_Category")) != 23:
        violations.append("target individual count is not 23")
    if len(instances_of(graph, "Quantity_Kind")) != 31:
        violations.append("quantity-kind individual count is not 31")
    if len(instances_of(graph, "Unit")) != 52:
        violations.append("unit individual count is not 52")

    data_properties = {
        subject
        for subject in graph.subjects(RDF.type, OWL.DatatypeProperty)
        if isinstance(subject, URIRef)
    }
    annotation_properties = {
        subject
        for subject in graph.subjects(RDF.type, OWL.AnnotationProperty)
        if isinstance(subject, URIRef)
    }
    object_properties = {
        subject
        for subject in graph.subjects(RDF.type, OWL.ObjectProperty)
        if isinstance(subject, URIRef)
    }
    inverse_functional = {
        subject
        for subject in graph.subjects(RDF.type, OWL.InverseFunctionalProperty)
        if isinstance(subject, URIRef)
    }
    if data_properties & inverse_functional:
        violations.append(
            f"datatype properties declared inverse-functional: {sorted(map(str, data_properties & inverse_functional))}"
        )
    if annotation_properties & (data_properties | object_properties):
        violations.append("annotation property is also declared as data or object property")

    transitive_properties = {
        subject
        for subject in graph.subjects(RDF.type, OWL.TransitiveProperty)
        if isinstance(subject, URIRef)
    }
    chain_superproperties = {
        subject
        for subject in graph.subjects(OWL.propertyChainAxiom, None)
        if isinstance(subject, URIRef)
    }
    non_simple = transitive_properties | chain_superproperties
    prohibited_characteristics = {
        OWL.FunctionalProperty,
        OWL.InverseFunctionalProperty,
        OWL.AsymmetricProperty,
        OWL.IrreflexiveProperty,
    }
    for property_ in non_simple:
        for characteristic in prohibited_characteristics:
            if (property_, RDF.type, characteristic) in graph:
                violations.append(
                    f"non-simple property {local_name(property_)} has prohibited characteristic {characteristic}"
                )
    for restriction in graph.subjects(RDF.type, OWL.Restriction):
        properties = set(graph.objects(restriction, OWL.onProperty))
        if properties & non_simple:
            has_cardinality_or_self = any(
                (restriction, predicate, None) in graph
                for predicate in (
                    OWL.cardinality,
                    OWL.minCardinality,
                    OWL.maxCardinality,
                    OWL.qualifiedCardinality,
                    OWL.minQualifiedCardinality,
                    OWL.maxQualifiedCardinality,
                    OWL.hasSelf,
                )
            )
            if has_cardinality_or_self:
                violations.append(f"restriction uses non-simple property on {restriction}")
    for _, head in graph.subject_objects(OWL.propertyChainAxiom):
        if isinstance(head, (URIRef, BNode)):
            try:
                members = set(rdf_list_values(graph, head))
            except ValidationError:
                continue
            if members & data_properties:
                violations.append("object-property chain contains a data property")
    _raise_phase("OWL structural validation", violations)


def _comparison_edges(graph: Graph, instance: URIRef) -> set[tuple[str, str]]:
    """Return all direct comparison-relation/window pairs for one route instance."""

    result: set[tuple[str, str]] = set()
    for relation_local in (
        "comparedWithWindow",
        "insideWindow",
        "atWindowEdge",
        "extendsWindow",
        "beyondWindow",
        "exactIndependentMatch",
    ):
        for window in graph.objects(instance, P(relation_local)):
            if isinstance(window, URIRef):
                result.add((relation_local, local_name(window)))
    return result


def _validate_coverage_and_windows(graph: Graph, options: BuildOptions) -> None:
    """Validate reconciled coverage, window assessments, and scaffold boundaries."""

    violations: list[str] = []
    assessments = instances_of(graph, "Coverage_Assessment")
    by_target: dict[str, URIRef] = {}
    for assessment in assessments:
        targets = list(graph.objects(assessment, P("assessesTarget")))
        if len(targets) != 1 or not isinstance(targets[0], URIRef):
            violations.append(f"{local_name(assessment)} does not assess exactly one target")
            continue
        by_target[local_name(targets[0])] = assessment
        if any(graph.objects(assessment, P("assertedBy"))):
            violations.append(f"coverage assessment {local_name(assessment)} has assertedBy")
    if len(assessments) != 23 or len(by_target) != 23:
        violations.append(
            f"coverage assessment cardinality is assessments={len(assessments)}, targets={len(by_target)}"
        )
    for row in options.coverage_rows:
        target_name = target_local(row.target)
        assessment = by_target.get(target_name)
        if assessment is None:
            violations.append(f"missing coverage assessment for {row.target}")
            continue
        expected_values = (
            (P("coverageRowCount"), {Literal(row.row_count, datatype=XSD.nonNegativeInteger)}),
            (
                P("coverageSourceCount"),
                {Literal(row.distinct_source_count, datatype=XSD.nonNegativeInteger)},
            ),
            (P("hasCoverageGrade"), {E(coverage_grade_local(row.coverage))}),
        )
        for predicate, expected in expected_values:
            if _single_values(graph, assessment, predicate) != expected:
                violations.append(
                    f"coverage assessment for {row.target} has incorrect {local_name(predicate)}"
                )
    actual_thin_bare: dict[str, tuple[int, int, str]] = {}
    for row in options.coverage_rows:
        if row.coverage in {"thin", "bare"}:
            actual_thin_bare[row.target] = (
                row.row_count,
                row.distinct_source_count,
                row.coverage,
            )
    if actual_thin_bare != THIN_BARE_EXPECTED:
        violations.append(f"thin/bare coverage set differs: {actual_thin_bare!r}")

    windows = instances_of(graph, "Literature_Window")
    if options.window_scaffold:
        if {local_name(window) for window in windows} != {
            spec.local_name for spec in WINDOW_SPECS
        }:
            violations.append("window scaffold set is not exact")
        for instance_local, assessment_local, relation_local, window_local in WINDOW_ASSESSMENTS:
            instance = E(instance_local)
            if _single_values(graph, instance, P("hasWindowAssessment")) != {
                E(assessment_local)
            }:
                violations.append(f"{instance_local} has incorrect window assessment status")
            actual_edges = _comparison_edges(graph, instance)
            expected_edges = (
                {(relation_local, window_local)}
                if relation_local is not None and window_local is not None
                else set()
            )
            if actual_edges != expected_edges:
                violations.append(
                    f"{instance_local} comparison edges {actual_edges} do not equal {expected_edges}"
                )
    else:
        if windows:
            violations.append("windows exist while scaffolding is disabled")
        for instance_local in ROUTE_INSTANCE_IDS:
            instance = E(instance_local)
            if _single_values(graph, instance, P("hasWindowAssessment")) != {
                E("Window_Assessment_Not_Assessed")
            }:
                violations.append(f"{instance_local} is not marked Not_Assessed")
            if _comparison_edges(graph, instance):
                violations.append(f"{instance_local} has a comparison while scaffold is disabled")

    for window in windows:
        if any(graph.objects(window, P("minValue"))) or any(
            graph.objects(window, P("maxValue"))
        ):
            violations.append(f"{local_name(window)} has a numeric bound")
        if any(graph.objects(window, P("contributingSourceCount"))):
            violations.append(f"{local_name(window)} has contributingSourceCount")
        if any(
            isinstance(value, URIRef) and value in instances_of(graph, "Range_Value")
            for _, _, value in graph.triples((window, None, None))
        ):
            violations.append(f"{local_name(window)} links to a Range_Value")
    if _single_values(graph, E("Instance_BS3_013"), P("transferBlockedBy")) != {
        Literal(TRANSFER_BLOCK_TEXT)
    }:
        violations.append("Instance_BS3_013 transfer blocker is not exact")
    for left, right in graph.subject_objects(OWL.sameAs):
        if isinstance(left, URIRef) and isinstance(right, URIRef):
            if "BS3" in local_name(left) or "BS3" in local_name(right):
                violations.append(f"forbidden BS3 owl:sameAs: {left} {right}")
    _raise_phase("coverage and window validation", violations)


def validate(
    graph: Graph,
    rows: Sequence[ClaimRow],
    route_spec: Sequence[StepSpec],
    build_options: BuildOptions,
) -> None:
    """Run all structural validation phases, collecting violations within each phase."""

    validate_route_spec(rows, route_spec)
    if build_options.strict:
        strict_violations: list[str] = []
        handlers = _quantity_handler_map(route_spec)
        for row in sorted(
            (item for item in rows if item.source_id == "BS3"),
            key=lambda item: item.claim_id,
        ):
            if row.value != row.value.strip() or row.unit != row.unit.strip():
                strict_violations.append(
                    f"{row.claim_id} has leading or trailing whitespace in parsed value/unit text"
                )
            _, handler = handlers[row.claim_id]
            if row.claim_id in RATIO_CLAIM_IDS:
                parsed: Decimal | str = parse_ratio(row.value, handler.ratio_prefix)
            elif row.claim_id in QUANTITY_CLAIM_IDS:
                parsed = parse_numeric(row.value, handler.parse_prefix)
            else:
                continue
            if parsed != EXPECTED_PARSED_VALUES[row.claim_id]:
                strict_violations.append(
                    f"{row.claim_id} strict extraction result is {parsed!r}"
                )
        _raise_phase("strict handler parsing validation", strict_violations)
    _validate_population(graph, rows, build_options)
    _validate_naming_and_declarations(graph)
    _validate_provenance_and_quantities(graph, build_options)
    _validate_route_shape(graph)
    _validate_owl_structure(graph)
    _validate_coverage_and_windows(graph, build_options)
    LOGGER.info("Structural validation passed")


SPARQL_PREFIXES = f"""
PREFIX ald: <{PROJECT_PREFIX}>
PREFIX owl: <{OWL}>
PREFIX rdf: <{RDF}>
PREFIX rdfs: <{RDFS}>
PREFIX xsd: <{XSD}>
"""


def make_competency_questions(
    rows: Sequence[ClaimRow], options: BuildOptions
) -> Sequence[CompetencyQuestion]:
    """Create all fourteen competency questions with exact current-build contracts."""

    expected_steps = tuple(
        (
            str(spec.index),
            spec.step_local,
            spec.module_scope,
        )
        for spec in BS3_ROUTE_SPEC
    )
    expected_suboperations = tuple((local,) for local in sorted(
        (
            "Op_02a_Hf_Precursor_Dose",
            "Op_02b_Zr_Precursor_Dose",
            "Op_02c_Co_Reactant_Dose",
            "Op_02d_Cycle_Repetition",
        )
    ))
    expected_bottom_quantities = tuple(sorted(
        (
            ("Qty_BS3_002", "15.0", "Unit_nm"),
            ("Qty_BS3_003", "100.0", "Unit_W"),
            ("Qty_BS3_004", "50.0", "Unit_sccm"),
            ("Qty_BS3_005", "3.0", "Unit_sccm"),
            ("Qty_BS3_006", "2.5", "Unit_mTorr"),
        )
    ))
    expected_window_rows: Sequence[Sequence[str]]
    if options.window_scaffold:
        expected_window_rows = tuple(sorted(
            (
                (
                    "Instance_BS3_006",
                    "extendsWindow",
                    "Window_Sputter_Pressure_Envelope",
                    "",
                ),
                (
                    "Instance_BS3_013",
                    "beyondWindow",
                    "Window_Precursor_Source_Temperature",
                    TRANSFER_BLOCK_TEXT,
                ),
            )
        ))
    else:
        expected_window_rows = ()
    expected_gap_rows = [
        ("Gap_BS3_015", "ledger"),
        ("Gap_BS3_019", "ledger"),
    ]
    if options.report_derived_gaps:
        expected_gap_rows.extend((spec.local_name, "report") for spec in REPORT_GAP_SPECS)
    expected_ordering = tuple(sorted(
        (
            ("Step_01_Bottom_Electrode", "Step_02_HZO_Deposition", "necessary"),
            ("Step_02_HZO_Deposition", "Step_03_Top_Electrode", "routeScoped"),
            ("Step_03_Top_Electrode", "Step_04_Photolithography", "routeScoped"),
            ("Step_04_Photolithography", "Step_05_Wet_Etch", "routeScoped"),
            ("Step_05_Wet_Etch", "Step_06_Crystallization_Anneal", "routeScoped"),
        )
    ))
    expected_second_hand = tuple((f"Claim_BS3_{index:03d}",) for index in range(1, 26))
    coverage_by_target = {row.target: row for row in options.coverage_rows}
    expected_coverage = tuple(sorted(
        (
            target_local(target),
            str(coverage_by_target[target].distinct_source_count),
            coverage_grade_local(coverage_by_target[target].coverage),
        )
        for target in THIN_BARE_EXPECTED
    ))
    expected_conditions = tuple(sorted(
        (claim_local(row.claim_id), row.condition)
        for row in rows
        if row.source_id == "BS3"
    ))
    expected_chemicals = tuple(sorted(
        (
            ("Layer_BS3_Bottom_TiN", "bottomMaterial", "TiN"),
            ("Layer_BS3_Top_TiN", "topMaterial", "TiN"),
            ("Layer_BS3_HZO", "filmMaterial", "HZO_Hf05Zr05O2"),
            ("Op_02a_Hf_Precursor_Dose", "hfPrecursor", "TEMAH"),
            ("Op_02b_Zr_Precursor_Dose", "zrPrecursor", "TEMAZ"),
            ("Op_01_Bottom_Electrode_Formation", "sputterGas", "Ar"),
            ("Op_01_Bottom_Electrode_Formation", "sputterGas", "N2"),
            ("Op_06_Crystallization_Anneal", "annealAmbient", "N2"),
            ("Op_05_Wet_Etch", "etchant", "NH4OH_H2O2_H2O_Etchant"),
        )
    ))
    expected_parameter_bindings = tuple(
        sorted(
            (operation_local, quantity_local(claim_id))
            for claim_id, operation_local in QUANTITY_OPERATION_MAP.items()
        )
    )
    return (
        CompetencyQuestion(
            1,
            "Which six BS3 route steps occur in order, and which are in or out of module scope?",
            SPARQL_PREFIXES
            + """
SELECT ?index ?step ?scope WHERE {
  ald:Route_BS3_Tsai2022 ald:hasStep ?step .
  ?step ald:stepIndex ?index ; ald:hasModuleScope ?scope .
}
ORDER BY ?index
""",
            expected_steps,
        ),
        CompetencyQuestion(
            2,
            "Into which exact four suboperations is the BS3 ALD film-formation operation decomposed?",
            SPARQL_PREFIXES
            + """
SELECT ?operation WHERE {
  ald:Op_02_ALD_Film_Formation ald:hasSubOperation ?operation .
}
ORDER BY ?operation
""",
            expected_suboperations,
        ),
        CompetencyQuestion(
            3,
            "What are the exact bottom-electrode quantitative settings and their units?",
            SPARQL_PREFIXES
            + """
SELECT ?quantity ?value ?unit WHERE {
  ald:Op_01_Bottom_Electrode_Formation ald:hasProcessParameterValue ?quantity .
  ?quantity ald:numericValue ?value ; ald:hasUnit ?unit .
}
ORDER BY ?quantity
""",
            expected_bottom_quantities,
        ),
        CompetencyQuestion(
            4,
            "Which BS3 instances extend or exceed a scaffold window, and what transfer blocker is recorded?",
            SPARQL_PREFIXES
            + """
SELECT ?instance ?relation ?window ?blocker WHERE {
  {
    ?instance ald:extendsWindow ?window .
    BIND("extendsWindow" AS ?relation)
  }
  UNION
  {
    ?instance ald:beyondWindow ?window .
    BIND("beyondWindow" AS ?relation)
  }
  OPTIONAL { ?instance ald:transferBlockedBy ?blocker . }
}
ORDER BY ?instance
""",
            expected_window_rows,
        ),
        CompetencyQuestion(
            5,
            "Which BS3 quantities concern first-order variables?",
            SPARQL_PREFIXES
            + """
SELECT ?quantity ?variable WHERE {
  ?quantity rdf:type ald:Quantity_Value ; ald:concernsVariable ?variable .
  ?variable rdf:type ald:First_Order_Variable .
}
ORDER BY ?quantity
""",
            (
                ("Qty_BS3_009", "Variable_Deposition_Temperature"),
                ("Qty_BS3_023", "Variable_Anneal_Temperature"),
            ),
        ),
        CompetencyQuestion(
            6,
            "Which evidence gaps are ledger-backed and which are report-derived?",
            SPARQL_PREFIXES
            + """
SELECT ?gap ?kind WHERE {
  ?gap rdf:type ald:Evidence_Gap .
  OPTIONAL { ?gap ald:assertedBy ?claim . }
  BIND(IF(BOUND(?claim), "ledger", "report") AS ?kind)
}
ORDER BY ?gap
""",
            tuple(sorted(expected_gap_rows)),
        ),
        CompetencyQuestion(
            7,
            "Is the crystallization anneal post-metallization and reachable from the top-electrode step?",
            SPARQL_PREFIXES
            + """
ASK {
  ald:Op_06_Crystallization_Anneal rdf:type ald:Post_Metallization_Anneal .
  ald:Step_03_Top_Electrode ald:directlyPrecedes+ ald:Step_06_Crystallization_Anneal .
}
""",
            (("true",),),
        ),
        CompetencyQuestion(
            8,
            "What exact evidence-qualified and route-scoped ordering assertions are present?",
            SPARQL_PREFIXES
            + """
SELECT ?left ?right ?kind WHERE {
  {
    ?left ald:necessarilyPrecedes ?right .
    BIND("necessary" AS ?kind)
  }
  UNION
  {
    ?left ald:routeScopedPrecedes ?right .
    BIND("routeScoped" AS ?kind)
  }
}
ORDER BY ?left ?right ?kind
""",
            expected_ordering,
        ),
        CompetencyQuestion(
            9,
            "Which claims are explicitly marked as second-hand BS3 transcriptions?",
            SPARQL_PREFIXES
            + """
SELECT ?claim WHERE {
  ?claim rdf:type ald:Claim ; ald:secondHandTranscription true .
}
ORDER BY ?claim
""",
            expected_second_hand,
        ),
        CompetencyQuestion(
            10,
            "Which targets have thin or bare coverage, with what distinct-source counts?",
            SPARQL_PREFIXES
            + """
SELECT ?target ?sourceCount ?grade WHERE {
  ?assessment rdf:type ald:Coverage_Assessment ;
      ald:assessesTarget ?target ;
      ald:coverageSourceCount ?sourceCount ;
      ald:hasCoverageGrade ?grade .
  VALUES ?grade { ald:Coverage_Thin ald:Coverage_Bare }
}
ORDER BY ?target
""",
            expected_coverage,
        ),
        CompetencyQuestion(
            11,
            "What nonempty scoping condition is preserved for each of the 25 BS3 claims?",
            SPARQL_PREFIXES
            + """
SELECT ?claim ?condition WHERE {
  ?claim rdf:type ald:Claim ; ald:conditionText ?condition .
  FILTER(STRLEN(STR(?condition)) > 0)
}
ORDER BY ?claim
""",
            expected_conditions,
        ),
        CompetencyQuestion(
            12,
            "What exact chemical-role bindings are asserted for the BS3 route?",
            SPARQL_PREFIXES
            + """
SELECT ?subject ?role ?chemical WHERE {
  { ald:Layer_BS3_Bottom_TiN ald:madeOfChemical ?chemical .
    BIND(ald:Layer_BS3_Bottom_TiN AS ?subject) BIND("bottomMaterial" AS ?role) }
  UNION
  { ald:Layer_BS3_Top_TiN ald:madeOfChemical ?chemical .
    BIND(ald:Layer_BS3_Top_TiN AS ?subject) BIND("topMaterial" AS ?role) }
  UNION
  { ald:Layer_BS3_HZO ald:madeOfChemical ?chemical .
    BIND(ald:Layer_BS3_HZO AS ?subject) BIND("filmMaterial" AS ?role) }
  UNION
  { ald:Op_02a_Hf_Precursor_Dose ald:usesPrecursor ?chemical .
    BIND(ald:Op_02a_Hf_Precursor_Dose AS ?subject) BIND("hfPrecursor" AS ?role) }
  UNION
  { ald:Op_02b_Zr_Precursor_Dose ald:usesPrecursor ?chemical .
    BIND(ald:Op_02b_Zr_Precursor_Dose AS ?subject) BIND("zrPrecursor" AS ?role) }
  UNION
  { ald:Op_01_Bottom_Electrode_Formation ald:usesSputterGas ?chemical .
    BIND(ald:Op_01_Bottom_Electrode_Formation AS ?subject) BIND("sputterGas" AS ?role) }
  UNION
  { ald:Op_06_Crystallization_Anneal ald:usesAnnealAmbient ?chemical .
    BIND(ald:Op_06_Crystallization_Anneal AS ?subject) BIND("annealAmbient" AS ?role) }
  UNION
  { ald:Op_05_Wet_Etch ald:usesEtchant ?chemical .
    BIND(ald:Op_05_Wet_Etch AS ?subject) BIND("etchant" AS ?role) }
}
ORDER BY ?subject ?role ?chemical
""",
            expected_chemicals,
        ),
        CompetencyQuestion(
            13,
            "Which exact BS3 quantity values parameterize each process operation?",
            SPARQL_PREFIXES
            + """
SELECT ?operation ?quantity WHERE {
  ?operation ald:hasProcessParameterValue ?quantity .
}
ORDER BY ?operation ?quantity
""",
            expected_parameter_bindings,
        ),
        CompetencyQuestion(
            14,
            "Is the future measurement schema connected while its BS3 ABox remains unpopulated?",
            SPARQL_PREFIXES
            + """
ASK {
  ald:hasResultValue a owl:ObjectProperty ;
      rdfs:domain ald:Measurement_Result ;
      rdfs:range ald:Quantity_Value .
  ald:representsStack a owl:ObjectProperty ;
      rdfs:domain ald:Specimen ;
      rdfs:range ald:Device_Stack .
  ald:correspondsToProcessVariable a owl:ObjectProperty ;
      rdfs:domain ald:Measurand ;
      rdfs:range ald:Process_Variable .
  ald:Measurement_Result rdfs:subClassOf [
      a owl:Restriction ;
      owl:onProperty ald:hasMeasurand ;
      owl:qualifiedCardinality "1"^^xsd:nonNegativeInteger ;
      owl:onClass ald:Measurand
  ] .
  ald:Measurement_Result rdfs:subClassOf [
      a owl:Restriction ;
      owl:onProperty ald:hasResultValue ;
      owl:qualifiedCardinality "1"^^xsd:nonNegativeInteger ;
      owl:onClass ald:Quantity_Value
  ] .
  ald:Measurement_Result rdfs:subClassOf [
      a owl:Restriction ;
      owl:onProperty ald:measuredOn ;
      owl:qualifiedCardinality "1"^^xsd:nonNegativeInteger ;
      owl:onClass ald:Specimen
  ] .
  ald:Measurement_Result rdfs:subClassOf [
      a owl:Restriction ;
      owl:onProperty ald:measuredBy ;
      owl:someValuesFrom ald:Characterization_Method
  ] .
  ald:Measurement_Result rdfs:subClassOf [
      a owl:Restriction ;
      owl:onProperty ald:assertedBy ;
      owl:someValuesFrom ald:Claim
  ] .
  ald:Measurement_Result rdfs:comment ?scaffoldNote .
  FILTER(CONTAINS(STR(?scaffoldNote), "TBox-only scaffolding"))
  FILTER NOT EXISTS { ?result rdf:type ald:Measurement_Result . }
  FILTER NOT EXISTS {
    ?method rdf:type owl:NamedIndividual, ?methodClass .
    ?methodClass rdfs:subClassOf* ald:Electrical_Test_Method .
  }
}
""",
            (("true",),),
        ),
    )


def _normalize_query_term(term: object) -> str:
    """Normalize a SPARQL result term for exact, readable comparison."""

    if term is None:
        return ""
    if isinstance(term, URIRef):
        return local_name(term)
    if isinstance(term, Literal):
        return str(term)
    return str(term)


def run_competency_questions(
    graph: Graph, questions: Sequence[CompetencyQuestion]
) -> str:
    """Run every competency question, print exact rows, and fail on any mismatch."""

    failures: list[str] = []
    for question in questions:
        result = graph.query(question.sparql)
        if getattr(result, "type", None) == "ASK":
            actual_rows = (("true" if bool(result) else "false",),)
        else:
            actual_rows = tuple(
                sorted(
                    tuple(_normalize_query_term(term) for term in result_row)
                    for result_row in result
                )
            )
        expected_rows = tuple(sorted(question.expected_rows))
        passed = actual_rows == expected_rows
        print(f"CQ{question.number}: {question.question}")
        if actual_rows:
            for row in actual_rows:
                print("  " + " | ".join(row))
        else:
            print("  (no rows)")
        print(f"  {'PASS' if passed else 'FAIL'}")
        if not passed:
            failures.append(
                f"CQ{question.number} result {actual_rows!r} does not equal {expected_rows!r}"
            )
    _raise_phase("competency-question validation", failures)
    return "PASSED"


def serialize_canonical_turtle(graph: Graph) -> bytes:
    """Serialize canonical LongTurtle, normalize newlines, and verify round-trip isomorphism."""

    serialized = graph.serialize(
        format="longturtle",
        canon=True,
        encoding="utf-8",
    )
    data = serialized.encode("utf-8") if isinstance(serialized, str) else bytes(serialized)
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    reparsed = Graph()
    reparsed.parse(data=data.decode("utf-8"), format="turtle")
    violations: list[str] = []
    if len(reparsed) != len(graph):
        violations.append(f"round-trip triple count {len(reparsed)} does not equal {len(graph)}")
    if not isomorphic(graph, reparsed):
        violations.append("round-trip graph is not isomorphic to the original")
    _raise_phase("serialization round-trip validation", violations)
    return data


def _without_generation_timestamp(graph: Graph) -> Graph:
    """Copy a graph while removing only the permitted generation timestamp triple."""

    stripped = Graph()
    for triple in graph:
        if triple[1] != P("generationTimestamp"):
            stripped.add(triple)
    return stripped


def verify_release_determinism(
    graph: Graph,
    first_bytes: bytes,
    rows: Sequence[ClaimRow],
    options: BuildOptions,
) -> None:
    """Require byte stability and prove that an alternate run changes only its timestamp."""

    second = build_graph(rows, options)
    validate(second, rows, BS3_ROUTE_SPEC, options)
    second_bytes = serialize_canonical_turtle(second)
    violations: list[str] = []
    if first_bytes != second_bytes:
        violations.append("two builds with the same generation timestamp are not byte-identical")
    if not isomorphic(graph, second):
        violations.append("two builds with the same generation timestamp are not isomorphic")

    alternate_options = replace(
        options,
        generation_timestamp=options.generation_timestamp + timedelta(seconds=1),
    )
    alternate = build_graph(rows, alternate_options)
    validate(alternate, rows, BS3_ROUTE_SPEC, alternate_options)
    if not isomorphic(
        _without_generation_timestamp(graph),
        _without_generation_timestamp(alternate),
    ):
        violations.append("graphs differ after removing only generationTimestamp triples")
    differing_iris = {
        term
        for candidate_graph in (graph, alternate)
        for triple in candidate_graph
        for term in triple
        if isinstance(term, URIRef)
        and (
            options.generation_timestamp.isoformat() in str(term)
            or alternate_options.generation_timestamp.isoformat() in str(term)
        )
    }
    if differing_iris:
        violations.append(f"generation timestamp appears in IRI(s): {sorted(map(str, differing_iris))}")
    _raise_phase("release deterministic-output validation", violations)


def graph_counts(graph: Graph) -> BuildCounts:
    """Compute the exact success-summary counts from explicit declarations and closure."""

    project_uris = lambda type_iri: {
        subject
        for subject in graph.subjects(RDF.type, type_iri)
        if isinstance(subject, URIRef) and str(subject).startswith(PROJECT_PREFIX)
    }
    return BuildCounts(
        triples=len(graph),
        classes=len(project_uris(OWL.Class)),
        object_properties=len(project_uris(OWL.ObjectProperty)),
        data_properties=len(project_uris(OWL.DatatypeProperty)),
        annotation_properties=len(project_uris(OWL.AnnotationProperty)),
        named_individuals=len(project_uris(OWL.NamedIndividual)),
        claims=len(instances_of(graph, "Claim")),
        quantities=len(instances_of(graph, "Quantity_Value")),
        route_instances=len(instances_of(graph, "Route_Instance")),
        evidence_gaps=len(instances_of(graph, "Evidence_Gap")),
        windows=len(instances_of(graph, "Literature_Window")),
        coverage_assessments=len(instances_of(graph, "Coverage_Assessment")),
    )


def _verification_report_text(
    ledger_sha256: str,
    turtle_sha256: str,
    counts: BuildCounts,
    cq_status: str,
    verification_status: str,
    profile_command: Sequence[str] | None,
    profile_result: subprocess.CompletedProcess[str] | None,
    profile_file_text: str,
    reason_command: Sequence[str] | None,
    reason_result: subprocess.CompletedProcess[str] | None,
    unsatisfiable_classes: Sequence[str],
) -> str:
    """Render the permanent UTF-8 structural and release-verification report."""

    lines = [
        "ALD HfO2 ontology validation report",
        "",
        f"Input ledger SHA-256: {ledger_sha256}",
        f"Generated Turtle SHA-256: {turtle_sha256}",
        f"Python version: {sys.version.split()[0]}",
        f"RDFLib version: {rdflib.__version__}",
        f"pandas version: {pd.__version__}",
        f"openpyxl version: {openpyxl.__version__}",
        f"Structural validation: PASSED ({counts.triples} triples)",
        f"Competency tests: {cq_status}",
        f"OWL 2 DL profile and HermiT verification: {verification_status}",
        "",
    ]
    if profile_command is None or reason_command is None:
        lines.extend(
            [
                "OWL 2 DL profile command: NOT RUN",
                "OWL 2 DL profile exit status: NOT RUN",
                "HermiT command: NOT RUN",
                "HermiT exit status: NOT RUN",
                "External OWL 2 DL conformance and consistency were not verified.",
            ]
        )
    else:
        lines.extend(
            [
                f"OWL 2 DL profile command: {subprocess.list2cmdline(list(profile_command))}",
                f"OWL 2 DL profile exit status: {profile_result.returncode if profile_result else 'NOT RUN'}",
                "OWL 2 DL profile stdout:",
                profile_result.stdout.strip() if profile_result else "",
                "OWL 2 DL profile stderr:",
                profile_result.stderr.strip() if profile_result else "",
                "OWL 2 DL profile output file:",
                profile_file_text.strip(),
                "",
                f"HermiT command: {subprocess.list2cmdline(list(reason_command))}",
                f"HermiT exit status: {reason_result.returncode if reason_result else 'NOT RUN'}",
                "HermiT stdout:",
                reason_result.stdout.strip() if reason_result else "",
                "HermiT stderr:",
                reason_result.stderr.strip() if reason_result else "",
            ]
        )
        if verification_status == "PASSED" and not unsatisfiable_classes:
            lines.append("Zero inconsistency/unsatisfiable-class failures were reported.")
        else:
            lines.append(
                "Unsatisfiable or inconsistency findings: "
                + (", ".join(unsatisfiable_classes) if unsatisfiable_classes else "not cleared")
            )
    return "\n".join(lines).rstrip() + "\n"


def run_external_verification(
    robot: str | None,
    turtle_path: Path,
    verification_report: Path,
    ledger_sha256: str,
    turtle_sha256: str,
    counts: BuildCounts,
    cq_status: str,
) -> str:
    """Optionally run ROBOT profile validation and HermiT, always writing a report."""

    verification_report.parent.mkdir(parents=True, exist_ok=True)
    if robot is None:
        text = _verification_report_text(
            ledger_sha256,
            turtle_sha256,
            counts,
            cq_status,
            "NOT RUN",
            None,
            None,
            "",
            None,
            None,
            (),
        )
        verification_report.write_text(text, encoding="utf-8", newline="\n")
        return "NOT RUN"

    robot_path = Path(robot)
    executable = str(robot_path) if robot_path.is_file() else shutil.which(robot)
    if executable is None:
        text = _verification_report_text(
            ledger_sha256,
            turtle_sha256,
            counts,
            cq_status,
            "FAILED",
            (robot, "validate-profile"),
            None,
            "ROBOT executable was not found.",
            (robot, "reason"),
            None,
            (),
        )
        verification_report.write_text(text, encoding="utf-8", newline="\n")
        raise ValidationError(f"ROBOT executable was not found: {robot}")

    with tempfile.TemporaryDirectory(prefix="ald_hfo2_robot_") as temporary:
        temporary_path = Path(temporary)
        temporary_turtle = temporary_path / "ald_hfo2.ttl"
        profile_output = temporary_path / "owl2dl-profile.txt"
        reasoned_output = temporary_path / "reasoned.owl"
        shutil.copyfile(turtle_path, temporary_turtle)
        profile_command = (
            executable,
            "validate-profile",
            "--profile",
            "DL",
            "--input",
            str(temporary_turtle),
            "--output",
            str(profile_output),
        )
        reason_command = (
            executable,
            "reason",
            "--reasoner",
            "hermit",
            "--input",
            str(temporary_turtle),
            "--output",
            str(reasoned_output),
        )
        profile_result = subprocess.run(
            list(profile_command),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        reason_result = subprocess.run(
            list(reason_command),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        profile_file_text = (
            profile_output.read_text(encoding="utf-8", errors="replace")
            if profile_output.is_file()
            else ""
        )
        unsatisfiable_classes: list[str] = []
        reason_parse_error = ""
        if reason_result.returncode == 0 and reasoned_output.is_file():
            try:
                reasoned_graph = Graph()
                reasoned_graph.parse(reasoned_output)
                for class_ in set(reasoned_graph.subjects(RDFS.subClassOf, OWL.Nothing)) | set(
                    reasoned_graph.subjects(OWL.equivalentClass, OWL.Nothing)
                ):
                    if isinstance(class_, URIRef) and class_ != OWL.Nothing:
                        unsatisfiable_classes.append(str(class_))
            except Exception as exc:
                reason_parse_error = f"Could not inspect reasoned ontology: {exc}"
        status = (
            "PASSED"
            if profile_result.returncode == 0
            and reason_result.returncode == 0
            and reasoned_output.is_file()
            and not unsatisfiable_classes
            and not reason_parse_error
            else "FAILED"
        )
        if reason_parse_error:
            unsatisfiable_classes.append(reason_parse_error)
        report_text = _verification_report_text(
            ledger_sha256,
            turtle_sha256,
            counts,
            cq_status,
            status,
            profile_command,
            profile_result,
            profile_file_text,
            reason_command,
            reason_result,
            tuple(sorted(unsatisfiable_classes)),
        )
        verification_report.write_text(report_text, encoding="utf-8", newline="\n")
        if status != "PASSED":
            raise ValidationError(
                "External OWL 2 DL profile or HermiT verification failed; see verification report"
            )
        return status


def print_summary(
    counts: BuildCounts,
    coverage_rows: Sequence[CoverageRow],
    ledger_sha256: str,
    turtle_sha256: str,
    cq_status: str,
    verification_status: str,
) -> None:
    """Print the required success summary to stdout."""

    print(f"Triple count: {counts.triples}")
    print(f"Class count: {counts.classes}")
    print(f"Object-property count: {counts.object_properties}")
    print(f"Data-property count: {counts.data_properties}")
    print(f"Annotation-property count: {counts.annotation_properties}")
    print(f"Named-individual count: {counts.named_individuals}")
    print(f"Claim count: {counts.claims}")
    print(f"Quantity count: {counts.quantities}")
    print(f"Route-instance count: {counts.route_instances}")
    print(f"Evidence-gap count: {counts.evidence_gaps}")
    print(f"Window count: {counts.windows}")
    print(f"Coverage-assessment count: {counts.coverage_assessments}")
    print("Per-target coverage:")
    for row in sorted(coverage_rows, key=lambda item: item.target):
        print(
            f"  {row.target}: rows={row.row_count}, "
            f"distinct_sources={row.distinct_source_count}, grade={row.coverage}"
        )
    print(f"Ledger SHA-256: {ledger_sha256}")
    print(f"Turtle SHA-256: {turtle_sha256}")
    print(f"Competency tests: {cq_status}")
    print(f"OWL 2 DL profile and HermiT verification: {verification_status}")


def _version_tuple(version: str) -> Sequence[int]:
    """Extract a comparable leading numeric version tuple."""

    match = re.match(r"^(\d+(?:\.\d+)*)", version)
    if match is None:
        raise ValidationError(f"Cannot parse library version {version!r}")
    return tuple(int(part) for part in match.group(1).split("."))


def check_runtime_versions() -> None:
    """Require the declared Python and library minimum versions."""

    violations: list[str] = []
    if sys.version_info < (3, 11):
        violations.append(f"Python {sys.version.split()[0]} is older than 3.11")
    requirements = (
        ("RDFLib", rdflib.__version__, (7, 2)),
        ("pandas", pd.__version__, (2, 0)),
        ("openpyxl", openpyxl.__version__, (3, 1)),
    )
    for name, installed, minimum in requirements:
        parsed = _version_tuple(installed)
        padded = parsed + (0,) * max(0, len(minimum) - len(parsed))
        if padded[: len(minimum)] < minimum:
            violations.append(
                f"{name} {installed} is older than {'.'.join(map(str, minimum))}"
            )
    _raise_phase("runtime version validation", violations)


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the fixed-BS3 command-line interface and reject release contradictions."""

    parser = argparse.ArgumentParser(
        description="Build and structurally validate the fixed-BS3 ALD HfO2 ontology."
    )
    parser.add_argument("--ledger", required=True, type=Path, help="Path to claim_ledger.xlsx")
    parser.add_argument("--sheet", required=True, help="Must be 'Corrected Ledger'")
    parser.add_argument("--out", required=True, type=Path, help="Output canonical Turtle path")
    parser.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format")
    parser.add_argument(
        "--window-scaffold",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Create non-numeric literature-window scaffolds (default: enabled)",
    )
    parser.add_argument(
        "--report-derived-gaps",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Create report-derived evidence gaps (default: enabled)",
    )
    parser.add_argument("--run-cq", action="store_true", help="Run all competency questions")
    parser.add_argument("--strict", action="store_true", help="Enable strict parsing checks")
    parser.add_argument("--robot", help="Path or command name for the ROBOT executable")
    parser.add_argument("--release", action="store_true", help="Run full release verification")
    parser.add_argument(
        "--verification-report",
        type=Path,
        help="Permanent verification report path; defaults beside --out",
    )
    args = parser.parse_args(argv)
    try:
        args.report_date_value = date.fromisoformat(args.report_date)
    except ValueError as exc:
        parser.error(f"--report-date must be YYYY-MM-DD: {exc}")
    if args.sheet != LEDGER_SHEET:
        parser.error(f"--sheet must be exactly {LEDGER_SHEET!r}")
    if args.release:
        contradictions: list[str] = []
        if not args.window_scaffold:
            contradictions.append("--no-window-scaffold")
        if not args.report_derived_gaps:
            contradictions.append("--no-report-derived-gaps")
        if args.robot is None:
            contradictions.append("missing --robot PATH")
        if contradictions:
            parser.error("--release contradicts or lacks: " + ", ".join(contradictions))
        args.strict = True
        args.run_cq = True
    if args.verification_report is None:
        args.verification_report = args.out.with_suffix(".validation.txt")
    resolved_ledger = args.ledger.resolve()
    resolved_out = args.out.resolve()
    resolved_report = args.verification_report.resolve()
    if resolved_out == resolved_ledger:
        parser.error("--out must not overwrite the input ledger")
    if resolved_report in {resolved_ledger, resolved_out}:
        parser.error("--verification-report must differ from the ledger and Turtle paths")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    """Load, build, validate, serialize, optionally verify externally, and summarize."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    args = parse_arguments(argv)
    try:
        check_runtime_versions()
        ledger_path = args.ledger.resolve()
        output_path = args.out.resolve()
        report_path = args.verification_report.resolve()
        LOGGER.info("Loading ledger contract from %s", ledger_path)
        rows = load_ledger(ledger_path, args.sheet)
        coverage_rows = load_and_reconcile_coverage(ledger_path, rows)
        ledger_sha256 = sha256_file(ledger_path)
        generation_timestamp = datetime.now(timezone.utc).replace(microsecond=0)
        options = BuildOptions(
            report_date=args.report_date_value,
            generation_timestamp=generation_timestamp,
            ledger_path=ledger_path,
            ledger_sha256=ledger_sha256,
            sheet_name=args.sheet,
            window_scaffold=bool(args.window_scaffold),
            report_derived_gaps=bool(args.report_derived_gaps),
            strict=bool(args.strict),
            release=bool(args.release),
            coverage_rows=coverage_rows,
        )
        LOGGER.info("Constructing schema and fixed BS3 build population")
        graph = build_graph(rows, options)
        validate(graph, rows, BS3_ROUTE_SPEC, options)

        cq_status = "NOT RUN"
        if args.run_cq:
            questions = make_competency_questions(rows, options)
            cq_status = run_competency_questions(graph, questions)

        turtle_bytes = serialize_canonical_turtle(graph)
        if args.release:
            verify_release_determinism(graph, turtle_bytes, rows, options)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(turtle_bytes)
        turtle_sha256 = hashlib.sha256(turtle_bytes).hexdigest()
        counts = graph_counts(graph)
        verification_status = run_external_verification(
            args.robot,
            output_path,
            report_path,
            ledger_sha256,
            turtle_sha256,
            counts,
            cq_status,
        )
        print_summary(
            counts,
            coverage_rows,
            ledger_sha256,
            turtle_sha256,
            cq_status,
            verification_status,
        )
        return 0
    except ValidationError as exc:
        LOGGER.error("Build failed: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
