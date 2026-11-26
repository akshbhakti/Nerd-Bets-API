"""Private, self-hosted API gateway. Do not expose it publicly without TLS and access controls."""
import os
import secrets
from fastapi import FastAPI, Header, HTTPException
from odds_client import capture, initialize
app = FastAPI(title='Nerd Bets Odds Gateway',version='0.1.0')

@app.get('/health')
def health():
    return {'service':'up','provider_key_configured':bool(os.getenv('ODDS_API_KEY')),
            'admin_token_configured':bool(os.getenv('ADMIN_TOKEN')),
            'provider_network_tested':False}

@app.post('/capture/{sport}')
def start_capture(sport: str, authorization: str | None = Header(default=None)):
    expected=os.getenv('ADMIN_TOKEN')
    if not expected or not authorization or not secrets.compare_digest(authorization, f'Bearer {expected}'):
        raise HTTPException(401,'Authentication required')
    if sport.upper() not in ('NFL','NBA'):
        raise HTTPException(400,'Unsupported sport')
    # Synchronous for MVP; production should queue this as a background job.
    return capture(sport.upper(),folder=os.getenv('DATA_DIR','./data'))
