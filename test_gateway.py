import json
import os
import httpx
from odds_client import OddsClient, ProviderFailure, capture

def test_successful_capture(tmp_path,monkeypatch):
    monkeypatch.setenv('ODDS_API_KEY','fake-test-key')
    event={'id':'abc123','commence_time':'2099-01-01T18:00:00Z','home_team':'A','away_team':'B'}
    def handler(request):
        assert request.url.params['apiKey']=='fake-test-key'
        if request.url.path.endswith('/events'): return httpx.Response(200,json=[event])
        if request.url.path.endswith('/markets'): return httpx.Response(200,json={'bookmakers':[{'key':'fanduel','markets':[{'key':'player_pass_yds'}]}]})
        return httpx.Response(200,json={'bookmakers':[{'key':'fanduel','markets':[{'key':'player_pass_yds','outcomes':[{'name':'Over','description':'Player A','price':-110,'point':210.5}]}]}]})
    r=capture('NFL',str(tmp_path),transport=httpx.MockTransport(handler))
    assert r['status']=='CAPTURED_UNCERTIFIED' and r['quote_count']==1
    assert 'fake-test-key' not in open(r['file_path']).read()

def test_rejects_bad_credentials():
    def handler(request): return httpx.Response(401,json={'message':'invalid'})
    c=OddsClient('test',transport=httpx.MockTransport(handler))
    try: c.get('/sports/americanfootball_nfl/events')
    except ProviderFailure as e: assert e.kind=='AUTHENTICATION'
    else: raise AssertionError('Expected failure')
