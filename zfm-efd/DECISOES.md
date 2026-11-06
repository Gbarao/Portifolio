# DECISOES.md — dúvidas e decisões de regra de negócio e de implementação

Formato: **D-nnn** (decisão tomada, pode ser revista) · **P-nnn** (pergunta pendente ao usuário).

---

## Decisões

**D-001 — Estrutura do código (Fase 1).** A leitura das duas EFDs é feita por um único leitor
(`zfm/parsers/base.py`); o que difere entre EFD ICMS/IPI e EFD Contribuições fica nos
dicionários de layout (`zfm/layouts/`). Os scripts chamados pelos `.bat` ficam em `ferramentas/`
e usam só a biblioteca padrão (rodam antes de os pacotes existirem).

**D-002 — Versões dos pacotes.** `pandas 3.x` e `streamlit ≥ 1.66` exigem Python 3.11+. Como a
SPEC admite Python 3.10, foi fixado um conjunto único, conferido com o `pip` (pacotes prontos para
Windows 64 bits em Python 3.10, 3.11, 3.12, 3.13 e 3.14): `duckdb 1.5.6`, `streamlit 1.65.0`,
`plotly 7.1.0`, `pandas 2.3.3`, `openpyxl 3.1.5`, `pytest 9.2.0`. Dependências indiretas (numpy,
pyarrow etc.) não são fixadas. A instalação usa `--only-binary=:all:` (nunca compila).

**D-003 — Layouts SPED e versões.** Os campos dos registros seguem o Guia Prático, mas **não foram
conferidos contra o Guia da versão 2026**. Cada registro tem uma ou mais versões; a versão de cada
linha é escolhida pelo `COD_VER` (quando mapeado) e pelo número de campos. Se o número de campos não
bater com nenhuma versão conhecida, a linha é lida por posição e aparece um aviso na tela
"Perímetro e qualidade". Pontos a conferir no Guia Prático vigente:
- EFD ICMS/IPI: `C170.VL_ABAT_NT` (último campo), `0200.CEST`, `E113.CHV_DOCe`, `E116.MES_REF`;
  eventuais campos novos de 2026.
- EFD Contribuições: `M210`/`M610` com 16 campos (versão com ajustes de base) × 13 campos;
  nome do campo `VL_CRED_DIF` em `M100`/`M500`.
- Os limites de `COD_VER` de cada versão ficaram em branco (escolha só pelo número de campos).

**D-004 — Retificadora.** Mesma chave = tipo + CNPJ + IE + período (`DT_INI`/`DT_FIN`).
Retificadora (`COD_FIN = 1` na ICMS/IPI; `TIPO_ESCRIT = 1` na Contribuições) prevalece sobre a
original, em qualquer ordem de carga. Entre duas do mesmo tipo, prevalece a carregada por último.
A versão substituída fica no banco como "Substituído" e não entra em nenhum cálculo.

**D-005 — Arquivo repetido.** Arquivo com o mesmo conteúdo (hash SHA-256) de um já carregado é
ignorado, sem alterar nada.

**D-006 — Tipo do arquivo.** Detectado pela posição da data inicial no registro 0000
(4º campo na ICMS/IPI; 6º na Contribuições).

**D-007 — Estabelecimento de cada linha da EFD Contribuições.** Registros dos blocos A, C e F
recebem o CNPJ do último `A010`/`C010`/`F010`; registros do bloco 0 após um `0140` recebem o CNPJ
desse `0140`; blocos M, 1 e 9 recebem o CNPJ da matriz (registro 0000).

**D-008 — Conversão de números e datas.** Feita no banco local (DuckDB): vírgula → ponto e
conversão para `DECIMAL` exato (valores: 2 casas; alíquotas: 4; quantidades: 6). Valor que não é
número vira vazio (nulo). Uma checagem de valores inválidos pode ser acrescentada na Fase 3.

**D-009 — Q1 (completude).** Considera os estabelecimentos com UF = AM (do 0000 da ICMS/IPI ou do
0140 da Contribuições). EFD ICMS/IPI: por CNPJ completo; EFD Contribuições: pela raiz do CNPJ
(entregue pela matriz). Período: janeiro/2026 até o último mês com arquivo carregado (ajustável).

**D-010 — Pasta de EFDs.** O programa lê todos os `.txt` da pasta informada **e das subpastas**.

**D-011 — Carga.** A carga é feita com barra de progresso, mas a tela fica ocupada até terminar
(não roda em segundo plano). Medição: 1 milhão de linhas em ~10 s, com memória estável (~20 MB).

**D-012 — Execução local.** Teste automático confirma que as telas não fazem nenhuma requisição
fora de `127.0.0.1`. O teste com a rede desligada no Windows (SPEC 2.1) depende do usuário.

---

## Perguntas pendentes (SPEC seção 12)

- **P-001** — Códigos `COD_AJ_APUR` (E111) e `COD_OR`/`COD_REC` (E116) de crédito estímulo e dos
  fundos FTI/UEA/FMPES. (Necessário na Fase 4.)
- **P-002** — A EFD Contribuições das empresas é detalhada (C100/C170) ou consolidada
  (C180–C195)? O programa já lê os dois formatos.
- **P-003** — Formato do estudo da A&M para importar em `param_produtos`.
- **P-004** — Lista das teses e forma de quantificar cada uma.
- **P-005** — Alíquotas de referência de CBS e IBS por cenário.
- **P-006** — Ordem de dedução dos créditos presumidos de IBS e fator de transição dos arts. 447/449.
- **P-007** — Inclusão futura do XML das NF-e de saída.
- **P-008** — Códigos IBGE de Presidente Figueiredo e Rio Preto da Eva (`param_municipios_zfm`).
