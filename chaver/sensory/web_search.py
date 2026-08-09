"""Web search sensory module — Chaver's eyes.

Uses the Tavily API to search the web. Results are encoded via the text
encoder, excited into working memory, and stored as hippocampal episodes.
This is how Chaver sees the world beyond his own memory.

Design discipline:
- Tavily is imported lazily so the module loads on deployments without it.
- search() is async; the sync Tavily client runs in a thread executor so
  it never blocks the event loop.
- web_search_enrich() is the only function heartbeat.py calls — it handles
  the full pipeline: search → encode → excite → store.
- No language faculty calls here. Results enter through the field, not
  through the mouth (CLAUDE.md principle 2).

Configuration:
    TAVILY_API_KEY=<key>     Required. Get from https://tavily.com
    CHAVER_SEARCH_RESULTS=5  Optional. Max results per query (default: 5).
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass


@dataclass
class SearchResult:
    """A single result returned from the web."""

    title: str
    url: str
    content: str
    score: float = 0.0


class WebSearch:
    """Tavily-backed web search — Chaver's eyes on the world.

    Instantiated at startup; lazy-imports tavily so the codebase loads
    cleanly on deployments that haven't installed it.
    """

    def __init__(self) -> None:
        self._client = None  # lazily initialised on first search

    @property
    def available(self) -> bool:
        """True if TAVILY_API_KEY is set in the environment."""
        return bool(os.environ.get("TAVILY_API_KEY", "").strip())

    def _get_client(self):
        """Lazy-init the Tavily client. Raises clearly if not configured."""
        if self._client is not None:
            return self._client
        try:
            from tavily import TavilyClient  # noqa: PLC0415 — lazy import
        except ImportError as exc:
            raise RuntimeError(
                "[web_search] tavily-python not installed — "
                "run: pip install tavily-python"
            ) from exc
        api_key = os.environ.get("TAVILY_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "[web_search] TAVILY_API_KEY not set — "
                "get a key at https://tavily.com and add it to .env"
            )
        self._client = TavilyClient(api_key=api_key)
        return self._client

    async def search(
        self, query: str, max_results: int | None = None
    ) -> list[SearchResult]:
        """Search the web and return structured results.

        Runs the sync Tavily client in a thread executor so it doesn't
        block the asyncio event loop.

        Args:
            query: What to look for.
            max_results: Override default result count.

        Returns:
            List of SearchResult objects, best first. Empty on error.
        """
        if not self.available:
            print("[web_search] TAVILY_API_KEY not set — skipping search")
            return []

        n = max_results or int(os.environ.get("CHAVER_SEARCH_RESULTS", "5"))

        def _sync_search() -> list[SearchResult]:
            client = self._get_client()
            response = client.search(query, max_results=n)
            results = []
            for item in response.get("results", []):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        content=item.get("content", ""),
                        score=float(item.get("score", 0.0)),
                    )
                )
            return results

        try:
            return await asyncio.to_thread(_sync_search)
        except Exception as exc:  # noqa: BLE001 — keep the mind alive
            print(f"[web_search] search error: {exc}")
            return []


async def web_search_enrich(
    state,
    query: str,
    max_results: int | None = None,
) -> int:
    """Search the web and load results into Chaver's working memory.

    This is the full sensory pipeline: fetch → encode → excite → store.
    Analogous to how hippocampal recall enriches working memory from
    internal memory, this enriches it from the external world.

    Args:
        state: The shared ChaverState (must have web_search, text_encoder,
               working_memory, and hippocampus populated).
        query: What to search for — typically the user's message or goal.
        max_results: Override default result count.

    Returns:
        Number of results successfully loaded into working memory.
    """
    if state.web_search is None or not state.web_search.available:
        return 0
    if state.text_encoder is None:
        return 0

    results = await state.web_search.search(query, max_results=max_results)
    if not results:
        return 0

    loaded = 0
    for i, result in enumerate(results):
        if not result.content.strip():
            continue

        # Combine title + content for richer encoding
        text = f"{result.title}\n{result.content}".strip()

        # Excite into working memory — search results ring alongside recalled
        # memories, giving the language faculty a world-enriched field.
        state.working_memory.excite(
            key=f"search:{i}:{result.url}",
            content=text,
            source="web_search",
            strength=0.6 + 0.2 * result.score,  # quality-weighted activation
            metadata={
                "url": result.url,
                "title": result.title,
                "search_score": result.score,
            },
        )

        # Encode and store as an episode so search results can be recalled
        # in future conversations — what Chaver sees becomes what he knows.
        if state.hippocampus is not None:
            try:
                vec = state.text_encoder.encode(text)
                joint = state.hippocampus.bind({"text": vec})
                state.hippocampus.store_episode(
                    key=f"web:{result.url}",
                    content=text,
                    joint_vector=joint,
                    modalities=["text"],
                    source="web_search",
                    activation=0.5 + 0.2 * result.score,
                    meta={
                        "url": result.url,
                        "title": result.title,
                        "query": query,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[web_search] episode store error: {exc}")

        loaded += 1

    if loaded:
        print(f"[web_search] {loaded} result(s) for '{query[:60]}' loaded into field")

    return loaded
