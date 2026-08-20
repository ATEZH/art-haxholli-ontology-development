# ALD HfO2 Ontology Record

## Scope

This ontology represents the evidence-backed BS3 ALD HfO2/HZO fabrication route described by 25 claims in `claim_ledger.xlsx`. It connects claims to a six-step process route, operations, quantities, units, process variables, chemicals, layers, a TiN/HZO/TiN device stack, provenance, coverage assessments, evidence gaps, and literature-window scaffolds.

All 754 corrected-ledger rows are used for input validation and coverage reconciliation, but only `BS3-001` through `BS3-025` populate claim and route-derived individuals. Measurement and electrical-test branches are retained as unpopulated TBox scaffolding for future evidence.

## Ontology IRI

```text
https://github.com/OPXHS/Ontologies-Development/ontology/ald-hfo2
```

Entity namespace:

```text
https://github.com/OPXHS/Ontologies-Development/ontology/ald-hfo2#
```

## Imports

None. The ontology contains no `owl:imports` axioms.

It references RDF, RDFS, OWL, XSD, SKOS, Dublin Core Terms, the project/report repository, and a publication DOI, but these references are not ontology imports.

## Reasoner

HermiT, executed through ROBOT during a release build:

```text
robot reason --reasoner hermit
```

ROBOT also performs OWL 2 DL profile validation before reasoning.

## Latest validation result

The supplied final release validation report records a successful build.

| Check | Result |
|---|---|
| Python structural validation | PASSED — 3,661 triples |
| Competency questions | PASSED |
| ROBOT OWL 2 DL profile | PASSED |
| HermiT consistency reasoning | PASSED |
| Inconsistency or unsatisfiable-class failures | None reported |

Validated artifact identifiers:

```text
Input ledger SHA-256:
39ad61b87617e697074eabede0e7b6aab10851d70baa75c9dfb5c20bd9917fbb

Generated Turtle SHA-256:
8db6607e851b2e8b2ee8721e0a24176ec44e7fba08ea31fa191306dbcd5ffc58
```

Validation environment: Python 3.12.6, RDFLib 7.6.0, pandas 3.0.1, and openpyxl 3.1.5.

## Known limitations

- The populated ABox is intentionally limited to the 25 BS3 claims; non-BS3 claims are not instantiated.
- BS3 is taken from Berinë Rahimi's week 4 dataset.
- Literature windows are non-numeric comparison scaffolds derived from non-BS3 evidence; they contain no asserted numeric bounds or contributing-source counts.
- Measurement results, specimens, measurands, and electrical-test methods have connected schema definitions but no BS3 individuals because the ledger provides no measurement-result evidence.
- Under OWL's open-world semantics, unreported information remains unknown; an evidence gap does not assert physical absence.
- The represented route is one literature-route instantiation, not a recommendation, production recipe, reference flow, or transferable production window.
