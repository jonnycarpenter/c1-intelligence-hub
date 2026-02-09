"""
ImportYeti Supply Chain Ingestion
==================================

Maps the competitive supply chain network around Composites One using
ImportYeti trade data (US Customs bills of lading). Builds a bipartite
graph of Companies (US importers) and Suppliers (overseas exporters)
with directional relationship edges stored in BigQuery.

Architecture mirrors the RPM Intelligence Hub reference implementation:
- 4-phase pipeline: Resolve → Companies → Suppliers → Stats
- BigQuery storage (companies, suppliers, edges, ingestion_log)
- 4 MCP agent tools for dynamic ad-hoc lookups

Tables created in BigQuery (c1_intelligence dataset):
- iy_companies: US importers (C1, competitors, discovered buyers)
- iy_suppliers: Overseas exporters/manufacturers
- iy_edges: Directional relationships (imports_from, supplies_to)
- iy_ingestion_log: Audit trail per pipeline run

Usage:
    # Run via CLI
    python -m app.ingestion.importyeti.run_importyeti --stats-only
    python -m app.ingestion.importyeti.run_importyeti --skip-suppliers
    python -m app.ingestion.importyeti.run_importyeti  # Full pipeline

    # Or from code
    from app.ingestion.importyeti.ingestion import IngestionPipeline
    pipeline = IngestionPipeline(api_key="your-key")
    pipeline.run()
"""
