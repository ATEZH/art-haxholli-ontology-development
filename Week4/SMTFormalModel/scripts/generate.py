"""
Builds the ferroelectric HfO2 memory ontology as OWL/Turtle from the specification data
in vocab.py, properties.py and flows.py.

Run:  python3 generate.py [output.ttl]

The build order mirrors the migration plan: annotation properties, then classes, then
vocabulary individuals, then properties, then flows, then axioms.
"""

import sys
from rdflib import Graph, Namespace, Literal, URIRef, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD

import vocab
import properties as props
import flows as fl

BASE = "http://www.semanticweb.org/art/ontologies/2026/8/ferroelectric-hfo2"
NS = Namespace(BASE + "#")

XSD_MAP = {
    "double": XSD.double, "int": XSD.int, "long": XSD.long,
    "string": XSD.string, "boolean": XSD.boolean,
}

CHARACTERISTIC_MAP = {
    "transitive": OWL.TransitiveProperty,
    "symmetric": OWL.SymmetricProperty,
    "asymmetric": OWL.AsymmetricProperty,
    "reflexive": OWL.ReflexiveProperty,
    "irreflexive": OWL.IrreflexiveProperty,
    "functional": OWL.FunctionalProperty,
    "inverse_functional": OWL.InverseFunctionalProperty,
}


def build():
    g = Graph()
    g.bind("", NS)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)

    onto = URIRef(BASE)
    g.add((onto, RDF.type, OWL.Ontology))
    g.add((onto, OWL.versionIRI, URIRef(BASE + "/v3")))
    g.add((onto, RDFS.comment, Literal(
        "Ferroelectric HfO2 memory ontology, generated from OntologySpec v3 and "
        "InstanceFlows. Every class, property and individual that makes a claim about the "
        "world carries a sourceLocator naming the source and section it came from. "
        "Entities without one carry epistemicStatus 'scaffolding' or 'inferred' and are "
        "modelling structure, not findings. Grounded in ten sources read in full or "
        "near-full; nothing derives from a search snippet or an abstract.")))

    # -- Stage 1: annotation properties ------------------------------------
    for name, comment in props.ANNOTATION_PROPERTIES:
        u = NS[name]
        g.add((u, RDF.type, OWL.AnnotationProperty))
        g.add((u, RDFS.comment, Literal(comment)))

    def annotate(subject, source, status, comment=None, scope=None):
        if source:
            for part in [s.strip() for s in source.split(";")]:
                g.add((subject, NS.sourceLocator, Literal(part)))
        if status:
            g.add((subject, NS.epistemicStatus, Literal(status)))
        if comment:
            g.add((subject, RDFS.comment, Literal(comment)))
        if scope:
            g.add((subject, NS.scopeNote, Literal(scope)))

    # -- Stage 2: classes ---------------------------------------------------
    declared = set()
    for name, parent, source, status, comment in vocab.CLASSES:
        u = NS[name]
        g.add((u, RDF.type, OWL.Class))
        g.add((u, RDFS.label, Literal(name.replace("_", " "))))
        if parent:
            g.add((u, RDFS.subClassOf, NS[parent]))
        scope = None
        if name == "Ferroelectric_Material":
            scope = ("HfO2-family only. Perovskite, multiferroic and hydrogen-bond "
                     "ferroelectrics are excluded by design, not absent for lack of "
                     "evidence. The class keeps its general name so scope can widen "
                     "later without a rename.")
        annotate(u, source, status, comment, scope)
        declared.add(name)

    # -- Stage 3: vocabulary individuals ------------------------------------
    for name, cls, source, comment in vocab.INDIVIDUALS:
        u = NS[name]
        g.add((u, RDF.type, OWL.NamedIndividual))
        g.add((u, RDF.type, NS[cls]))
        g.add((u, RDFS.label, Literal(name)))
        annotate(u, source, "verified" if source else "scaffolding", comment)

    # Layer_Role is a closed vocabulary: one of the few places closing the world is
    # correct, because the role set is a modelling decision rather than a claim.
    roles = [NS[r] for r in vocab.LAYER_ROLES]
    coll = BNode()
    g.add((NS.Layer_Role, OWL.equivalentClass, coll))
    g.add((coll, RDF.type, OWL.Class))
    _add_list(g, coll, OWL.oneOf, roles)

    # -- Stage 4: object properties ----------------------------------------
    for name, dom, rng, chars, source, status, comment in props.OBJECT_PROPERTIES:
        u = NS[name]
        g.add((u, RDF.type, OWL.ObjectProperty))
        g.add((u, RDFS.label, Literal(name)))
        _set_domain_range(g, u, RDFS.domain, dom)
        _set_domain_range(g, u, RDFS.range, rng)
        for c in chars:
            g.add((u, RDF.type, CHARACTERISTIC_MAP[c]))
        annotate(u, source, status, comment)

    g.add((NS.hasTopElectrode, RDFS.subPropertyOf, NS.hasElectrode))
    g.add((NS.hasBottomElectrode, RDFS.subPropertyOf, NS.hasElectrode))
    g.add((NS.directlyPrecedes, RDFS.subPropertyOf, NS.precedes))

    # -- Stage 5: data properties -------------------------------------------
    for name, dom, xtype, source, status, comment, oneof in props.DATA_PROPERTIES:
        u = NS[name]
        g.add((u, RDF.type, OWL.DatatypeProperty))
        g.add((u, RDFS.label, Literal(name)))
        _set_domain_range(g, u, RDFS.domain, dom)
        if oneof:
            dr = BNode()
            g.add((u, RDFS.range, dr))
            g.add((dr, RDF.type, RDFS.Datatype))
            g.add((dr, OWL.onDatatype, XSD_MAP[xtype]))
            lits = [Literal(v, datatype=XSD_MAP[xtype]) for v in oneof]
            _add_list(g, dr, OWL.oneOf, lits)
        else:
            g.add((u, RDFS.range, XSD_MAP[xtype]))
        annotate(u, source, status, comment)

    # -- Stage 6: flows ------------------------------------------------------
    for fid, ind, stack, node, source, comment in fl.FLOWS:
        u = NS[ind]
        g.add((u, RDF.type, OWL.NamedIndividual))
        g.add((u, RDF.type, NS.Process_Flow))
        g.add((u, RDFS.label, Literal(ind)))
        if stack:
            g.add((u, NS.flowProducesArchitecture, NS[stack]))
        if node:
            g.add((u, NS.flowTargetsNode, NS[node]))
        annotate(u, source, "verified", comment)

    flow_ind = {fid: ind for fid, ind, _, _, _, _ in fl.FLOWS}
    by_flow = {}
    for fid, idx, name, cls, source, dprops, oprops in fl.STEPS:
        u = NS[name]
        g.add((u, RDF.type, OWL.NamedIndividual))
        g.add((u, RDF.type, NS[cls]))
        g.add((u, RDFS.label, Literal(name)))
        g.add((u, NS.belongsToFlow, NS[flow_ind[fid]]))
        g.add((u, NS.hasStepIndex, Literal(idx, datatype=XSD.int)))
        for k, v in dprops.items():
            g.add((u, NS[k], _lit(k, v)))
        for k, vals in oprops.items():
            for v in vals:
                g.add((u, NS[k], NS[v]))
        annotate(u, source, "verified")
        by_flow.setdefault(fid, []).append((idx, name))

    # Ordering. directlyPrecedes between consecutive steps; precedes is asserted only
    # within a flow, which is what keeps Flow C from contradicting the rest.
    for fid, steps in by_flow.items():
        steps.sort()
        for i in range(len(steps) - 1):
            g.add((NS[steps[i][1]], NS.directlyPrecedes, NS[steps[i + 1][1]]))
        for i in range(len(steps)):
            for j in range(i + 1, len(steps)):
                g.add((NS[steps[i][1]], NS.precedes, NS[steps[j][1]]))

    # A6 keeps both locators and is marked contradicted by its own source.
    g.add((NS.A6_Patterned_Metal_Deposition, NS.contradictedBy, Literal("S1")))
    g.add((NS.A6_Patterned_Metal_Deposition, RDFS.comment, Literal(
        "S1's body text says step 5 is metal electrode deposition; the Figure 3 caption "
        "says step 5 is electrode patterning. Both locators are kept and neither is "
        "picked as the true version.")))
    g.add((NS.A3_FE_Deposition, RDFS.comment, Literal(
        "Typed at the parent class Deposition and at no subclass. S1 says the "
        "ferroelectric can be deposited by ALD, sputter, PLD or CSD and does not choose. "
        "Typing it as ALD would assert something S1 never said.")))
    g.add((NS.A5_Crystallisation_Anneal, RDFS.comment, Literal(
        "No temperature or duration value. S1's body gives 400-1000 C and 1-60 s while "
        "its tables give 1 s to 20 min. Empty because the source is inconsistent, not "
        "because the answer is zero.")))

    # Stacks and slots
    for stack, cls, source, slots in fl.STACKS:
        su = NS[stack]
        g.add((su, RDF.type, OWL.NamedIndividual))
        g.add((su, RDF.type, NS[cls]))
        g.add((su, RDFS.label, Literal(stack)))
        annotate(su, source, "verified")
        for idx, mat, role, thick in slots:
            slot = NS["Slot_%s_%d" % (stack.replace("Stack_", ""), idx)]
            g.add((slot, RDF.type, OWL.NamedIndividual))
            g.add((slot, RDF.type, NS.Layer_Slot))
            g.add((su, NS.hasSlot, slot))
            g.add((slot, NS.layerIndex, Literal(idx, datatype=XSD.int)))
            g.add((slot, NS.slotMaterial, NS[mat]))
            g.add((slot, NS.slotRole, NS[role]))
            if thick is not None:
                g.add((slot, NS.hasSlotThickness_nm, Literal(thick, datatype=XSD.double)))
            annotate(slot, source, "verified")
            # Derived electrode shortcuts, generated rather than hand-asserted.
            if role == "bottom_electrode":
                g.add((su, NS.hasBottomElectrode, NS[mat]))
            elif role == "top_electrode":
                g.add((su, NS.hasTopElectrode, NS[mat]))
            elif role == "ferroelectric_layer":
                g.add((su, NS.hasFerroelectricLayer, NS[mat]))
            elif role == "interfacial_layer":
                g.add((su, NS.hasInterfacialLayer, NS[mat]))

    for name, cls, stack, source, dprops, oprops in fl.DEVICES:
        u = NS[name]
        g.add((u, RDF.type, OWL.NamedIndividual))
        g.add((u, RDF.type, NS[cls]))
        g.add((u, NS.usesStack, NS[stack]))
        for k, v in dprops.items():
            g.add((u, NS[k], _lit(k, v)))
        for k, vals in oprops.items():
            for v in vals:
                g.add((u, NS[k], NS[v]))
        annotate(u, source, "verified")

    for name, cls, source, dprops, comment in fl.ARTIFACTS:
        u = NS[name]
        g.add((u, RDF.type, OWL.NamedIndividual))
        g.add((u, RDF.type, NS[cls]))
        for k, v in dprops.items():
            g.add((u, NS[k], _lit(k, v)))
        annotate(u, source, "verified", comment)

    for name, method, prop, artifact, source, dprops, comment in fl.MEASUREMENTS:
        u = NS[name]
        g.add((u, RDF.type, OWL.NamedIndividual))
        g.add((u, RDF.type, NS.Measurement))
        g.add((u, NS.measurementMethod, NS[method]))
        g.add((u, NS.measuresProperty, NS[prop]))
        g.add((u, NS.measuredOn, NS[artifact]))
        g.add((NS[artifact], NS.hasMeasurement, u))
        for k, v in dprops.items():
            g.add((u, NS[k], _lit(k, v)))
        annotate(u, source, "verified", comment)

    for step, ms in fl.PRODUCES:
        for m in ms:
            g.add((NS[step], NS.producesMeasurement, NS[m]))

    for subj, prop, obj, source, status in fl.CAUSAL:
        g.add((NS[subj], NS[prop], NS[obj]))

    for ind, facts, source in fl.PHASE_FACTS + fl.MATERIAL_FACTS:
        for k, v in facts.items():
            g.add((NS[ind], NS[k], _lit(k, v)))

    for entity, uref in fl.UNCERTAINTY_REFS:
        g.add((NS[entity], NS.uncertaintyRef, Literal(uref)))

    # -- Stage 7: disjointness ----------------------------------------------
    disjoint_top = ["Material", "Dopant", "Phase_State", "Defect", "Layer_Stack",
                    "Layer_Slot", "Layer_Role", "Memory_Cell_Architecture",
                    "Array_Architecture", "Process_Flow", "Unit_Process", "Equipment",
                    "Capability", "Measurement_Method", "Measurement",
                    "Measured_Property", "Artifact", "Technology_Node",
                    "Degradation_Phenomenon"]
    _all_disjoint(g, [NS[c] for c in disjoint_top])
    _all_disjoint(g, [NS[c] for c in ["Blanket_Film", "Patterned_Capacitor",
                                      "Single_Cell", "Array_Specimen"]])
    _all_disjoint(g, [NS[c] for c in ["Film_Level_Degradation",
                                      "Array_Level_Degradation"]])

    # Deliberately NOT disjoint, recorded so the absence is a decision and not an
    # oversight: Substrate / Channel_Material (Si is both, in different slots);
    # the subclasses of Degradation_Phenomenon (a real film shows several at once);
    # Ferroelectric_Material / Dielectric_Layer_Material (HfO2 is both, by phase).
    for a, b, why in [
        ("Substrate", "Channel_Material",
         "Not disjoint: Si_substrate occupies a substrate slot in Flow A and a channel "
         "slot in Flow B1. The distinction is a role and lives on Layer_Slot."),
        ("Ferroelectric_Material", "Dielectric_Layer_Material",
         "Not disjoint: HfO2 is dielectric in one stack position and ferroelectric in "
         "another depending on phase."),
    ]:
        g.add((NS[a], NS.scopeNote, Literal(why)))

    # -- Stage 7: restrictions, sparingly ------------------------------------
    _some_values(g, NS.Unit_Process, NS.belongsToFlow, NS.Process_Flow)
    _some_values(g, NS.Measurement, NS.measuredOn, NS.Artifact)
    _exact_one(g, NS.Layer_Slot, NS.slotMaterial, NS.Material)
    _exact_one(g, NS.Layer_Slot, NS.slotRole, NS.Layer_Role)

    return g


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _lit(prop_name, value):
    for n, _, xtype, _, _, _, _ in props.DATA_PROPERTIES:
        if n == prop_name:
            return Literal(value, datatype=XSD_MAP[xtype])
    return Literal(value)


def _add_list(g, subject, predicate, items):
    head = BNode()
    g.add((subject, predicate, head))
    cur = head
    for i, item in enumerate(items):
        g.add((cur, RDF.first, item))
        if i == len(items) - 1:
            g.add((cur, RDF.rest, RDF.nil))
        else:
            nxt = BNode()
            g.add((cur, RDF.rest, nxt))
            cur = nxt


def _set_domain_range(g, prop, predicate, spec):
    if spec is None:
        return
    if isinstance(spec, str):
        g.add((prop, predicate, NS[spec]))
        return
    union = BNode()
    g.add((prop, predicate, union))
    g.add((union, RDF.type, OWL.Class))
    _add_list(g, union, OWL.unionOf, [NS[c] for c in spec])


def _all_disjoint(g, members):
    node = BNode()
    g.add((node, RDF.type, OWL.AllDisjointClasses))
    _add_list(g, node, OWL.members, members)


def _some_values(g, cls, prop, filler):
    r = BNode()
    g.add((r, RDF.type, OWL.Restriction))
    g.add((r, OWL.onProperty, prop))
    g.add((r, OWL.someValuesFrom, filler))
    g.add((cls, RDFS.subClassOf, r))


def _exact_one(g, cls, prop, filler):
    r = BNode()
    g.add((r, RDF.type, OWL.Restriction))
    g.add((r, OWL.onProperty, prop))
    g.add((r, OWL.qualifiedCardinality,
           Literal(1, datatype=XSD.nonNegativeInteger)))
    g.add((r, OWL.onClass, filler))
    g.add((cls, RDFS.subClassOf, r))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "Ferroelectric_HfO2.ttl"
    graph = build()
    graph.serialize(destination=out, format="turtle")
    print("wrote %s: %d triples" % (out, len(graph)))
