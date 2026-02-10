"""Verify nugget extraction results."""
from google.cloud import bigquery

c = bigquery.Client(project="gen-lang-client-0436975498")
table = "gen-lang-client-0436975498.c1_intelligence.sec_filing_nuggets"

# Total counts
q1 = f"""
SELECT 
    COUNT(*) as total,
    COUNT(DISTINCT ticker) as tickers,
    COUNT(DISTINCT filing_id) as filings,
    COUNTIF(ticker = '?') as bad_ticker,
    COUNTIF(is_actionable = TRUE) as actionable,
    COUNTIF(is_new_disclosure = TRUE) as new_disclosures
FROM `{table}`
"""
print("=== Nugget Summary ===")
for row in c.query(q1).result():
    print(f"Total nuggets: {row.total}")
    print(f"Distinct tickers: {row.tickers}")
    print(f"Distinct filings: {row.filings}")
    print(f"Bad ticker ('?'): {row.bad_ticker}")
    print(f"Actionable: {row.actionable}")
    print(f"New disclosures: {row.new_disclosures}")

# By model
q2 = f"""
SELECT extraction_model, COUNT(*) as cnt 
FROM `{table}` 
GROUP BY extraction_model 
ORDER BY cnt DESC
"""
print("\n=== By Model ===")
for row in c.query(q2).result():
    print(f"  {row.extraction_model}: {row.cnt}")

# Top tickers
q3 = f"""
SELECT ticker, COUNT(*) as cnt, COUNTIF(is_actionable = TRUE) as actionable
FROM `{table}` 
WHERE ticker != '?'
GROUP BY ticker 
ORDER BY cnt DESC
LIMIT 15
"""
print("\n=== Top Tickers ===")
for row in c.query(q3).result():
    print(f"  {row.ticker}: {row.cnt} nuggets ({row.actionable} actionable)")

# Nugget types
q4 = f"""
SELECT nugget_type, COUNT(*) as cnt
FROM `{table}`
WHERE extraction_model = 'claude-sonnet-4-5'
GROUP BY nugget_type
ORDER BY cnt DESC
"""
print("\n=== Nugget Types (Sonnet 4.5 only) ===")
for row in c.query(q4).result():
    print(f"  {row.nugget_type}: {row.cnt}")

# SEC filings table stats
q5 = """
SELECT 
    COUNT(*) as total,
    COUNT(DISTINCT ticker) as tickers,
    COUNT(DISTINCT form_type) as form_types
FROM `gen-lang-client-0436975498.c1_intelligence.sec_filings`
"""
print("\n=== SEC Filings Table ===")
for row in c.query(q5).result():
    print(f"Total filings: {row.total}")
    print(f"Distinct tickers: {row.tickers}")
    print(f"Form types: {row.form_types}")
