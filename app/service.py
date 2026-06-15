from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.orm_models import Drug, DrugLabel, DrugInteraction
from app.clients import get_rxcui, get_fda_drug_interactions
from app.normalizer import normalize_rxcui_lookup, parse_fda_label_interactions, normalize_severity
from app.logger import get_logger

logger = get_logger(__name__)

STALE_AFTER_DAYS = 7


def _is_stale(last_updated: datetime) -> bool:
    age = datetime.now(timezone.utc) - last_updated.replace(tzinfo=timezone.utc)
    return age > timedelta(days=STALE_AFTER_DAYS)


async def get_or_fetch_drug(name: str, db: AsyncSession) -> Drug | None:
    result = await db.execute(select(Drug).where(Drug.name == name.lower()))
    drug = result.scalar_one_or_none()

    if drug and not _is_stale(drug.last_updated):
        logger.info(f"[CACHE HIT] drug='{name}'")
        return drug

    logger.info(f"[CACHE MISS] drug='{name}' — fetching from RxNorm")
    raw = await get_rxcui(name)
    lookup = normalize_rxcui_lookup(name, raw)

    if not lookup.rxcui:
        logger.warning(f"[NOT FOUND] drug='{name}' — no RxCUI returned from RxNorm")
        return None

    if drug:
        drug.rxcui = lookup.rxcui
        drug.last_updated = datetime.now(timezone.utc)
        logger.info(f"[CACHE REFRESH] drug='{name}' rxcui={lookup.rxcui}")
    else:
        drug = Drug(
            name=name.lower(),
            rxcui=lookup.rxcui,
            generic_name=lookup.synonym,
        )
        db.add(drug)
        logger.info(f"[CACHE WRITE] drug='{name}' rxcui={lookup.rxcui}")

    await db.commit()
    await db.refresh(drug)
    return drug


async def get_or_fetch_label(drug: Drug, db: AsyncSession) -> DrugLabel | None:
    result = await db.execute(select(DrugLabel).where(DrugLabel.drug_id == drug.id))
    label = result.scalar_one_or_none()

    if label and not _is_stale(label.last_updated):
        logger.info(f"[CACHE HIT] label for drug='{drug.name}'")
        return label

    logger.info(f"[CACHE MISS] label for drug='{drug.name}' — fetching from OpenFDA")
    raw = await get_fda_drug_interactions(drug.name)

    interactions_text = " ".join(raw.get("drug_interactions", []))
    warnings_text = " ".join(
        raw.get("warnings", []) + raw.get("warnings_and_cautions", [])
    )
    contraindications_text = " ".join(raw.get("contraindications", []))

    if not interactions_text and not warnings_text:
        logger.warning(f"[EMPTY LABEL] drug='{drug.name}' — OpenFDA returned no label text")

    if label:
        label.drug_interactions_text = interactions_text
        label.warnings_text = warnings_text
        label.contraindications_text = contraindications_text
        label.last_updated = datetime.now(timezone.utc)
        logger.info(f"[CACHE REFRESH] label for drug='{drug.name}'")
    else:
        label = DrugLabel(
            drug_id=drug.id,
            drug_interactions_text=interactions_text,
            warnings_text=warnings_text,
            contraindications_text=contraindications_text,
        )
        db.add(label)
        logger.info(f"[CACHE WRITE] label for drug='{drug.name}'")

    await db.commit()
    await db.refresh(label)
    return label


async def get_or_fetch_interactions(
    drug_a: Drug,
    drug_b: Drug,
    label_a: DrugLabel,
    label_b: DrugLabel,
    db: AsyncSession
) -> list[DrugInteraction]:
    if drug_a.id > drug_b.id:
        drug_a, drug_b = drug_b, drug_a
        label_a, label_b = label_b, label_a

    result = await db.execute(
        select(DrugInteraction).where(
            DrugInteraction.drug_a_id == drug_a.id,
            DrugInteraction.drug_b_id == drug_b.id,
        )
    )
    existing = result.scalars().all()

    if existing and not _is_stale(existing[0].last_updated):
        logger.info(f"[CACHE HIT] interactions '{drug_a.name}' <-> '{drug_b.name}' ({len(existing)} rows)")
        return existing

    logger.info(f"[CACHE MISS] interactions '{drug_a.name}' <-> '{drug_b.name}' — parsing from labels")

    label_a_data = _label_to_dict(label_a)
    label_b_data = _label_to_dict(label_b)

    pairs_from_a = parse_fda_label_interactions(drug_a.name, label_a_data, [drug_b.name])
    pairs_from_b = parse_fda_label_interactions(drug_b.name, label_b_data, [drug_a.name])
    all_pairs = pairs_from_a + pairs_from_b

    if not all_pairs:
        logger.info(f"[NO INTERACTIONS] '{drug_a.name}' <-> '{drug_b.name}' — no mentions found in labels")
        return []

    for row in existing:
        await db.delete(row)

    new_rows = []
    seen_descriptions = set()

    for pair in all_pairs:
        if pair.description in seen_descriptions:
            continue
        seen_descriptions.add(pair.description)

        row = DrugInteraction(
            drug_a_id=drug_a.id,
            drug_b_id=drug_b.id,
            description=pair.description,
            severity=normalize_severity(pair.description),
            source="OpenFDA Drug Label",
        )
        db.add(row)
        new_rows.append(row)

    await db.commit()
    logger.info(f"[CACHE WRITE] {len(new_rows)} interaction(s) stored for '{drug_a.name}' <-> '{drug_b.name}'")
    return new_rows


def _label_to_dict(label: DrugLabel) -> dict:
    return {
        "drug_interactions": [label.drug_interactions_text] if label.drug_interactions_text else [],
        "warnings": [label.warnings_text] if label.warnings_text else [],
        "contraindications": [label.contraindications_text] if label.contraindications_text else [],
    }