from app.models import DrugLookup, InteractionPair


def normalize_rxcui_lookup(drug_name: str, raw: dict) -> DrugLookup:
    """
    Extract RxCUI and synonym from raw RxNorm rxcui.json response.
    """
    id_group = raw.get("idGroup", {})
    rxcui_list = id_group.get("rxnormId", [])
    rxcui = rxcui_list[0] if rxcui_list else None

    return DrugLookup(
        drug_name=drug_name,
        rxcui=rxcui or "",
        synonym=id_group.get("name")
    )


def normalize_severity(raw_severity: str | None) -> str | None:
    """
    If severity label exists from API call, try to salvage it, otherwise leave it.
    """
    if not raw_severity:
        return None

    s = raw_severity.lower()

    if any(word in s for word in ["contraindicated", "avoid", "fatal", "life-threatening", "severe"]):
        return "high"
    elif any(word in s for word in ["caution", "monitor", "reduce", "adjust", "moderate", "significant"]):
        return "moderate"
    elif any(word in s for word in ["minor", "minimal", "slight", "low"]):
        return "low"

    return None


def parse_fda_label_interactions(drug_name: str, label_data: dict, other_drugs: list[str]) -> list[InteractionPair]:
    """
    Parse FDA label drug_interactions text for mentions of other medications in the given list. Each found match is returned as an InteractionPair.

    The FDA's drug_interactions field is prose, therefore we scan each sentence for mentions of other pharmaceuticals and extract the context to describe the interaction.
    """
    import re

    pairs = []
    other_drugs_lower = {d.lower(): d for d in other_drugs}

    sections = (
        label_data.get("drug_interactions", []) +
        label_data.get("warnings", []) +
        label_data.get("warnings_and_cautions", []) +
        label_data.get("contraindications", [])
    )

    full_text = " ".join(sections)

    sentences = re.split(r'(?<=[.!?])\s+', full_text)

    for other_drug in other_drugs_lower:
        if other_drug == drug_name.lower():
            continue

        matched_sentences = [
            s.strip() for s in sentences
            if other_drug in s.lower() and len(s.strip()) > 20
        ]

        if matched_sentences:
            best = next(
                (s for s in matched_sentences if drug_name.lower() in s.lower()),
                matched_sentences[0]
            )

            pairs.append(InteractionPair(
                drug_1=drug_name,
                drug_2=other_drugs_lower[other_drug],
                description=best,
                severity=normalize_severity(best),
                source="OpenFDA Drug Label"
            ))

    return pairs


def deduplicate_interactions(interactions: list[InteractionPair]) -> list[InteractionPair]:
    """
    When checking multiple drugs, the same interaction pair can show up twice
    (A->B and B->A). Deduplicate by treating pairs as unordered.
    """
    seen = set()
    unique = []

    for interaction in interactions:
        key = frozenset([interaction.drug_1.lower(), interaction.drug_2.lower()])
        if key not in seen:
            seen.add(key)
            unique.append(interaction)

    return unique
