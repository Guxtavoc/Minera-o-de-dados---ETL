-- Repositório analítico "Mercatto DW"  ·  PostgreSQL 16 · UTF-8
-- Camadas: stg preserva as origens, dw integra o esquema estrela e abt atende à pergunta preditiva.
CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS dw;
CREATE SCHEMA IF NOT EXISTS abt;
CREATE SCHEMA IF NOT EXISTS qa;  -- Resultados das asserções de qualidade.

-- stg: nomes e tipos espelham as origens, sem conversão semântica.

-- dw: esquema estrela conformado.
DROP TABLE IF EXISTS dw.fato_item_pedido CASCADE;
DROP TABLE IF EXISTS dw.fato_pedido      CASCADE;
DROP TABLE IF EXISTS dw.mapa_cliente_origem CASCADE;
DROP TABLE IF EXISTS dw.dim_cliente      CASCADE;
DROP TABLE IF EXISTS dw.dim_produto      CASCADE;
DROP TABLE IF EXISTS dw.dim_tempo        CASCADE;
DROP TABLE IF EXISTS dw.dim_canal        CASCADE;
DROP TABLE IF EXISTS dw.dim_status       CASCADE;

-- Grão: um cliente unificado, com procedência das duas origens.
CREATE TABLE dw.dim_cliente (
  cliente_sk        BIGSERIAL PRIMARY KEY,
  cpf_normalizado   CHAR(11)     NULL,   -- apenas dígitos; NULL quando ausente
  cpf_valido        BOOLEAN      NULL,   -- dígito verificador confere?
  nome_padronizado  TEXT         NOT NULL,
  cidade            TEXT         NULL,
  uf                CHAR(2)      NULL,
  dt_primeiro_cadastro DATE      NULL,
  id_legado         INT          NULL,   -- rastro de procedência
  id_ecommerce      BIGINT       NULL,   -- rastro de procedência
  origem_unificacao TEXT         NOT NULL,  -- 'LEGADO' | 'ECOM' | 'AMBOS'
  regra_pareamento  TEXT         NULL,   -- qual regra uniu os registros
  CONSTRAINT ck_origem CHECK (origem_unificacao IN ('LEGADO','ECOM','AMBOS'))
);
CREATE INDEX ix_dim_cliente_cpf ON dw.dim_cliente (cpf_normalizado);
CREATE INDEX ix_dim_cliente_id_legado ON dw.dim_cliente (id_legado);
CREATE INDEX ix_dim_cliente_id_ecommerce ON dw.dim_cliente (id_ecommerce);

-- Mapeia cada ID original, inclusive duplicado, para o cliente canônico.
CREATE TABLE dw.mapa_cliente_origem (
  sistema           TEXT   NOT NULL,
  id_origem_natural BIGINT NOT NULL,
  id_canonico       BIGINT NOT NULL,
  regra             TEXT   NOT NULL,
  PRIMARY KEY (sistema, id_origem_natural)
);

-- Grão: um produto conformado.
CREATE TABLE dw.dim_produto (
  produto_sk       BIGSERIAL PRIMARY KEY,
  sku              TEXT        NULL,
  descricao        TEXT        NOT NULL,
  categoria_nivel1 TEXT        NULL,   -- taxonomia conformada
  categoria_nivel2 TEXT        NULL,
  categoria_origem TEXT        NULL,   -- valor bruto, preservado
  preco_referencia NUMERIC(12,2) NULL,
  ativo            BOOLEAN     NULL,
  id_legado        INT         NULL,
  id_ecommerce     BIGINT      NULL,
  origem           TEXT        NOT NULL
);
CREATE INDEX ix_dim_produto_sku ON dw.dim_produto (sku);
CREATE INDEX ix_dim_produto_id_legado ON dw.dim_produto (id_legado);
CREATE INDEX ix_dim_produto_id_ecommerce ON dw.dim_produto (id_ecommerce);

CREATE TABLE dw.dim_tempo (
  data_sk        DATE PRIMARY KEY,
  ano            INT  NOT NULL,
  trimestre      INT  NOT NULL,
  mes            INT  NOT NULL,
  dia            INT  NOT NULL,
  dia_semana     INT  NOT NULL,
  nome_mes       TEXT NOT NULL,
  eh_fim_semana  BOOLEAN NOT NULL
);

CREATE TABLE dw.dim_canal (
  canal_sk     SERIAL PRIMARY KEY,
  canal_origem TEXT NOT NULL,   -- valor bruto: LOJA, web, app...
  canal_conformado TEXT NOT NULL, -- FISICO | ONLINE_PROPRIO | MARKETPLACE | TELEVENDAS
  sistema      TEXT NOT NULL
);

-- Materializa a conformação de cancelamentos registrada no RDT.
CREATE TABLE dw.dim_status (
  status_sk            SERIAL PRIMARY KEY,
  status_origem        TEXT NOT NULL,
  sistema              TEXT NOT NULL,
  status_conformado    TEXT NOT NULL,
  motivo_cancelamento  TEXT NULL,   -- NULL quando a origem não distingue
  UNIQUE (status_origem, sistema)
);

-- Grão: um pedido.
CREATE TABLE dw.fato_pedido (
  pedido_sk        BIGSERIAL PRIMARY KEY,
  id_origem        TEXT   NOT NULL,   -- 'LEG-123' | 'ECOM-456'
  sistema_origem   TEXT   NOT NULL,
  cliente_sk       BIGINT NOT NULL REFERENCES dw.dim_cliente (cliente_sk),
  data_pedido_sk   DATE   NOT NULL REFERENCES dw.dim_tempo (data_sk),
  data_entrega_sk  DATE   NULL     REFERENCES dw.dim_tempo (data_sk),
  canal_sk         INT    NOT NULL REFERENCES dw.dim_canal (canal_sk),
  status_sk        INT    NOT NULL REFERENCES dw.dim_status (status_sk),
  qtd_itens        INT    NOT NULL,
  valor_mercadoria NUMERIC(12,2) NOT NULL,  -- SEM frete, conformado
  valor_frete      NUMERIC(12,2) NOT NULL,
  valor_desconto   NUMERIC(12,2) NOT NULL,
  valor_total      NUMERIC(12,2) NOT NULL,  -- mercadoria + frete - desconto
  dias_entrega     INT    NULL,
  UNIQUE (id_origem, sistema_origem)
);
CREATE INDEX ix_fato_pedido_cli  ON dw.fato_pedido (cliente_sk);
CREATE INDEX ix_fato_pedido_data ON dw.fato_pedido (data_pedido_sk);
CREATE INDEX ix_fato_pedido_cli_data ON dw.fato_pedido (cliente_sk, data_pedido_sk);

-- Grão: uma linha de item de pedido.
CREATE TABLE dw.fato_item_pedido (
  item_sk     BIGSERIAL PRIMARY KEY,
  pedido_sk   BIGINT NOT NULL REFERENCES dw.fato_pedido (pedido_sk),
  produto_sk  BIGINT NOT NULL REFERENCES dw.dim_produto (produto_sk),
  quantidade  INT    NOT NULL,
  valor_unitario NUMERIC(12,2) NOT NULL,
  valor_desconto NUMERIC(12,2) NOT NULL,
  valor_linha    NUMERIC(12,2) NOT NULL
);
CREATE INDEX ix_fato_item_pedido_pedido  ON dw.fato_item_pedido (pedido_sk);
CREATE INDEX ix_fato_item_pedido_produto ON dw.fato_item_pedido (produto_sk);

-- Grão: um atendimento ou uma avaliação, conforme a tabela.
CREATE TABLE IF NOT EXISTS dw.fato_atendimento (
  atendimento_sk  BIGSERIAL PRIMARY KEY,
  protocolo       TEXT   NOT NULL UNIQUE,
  cliente_sk      BIGINT NULL REFERENCES dw.dim_cliente (cliente_sk),
  pedido_sk       BIGINT NULL REFERENCES dw.fato_pedido (pedido_sk),
  data_abertura_sk  DATE NOT NULL REFERENCES dw.dim_tempo (data_sk),
  data_fechamento_sk DATE NULL   REFERENCES dw.dim_tempo (data_sk),
  canal           TEXT   NULL,
  motivo_conformado TEXT NULL,
  nota_satisfacao INT    NULL,
  horas_resolucao NUMERIC(10,2) NULL
);

CREATE TABLE IF NOT EXISTS dw.fato_avaliacao (
  avaliacao_sk BIGSERIAL PRIMARY KEY,
  review_id    TEXT   NOT NULL UNIQUE,
  pedido_sk    BIGINT NULL REFERENCES dw.fato_pedido (pedido_sk),
  produto_sk   BIGINT NULL REFERENCES dw.dim_produto (produto_sk),
  data_sk      DATE   NOT NULL REFERENCES dw.dim_tempo (data_sk),
  nota         INT    NULL,
  compra_verificada BOOLEAN NULL,
  votos_uteis  INT    NULL
);

CREATE INDEX IF NOT EXISTS ix_fato_atendimento_cli  ON dw.fato_atendimento (cliente_sk);
CREATE INDEX IF NOT EXISTS ix_fato_atendimento_ped  ON dw.fato_atendimento (pedido_sk);
CREATE INDEX IF NOT EXISTS ix_fato_avaliacao_ped    ON dw.fato_avaliacao (pedido_sk);
CREATE INDEX IF NOT EXISTS ix_fato_avaliacao_prod   ON dw.fato_avaliacao (produto_sk);
CREATE INDEX IF NOT EXISTS ix_fato_avaliacao_data   ON dw.fato_avaliacao (data_sk);

-- abt: prevê recompra entre 2025-07-01 e 2025-09-28 com dados até 2025-06-30.
-- cliente_sk, data_corte e alvo_recompra_90d formam o contrato mínimo.
DROP TABLE IF EXISTS abt.recompra_90d CASCADE;
CREATE TABLE abt.recompra_90d (
  cliente_sk            BIGINT  NOT NULL REFERENCES dw.dim_cliente (cliente_sk),
  data_corte            DATE    NOT NULL,
  alvo_recompra_90d     SMALLINT NOT NULL CHECK (alvo_recompra_90d IN (0,1)),
  recencia_dias          DOUBLE PRECISION,
  frequencia_pedidos     BIGINT,
  valor_monetario        DOUBLE PRECISION,
  ticket_medio           DOUBLE PRECISION,
  prazo_medio_entrega    DOUBLE PRECISION,
  taxa_cancelamento      DOUBLE PRECISION,
  categorias_distintas   BIGINT,
  canal_predominante     TEXT,
  qtd_atendimentos_sac   BIGINT,
  nota_media_avaliacoes  DOUBLE PRECISION,
  tempo_como_cliente     BIGINT,
  qtd_itens              BIGINT,
  PRIMARY KEY (cliente_sk, data_corte)
);

-- qa: resultados das asserções e registros em quarentena.
CREATE TABLE IF NOT EXISTS qa.execucao_assercao (
  id           BIGSERIAL PRIMARY KEY,
  executado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
  etapa        TEXT NOT NULL,
  nome         TEXT NOT NULL,
  descricao    TEXT NULL,
  valor_obtido NUMERIC NULL,
  valor_esperado TEXT NULL,
  aprovado     BOOLEAN NOT NULL
);

-- Itens sem pedido ficam disponíveis para auditoria e recuperação.
CREATE TABLE IF NOT EXISTS qa.quarentena_item_pedido (
  id                  BIGSERIAL PRIMARY KEY,
  id_origem           TEXT   NOT NULL,   -- 'LEG-...' | 'ECOM-...'
  sistema_origem      TEXT   NOT NULL,
  id_produto_legado   BIGINT NULL,
  id_produto_ecommerce BIGINT NULL,
  quantidade          INT    NULL,
  valor_unitario      NUMERIC(12,2) NULL,
  valor_desconto      NUMERIC(12,2) NULL,
  valor_linha         NUMERIC(12,2) NULL,
  motivo              TEXT   NOT NULL,
  detectado_em        TIMESTAMPTZ NOT NULL DEFAULT now()
);
