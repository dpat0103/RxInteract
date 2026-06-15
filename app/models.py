from pydantic import BaseModel
from typing import Optional


class DrugLookup(BaseModel):
    drug_name: str
    rxcui: str
    synonym: Optional[str] = None


class InteractionPair(BaseModel):
    drug_1: str
    drug_2: str
    description: str
    severity: Optional[str] = None
    source: Optional[str] = None


class DrugInteractionResult(BaseModel):
    drug_name: str
    rxcui: str
    interactions: list[InteractionPair]
    interaction_count: int


class MultiDrugInteractionResult(BaseModel):
    drugs_checked: list[str]
    total_interactions_found: int
    interactions: list[InteractionPair]
