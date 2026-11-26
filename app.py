
import os
import secrets
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from odds_client import capture, initialize

app = FastAPI(title="Nerd Bets Odds Gateway", version="0.1.1")
bearer = HTTPBearer(auto_error=False)

@app.get("/health")
def health():
    return {
        "service": "up",
        "provider_key_configured": bool(os.getenv("ODDS_API_KEY")),
        "admin_token_configured": bool(os.getenv("ADMIN_TOKEN")),
        "provider_network_tested": False
    }

@app.post("/capture/{sport}")
def start_capture(
    sport: str,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer)
):
    expected = os.getenv("ADMIN_TOKEN")

    if not expected or credentials is None or not secrets.compare_digest(
        credentials.credentials.encode("utf-8"),
        expected.encode("utf-8")
    ):
        raise HTTPException(
            401, "Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if sport.upper() not in ("NFL", "NBA"):
        raise HTTPException(400, "Unsupported sport")

    return capture(
        sport.upper(),
        folder=os.getenv("DATA_DIR", "./data")
    )
