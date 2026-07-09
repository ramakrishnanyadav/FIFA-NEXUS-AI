"""
backend/app/ai/vector.py — SOP Retrieval Engine

Retrieves relevant Standard Operating Procedures for a given operational scenario.

When Qdrant is available and an OpenAI API key is configured, performs genuine
semantic vector search by embedding the query text via OpenAI's text-embedding-3-small
model and querying the nearest-neighbour SOP documents.

Falls back to structured keyword-based catalog retrieval (category filter) when
Qdrant is unavailable or the OpenAI key is absent.
"""
from uuid import UUID
from backend.app.core.database import get_qdrant_client
from backend.app.core.config import settings
from backend.app.core.logging import logger

# Authoritative Local SOP fallback catalog
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


async def _embed_query(query_text: str) -> list[float]:
    """
    Generate an embedding vector using OpenAI text-embedding-3-small.
    Only called when OPENAI_API_KEY is configured — Featherless does not support embeddings.
    """
    import openai
    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=query_text
    )
    return response.data[0].embedding


async def retrieve_relevant_procedures(
    category: str,
    stadium_id: UUID,
    query_text: str
) -> list[str]:
    """
    Retrieves relevant SOPs for an operational query.

    Execution path:
    1. If Qdrant is available AND OPENAI_API_KEY is set:
       → Embed query via text-embedding-3-small → semantic nearest-neighbour search
    2. If Qdrant is available but no OpenAI embeddings key (e.g. Featherless provider):
       → Category metadata filter (structured retrieval, no vector search)
    3. If Qdrant is unavailable:
       → Return static SOP catalog for the matching category
    """
    # Embeddings require OpenAI specifically — Featherless does not support the /embeddings endpoint
    has_openai_embeddings = bool(settings.OPENAI_API_KEY)

    try:
        client = get_qdrant_client()
        collections = client.get_collections().collections
        exists = any(c.name == "stadium_procedures" for c in collections)

        if exists:
            if has_openai_embeddings:
                try:
                    query_vector = await _embed_query(query_text)
                    search_result = client.search(
                        collection_name="stadium_procedures",
                        query_vector=query_vector,
                        limit=3
                    )
                    if search_result:
                        logger.info(
                            f"Semantic RAG: retrieved {len(search_result)} SOPs for '{query_text[:60]}'",
                            extra={"correlation_id": str(stadium_id)}
                        )
                        return [r.payload["text"] for r in search_result if r.payload]
                except Exception as embed_err:
                    logger.warning(
                        f"OpenAI embedding failed: {embed_err}. Falling back to category filter.",
                        extra={"correlation_id": str(stadium_id)}
                    )
            else:
                logger.info(
                    "Featherless provider active — using category-filter SOP retrieval (no embeddings).",
                    extra={"correlation_id": str(stadium_id)}
                )

            # Structured category filter (Featherless path or embedding failure fallback)
            results = client.scroll(
                collection_name="stadium_procedures",
                scroll_filter={"must": [{"key": "category", "match": {"value": category}}]},
                limit=3
            )[0]
            if results:
                return [r.payload["text"] for r in results if r.payload]

    except Exception as e:
        logger.warning(
            f"Qdrant unavailable or collection unseeded: {e}. Using local SOP catalog.",
            extra={"correlation_id": str(stadium_id)}
        )

    return DEFAULT_SOPS.get(category.upper(), DEFAULT_SOPS["CROWD"])
