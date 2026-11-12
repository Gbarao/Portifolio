-- =====================================================================================
-- Estruturas permanentes (controle, filtros, snapshots, sessão, referências e tabela fato)
-- As tabelas brutas sf_* / ec_* são criadas a partir de app/parser/normalizer.py:SCHEMAS
-- =====================================================================================

CREATE SEQUENCE IF NOT EXISTS seq_arquivo START 1;
CREATE SEQUENCE IF NOT EXISTS seq_filtro START 1;
CREATE SEQUENCE IF NOT EXISTS seq_snapshot START 1;
CREATE SEQUENCE IF NOT EXISTS seq_log START 1;

CREATE TABLE IF NOT EXISTS sys_arquivos_importados (
    id_arquivo        BIGINT PRIMARY KEY,
    hash_sha256       VARCHAR NOT NULL,
    tipo_sped         VARCHAR NOT NULL,          -- ICMS_IPI | CONTRIB
    cnpj              VARCHAR,                   -- CNPJ do 0000 (filial no SPED Fiscal, matriz na EFD-Contribuições)
    nome              VARCHAR,
    uf                VARCHAR,
    competencia       VARCHAR NOT NULL,          -- AAAA-MM
    dt_ini            DATE,
    dt_fin            DATE,
    finalidade        VARCHAR,                   -- ORIGINAL | RETIFICADORA
    cod_ver           VARCHAR,
    caminho_origem    VARCHAR,
    tamanho_bytes     BIGINT,
    linhas            BIGINT,
    documentos        BIGINT,
    data_importacao   TIMESTAMP DEFAULT current_timestamp,
    ativo             BOOLEAN DEFAULT TRUE,
    substituido_por   BIGINT,
    data_substituicao TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sys_log_importacao (
    id        BIGINT PRIMARY KEY DEFAULT nextval('seq_log'),
    data      TIMESTAMP DEFAULT current_timestamp,
    arquivo   VARCHAR,
    acao      VARCHAR,     -- IMPORTADO | DUPLICADO | SUBSTITUIDO | IGNORADO | ERRO | REMOVIDO
    mensagem  VARCHAR
);

CREATE TABLE IF NOT EXISTS sys_filtros_salvos (
    id             BIGINT PRIMARY KEY DEFAULT nextval('seq_filtro'),
    nome           VARCHAR NOT NULL,
    categoria      VARCHAR,
    definicao_json VARCHAR NOT NULL,
    criado_em      TIMESTAMP DEFAULT current_timestamp,
    atualizado_em  TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS sys_snapshots_analises (
    id             BIGINT PRIMARY KEY DEFAULT nextval('seq_snapshot'),
    nome           VARCHAR NOT NULL,
    anotacoes      VARCHAR,
    criado_em      TIMESTAMP DEFAULT current_timestamp,
    contexto_json  VARCHAR,      -- filtros globais, regras, hierarquia, métricas
    arquivo        VARCHAR,      -- parquet imutável em data/snapshots
    linhas         BIGINT,
    hash_sha256    VARCHAR       -- integridade do parquet congelado
);

CREATE TABLE IF NOT EXISTS sys_sessao (
    chave VARCHAR PRIMARY KEY,
    valor VARCHAR,
    atualizado_em TIMESTAMP DEFAULT current_timestamp
);

-- Tabela IBGE: 2 primeiros dígitos do código do município -> UF
CREATE TABLE IF NOT EXISTS ref_uf_ibge (cod VARCHAR PRIMARY KEY, uf VARCHAR);

-- Item sintético por modelo de documento
CREATE TABLE IF NOT EXISTS ref_item_sintetico (cod_mod VARCHAR PRIMARY KEY, cod_item VARCHAR);

-- CFOP -> Natureza da Base de Cálculo do Crédito (derivação parametrizável; usada só quando o registro
-- de origem não informa NAT_BC_CRED, p.ex. C170 da EFD-Contribuições)
CREATE TABLE IF NOT EXISTS ref_cfop_nat_bc_cred (cfop VARCHAR PRIMARY KEY, nat_bc_cred VARCHAR);

-- Dimensões (reconstruídas a cada consolidação)
CREATE TABLE IF NOT EXISTS dim_filial (
    cnpj_filial VARCHAR PRIMARY KEY, nome_filial VARCHAR, uf_filial VARCHAR, raiz_cnpj VARCHAR, fonte VARCHAR
);
CREATE TABLE IF NOT EXISTS dim_fornecedor (
    cnpj_cpf VARCHAR PRIMARY KEY, razao_social VARCHAR, uf VARCHAR, cod_pais VARCHAR, ultima_competencia VARCHAR
);
CREATE TABLE IF NOT EXISTS dim_item_depara (
    cnpj_filial VARCHAR, cod_ant VARCHAR, cod_atual VARCHAR, competencia VARCHAR
);

-- =====================================================================================
-- Tabela fato consolidada (uma linha por item de entrada já cruzado SPED Fiscal x EFD-Contribuições)
-- =====================================================================================
CREATE TABLE IF NOT EXISTS fato_entradas_consolidadas (
    competencia               VARCHAR,
    cnpj_filial               VARCHAR,
    nome_filial               VARCHAR,
    uf_filial                 VARCHAR,
    raiz_cnpj_filial          VARCHAR,
    origem                    VARCHAR,       -- SF_C170 | EC_C170_VIA_CHAVE | SF_C190_SINTETICO | SF_C590_SINTETICO | ...
    reg_doc                   VARCHAR,
    file_id_sf                BIGINT,
    file_id_ec                BIGINT,
    doc_id                    BIGINT,
    cod_part                  VARCHAR,
    cnpj_cpf_fornecedor       VARCHAR,
    raiz_cnpj_fornecedor      VARCHAR,
    razao_social_fornecedor   VARCHAR,
    nome_part_na_data         VARCHAR,
    uf_fornecedor             VARCHAR,
    cod_mod                   VARCHAR,
    cod_sit                   VARCHAR,
    ind_emit                  VARCHAR,
    serie                     VARCHAR,
    num_doc                   VARCHAR,
    chave                     VARCHAR,
    dt_doc                    DATE,
    dt_e_s                    DATE,
    num_item                  BIGINT,
    cod_item                  VARCHAR,
    cod_item_unificado        VARCHAR,
    chave_item_global         VARCHAR,
    descr_item                VARCHAR,
    descr_compl               VARCHAR,
    tipo_item                 VARCHAR,
    cod_ncm                   VARCHAR,
    cest                      VARCHAR,
    cod_barra                 VARCHAR,
    unid                      VARCHAR,
    cfop                      VARCHAR,
    cod_nat                   VARCHAR,
    cst_icms                  VARCHAR,
    aliq_icms                 DECIMAL(18,6),
    cst_ipi                   VARCHAR,
    aliq_ipi                  DECIMAL(18,6),
    cst_pis                   VARCHAR,
    aliq_pis                  DECIMAL(18,6),
    cst_cofins                VARCHAR,
    aliq_cofins               DECIMAL(18,6),
    nat_bc_cred               VARCHAR,
    nat_bc_cred_origem        VARCHAR,       -- INFORMADO | DERIVADO_CFOP
    cod_cta                   VARCHAR,
    qtd                       DECIMAL(20,6),
    vl_item                   DECIMAL(18,2),
    vl_desc                   DECIMAL(18,2),
    vl_rateio_c190            DECIMAL(18,2), -- diferença rateada para fechar com VL_OPR do C190
    vl_contabil               DECIMAL(18,2),
    vl_bc_icms                DECIMAL(18,2),
    vl_icms                   DECIMAL(18,2),
    vl_bc_icms_st             DECIMAL(18,2),
    vl_icms_st                DECIMAL(18,2),
    vl_fcp                    DECIMAL(18,2),
    vl_fcp_st                 DECIMAL(18,2),
    vl_bc_ipi                 DECIMAL(18,2),
    vl_ipi                    DECIMAL(18,2),
    vl_bc_pis                 DECIMAL(18,2),
    vl_pis                    DECIMAL(18,2),
    vl_bc_cofins              DECIMAL(18,2),
    vl_cofins                 DECIMAL(18,2),
    vl_trib_recuperaveis      DECIMAL(18,2),
    vl_custo_liquido          DECIMAL(18,2),
    nivel_cruzamento_efd      VARCHAR,       -- N1_ITEM | N2_ITEM_CFOP | N3_CONSOLIDADO_C190 | DOC_CHAVE | DOC_NUMERO | EC_EXCLUSIVO
    status_efd                VARCHAR,
    flag_item_sintetico       BOOLEAN,
    flag_sem_c190             BOOLEAN
);
