from typing import List, Dict, Any
from uuid import UUID
from backend.app.core.database import get_qdrant_client

# Authoritative Local Standard Operating Procedures (SOPs) fallback catalog
DEFAULT_SOPS = {
    "CROWD": [
        "SOP-CROWD-01: When crowd occupancy in any gate reaches 80% safe capacity, route incoming traffic to adjacent doors.",
        "SOP-CROWD-02: Deploy physical signboards and dispatch volunteers to assist verbal direction.",
        "SOP-CROWD-03: Coordinate with transit control to delay incoming shuttle waves until concourse clears."
    ],
    "TRANSPORT": [
        "SOP-TRANS-01: If metro service experiences delays > 15m, dispatch shuttle bus wave to Transport Hub.",
        "SOP-TRANS-02: Alert fans on video screens to remain inside stadium plaza food concessions to prevent gate congestion."
    ],
    "SECURITY": [
        "SOP-SEC-01: Isolate active threat zones immediately using security perimeter cordons.",
        "SOP-SEC-02: Dispatch tactical teams and redirect civilians away from threat radius."
    ]
}

from backend.app.core.logging import logger

async def retrieve_relevant_procedures(
    category: str,
    stadium_id: UUID,
    query_text: str
) -> List[str]:
    # Try connecting to Qdrant if configured
    try:
        client = get_qdrant_client()
        # Ensure collection exists before querying. In MVP, collection might not be seeded.
        collections = client.get_collections().collections
        exists = any(c.name == "stadium_procedures" for c in collections)
        
        if exists:
            # We mock the semantic vector search using client calls
            # In a real environment, we'd use OpenAI embeddings first:
            # embeddings = get_embeddings(query_text)
            # search_result = client.search(collection_name="stadium_procedures", query_vector=embeddings, limit=3)
            # For the demo, let's pull all items matching metadata filters
            results = client.scroll(
                collection_name="stadium_procedures",
                scroll_filter={"must": [{"key": "category", "match": {"value": category}}]},
                limit=3
            )[0]
            if results:
                return [r.payload["text"] for r in results]
    except Exception as e:
        logger.warning(
            f"Qdrant vector client unavailable or collection unseeded: {e}. Executing local SOP fallback.",
            extra={"correlation_id": str(stadium_id)}
        )


    # Fallback: Query default localized database dict
    return DEFAULT_SOPS.get(category.upper(), DEFAULT_SOPS["CROWD"])
