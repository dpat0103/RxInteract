import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from app.service import get_or_fetch_drug, get_or_fetch_label, get_or_fetch_interactions, STALE_AFTER_DAYS



async def test_get_or_fetch_drug_cache_hit(mock_db, fresh_drug):
    result = MagicMock()
    result.scalar_one_or_none.return_value = fresh_drug
    mock_db.execute = AsyncMock(return_value=result)

    with patch("app.service.get_rxcui") as mock_rxcui:
        drug = await get_or_fetch_drug("warfarin", mock_db)

    assert drug.name == "warfarin"
    assert drug.rxcui == "11289"
    mock_rxcui.assert_not_called()  


async def test_get_or_fetch_drug_cache_miss(mock_db):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    mock_rxnorm_response = {
        "idGroup": {
            "rxnormId": ["11289"],
            "name": "warfarin"
        }
    }

    with patch("app.service.get_rxcui", AsyncMock(return_value=mock_rxnorm_response)):
        drug = await get_or_fetch_drug("warfarin", mock_db)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


async def test_get_or_fetch_drug_not_found(mock_db):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)

    mock_rxnorm_response = {"idGroup": {"rxnormId": []}}

    with patch("app.service.get_rxcui", AsyncMock(return_value=mock_rxnorm_response)):
        drug = await get_or_fetch_drug("notadrugxyz", mock_db)

    assert drug is None
    mock_db.add.assert_not_called()


async def test_get_or_fetch_drug_stale_refreshes(mock_db, fresh_drug):
    fresh_drug.last_updated = datetime.now(timezone.utc) - timedelta(days=STALE_AFTER_DAYS + 1)

    result = MagicMock()
    result.scalar_one_or_none.return_value = fresh_drug
    mock_db.execute = AsyncMock(return_value=result)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    mock_rxnorm_response = {
        "idGroup": {"rxnormId": ["11289"], "name": "warfarin"}
    }

    with patch("app.service.get_rxcui", AsyncMock(return_value=mock_rxnorm_response)) as mock_rxcui:
        await get_or_fetch_drug("warfarin", mock_db)

    mock_rxcui.assert_called_once()
    mock_db.commit.assert_called_once()



async def test_get_or_fetch_label_cache_hit(mock_db, fresh_drug, fresh_label):
    result = MagicMock()
    result.scalar_one_or_none.return_value = fresh_label
    mock_db.execute = AsyncMock(return_value=result)

    with patch("app.service.get_fda_drug_interactions") as mock_fda:
        label = await get_or_fetch_label(fresh_drug, mock_db)

    assert label.drug_interactions_text is not None
    mock_fda.assert_not_called()


async def test_get_or_fetch_label_cache_miss(mock_db, fresh_drug):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    mock_fda_response = {
        "drug_interactions": ["Warfarin interacts with aspirin."],
        "warnings": ["Monitor INR closely."],
        "warnings_and_cautions": [],
        "contraindications": [],
    }

    with patch("app.service.get_fda_drug_interactions", AsyncMock(return_value=mock_fda_response)):
        label = await get_or_fetch_label(fresh_drug, mock_db)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()



async def test_get_or_fetch_interactions_cache_hit(mock_db, fresh_drug, fresh_drug_b, fresh_label, fresh_label_b):
    existing_row = MagicMock()
    existing_row.last_updated = datetime.now(timezone.utc)
    existing_row.description = "Warfarin interacts with aspirin."
    existing_row.severity = "high"

    result = MagicMock()
    result.scalars.return_value.all.return_value = [existing_row]
    mock_db.execute = AsyncMock(return_value=result)

    rows = await get_or_fetch_interactions(fresh_drug, fresh_drug_b, fresh_label, fresh_label_b, mock_db)

    assert len(rows) == 1
    assert rows[0].description == "Warfarin interacts with aspirin."
    mock_db.add.assert_not_called()


async def test_get_or_fetch_interactions_cache_miss_finds_interactions(
    mock_db, fresh_drug, fresh_drug_b, fresh_label, fresh_label_b
):
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result)
    mock_db.commit = AsyncMock()

    rows = await get_or_fetch_interactions(fresh_drug, fresh_drug_b, fresh_label, fresh_label_b, mock_db)

    assert mock_db.add.called
    assert mock_db.commit.called


async def test_get_or_fetch_interactions_no_interactions_found(
    mock_db, fresh_drug, fresh_drug_b
):
    label_a = MagicMock()
    label_a.last_updated = datetime.now(timezone.utc)
    label_a.drug_interactions_text = "Take with food."
    label_a.warnings_text = ""
    label_a.contraindications_text = ""

    label_b = MagicMock()
    label_b.last_updated = datetime.now(timezone.utc)
    label_b.drug_interactions_text = "Store at room temperature."
    label_b.warnings_text = ""
    label_b.contraindications_text = ""

    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=result)

    rows = await get_or_fetch_interactions(fresh_drug, fresh_drug_b, label_a, label_b, mock_db)

    assert rows == []
    mock_db.add.assert_not_called()
