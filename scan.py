import argparse,csv,json,hashlib
from pathlib import Path
from odds_client import capture
p=argparse.ArgumentParser();p.add_argument('--sport',choices=['NFL','NBA'],default='NFL'); a=p.parse_args()
r=capture(a.sport,'data'); raw=Path(r['file_path']); obj=json.loads(raw.read_bytes()); rows=[]
for event in obj['responses']:
 for batch in event['odds_batches']:
  for book in batch['data'].get('bookmakers',[]):
   if book['key']!='fanduel':continue
   for market in book.get('markets',[]):
    for quote in market.get('outcomes',[]):
     rows.append(dict(event_id=event['event']['id'],commence_time=event['event']['commence_time'],home_team=event['event']['home_team'],away_team=event['event']['away_team'],market=market['key'],updated_at=market.get('last_update'),player=quote.get('description'),side=quote.get('name'),line=quote.get('point'),american_price=quote.get('price')))
fields='event_id commence_time home_team away_team market updated_at player side line american_price'.split()
with raw.with_suffix('.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
print(json.dumps({k:r[k] for k in ('status','event_count','quote_count','requests','sha256')}))
if not rows or r['status']!='CAPTURED_UNCERTIFIED':raise SystemExit(1)
