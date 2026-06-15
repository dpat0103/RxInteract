import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from app.main import app


def make_mock_drug(name="warfarin", rxcui="11289"):
    drug = MagicMock()
    drug.id = 1
    drug.name = name
    drug.rxcui = rxcui
    drug.generic_name = name
    drug.last_updated = datetime.now(timezone.utc)
    return drug


def make_mock_label(drug, interactions_text="", warnings_text=""):
    label = MagicMock()
    label.drug_id = drug.id
    label.drug_interactions_text = interactions_text
    label.warnings_text = warnings_text
    label.contraindications_text = ""
    label.last_updated = datetime.now(timezone.utc)
    return label



async def test_lookup_drug_success():
    mock_drug = make_mock_drug()

    with patch("app.routers.drugs.get_or_fetch_drug", AsyncMock(return_value=mock_drug)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/drugs/lookup/warfarin")

    assert response.status_code == 200
    data = response.json()
    assert data["rxcui"] == "11289"
    assert data["drug_name"] == "warfarin"


async def test_lookup_drug_not_found():
    with patch("app.routers.drugs.get_or_fetch_drug", AsyncMock(return_value=None)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/drugs/lookup/notadrugxyz")

    assert response.status_code == 404



async def test_check_interactions_too_few_drugs():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/drugs/interactions/check", json={"drugs": ["warfarin"]})

    assert response.status_code == 400
    assert "at least 2" in response.json()["detail"]


async def test_check_interactions_too_many_drugs():
    drugs = [f"drug{i}" for i in range(11)]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/drugs/interactions/check", json={"drugs": drugs})

    assert response.status_code == 400
    assert "Maximum 10" in response.json()["detail"]


async def test_check_interactions_success():
    drug_a = make_mock_drug("warfarin", "11289")
    drug_b = make_mock_drug("aspirin", "1191")
    drug_b.id = 2

    label_a = make_mock_label(drug_a, interactions_text="Warfarin interacts with aspirin increasing bleeding risk.")
    label_b = make_mock_label(drug_b, interactions_text="Aspirin concurrent use with warfarin is dangerous.")

    mock_interaction = MagicMock()
    mock_interaction.description = "Warfarin interacts with aspirin increasing bleeding risk."
    mock_interaction.severity = "high"
    mock_interaction.source = "OpenFDA Drug Label"

    async def mock_get_drug(name, db):
        return drug_a if name == "warfarin" else drug_b

    async def mock_get_label(drug, db):
        return label_a if drug.name == "warfarin" else label_b

    with patch("app.routers.drugs.get_or_fetch_drug", side_effect=mock_get_drug), \
         patch("app.routers.drugs.get_or_fetch_label", side_effect=mock_get_label), \
         patch("app.routers.drugs.get_or_fetch_interactions", AsyncMock(return_value=[mock_interaction])):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/drugs/interactions/check",
                json={"drugs": ["warfarin", "aspirin"]}
            )

    assert response.status_code == 200
    data = response.json()
    assert data["total_interactions_found"] >= 1
    assert data["drugs_checked"] == ["warfarin", "aspirin"]


async def test_check_interactions_unresolvable_drugs():
    with patch("app.routers.drugs.get_or_fetch_drug", AsyncMock(return_value=None)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/drugs/interactions/check",
                json={"drugs": ["fakedrug1", "fakedrug2"]}
            )

    assert response.status_code == 404
