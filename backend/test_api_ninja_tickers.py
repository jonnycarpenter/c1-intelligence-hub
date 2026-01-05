"""Test API Ninja earnings endpoint for all tracked tickers."""

from app.mcp.tools.api_ninja_earnings import get_earnings_transcript_ninja
import json
import time

TICKERS = [
    "VMC", "MLM", "CRH", "SUM", "GVA", "PWR", "MTZ", "PRIM", "SKBSY", "ACM",
    "J", "FLR", "SGL.DE", "HXL", "TINLY", "GURN.SW", "SOLVY", "TRYIY", "BA",
    "EADSY", "ERJ", "RTX", "NOC", "LMT", "GD", "BAESY", "GE", "SAFRY", "RYCEY",
    "RKLB", "VWDRY", "GCTAF", "GEV", "NRDXF", "BC", "BEN.PA", "BMWYY", "RACE",
    "FINMY", "BDRBF", "TXT", "JOBY", "ACHR", "MBUU", "MCFT", "TM", "F", "GM"
]

def main():
    print(f"Testing {len(TICKERS)} tickers for Q3 2025 earnings transcripts...\n")
    
    found = []
    not_found = []
    
    for ticker in TICKERS:
        result = json.loads(get_earnings_transcript_ninja.invoke({
            'ticker': ticker, 
            'year': 2025, 
            'quarter': 3
        }))
        
        if 'error' in result:
            not_found.append(ticker)
            print(f"  X {ticker}")
        else:
            date = result.get('date', 'unknown')
            found.append((ticker, date))
            print(f"  ✓ {ticker} - {date}")
        
        time.sleep(0.3)  # Rate limit
    
    print(f"\n{'='*50}")
    print(f"SUMMARY")
    print(f"{'='*50}")
    print(f"Found transcripts: {len(found)}/{len(TICKERS)}")
    print(f"Not found: {len(not_found)}")
    
    if found:
        print(f"\nCompanies WITH Q3 2025 transcripts:")
        for ticker, date in found:
            print(f"  {ticker}: {date}")
    
    if not_found:
        print(f"\nCompanies WITHOUT Q3 2025 transcripts:")
        print(f"  {', '.join(not_found)}")

if __name__ == "__main__":
    main()
