import csv

rows = list(csv.DictReader(open('app/resources/master_company_list.csv')))
ticker_rows = [r for r in rows if r.get('stock_ticker', '').strip()]
print(f"Companies with tickers: {len(ticker_rows)}/{len(rows)}")
print()
for r in ticker_rows:
    print(f"  {r['company']:45s} -> {r['stock_ticker']}")
