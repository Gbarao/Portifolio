"""Verificacao de saude e identificacao da API."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import SessaoDep

router = APIRouter(tags=["saude"])


@router.get("/saude")
def saude(sessao: SessaoDep) -> dict[str, object]:
    banco_ok = sessao.execute(text("SELECT 1")).scalar() == 1
    return {"status": "ok" if banco_ok else "degradado", "banco": banco_ok}
