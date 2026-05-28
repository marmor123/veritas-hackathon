"""
Graphify Module — Clinical Knowledge Graph Builder

Transforms biomarker results and RAG-retrieved patterns into a knowledge graph
representing causal relationships between biomarkers, clinical patterns, and
body systems.

Instead of showing 40 separate alerts, we build a graph that shows:
- Root causes → downstream effects
- Biomarker → pattern relationships
- Pattern → body system membership
- Causal chains (e.g., Low Ferritin → Low Iron → Low MCV → Low Hemoglobin)

This graph powers:
1. The Network Graph visualization in the frontend (D3.js)
2. Enhanced RAG retrieval (search by relationships, not just text similarity)
3. Root cause identification (parent-child suppression)
"""

from backend.api.models.schemas import (
    GraphNode,
    GraphEdge,
    ClinicalGraph,
    VerifiedResult,
    RetrievedChunk,
)


# ── Known causal chains (curated for demo) ──────────────────────────────

CAUSAL_CHAINS: list[dict] = [
    # Iron deficiency cascade
    {
        "trigger": ["ferritin"],
        "chain": [
            {"from": "ferritin", "to": "iron", "relation": "causes", "label": "Low Ferritin → Low Serum Iron"},
            {"from": "iron", "to": "mcv", "relation": "contributes_to", "label": "Low Iron → Low MCV"},
            {"from": "mcv", "to": "hemoglobin", "relation": "contributes_to", "label": "Low MCV → Low Hemoglobin"},
            {"from": "hemoglobin", "to": "resting_hr", "relation": "may_cause", "label": "Low Hemoglobin → Elevated HR"},
        ],
        "pattern": "Iron Deficiency",
        "system": "Hematologic",
    },
    # Metabolic syndrome cluster
    {
        "trigger": ["glucose", "triglycerides", "hdl"],
        "chain": [
            {"from": "insulin_resistance", "to": "glucose", "relation": "causes", "label": "Insulin Resistance → High Glucose"},
            {"from": "insulin_resistance", "to": "triglycerides", "relation": "causes", "label": "Insulin Resistance → High Triglycerides"},
            {"from": "insulin_resistance", "to": "hdl", "relation": "causes", "label": "Insulin Resistance → Low HDL"},
            {"from": "insulin_resistance", "to": "alt", "relation": "may_cause", "label": "Insulin Resistance → Elevated ALT (fatty liver)"},
            {"from": "insulin_resistance", "to": "uric_acid", "relation": "may_cause", "label": "Insulin Resistance → High Uric Acid"},
        ],
        "pattern": "Metabolic Syndrome",
        "system": "Cardiometabolic",
    },
    # Thyroid dysfunction
    {
        "trigger": ["tsh"],
        "chain": [
            {"from": "tsh", "to": "ft4", "relation": "indicates", "label": "Abnormal TSH → Check Free T4"},
            {"from": "tsh", "to": "ft3", "relation": "indicates", "label": "Abnormal TSH → Check Free T3"},
            {"from": "hypothyroid", "to": "cholesterol", "relation": "may_cause", "label": "Hypothyroidism → Elevated Cholesterol"},
            {"from": "hypothyroid", "to": "creatinine", "relation": "may_cause", "label": "Hypothyroidism → Mild Creatinine Elevation"},
        ],
        "pattern": "Thyroid Dysfunction",
        "system": "Thyroid",
    },
    # B12 deficiency
    {
        "trigger": ["vitamin_b12", "b12"],
        "chain": [
            {"from": "b12", "to": "mcv", "relation": "causes", "label": "Low B12 → High MCV (macrocytosis)"},
            {"from": "b12", "to": "homocysteine", "relation": "causes", "label": "Low B12 → High Homocysteine"},
        ],
        "pattern": "B12 Deficiency",
        "system": "Nutritional",
    },
    # Kidney disease
    {
        "trigger": ["creatinine", "egfr"],
        "chain": [
            {"from": "egfr", "to": "creatinine", "relation": "indicates", "label": "Low eGFR ↔ High Creatinine"},
            {"from": "kidney", "to": "potassium", "relation": "may_cause", "label": "Kidney Dysfunction → High Potassium"},
            {"from": "kidney", "to": "phosphate", "relation": "may_cause", "label": "Kidney Dysfunction → High Phosphate"},
            {"from": "kidney", "to": "calcium", "relation": "may_cause", "label": "Kidney Dysfunction → Low Calcium"},
            {"from": "kidney", "to": "hemoglobin", "relation": "may_cause", "label": "Kidney Dysfunction → Anemia"},
        ],
        "pattern": "Kidney Dysfunction",
        "system": "Renal",
    },
]


def build_clinical_graph(
    verified_results: list[VerifiedResult],
    retrieved_chunks: list[RetrievedChunk] | None = None,
    wearable_data: dict | None = None,
) -> ClinicalGraph:
    """
    Build a clinical knowledge graph from verified biomarker results.

    This is the core Graphify function. It:
    1. Creates nodes for each abnormal biomarker
    2. Identifies matching causal chains
    3. Adds pattern nodes and system nodes
    4. Connects everything with typed edges
    5. Optionally adds wearable data nodes

    Args:
        verified_results: Verified biomarker results from the verification layer
        retrieved_chunks: RAG-retrieved chunks (for additional context)
        wearable_data: Optional wearable data dict

    Returns:
        ClinicalGraph with nodes and edges for the frontend network visualization.
    """
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    # Get abnormal biomarkers
    abnormal = [r for r in verified_results if r.flagged]
    abnormal_names = {r.biomarker.lower().replace(" ", "_") for r in abnormal}

    # Step 1: Create biomarker nodes for all abnormal results
    for r in abnormal:
        node_id = r.biomarker.lower().replace(" ", "_")
        direction = "Low" if r.ref_low and r.value < r.ref_low else "High"
        nodes[node_id] = GraphNode(
            id=node_id,
            label=f"{direction} {r.biomarker}",
            type="biomarker",
            severity=_infer_severity(r),
            value=r.value,
            unit=r.unit,
        )

    # Step 2: Match causal chains
    matched_chains = _match_causal_chains(abnormal_names)

    for chain_def in matched_chains:
        # Add pattern node
        pattern_id = chain_def["pattern"].lower().replace(" ", "_")
        if pattern_id not in nodes:
            nodes[pattern_id] = GraphNode(
                id=pattern_id,
                label=chain_def["pattern"],
                type="pattern",
            )

        # Add system node
        system_id = chain_def["system"].lower().replace(" ", "_")
        if system_id not in nodes:
            nodes[system_id] = GraphNode(
                id=system_id,
                label=chain_def["system"],
                type="system",
            )

        # Connect pattern to system
        edges.append(GraphEdge(
            source=pattern_id,
            target=system_id,
            relation="belongs_to",
        ))

        # Add causal chain edges (only for biomarkers that are actually abnormal)
        for link in chain_def["chain"]:
            from_id = link["from"]
            to_id = link["to"]

            # Only add edges where at least one endpoint is an abnormal biomarker
            if from_id in abnormal_names or to_id in abnormal_names:
                # Ensure both nodes exist
                if from_id not in nodes:
                    nodes[from_id] = GraphNode(
                        id=from_id,
                        label=_id_to_label(from_id),
                        type="biomarker" if from_id in abnormal_names else "pattern",
                    )
                if to_id not in nodes:
                    nodes[to_id] = GraphNode(
                        id=to_id,
                        label=_id_to_label(to_id),
                        type="biomarker" if to_id in abnormal_names else "symptom",
                    )

                edges.append(GraphEdge(
                    source=from_id,
                    target=to_id,
                    relation=link["relation"],
                ))

                # Connect involved biomarkers to the pattern
                if from_id in abnormal_names:
                    edges.append(GraphEdge(
                        source=from_id,
                        target=pattern_id,
                        relation="supports",
                    ))

    # Step 3: Add wearable data node if relevant
    if wearable_data:
        _add_wearable_nodes(nodes, edges, wearable_data, abnormal_names)

    # Step 4: Connect isolated abnormal biomarkers (not part of any chain)
    connected_biomarkers = set()
    for edge in edges:
        connected_biomarkers.add(edge.source)
        connected_biomarkers.add(edge.target)

    for node_id, node in nodes.items():
        if node.type == "biomarker" and node_id not in connected_biomarkers:
            # Isolated abnormal biomarker — add as standalone
            edges.append(GraphEdge(
                source=node_id,
                target="isolated_findings",
                relation="unconnected",
            ))

    if "isolated_findings" in {e.target for e in edges}:
        nodes["isolated_findings"] = GraphNode(
            id="isolated_findings",
            label="Isolated Findings",
            type="pattern",
        )

    # Deduplicate edges
    seen_edges = set()
    unique_edges = []
    for edge in edges:
        key = (edge.source, edge.target, edge.relation)
        if key not in seen_edges:
            seen_edges.add(key)
            unique_edges.append(edge)

    return ClinicalGraph(
        nodes=list(nodes.values()),
        edges=unique_edges,
    )


def build_pattern_subgraph(
    pattern_name: str,
    supporting_biomarkers: list[VerifiedResult],
    wearable_data: dict | None = None,
) -> ClinicalGraph:
    """
    Build a focused subgraph for a single clinical pattern.
    Used for the per-pattern graph in PatternCard expansion.
    """
    return build_clinical_graph(
        verified_results=supporting_biomarkers,
        wearable_data=wearable_data,
    )


def _match_causal_chains(abnormal_names: set[str]) -> list[dict]:
    """Find causal chains that match the abnormal biomarkers."""
    matched = []
    for chain_def in CAUSAL_CHAINS:
        # Check if any trigger biomarker is abnormal
        triggers = {t.lower().replace(" ", "_") for t in chain_def["trigger"]}
        if triggers & abnormal_names:
            matched.append(chain_def)
    return matched


def _infer_severity(result: VerifiedResult) -> str:
    """Infer severity from how far a value is from the reference range."""
    if result.ref_low is None and result.ref_high is None:
        return "ADVISORY"

    if result.ref_low and result.value < result.ref_low:
        deviation = (result.ref_low - result.value) / result.ref_low
    elif result.ref_high and result.value > result.ref_high:
        deviation = (result.value - result.ref_high) / result.ref_high
    else:
        return "NORMAL"

    if deviation > 0.5:
        return "WARNING"
    elif deviation > 0.2:
        return "CAUTION"
    else:
        return "ADVISORY"


def _add_wearable_nodes(
    nodes: dict[str, GraphNode],
    edges: list[GraphEdge],
    wearable_data: dict,
    abnormal_names: set[str],
):
    """Add wearable data as nodes connected to relevant biomarkers."""
    hr_trend = wearable_data.get("resting_hr_trend")
    hr_avg = wearable_data.get("resting_hr_avg")

    if hr_trend == "rising" or (hr_avg and hr_avg > 75):
        nodes["resting_hr"] = GraphNode(
            id="resting_hr",
            label=f"Resting HR ↑ ({hr_avg} bpm)" if hr_avg else "Resting HR Rising",
            type="symptom",
        )
        # Connect to hemoglobin if it's abnormal (compensatory tachycardia)
        if "hemoglobin" in abnormal_names:
            edges.append(GraphEdge(
                source="hemoglobin",
                target="resting_hr",
                relation="may_cause",
            ))


def _id_to_label(node_id: str) -> str:
    """Convert a node ID to a human-readable label."""
    labels = {
        "insulin_resistance": "Insulin Resistance",
        "hypothyroid": "Hypothyroidism",
        "kidney": "Kidney Dysfunction",
        "resting_hr": "Elevated Resting HR",
        "isolated_findings": "Isolated Findings",
    }
    if node_id in labels:
        return labels[node_id]
    return node_id.replace("_", " ").title()
