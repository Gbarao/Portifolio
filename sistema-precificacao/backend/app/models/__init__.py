"""Registro central dos modelos.

Importar este pacote e suficiente para que ``Base.metadata`` conheca todas as
tabelas -- e o que o Alembic usa para gerar migracoes.
"""

from app.db.base import Base
from app.models.cadastro import (
    ContratoTabela,
    Material,
    MaterialSaidaEsperada,
    Parceiro,
)
from app.models.comercial import (
    CotacaoPreco,
    CotacaoVenda,
    CotacaoVersao,
    PedidoVenda,
    SimulacaoCenario,
)
from app.models.empresa import Empresa, EmpresaParametro, Unidade, Usuario
from app.models.fiscal import (
    ApuracaoRbt12,
    ApuracaoTributaria,
    FaixaSimplesNacional,
    RegraTributaria,
)
from app.models.governanca import (
    Alerta,
    Auditoria,
    FechamentoMensal,
    MemoriaCalculo,
    MemoriaPasso,
)
from app.models.operacao import (
    EventoBalanca,
    EventoFrete,
    EventoProcesso,
    EventoQualidade,
    LoteCompra,
    LoteSaida,
    MovimentoEstoque,
    RejeitoPerda,
)
from app.models.recurso import (
    Atividade,
    AtividadeTaxa,
    CentroCusto,
    DespesaEstrutural,
    EmpregadoCusto,
    ImovelCusto,
    MaquinaCusto,
    Recurso,
    VeiculoCusto,
)

__all__ = [
    "Base",
    # empresa
    "Empresa",
    "Unidade",
    "EmpresaParametro",
    "Usuario",
    # cadastro
    "Material",
    "MaterialSaidaEsperada",
    "Parceiro",
    "ContratoTabela",
    # recursos
    "CentroCusto",
    "Recurso",
    "EmpregadoCusto",
    "VeiculoCusto",
    "MaquinaCusto",
    "ImovelCusto",
    "Atividade",
    "AtividadeTaxa",
    "DespesaEstrutural",
    # operacao
    "LoteCompra",
    "EventoBalanca",
    "EventoQualidade",
    "EventoProcesso",
    "LoteSaida",
    "RejeitoPerda",
    "EventoFrete",
    "MovimentoEstoque",
    # fiscal
    "RegraTributaria",
    "FaixaSimplesNacional",
    "ApuracaoRbt12",
    "ApuracaoTributaria",
    # comercial
    "CotacaoVenda",
    "CotacaoVersao",
    "CotacaoPreco",
    "SimulacaoCenario",
    "PedidoVenda",
    # governanca
    "MemoriaCalculo",
    "MemoriaPasso",
    "Alerta",
    "FechamentoMensal",
    "Auditoria",
]
