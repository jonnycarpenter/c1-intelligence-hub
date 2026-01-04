import sys
import os
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from app.ingestion.orchestrator import IngestionOrchestrator
    from app.tools.press_releases.models import SearchResult
    from app.db.gcp_storage import DataSource

    # Mock config and db
    mock_config = MagicMock()
    mock_db = MagicMock()
    
    orchestrator = IngestionOrchestrator(mock_config)
    
    # Create a dummy result
    result = SearchResult(
        title="Test Article",
        url="https://example.com/article",
        snippet="This is a test snippet",
        score=0.9,
        published_date="2025-01-01T00:00:00Z"
    )
    
    company = {"id": "123", "name": "TestCorp", "stock_ticker": "TST"}
    
    # Test 1: Exa
    article_exa = orchestrator._convert_search_result_to_article(result, company, search_engine="exa")
    print(f"Exa Source Type: {article_exa.source_type}")
    assert article_exa.source_type == "web_news_exa"
    assert article_exa.raw_data["search_engine"] == "exa"

    # Test 2: Tavily
    article_tavily = orchestrator._convert_search_result_to_article(result, company, search_engine="tavily")
    print(f"Tavily Source Type: {article_tavily.source_type}")
    assert article_tavily.source_type == "web_news_tavily"
    assert article_tavily.raw_data["search_engine"] == "tavily"
    
    # Test 3: Default (None)
    article_default = orchestrator._convert_search_result_to_article(result, company)
    print(f"Default Source Type: {article_default.source_type}")
    assert article_default.source_type == "web_news"
    
    print("SUCCESS: Source type delineation verified.")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
