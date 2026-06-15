from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.clients import get_drug_properties, get_fda_label, get_fda_adverse_events
from app.normalizer import normalize_rxcui_lookup, deduplicate_interactions
from app.models import DrugInteractionResult, MultiDrugInteractionResult, InteractionPair
from app.service import get_or_fetch_drug, get_or_fetch_label, get_or_fetch_interactions
from app.clients import get_rxcui

router = APIRouter()


class MultiDrugRequest(BaseModel):
    drugs: list[str]


@router.get("/lookup/{drug_name}")
async def lookup_drug(drug_name: str, db: AsyncSession = Depends(get_db)):
    drug = await get_or_fetch_drug(drug_name, db)
    if not drug:
        raise HTTPException(status_code=404, detail=f"No RxCUI found for '{drug_name}'. Try the generic name.")
    return {"drug_name": drug.name, "rxcui": drug.rxcui, "generic_name": drug.generic_name}


@router.get("/interactions/{drug_name}", response_model=DrugInteractionResult)
async def drug_interactions(drug_name: str, compare_with: str = "", db: AsyncSession = Depends(get_db)):
    drug = await get_or_fetch_drug(drug_name, db)
    if not drug:
        raise HTTPException(status_code=404, detail=f"No RxCUI found for '{drug_name}'")

    label = await get_or_fetch_label(drug, db)
    if not label:
        raise HTTPException(status_code=404, detail=f"No FDA label found for '{drug_name}'")

    other_names = [d.strip() for d in compare_with.split(",") if d.strip()] if compare_with else []

    all_pairs = []
    for other_name in other_names:
        other_drug = await get_or_fetch_drug(other_name, db)
        if not other_drug:
            continue
        other_label = await get_or_fetch_label(other_drug, db)
        if not other_label:
            continue
        rows = await get_or_fetch_interactions(drug, other_drug, label, other_label, db)
        for row in rows:
            all_pairs.append(InteractionPair(
                drug_1=drug.name,
                drug_2=other_drug.name,
                description=row.description,
                severity=row.severity,
                source=row.source,
            ))

    return DrugInteractionResult(
        drug_name=drug.name,
        rxcui=drug.rxcui,
        interactions=all_pairs,
        interaction_count=len(all_pairs)
    )


@router.post("/interactions/check", response_model=MultiDrugInteractionResult)
async def check_multi_drug_interactions(body: MultiDrugRequest, db: AsyncSession = Depends(get_db)):
    if len(body.drugs) < 2:
        raise HTTPException(status_code=400, detail="Submit at least 2 drugs to check interactions.")
    if len(body.drugs) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 drugs per request.")

    # Resolve and cache all drugs
    drug_map = {}
    for name in body.drugs:
        drug = await get_or_fetch_drug(name, db)
        if drug:
            drug_map[name] = drug

    if len(drug_map) < 2:
        raise HTTPException(status_code=404, detail="Could not resolve at least 2 drugs.")

    # Fetch and cache all labels
    label_map = {}
    for name, drug in drug_map.items():
        label = await get_or_fetch_label(drug, db)
        if label:
            label_map[name] = label

    # Check every unique pair
    all_pairs = []
    drug_names = list(drug_map.keys())

    for i in range(len(drug_names)):
        for j in range(i + 1, len(drug_names)):
            name_a, name_b = drug_names[i], drug_names[j]
            if name_a not in label_map or name_b not in label_map:
                continue

            rows = await get_or_fetch_interactions(
                drug_map[name_a], drug_map[name_b],
                label_map[name_a], label_map[name_b],
                db
            )
            for row in rows:
                all_pairs.append(InteractionPair(
                    drug_1=name_a,
                    drug_2=name_b,
                    description=row.description,
                    severity=row.severity,
                    source=row.source,
                ))

    unique_pairs = deduplicate_interactions(all_pairs)

    return MultiDrugInteractionResult(
        drugs_checked=drug_names,
        total_interactions_found=len(unique_pairs),
        interactions=unique_pairs
    )



#kind of useless command
@router.get("/properties/{drug_name}")
async def drug_properties(drug_name: str, db: AsyncSession = Depends(get_db)):
    drug = await get_or_fetch_drug(drug_name, db)
    if not drug:
        raise HTTPException(status_code=404, detail=f"No RxCUI found for '{drug_name}'")
    props = await get_drug_properties(drug.rxcui)
    return {"drug_name": drug.name, "rxcui": drug.rxcui, "properties": props}


@router.get("/fda-label/{drug_name}")
async def fda_label(drug_name: str):
    label = await get_fda_label(drug_name)
    return {"drug_name": drug_name, "label": label}


@router.get("/adverse-events/{drug_name}")
async def adverse_events(drug_name: str, limit: int = 5):
    events = await get_fda_adverse_events(drug_name, limit=limit)
    return {"drug_name": drug_name, "adverse_events": events}