"""
Semantic Search for Structured Intelligence Tables
====================================================

Provides vector-based semantic search for earnings_quotes, sec_filing_nuggets,
and podcast_quotes tables using the same Vertex AI embeddings as the article
corpus (text-embedding-004, 768 dims).

Problem solved:
    Previously these tables used SQL LIKE '%query%' for search, which failed on
    natural-language queries like "any themes related to hexcel" because the
    literal string doesn't appear in quote text. Semantic search matches by
    meaning instead.

Architecture:
    - Reuses EmbeddingGenerator from bq_vector_store.py (singleton)
    - Each table gets an `embedding` column (FLOAT64 REPEATED) populated at
      ingestion time
    - Query method: embed the user query → ML.DISTANCE cosine search → filter
      by metadata (ticker, type, etc.) → ORDER BY distance ASC

Usage:
    from app.db.semantic_search import get_semantic_searcher

    searcher = await get_semantic_searcher()
    results = await searcher.search_earnings_quotes("hexcel guidance", limit=15)
"""

import json
import time
from typing import List, Dict, Any, Optional

from app.utils.logger import get_logger
from app.db.gcp_storage import gcp_config, GCPConfig

logger = get_logger(__name__)


class SemanticSearcher:
    """
    Semantic search across structured intelligence tables.

    Uses the same EmbeddingGenerator singleton as BigQueryVectorStore to avoid
    initializing Vertex AI multiple times.
    """

    def __init__(self, config: Optional[GCPConfig] = None):
        self.config = config or gcp_config
        self._client = None
        self._embedder = None
        self._initialized = False

    @property
    def client(self):
        if self._client is None:
            from google.cloud import bigquery
            self._client = bigquery.Client(project=self.config.project_id)
        return self._client

    @property
    def is_available(self) -> bool:
        return self._initialized and self._embedder is not None and self._embedder.is_available

    async def initialize(self):
        """Initialize embedder (reuses singleton from bq_vector_store)."""
        if self._initialized:
            return

        from app.db.bq_vector_store import EmbeddingGenerator
        self._embedder = EmbeddingGenerator()
        await self._embedder.initialize()

        if not self._embedder.is_available:
            logger.warning("[SEMANTIC_SEARCH] Embedding model not available — falling back to LIKE search")
        else:
            logger.info("[SEMANTIC_SEARCH] Initialized with Vertex AI embeddings")

        self._initialized = True

    # =========================================================================
    # Embedding helpers
    # =========================================================================

    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text string."""
        if not self._embedder or not self._embedder.is_available:
            return []
        return await self._embedder.embed_text(text)

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts."""
        if not self._embedder or not self._embedder.is_available:
            return []
        return await self._embedder.embed_texts(texts)

    def build_embed_text_for_earnings(self, row: Dict[str, Any]) -> str:
        """Build the searchable text blob for an earnings quote embedding."""
        parts = []
        if row.get("company_name"):
            parts.append(row["company_name"])
        if row.get("ticker"):
            parts.append(row["ticker"])
        if row.get("speaker_name"):
            parts.append(f"Speaker: {row['speaker_name']}")
        if row.get("speaker_role"):
            parts.append(f"Role: {row['speaker_role']}")
        if row.get("quote_type"):
            parts.append(f"Type: {row['quote_type']}")
        if row.get("quote_text"):
            parts.append(row["quote_text"])
        if row.get("context_summary"):
            parts.append(row["context_summary"])
        return " | ".join(parts)

    def build_embed_text_for_sec(self, row: Dict[str, Any]) -> str:
        """Build the searchable text blob for a SEC nugget embedding."""
        parts = []
        if row.get("company_name"):
            parts.append(row["company_name"])
        if row.get("ticker"):
            parts.append(row["ticker"])
        if row.get("filing_type"):
            parts.append(f"Filing: {row['filing_type']}")
        if row.get("nugget_type"):
            parts.append(f"Type: {row['nugget_type']}")
        if row.get("nugget_text"):
            parts.append(row["nugget_text"])
        if row.get("context_text"):
            parts.append(row["context_text"])
        # Include named entities for better matching
        for field in ("companies_mentioned", "competitors_named", "brands_mentioned"):
            val = row.get(field)
            if val:
                if isinstance(val, str):
                    try:
                        val = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        val = [val]
                if isinstance(val, list):
                    parts.append(", ".join(str(v) for v in val))
        return " | ".join(parts)

    def build_embed_text_for_podcast(self, row: Dict[str, Any]) -> str:
        """Build the searchable text blob for a podcast quote embedding."""
        parts = []
        if row.get("podcast_name"):
            parts.append(row["podcast_name"])
        if row.get("speaker_name"):
            parts.append(f"Speaker: {row['speaker_name']}")
        if row.get("speaker_company"):
            parts.append(row["speaker_company"])
        if row.get("quote_text"):
            parts.append(row["quote_text"])
        if row.get("context_summary"):
            parts.append(row["context_summary"])
        # Themes
        themes = row.get("themes")
        if themes:
            if isinstance(themes, str):
                try:
                    themes = json.loads(themes)
                except (json.JSONDecodeError, TypeError):
                    themes = [themes]
            if isinstance(themes, list):
                parts.append(", ".join(str(t) for t in themes))
        return " | ".join(parts)

    # =========================================================================
    # Vector search queries
    # =========================================================================

    async def search_earnings_quotes(
        self,
        query: str,
        ticker: Optional[str] = None,
        quote_type: Optional[str] = None,
        speaker_role: Optional[str] = None,
        section: Optional[str] = None,
        year: Optional[int] = None,
        quarter: Optional[int] = None,
        themes: Optional[List[str]] = None,
        quotable_only: bool = False,
        min_relevance: float = 0.0,
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        """Semantic search over earnings_quotes using vector embeddings.

        Falls back to LIKE search if embeddings are not available.
        """
        start = time.time()
        table_id = f"{self.config.full_dataset_id}.earnings_quotes"

        # Build metadata filters
        conditions, params = self._build_earnings_filters(
            ticker=ticker, quote_type=quote_type, speaker_role=speaker_role,
            section=section, year=year, quarter=quarter, themes=themes,
            quotable_only=quotable_only, min_relevance=min_relevance,
        )

        # Try vector search first
        if self.is_available:
            query_embedding = await self.embed_text(query)
            if query_embedding:
                results = await self._vector_search_table(
                    table_id=table_id,
                    query_embedding=query_embedding,
                    conditions=conditions,
                    params=params,
                    order_cols="distance ASC",
                    limit=limit,
                    embedding_col="embedding",
                )
                elapsed = time.time() - start
                logger.info(f"[SEMANTIC_SEARCH] earnings_quotes vector search: {len(results)} results in {elapsed:.2f}s")
                return results

        # Fallback: LIKE search (original behavior)
        logger.info("[SEMANTIC_SEARCH] Falling back to LIKE search for earnings_quotes")
        return await self._like_search_earnings(query, conditions, params, table_id, limit)

    async def search_sec_nuggets(
        self,
        query: str,
        ticker: Optional[str] = None,
        nugget_type: Optional[str] = None,
        section: Optional[str] = None,
        signal_strength: Optional[str] = None,
        fiscal_year: Optional[int] = None,
        themes: Optional[List[str]] = None,
        actionable_only: bool = False,
        new_disclosures_only: bool = False,
        min_relevance: float = 0.0,
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        """Semantic search over sec_filing_nuggets using vector embeddings."""
        start = time.time()
        table_id = f"{self.config.full_dataset_id}.sec_filing_nuggets"

        conditions, params = self._build_sec_filters(
            ticker=ticker, nugget_type=nugget_type, section=section,
            signal_strength=signal_strength, fiscal_year=fiscal_year,
            themes=themes, actionable_only=actionable_only,
            new_disclosures_only=new_disclosures_only, min_relevance=min_relevance,
        )

        if self.is_available:
            query_embedding = await self.embed_text(query)
            if query_embedding:
                results = await self._vector_search_table(
                    table_id=table_id,
                    query_embedding=query_embedding,
                    conditions=conditions,
                    params=params,
                    order_cols="distance ASC",
                    limit=limit,
                    embedding_col="embedding",
                )
                elapsed = time.time() - start
                logger.info(f"[SEMANTIC_SEARCH] sec_filing_nuggets vector search: {len(results)} results in {elapsed:.2f}s")
                return results

        logger.info("[SEMANTIC_SEARCH] Falling back to LIKE search for sec_filing_nuggets")
        return await self._like_search_sec(query, conditions, params, table_id, limit)

    async def search_podcast_quotes(
        self,
        query: str,
        themes: Optional[List[str]] = None,
        podcast_name: Optional[str] = None,
        speaker_name: Optional[str] = None,
        days: int = 90,
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        """Semantic search over podcast_quotes using vector embeddings."""
        start = time.time()
        table_id = f"{self.config.full_dataset_id}.podcast_quotes"

        conditions, params = self._build_podcast_filters(
            themes=themes, podcast_name=podcast_name,
            speaker_name=speaker_name, days=days,
        )

        if self.is_available:
            query_embedding = await self.embed_text(query)
            if query_embedding:
                results = await self._vector_search_table(
                    table_id=table_id,
                    query_embedding=query_embedding,
                    conditions=conditions,
                    params=params,
                    order_cols="distance ASC",
                    limit=limit,
                    embedding_col="embedding",
                )
                elapsed = time.time() - start
                logger.info(f"[SEMANTIC_SEARCH] podcast_quotes vector search: {len(results)} results in {elapsed:.2f}s")
                return results

        logger.info("[SEMANTIC_SEARCH] Falling back to LIKE search for podcast_quotes")
        return await self._like_search_podcast(query, conditions, params, table_id, limit)

    # =========================================================================
    # Core vector search
    # =========================================================================

    async def _vector_search_table(
        self,
        table_id: str,
        query_embedding: List[float],
        conditions: List[str],
        params: list,
        order_cols: str,
        limit: int,
        embedding_col: str = "embedding",
    ) -> List[Dict[str, Any]]:
        """Execute ML.DISTANCE vector search on any table with an embedding column."""
        from google.cloud.bigquery import QueryJobConfig

        # Only search rows that have embeddings
        conditions = list(conditions)  # copy
        conditions.append(f"base.{embedding_col} IS NOT NULL")
        conditions.append(f"ARRAY_LENGTH(base.{embedding_col}) > 0")

        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        embedding_str = ", ".join(str(x) for x in query_embedding)

        sql = f"""
        WITH query_embedding AS (
            SELECT [{embedding_str}] AS embedding
        )
        SELECT
            base.*,
            ML.DISTANCE(base.{embedding_col}, query.embedding, 'COSINE') AS distance
        FROM `{table_id}` base
        CROSS JOIN query_embedding query
        {where_sql}
        ORDER BY {order_cols}
        LIMIT {limit}
        """

        try:
            job_config = QueryJobConfig(query_parameters=params)
            rows = self.client.query(sql, job_config=job_config).result()
            results = []
            for row in rows:
                d = dict(row)
                # Convert distance to similarity score
                dist = d.pop("distance", 1.0)
                d["semantic_score"] = 1.0 - (float(dist) if dist else 1.0)
                # Remove raw embedding from results to save bandwidth
                d.pop(embedding_col, None)
                results.append(d)
            return results
        except Exception as e:
            logger.error(f"[SEMANTIC_SEARCH] Vector search failed on {table_id}: {e}", exc_info=True)
            return []

    # =========================================================================
    # Filter builders
    # =========================================================================

    def _build_earnings_filters(self, **kwargs):
        from google.cloud.bigquery import ScalarQueryParameter
        conditions = []
        params = []

        if kwargs.get("ticker"):
            conditions.append("base.ticker = @ticker")
            params.append(ScalarQueryParameter("ticker", "STRING", kwargs["ticker"].upper()))
        if kwargs.get("quote_type"):
            conditions.append("base.quote_type = @quote_type")
            params.append(ScalarQueryParameter("quote_type", "STRING", kwargs["quote_type"].lower()))
        if kwargs.get("speaker_role"):
            conditions.append("base.speaker_role = @speaker_role")
            params.append(ScalarQueryParameter("speaker_role", "STRING", kwargs["speaker_role"].lower()))
        if kwargs.get("section"):
            conditions.append("base.call_section = @section")
            params.append(ScalarQueryParameter("section", "STRING", kwargs["section"].lower()))
        if kwargs.get("year"):
            conditions.append("base.year = @year")
            params.append(ScalarQueryParameter("year", "INT64", kwargs["year"]))
        if kwargs.get("quarter"):
            conditions.append("base.quarter = @quarter")
            params.append(ScalarQueryParameter("quarter", "INT64", kwargs["quarter"]))
        if kwargs.get("quotable_only"):
            conditions.append("base.is_quotable = TRUE")
        if kwargs.get("min_relevance", 0) > 0:
            conditions.append("base.relevance_score >= @min_relevance")
            params.append(ScalarQueryParameter("min_relevance", "FLOAT64", kwargs["min_relevance"]))
        if kwargs.get("themes"):
            for i, theme in enumerate(kwargs["themes"]):
                pn = f"theme_{i}"
                conditions.append(f"LOWER(base.themes) LIKE @{pn}")
                params.append(ScalarQueryParameter(pn, "STRING", f"%{theme.lower()}%"))

        return conditions, params

    def _build_sec_filters(self, **kwargs):
        from google.cloud.bigquery import ScalarQueryParameter
        conditions = []
        params = []

        if kwargs.get("ticker"):
            conditions.append("base.ticker = @ticker")
            params.append(ScalarQueryParameter("ticker", "STRING", kwargs["ticker"].upper()))
        if kwargs.get("nugget_type"):
            conditions.append("base.nugget_type = @nugget_type")
            params.append(ScalarQueryParameter("nugget_type", "STRING", kwargs["nugget_type"].lower()))
        if kwargs.get("section"):
            conditions.append("base.section = @section")
            params.append(ScalarQueryParameter("section", "STRING", kwargs["section"].lower()))
        if kwargs.get("signal_strength"):
            conditions.append("base.signal_strength = @signal_strength")
            params.append(ScalarQueryParameter("signal_strength", "STRING", kwargs["signal_strength"].lower()))
        if kwargs.get("fiscal_year"):
            conditions.append("base.fiscal_year = @fiscal_year")
            params.append(ScalarQueryParameter("fiscal_year", "INT64", kwargs["fiscal_year"]))
        if kwargs.get("actionable_only"):
            conditions.append("base.is_actionable = TRUE")
        if kwargs.get("new_disclosures_only"):
            conditions.append("base.is_new_disclosure = TRUE")
        if kwargs.get("min_relevance", 0) > 0:
            conditions.append("base.relevance_score >= @min_relevance")
            params.append(ScalarQueryParameter("min_relevance", "FLOAT64", kwargs["min_relevance"]))
        if kwargs.get("themes"):
            for i, theme in enumerate(kwargs["themes"]):
                pn = f"theme_{i}"
                conditions.append(f"LOWER(base.themes) LIKE @{pn}")
                params.append(ScalarQueryParameter(pn, "STRING", f"%{theme.lower()}%"))

        return conditions, params

    def _build_podcast_filters(self, **kwargs):
        from google.cloud.bigquery import ScalarQueryParameter
        conditions = [
            f"base.published_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {kwargs.get('days', 90)} DAY)"
        ]
        params = []

        if kwargs.get("podcast_name"):
            conditions.append("LOWER(base.podcast_name) LIKE @podcast_pattern")
            params.append(ScalarQueryParameter("podcast_pattern", "STRING", f"%{kwargs['podcast_name'].lower()}%"))
        if kwargs.get("speaker_name"):
            conditions.append("LOWER(base.speaker_name) LIKE @speaker_pattern")
            params.append(ScalarQueryParameter("speaker_pattern", "STRING", f"%{kwargs['speaker_name'].lower()}%"))
        if kwargs.get("themes"):
            for i, theme in enumerate(kwargs["themes"]):
                pn = f"theme_{i}"
                conditions.append(f"LOWER(base.themes) LIKE @{pn}")
                params.append(ScalarQueryParameter(pn, "STRING", f"%{theme.lower()}%"))

        return conditions, params

    # =========================================================================
    # LIKE fallbacks (original behavior when embeddings unavailable)
    # =========================================================================

    async def _like_search_earnings(self, query, conditions, params, table_id, limit):
        from google.cloud.bigquery import ScalarQueryParameter, QueryJobConfig
        conditions = list(conditions)
        conditions.append(
            "(LOWER(base.quote_text) LIKE @search_pattern "
            "OR LOWER(base.context_summary) LIKE @search_pattern "
            "OR LOWER(base.companies_mentioned) LIKE @search_pattern "
            "OR LOWER(base.speaker_name) LIKE @search_pattern "
            "OR LOWER(base.company_name) LIKE @search_pattern "
            "OR LOWER(base.speaker_company) LIKE @search_pattern)"
        )
        params = list(params)
        params.append(ScalarQueryParameter("search_pattern", "STRING", f"%{query.lower()}%"))
        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM `{table_id}` base {where_sql} ORDER BY base.relevance_score DESC, base.year DESC, base.quarter DESC LIMIT {limit}"
        try:
            job_config = QueryJobConfig(query_parameters=params)
            rows = self.client.query(sql, job_config=job_config).result()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"[SEMANTIC_SEARCH] LIKE fallback failed (earnings): {e}")
            return []

    async def _like_search_sec(self, query, conditions, params, table_id, limit):
        from google.cloud.bigquery import ScalarQueryParameter, QueryJobConfig
        conditions = list(conditions)
        conditions.append(
            "(LOWER(base.nugget_text) LIKE @search_pattern "
            "OR LOWER(base.companies_mentioned) LIKE @search_pattern "
            "OR LOWER(base.competitors_named) LIKE @search_pattern "
            "OR LOWER(base.brands_mentioned) LIKE @search_pattern "
            "OR LOWER(base.company_name) LIKE @search_pattern)"
        )
        params = list(params)
        params.append(ScalarQueryParameter("search_pattern", "STRING", f"%{query.lower()}%"))
        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM `{table_id}` base {where_sql} ORDER BY base.relevance_score DESC, base.fiscal_year DESC LIMIT {limit}"
        try:
            job_config = QueryJobConfig(query_parameters=params)
            rows = self.client.query(sql, job_config=job_config).result()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"[SEMANTIC_SEARCH] LIKE fallback failed (sec): {e}")
            return []

    async def _like_search_podcast(self, query, conditions, params, table_id, limit):
        from google.cloud.bigquery import ScalarQueryParameter, QueryJobConfig
        conditions = list(conditions)
        conditions.append(
            "(LOWER(base.quote_text) LIKE @search_pattern "
            "OR LOWER(base.context_summary) LIKE @search_pattern "
            "OR LOWER(base.speaker_name) LIKE @search_pattern)"
        )
        params = list(params)
        params.append(ScalarQueryParameter("search_pattern", "STRING", f"%{query.lower()}%"))
        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM `{table_id}` base {where_sql} ORDER BY base.relevance_score DESC, base.published_at DESC LIMIT {limit}"
        try:
            job_config = QueryJobConfig(query_parameters=params)
            rows = self.client.query(sql, job_config=job_config).result()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"[SEMANTIC_SEARCH] LIKE fallback failed (podcast): {e}")
            return []


# =============================================================================
# Singleton
# =============================================================================

_semantic_searcher: Optional[SemanticSearcher] = None


async def get_semantic_searcher() -> SemanticSearcher:
    """Get or create the semantic searcher singleton."""
    global _semantic_searcher
    if _semantic_searcher is None:
        _semantic_searcher = SemanticSearcher()
        await _semantic_searcher.initialize()
    return _semantic_searcher
