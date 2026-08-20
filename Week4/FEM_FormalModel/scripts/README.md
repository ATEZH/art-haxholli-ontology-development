# Generator

Builds `Ferroelectric_HfO2.ttl` from the specification data.

    python3 generate.py ../Ferroelectric_HfO2.ttl
    python3 verify.py ../Ferroelectric_HfO2.ttl

Requires `rdflib`; `verify.py` additionally uses `owlready2` and a JRE for HermiT, and
skips the reasoner check cleanly if either is missing.

| File | Contains |
|---|---|
| `vocab.py` | class tree and vocabulary individuals, from OntologySpec §2 |
| `properties.py` | object, data and annotation properties, from §3 and §4 |
| `flows.py` | the eight flows, stacks, slots, specimens and measurements |
| `generate.py` | assembles the graph in migration-plan order |
| `verify.py` | reasoner plus the stage-8 checks |
| `DECISIONS.md` | what formalisation forced that the spec left open |

Edit the data files, not the Turtle. Re-run and re-verify.
