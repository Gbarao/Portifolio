"""Erros de dominio.

A especificacao (secao 1) exige bloquear o calculo -- nunca produzir um numero
silenciosamente errado -- quando houver denominador zero, massa inconsistente,
regra fiscal vencida ou dado obrigatorio ausente. Cada situacao tem sua
excecao para que a interface possa reagir de forma especifica.
"""

from __future__ import annotations


class ErroDominio(Exception):
    """Base de todos os erros de regra de negocio."""


class DenominadorZeroError(ErroDominio):
    """Divisao por zero em um calculo de custo, taxa ou rendimento."""


class MassaInconsistenteError(ErroDominio):
    """Balanco de massa fora da tolerancia configurada (secao 7.1)."""


class DadoObrigatorioAusenteError(ErroDominio):
    """Campo exigido para concluir o calculo nao foi informado."""


class RegraFiscalIndisponivelError(ErroDominio):
    """Nenhuma regra vigente, ou regra vencida, para a operacao (secao 11.2)."""


class DuplaContagemError(ErroDominio):
    """O mesmo custo apareceria na taxa da atividade e como lancamento direto.

    Regra 12 da secao 11 e caso de teste 8 da secao 17.
    """


class ParametroInvalidoError(ErroDominio):
    """Premissa fora da faixa aceitavel (ex.: deducoes de 100% do preco)."""
