"""Configuracao da aplicacao, carregada de variaveis de ambiente."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+pysqlite:///./precificacao.db"

    # Casas decimais mantidas nos passos intermediarios do motor de calculo.
    # O arredondamento de apresentacao e definido por empresa em `empresa_parametro`.
    precisao_interna: int = 10
    moeda_padrao: str = "BRL"


@lru_cache
def get_settings() -> Settings:
    return Settings()
