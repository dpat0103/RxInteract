import httpx

RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"
OPENFDA_BASE = "https://api.fda.gov/drug"


async def get_rxcui(drug_name: str) -> dict:
    """
    Look up a drug's RxCUI identifier by name.
    A RXCUI is a unique number assigned to a specific drug or mediciation in US medicine database.
    """
    url = f"{RXNORM_BASE}/rxcui.json"
    params = {"name": drug_name, "search": 1}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def get_drug_properties(rxcui: str) -> dict:
    """
    Given an RxCUI, fetch the drug's properties from RxNorm.
    Returns name, drug class, TTY (term type), and related identifiers.
    """
    url = f"{RXNORM_BASE}/rxcui/{rxcui}/properties.json"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def get_fda_drug_interactions(drug_name: str) -> dict:
    """
    Fetch the drug_interactions and warnings sections from the FDA label.
    These fields contain FDA documented interaction text.
    Uses OR search so we match on either brand or generic name.
    """
    url = f"{OPENFDA_BASE}/label.json"
    params = {
        "search": f'openfda.brand_name:"{drug_name}"+openfda.generic_name:"{drug_name}"',
        "limit": 1
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, params=params)
        if response.status_code == 404:
            return {"results": [], "message": "No FDA label found"}
        response.raise_for_status()
        data = response.json()

    results = data.get("results", [])
    if not results:
        return {"drug_interactions": [], "warnings": [], "drug_name": drug_name}

    label = results[0]

    return {
        "drug_name": drug_name,
        "drug_interactions": label.get("drug_interactions", []),
        "warnings": label.get("warnings", []),
        "warnings_and_cautions": label.get("warnings_and_cautions", []),
        "contraindications": label.get("contraindications", []),
    }


async def get_fda_label(drug_name: str) -> dict:
    """
    Pull the FDA drug label for a given drug name.
    Returns warnings, contraindications, adverse reactions, and more.
    Limits to 1 result.
    """
    url = f"{OPENFDA_BASE}/label.json"
    params = {
        "search": f'openfda.brand_name:"{drug_name}"+openfda.generic_name:"{drug_name}"',
        "limit": 1
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, params=params)
        # 404 from OpenFDA just means no results — not a true error
        if response.status_code == 404:
            return {"results": [], "message": "No FDA label found for this drug"}
        response.raise_for_status()
        return response.json()


async def get_fda_adverse_events(drug_name: str, limit: int = 5) -> dict:
    """
    Fetch recent adverse event reports from OpenFDA for a given drug.
    """
    url = f"{OPENFDA_BASE}/event.json"
    params = {
        "search": f'patient.drug.medicinalproduct:"{drug_name}"',
        "limit": limit
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, params=params)
        if response.status_code == 404:
            return {"results": [], "message": "No adverse events found for this drug"}
        response.raise_for_status()
        return response.json()
