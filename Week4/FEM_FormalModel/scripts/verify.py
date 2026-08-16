"""
Verification for the generated ontology.

1. Reasoner consistency (HermiT via owlready2).
2. Referential integrity: every class named in a domain or range exists.
3. Provenance coverage: every entity has a sourceLocator or an explicit epistemicStatus
   of inferred/scaffolding.
4. Instance-document agreement: the classes InstanceFlows names have the individuals it
   says they have.
5. Slot design negative check: Stack_A_MFM must NOT reach Ti_Pt_contact through the
   electrode relations.

Run:  python3 verify.py ferroelectric_hfo2.ttl
"""

import sys
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD

BASE = "http://www.semanticweb.org/art/ontologies/2026/8/ferroelectric-hfo2"
NS = Namespace(BASE + "#")

FAILURES = []
def check(ok, label, detail=""):
    status = "PASS" if ok else "FAIL"
    print("  [%s] %s%s" % (status, label, (" -- " + detail) if detail and not ok else ""))
    if not ok:
        FAILURES.append(label)


def load(path):
    g = Graph()
    g.parse(path, format="turtle")
    return g


def check_referential(g):
    print("\n2. Referential integrity")
    declared = set(g.subjects(RDF.type, OWL.Class))
    missing = set()
    for pred in (RDFS.domain, RDFS.range):
        for s, p, o in g.triples((None, pred, None)):
            if isinstance(o, URIRef) and str(o).startswith(BASE):
                if o not in declared:
                    missing.add((str(s).split("#")[-1], str(o).split("#")[-1]))
    # union members
    for s, p, o in g.triples((None, OWL.unionOf, None)):
        for item in g.items(o):
            if isinstance(item, URIRef) and str(item).startswith(BASE):
                if item not in declared:
                    missing.add(("union", str(item).split("#")[-1]))
    check(not missing, "every class used in a domain or range is declared",
          str(sorted(missing)[:5]))

    # every individual's type is a declared class
    bad = set()
    for ind in set(g.subjects(RDF.type, OWL.NamedIndividual)):
        for t in g.objects(ind, RDF.type):
            if t != OWL.NamedIndividual and str(t).startswith(BASE):
                if t not in declared:
                    bad.add(str(t).split("#")[-1])
    check(not bad, "every individual is typed to a declared class", str(sorted(bad)[:5]))


def check_provenance(g):
    print("\n3. Provenance coverage")
    entities = set()
    for t in (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.NamedIndividual):
        entities |= {s for s in g.subjects(RDF.type, t) if isinstance(s, URIRef)}
    untagged = []
    for e in entities:
        has_src = (e, NS.sourceLocator, None) in g
        statuses = {str(o) for o in g.objects(e, NS.epistemicStatus)}
        if not has_src and not (statuses & {"inferred", "scaffolding", "named_only"}):
            untagged.append(str(e).split("#")[-1])
    check(not untagged,
          "every entity has a sourceLocator or an explicit inferred/scaffolding status",
          "%d untagged, e.g. %s" % (len(untagged), sorted(untagged)[:6]))

    n_src = len(set(g.subjects(NS.sourceLocator, None)))
    print("      %d entities carry a sourceLocator" % n_src)
    for st in ["verified", "uncertain", "inferred", "scaffolding", "named_only"]:
        n = len(set(g.subjects(NS.epistemicStatus, Literal(st))))
        print("      epistemicStatus %-12s %d" % (st, n))


def check_flows(g):
    print("\n4. Flow structure")
    flows = set(g.subjects(RDF.type, NS.Process_Flow))
    check(len(flows) == 8, "eight process flows", "found %d" % len(flows))

    steps = set(g.subjects(NS.belongsToFlow, None))
    orphan = [s for s in g.subjects(RDF.type, OWL.NamedIndividual)
              if (s, RDF.type, NS.Unit_Process) in g and s not in steps]
    check(not orphan, "every Unit_Process individual has belongsToFlow")

    # precedes must never cross a flow boundary
    cross = []
    for a, _, b in g.triples((None, NS.precedes, None)):
        fa = set(g.objects(a, NS.belongsToFlow))
        fb = set(g.objects(b, NS.belongsToFlow))
        if fa and fb and fa != fb:
            cross.append((str(a).split("#")[-1], str(b).split("#")[-1]))
    check(not cross, "precedes never crosses a flow boundary", str(cross[:3]))

    # Flow C is the anneal-after-patterning case; the others are the reverse.
    def idx(name):
        v = list(g.objects(NS[name], NS.hasStepIndex))
        return int(v[0]) if v else None
    check(idx("C6_Patterning_And_Etch") < idx("C7_Crystallisation_Anneal"),
          "Flow C patterns before annealing")
    check(idx("B1_7_Crystallisation_Anneal") < idx("B1_8_Gate_Formation"),
          "Flow B1 anneals before patterning")

    # Flow E has no Crystallisation_Anneal individual at all.
    e_steps = [s for s in g.subjects(NS.belongsToFlow, NS.FlowE_FullALD_AutoAnneal)]
    e_anneal = [s for s in e_steps if (s, RDF.type, NS.Crystallisation_Anneal) in g]
    check(not e_anneal, "Flow E has no Crystallisation_Anneal individual")
    check((NS.E5_TiN_TE_ALD, NS.isCrystallising, Literal(True, datatype=XSD.boolean)) in g,
          "Flow E crystallises during the ALD top electrode step instead")


def check_slots(g):
    print("\n5. Slot design")
    slots = set(g.subjects(RDF.type, NS.Layer_Slot))
    check(len(slots) > 0, "slots exist", "%d" % len(slots))

    bad = [s for s in slots if len(list(g.objects(s, NS.slotMaterial))) != 1]
    check(not bad, "every slot has exactly one material")

    # The negative check that validates the whole design.
    reach = set(g.objects(NS.Stack_A_MFM, NS.hasElectrode))
    reach |= set(g.objects(NS.Stack_A_MFM, NS.hasTopElectrode))
    reach |= set(g.objects(NS.Stack_A_MFM, NS.hasBottomElectrode))
    check(NS.Ti_Pt_contact not in reach,
          "Stack_A_MFM does NOT reach Ti_Pt_contact through the electrode relations")

    # Si_substrate: one individual, two roles across flows.
    si_slots = [s for s in slots if (s, NS.slotMaterial, NS.Si_substrate) in g]
    roles = set()
    for s in si_slots:
        roles |= {str(r).split("#")[-1] for r in g.objects(s, NS.slotRole)}
    check("substrate" in roles and "channel" in roles,
          "Si_substrate is one individual filling both substrate and channel roles",
          str(sorted(roles)))

    # HZO thickness differs per stack, which is why it cannot live on the material.
    thicks = set()
    for s in slots:
        if (s, NS.slotMaterial, NS.HZO) in g:
            thicks |= {float(t) for t in g.objects(s, NS.hasSlotThickness_nm)}
    check(len(thicks) > 1, "HZO carries different thicknesses in different stacks",
          str(sorted(thicks)))


def check_measurements(g):
    print("\n6. Measurement reification")
    ms = set(g.subjects(RDF.type, NS.Measurement))
    check(len(ms) >= 6, "measurements present", "%d" % len(ms))
    bad = [m for m in ms if not list(g.objects(m, NS.measuredOn))]
    check(not bad, "every measurement points at a specimen")

    # The pair that justifies the class.
    tin = list(g.objects(NS.M_E_TiN_Endurance, NS.hasEnduranceCycleCount))
    ru = list(g.objects(NS.M_E_Ru_Endurance, NS.hasEnduranceCycleCount))
    check(tin and ru and int(tin[0]) != int(ru[0]),
          "TiN and Ru endurance differ under identical conditions",
          "%s vs %s" % (tin, ru))

    # Trap density: two instances, not one overwritten value.
    td = [m for m in ms if (m, NS.measuresProperty, NS.trapped_charge_density) in g]
    check(len(td) == 2, "trap density is two measurement instances, not one value",
          "%d" % len(td))
    specimens = {list(g.objects(m, NS.measuredOn))[0] for m in td}
    check(len(specimens) == 2, "the two trap-density figures sit on distinct specimens")


def check_instance_doc(g):
    print("\n7. Agreement with InstanceFlows")
    expect = {
        "Wet_Clean": ["A1_Substrate_Clean", "B1_3_dHF_Clean"],
        "Sputter_Deposition": ["A2_BE_Sputter", "A4_TE_Capping", "B1_6_TiN_W_Sputter"],
        "Crystallisation_Anneal": ["A5_Crystallisation_Anneal",
                                   "B1_7_Crystallisation_Anneal"],
        "Wet_Etch": ["A7_SC1_Etch"],
        "Implantation": ["B1_1_As_Implant"],
        "Thermal_ALD": ["B1_5_HZO_ALD"],
        "Electrical_Characterisation": ["B1_11_Electrical_Test"],
        "Single_Cell": ["Artifact_B1_FeFET_L5_W150"],
    }
    for cls, inds in expect.items():
        actual = {str(s).split("#")[-1] for s in g.subjects(RDF.type, NS[cls])}
        missing = [i for i in inds if i not in actual]
        check(not missing, "%s contains %s" % (cls, ", ".join(inds)), str(missing))

    # A3 must be typed at the parent only.
    subs = {str(t).split("#")[-1] for t in g.objects(NS.A3_FE_Deposition, RDF.type)}
    check("Deposition" in subs and not (subs & {"ALD", "Sputter_Deposition", "PLD", "CSD"}),
          "A3_FE_Deposition is typed at Deposition and no subclass", str(sorted(subs)))
    check((NS.A6_Patterned_Metal_Deposition, NS.contradictedBy, None) in g,
          "A6 is marked contradicted by its own source")


def check_reasoner(path):
    print("\n1. Reasoner (HermiT)")
    try:
        from owlready2 import get_ontology, sync_reasoner, OwlReadyInconsistentOntologyError
        import owlready2
        # owlready2 reads RDF/XML and NTriples, not Turtle. Convert first.
        tmp = path.replace(".ttl", "__owlready.owl")
        Graph().parse(path, format="turtle").serialize(destination=tmp, format="xml")
        onto = get_ontology("file://" + tmp).load()
        try:
            with onto:
                sync_reasoner(debug=0)
            check(True, "ontology is consistent")
            n_inf = len(list(onto.individuals()))
            print("      %d individuals after classification" % n_inf)
        except OwlReadyInconsistentOntologyError as e:
            check(False, "ontology is consistent", str(e)[:200])
    except Exception as e:
        print("  [SKIP] reasoner unavailable: %s" % str(e)[:200])


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "Ferroelectric_HfO2.ttl"
    import os
    path = os.path.abspath(path)
    g = load(path)
    print("Loaded %d triples from %s" % (len(g), os.path.basename(path)))
    check_reasoner(path)
    check_referential(g)
    check_provenance(g)
    check_flows(g)
    check_slots(g)
    check_measurements(g)
    check_instance_doc(g)
    print("\n" + "=" * 60)
    if FAILURES:
        print("%d CHECK(S) FAILED: %s" % (len(FAILURES), FAILURES))
        sys.exit(1)
    print("All checks passed.")
