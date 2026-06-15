# RxInteract API

A REST API service for checking drug-drug interactions and retrieving FDA label data. Built with FastAPI and PostgreSQL, powered by real-world data from the NIH RxNorm and OpenFDA APIs.

## Overview

RxInteract accepts a list of medication names and returns known interactions found across their FDA-approved drug labels. Interaction data is cached in PostgreSQL using a cache-aside pattern where the first request for a drug fetches from OpenFDA and writes to the database, subsequent requests are served from the local cache. A background scheduler refreshes stale data every 24 hours.

## Tech Stack

- **FastAPI** — async REST API framework
- **PostgreSQL** — relational data store for drugs, labels, and interaction pairs
- **SQLAlchemy (async)** — ORM with async session support
- **Alembic** — database migrations
- **APScheduler** — background job for periodic cache refresh
- **Docker** — containerized Postgres for local development
- **RxNorm (NIH NLM)** — drug name resolution and RxCUI lookup
- **OpenFDA** — FDA drug label data including interactions, warnings, and contraindications

## Architecture

```
Request
  │
  ▼
FastAPI Router
  │
  ▼
Service Layer (cache-aside)
  ├── Cache HIT  → return from PostgreSQL
  └── Cache MISS → fetch from OpenFDA → write to PostgreSQL → return
```

### Database Schema

**`drugs`** — one row per unique drug looked up. Stores name, RxCUI, and generic name.

**`drug_labels`** — FDA label text per drug (interactions, warnings, contraindications). One-to-one with drugs.

**`drug_interactions`** — pre-parsed interaction pairs between two drugs with severity classification. Stored as unordered pairs (lower drug ID always as drug_a) to prevent duplicates.

## Getting Started

### Prerequisites

- Python 3.12+
- Docker Desktop

### Setup

```bash
# Clone the repo
git clone https://github.com/yourusername/RxInteract.git
cd RxInteract

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start Postgres
docker compose up -d

# Run database migrations
alembic upgrade head

# Start the API
uvicorn app.main:app --reload
```

API runs at `http://localhost:8000`
Swagger UI at `http://localhost:8000/docs`

## API Endpoints

### Core

#### `POST /drugs/interactions/check`

Submit a list of 2–10 drug names and receive all known interactions found across their FDA labels.

```bash
curl -X POST http://localhost:8000/drugs/interactions/check \
  -H "Content-Type: application/json" \
  -d '{"drugs": ["warfarin", "aspirin", "ibuprofen"]}'
```

```json
{
  "drugs_checked": ["warfarin", "aspirin", "ibuprofen"],
  "total_interactions_found": 2,
  "interactions": [
    {
      "drug_1": "warfarin",
      "drug_2": "aspirin",
      "description": "Concurrent use of warfarin and aspirin may increase bleeding risk.",
      "severity": "high",
      "source": "OpenFDA Drug Label"
    }
  ]
}
```

#### `GET /drugs/interactions/{drug_name}?compare_with=drug1,drug2`

Get interactions for a single drug cross-referenced against an optional comma-separated list.

```bash
curl "http://localhost:8000/drugs/interactions/warfarin?compare_with=aspirin,ibuprofen"
```

### Supporting Endpoints

| Method | Endpoint                            | Description                 |
| ------ | ----------------------------------- | --------------------------- |
| GET    | `/drugs/lookup/{drug_name}`         | Resolve drug name to RxCUI  |
| GET    | `/drugs/properties/{drug_name}`     | RxNorm drug properties      |
| GET    | `/drugs/fda-label/{drug_name}`      | Full raw FDA label          |
| GET    | `/drugs/adverse-events/{drug_name}` | FAERS adverse event reports |
| GET    | `/health`                           | Health check                |

## Running Tests

```bash
pytest -v
```

14 unit tests covering the service layer cache-aside logic and all core endpoint behaviors including error cases.

## Data Sources

| Source                                           | Usage                                  | Auth                        |
| ------------------------------------------------ | -------------------------------------- | --------------------------- |
| [RxNorm (NIH NLM)](https://rxnav.nlm.nih.gov)    | Drug name → RxCUI resolution           | None required               |
| [OpenFDA](https://open.fda.gov/apis/drug/label/) | FDA label text, interactions, warnings | None required (240 req/min) |

## Disclaimer

This API is a portfolio project and is not intended for clinical or medical use. Always consult a licensed healthcare professional or pharmacist regarding drug interactions.
