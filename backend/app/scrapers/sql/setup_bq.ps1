# ============================================================================
# Setup BigQuery tables for Datasheet Scraper
# ============================================================================
# Run this from the sql/ directory:
#   .\setup_bq.ps1
# ============================================================================

$PROJECT = "<GCP_PROJECT_ID>"
$DATASET = "c1_intelligence"

Write-Host "Creating BigQuery tables for Datasheet Scraper..." -ForegroundColor Cyan

# Check if dataset exists, create if not
Write-Host "`n[1/5] Checking dataset..." -ForegroundColor Yellow
$datasetExists = bq ls --project_id=$PROJECT | Select-String $DATASET
if (-not $datasetExists) {
    Write-Host "Creating dataset $DATASET..."
    bq mk --dataset --location=US "$PROJECT`:$DATASET"
} else {
    Write-Host "Dataset $DATASET already exists"
}

# Create tables one by one (BigQuery doesn't support multiple statements in one query)
Write-Host "`n[2/5] Creating datasheets table..." -ForegroundColor Yellow
bq query --use_legacy_sql=false --project_id=$PROJECT @"
CREATE TABLE IF NOT EXISTS ``$PROJECT.$DATASET.datasheets`` (
  datasheet_id STRING NOT NULL,
  supplier_name STRING NOT NULL,
  product_name STRING,
  product_family STRING,
  title STRING,
  url STRING NOT NULL,
  filename STRING,
  material_category STRING,
  material_subcategory STRING,
  industries ARRAY<STRING>,
  extracted_text STRING,
  text_preview STRING,
  page_count INT64,
  text_extraction_success BOOL,
  structured_properties JSON,
  properties_extracted_at TIMESTAMP,
  file_size_bytes INT64,
  file_hash STRING,
  content_type STRING DEFAULT 'application/pdf',
  scrape_run_id STRING,
  discovered_at TIMESTAMP,
  downloaded_at TIMESTAMP,
  last_verified_at TIMESTAMP,
  is_active BOOL DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(created_at)
CLUSTER BY supplier_name, material_category
"@

Write-Host "`n[3/5] Creating datasheet_scrape_runs table..." -ForegroundColor Yellow
bq query --use_legacy_sql=false --project_id=$PROJECT @"
CREATE TABLE IF NOT EXISTS ``$PROJECT.$DATASET.datasheet_scrape_runs`` (
  run_id STRING NOT NULL,
  run_date TIMESTAMP NOT NULL,
  run_type STRING,
  supplier_name STRING NOT NULL,
  datasheets_discovered INT64,
  datasheets_downloaded INT64,
  datasheets_skipped INT64,
  datasheets_failed INT64,
  errors JSON,
  duration_seconds FLOAT64,
  status STRING,
  error_message STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(run_date)
CLUSTER BY supplier_name
"@

Write-Host "`n[4/5] Creating datasheet_suppliers table..." -ForegroundColor Yellow
bq query --use_legacy_sql=false --project_id=$PROJECT @"
CREATE TABLE IF NOT EXISTS ``$PROJECT.$DATASET.datasheet_suppliers`` (
  supplier_id STRING NOT NULL,
  supplier_name STRING NOT NULL,
  display_name STRING,
  website STRING,
  datasheet_index_url STRING,
  scraper_class STRING,
  is_enabled BOOL DEFAULT TRUE,
  requires_javascript BOOL DEFAULT FALSE,
  last_successful_scrape TIMESTAMP,
  last_failed_scrape TIMESTAMP,
  consecutive_failures INT64 DEFAULT 0,
  primary_materials ARRAY<STRING>,
  primary_industries ARRAY<STRING>,
  notes STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
"@

Write-Host "`n[5/5] Seeding supplier configuration..." -ForegroundColor Yellow
bq query --use_legacy_sql=false --project_id=$PROJECT @"
MERGE ``$PROJECT.$DATASET.datasheet_suppliers`` AS target
USING (
  SELECT * FROM UNNEST([
    STRUCT('hexcel' AS supplier_id, 'Hexcel' AS supplier_name, 'Hexcel Corporation' AS display_name, 
           'https://www.hexcel.com' AS website, 'https://www.hexcel.com/Resources/DataSheets/' AS datasheet_index_url,
           'HexcelScraper' AS scraper_class, TRUE AS is_enabled, FALSE AS requires_javascript,
           ['carbon_fiber', 'prepreg', 'core_honeycomb', 'adhesive'] AS primary_materials,
           ['aerospace', 'defense', 'space'] AS primary_industries,
           'Major aerospace carbon fiber and prepreg supplier' AS notes),
    STRUCT('owens_corning', 'Owens Corning', 'Owens Corning Composites',
           'https://www.owenscorning.com', 'https://www.owenscorning.com/en-us/composites/resources-support/technical-resources',
           'OwensCorningScraper', TRUE, FALSE,
           ['glass_fiber', 'fabric'], ['marine', 'construction', 'wind_energy', 'automotive'],
           'Leading glass fiber manufacturer'),
    STRUCT('toray', 'Toray', 'Toray Composite Materials America',
           'https://www.toraytac.com', 'https://www.toraytac.com/resources/datasheets',
           'TorayScraper', TRUE, FALSE,
           ['carbon_fiber', 'prepreg'], ['aerospace', 'automotive', 'sports'],
           'World leader in carbon fiber production'),
    STRUCT('polynt', 'Polynt-Reichhold', 'Polynt-Reichhold Group',
           'https://www.polynt.com', 'https://www.polynt.com/composites/',
           'PolyntScraper', TRUE, FALSE,
           ['resin_polyester', 'resin_vinylester'], ['marine', 'construction', 'transportation'],
           'Major resin supplier - polyester and vinyl ester'),
    STRUCT('gurit', 'Gurit', 'Gurit Holding AG',
           'https://www.gurit.com', 'https://www.gurit.com/products/',
           'GuritScraper', TRUE, FALSE,
           ['prepreg', 'core_foam', 'adhesive'], ['wind_energy', 'marine', 'transportation'],
           'Wind energy and marine composites specialist')
  ])
) AS source
ON target.supplier_id = source.supplier_id
WHEN NOT MATCHED THEN
  INSERT (supplier_id, supplier_name, display_name, website, datasheet_index_url, 
          scraper_class, is_enabled, requires_javascript, primary_materials, primary_industries, notes)
  VALUES (source.supplier_id, source.supplier_name, source.display_name, source.website, source.datasheet_index_url,
          source.scraper_class, source.is_enabled, source.requires_javascript, source.primary_materials, source.primary_industries, source.notes)
"@

Write-Host "`n✅ BigQuery setup complete!" -ForegroundColor Green
Write-Host "`nTables created:"
Write-Host "  - $PROJECT.$DATASET.datasheets"
Write-Host "  - $PROJECT.$DATASET.datasheet_scrape_runs"
Write-Host "  - $PROJECT.$DATASET.datasheet_suppliers"

Write-Host "`nVerify with:"
Write-Host "  bq ls $PROJECT`:$DATASET"
