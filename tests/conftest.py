import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone


@pytest.fixture
def mock_db():
    db = AsyncMock()
    return db


@pytest.fixture
def fresh_drug():
    drug = MagicMock()
    drug.id = 1
    drug.name = "warfarin"
    drug.rxcui = "11289"
    drug.generic_name = "warfarin"
    drug.last_updated = datetime.now(timezone.utc)
    return drug


@pytest.fixture
def fresh_label(fresh_drug):
    label = MagicMock()
    label.id = 1
    label.drug_id = fresh_drug.id
    label.drug_interactions_text = "Warfarin interacts with aspirin and may increase bleeding risk."
    label.warnings_text = "Avoid concurrent use with NSAIDs such as ibuprofen."
    label.contraindications_text = ""
    label.last_updated = datetime.now(timezone.utc)
    return label


@pytest.fixture
def fresh_drug_b():
    drug = MagicMock()
    drug.id = 2
    drug.name = "aspirin"
    drug.rxcui = "1191"
    drug.generic_name = "aspirin"
    drug.last_updated = datetime.now(timezone.utc)
    return drug


@pytest.fixture
def fresh_label_b(fresh_drug_b):
    label = MagicMock()
    label.id = 2
    label.drug_id = fresh_drug_b.id
    label.drug_interactions_text = "Aspirin concurrent use with warfarin increases bleeding risk."
    label.warnings_text = ""
    label.contraindications_text = ""
    label.last_updated = datetime.now(timezone.utc)
    return label
