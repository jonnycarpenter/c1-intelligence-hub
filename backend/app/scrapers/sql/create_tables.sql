-- ============================================================================
-- C1 Intelligence Hub - Datasheet Scraper Tables
-- ============================================================================
-- Run this script to create the required BigQuery tables.
--
-- Usage:
--   bq query --use_legacy_sql=false < create_tables.sql
--
-- Or run each statement individually in the BigQuery console.
-- ============================================================================

-- Create dataset if it doesn't exist
-- CREATE SCHEMA IF NOT EXISTS `ketzero-consulting.c1_intelligence`;

-- ============================================================================
-- Table 1: datasheets
-- Core table storing all scraped datasheets
-- ============================================================================

CREATE TABLE IF NOT EXISTS `ketzero-consulting.c1_intelligence.datasheets` (
  -- Primary key
  datasheet_id STRING NOT NULL,
  
  -- Supplier info
  supplier_name STRING NOT NULL,
  
  -- Product identification
  product_name STRING,
  product_family STRING,
  title STRING,
  url STRING NOT NULL,
  filename STRING,
  
  -- Classification
  material_category STRING,
  material_subcategory STRING,
  industries ARRAY<STRING>,
  
  -- Content
  extracted_text STRING,
  text_preview STRING,
  page_count INT64,
  text_extraction_success BOOL,
  
  -- Structured properties (LLM-extracted, stored as JSON)
  structured_properties JSON,
  properties_extracted_at TIMESTAMP,
  
  -- File metadata
  file_size_bytes INT64,
  file_hash STRING,
  content_type STRING DEFAULT 'application/pdf',
  
  -- Tracking
  scrape_run_id STRING,
  discovered_at TIMESTAMP,
  downloaded_at TIMESTAMP,
  last_verified_at TIMESTAMP,
  is_active BOOL DEFAULT TRUE,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(created_at)
CLUSTER BY supplier_name, material_category
OPTIONS (
  description = 'Technical datasheets scraped from composite material suppliers',
  labels = [('module', 'datasheet_scraper'), ('data_type', 'documents')]
);


-- ============================================================================
-- Table 2: datasheet_scrape_runs
-- Tracks each scraping run for monitoring and health checks
-- ============================================================================

CREATE TABLE IF NOT EXISTS `ketzero-consulting.c1_intelligence.datasheet_scrape_runs` (
  -- Run identification
  run_id STRING NOT NULL,
  run_date TIMESTAMP NOT NULL,
  run_type STRING,  -- 'scheduled', 'manual', 'backfill'
  
  -- Per-supplier stats
  supplier_name STRING NOT NULL,
  datasheets_discovered INT64,
  datasheets_downloaded INT64,
  datasheets_skipped INT64,
  datasheets_failed INT64,
  
  -- Error tracking (JSON array of error objects)
  errors JSON,
  
  -- Performance
  duration_seconds FLOAT64,
  
  -- Status
  status STRING,  -- 'success', 'partial', 'failed'
  error_message STRING,
  
  -- Timestamp
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(run_date)
CLUSTER BY supplier_name
OPTIONS (
  description = 'Tracking table for datasheet scraping runs',
  labels = [('module', 'datasheet_scraper'), ('data_type', 'metrics')]
);


-- ============================================================================
-- Table 3: datasheet_suppliers
-- Configuration and status for each supplier
-- ============================================================================

CREATE TABLE IF NOT EXISTS `ketzero-consulting.c1_intelligence.datasheet_suppliers` (
  -- Identification
  supplier_id STRING NOT NULL,
  supplier_name STRING NOT NULL,
  display_name STRING,
  website STRING,
  datasheet_index_url STRING,
  
  -- Scraper config
  scraper_class STRING,
  is_enabled BOOL DEFAULT TRUE,
  requires_javascript BOOL DEFAULT FALSE,
  
  -- Health tracking
  last_successful_scrape TIMESTAMP,
  last_failed_scrape TIMESTAMP,
  consecutive_failures INT64 DEFAULT 0,
  
  -- Metadata
  primary_materials ARRAY<STRING>,
  primary_industries ARRAY<STRING>,
  notes STRING,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
OPTIONS (
  description = 'Configuration and status for datasheet suppliers',
  labels = [('module', 'datasheet_scraper'), ('data_type', 'config')]
);


-- ============================================================================
-- Insert initial supplier configuration
-- ============================================================================

-- Clear existing data (idempotent)
DELETE FROM `ketzero-consulting.c1_intelligence.datasheet_suppliers` WHERE TRUE;

-- Insert supplier configurations
INSERT INTO `ketzero-consulting.c1_intelligence.datasheet_suppliers` (
  supplier_id, supplier_name, display_name, website, datasheet_index_url,
  scraper_class, is_enabled, requires_javascript,
  primary_materials, primary_industries, notes
) VALUES
  (
    'hexcel', 'Hexcel', 'Hexcel Corporation',
    'https://www.hexcel.com',
    'https://www.hexcel.com/Resources/DataSheets/',
    'HexcelScraper', TRUE, FALSE,
    ['carbon_fiber', 'prepreg', 'core_honeycomb', 'adhesive'],
    ['aerospace', 'defense', 'space'],
    'Major aerospace carbon fiber and prepreg supplier'
  ),
  (
    'owens_corning', 'Owens Corning', 'Owens Corning Composites',
    'https://www.owenscorning.com',
    'https://www.owenscorning.com/en-us/composites/resources-support/technical-resources',
    'OwensCorningScraper', TRUE, FALSE,
    ['glass_fiber', 'fabric'],
    ['marine', 'construction', 'wind_energy', 'automotive'],
    'Leading glass fiber manufacturer'
  ),
  (
    'toray', 'Toray', 'Toray Composite Materials America',
    'https://www.toraytac.com',
    'https://www.toraytac.com/resources/datasheets',
    'TorayScraper', TRUE, FALSE,
    ['carbon_fiber', 'prepreg'],
    ['aerospace', 'automotive', 'sports'],
    'World leader in carbon fiber production'
  ),
  (
    'polynt', 'Polynt-Reichhold', 'Polynt-Reichhold Group',
    'https://www.polynt.com',
    'https://www.polynt.com/composites/',
    'PolyntScraper', TRUE, FALSE,
    ['resin_polyester', 'resin_vinylester'],
    ['marine', 'construction', 'transportation'],
    'Major resin supplier - polyester and vinyl ester'
  ),
  (
    'gurit', 'Gurit', 'Gurit Holding AG',
    'https://www.gurit.com',
    'https://www.gurit.com/products/',
    'GuritScraper', TRUE, FALSE,
    ['prepreg', 'core_foam', 'adhesive'],
    ['wind_energy', 'marine', 'transportation'],
    'Wind energy and marine composites specialist'
  );


-- ============================================================================
-- Create useful views
-- ============================================================================

-- View: Active datasheets summary
CREATE OR REPLACE VIEW `ketzero-consulting.c1_intelligence.v_datasheet_summary` AS
SELECT 
  supplier_name,
  material_category,
  COUNT(*) as datasheet_count,
  COUNTIF(text_extraction_success) as with_extracted_text,
  SUM(file_size_bytes) / 1024 / 1024 as total_size_mb,
  MAX(downloaded_at) as latest_download
FROM `ketzero-consulting.c1_intelligence.datasheets`
WHERE is_active = TRUE
GROUP BY supplier_name, material_category
ORDER BY supplier_name, datasheet_count DESC;


-- View: Recent scrape health
CREATE OR REPLACE VIEW `ketzero-consulting.c1_intelligence.v_scrape_health` AS
SELECT 
  supplier_name,
  COUNT(*) as runs_last_30d,
  COUNTIF(status = 'success') as successful_runs,
  COUNTIF(status = 'failed') as failed_runs,
  MAX(run_date) as last_run,
  AVG(duration_seconds) as avg_duration_seconds,
  SUM(datasheets_downloaded) as total_downloaded,
  SUM(datasheets_failed) as total_errors
FROM `ketzero-consulting.c1_intelligence.datasheet_scrape_runs`
WHERE run_date > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY supplier_name;


-- ============================================================================
-- Indexes (BigQuery uses clustering instead of traditional indexes)
-- The tables above are already clustered by supplier_name and material_category
-- ============================================================================

-- For text search, consider adding a Search Index in the future:
-- CREATE SEARCH INDEX datasheet_search_idx
-- ON `ketzero-consulting.c1_intelligence.datasheets`(extracted_text);


-- ============================================================================
-- Grant permissions (adjust as needed for your project)
-- ============================================================================

-- Example: Grant read access to a service account
-- GRANT `roles/bigquery.dataViewer`
-- ON SCHEMA `ketzero-consulting.c1_intelligence`
-- TO "serviceAccount:c1-hub-backend@ketzero-consulting.iam.gserviceaccount.com";
