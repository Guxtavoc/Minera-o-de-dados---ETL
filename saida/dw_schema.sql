--
-- PostgreSQL database dump
--

\restrict RrFiaxp8896Cd6aD8yWxoC5A6kd4AZvURyboLyc2J41MbIGgMuoQ5DCLl4cSm0D

-- Dumped from database version 16.15 (Debian 16.15-1.pgdg13+2)
-- Dumped by pg_dump version 16.15 (Debian 16.15-1.pgdg13+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: abt; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA abt;


--
-- Name: dw; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA dw;


--
-- Name: qa; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA qa;


--
-- Name: stg; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA stg;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: recompra_90d; Type: TABLE; Schema: abt; Owner: -
--

CREATE TABLE abt.recompra_90d (
    cliente_sk bigint NOT NULL,
    data_corte date NOT NULL,
    alvo_recompra_90d smallint NOT NULL,
    recencia_dias double precision,
    frequencia_pedidos bigint,
    valor_monetario double precision,
    ticket_medio double precision,
    prazo_medio_entrega double precision,
    taxa_cancelamento double precision,
    categorias_distintas bigint,
    canal_predominante text,
    qtd_atendimentos_sac bigint,
    nota_media_avaliacoes double precision,
    tempo_como_cliente bigint,
    qtd_itens bigint,
    CONSTRAINT ck_recompra_90d_alvo CHECK ((alvo_recompra_90d = ANY (ARRAY[0, 1])))
);


--
-- Name: recompra_90d_vazamento; Type: TABLE; Schema: abt; Owner: -
--

CREATE TABLE abt.recompra_90d_vazamento (
    cliente_sk bigint NOT NULL,
    data_corte date NOT NULL,
    alvo_recompra_90d smallint NOT NULL,
    recencia_dias double precision,
    frequencia_pedidos bigint,
    valor_monetario double precision,
    ticket_medio double precision,
    prazo_medio_entrega double precision,
    taxa_cancelamento double precision,
    categorias_distintas bigint,
    canal_predominante text,
    qtd_atendimentos_sac bigint,
    nota_media_avaliacoes double precision,
    tempo_como_cliente bigint,
    qtd_itens bigint,
    valor_monetario_z double precision,
    CONSTRAINT ck_recompra_90d_vazamento_alvo CHECK ((alvo_recompra_90d = ANY (ARRAY[0, 1])))
);


--
-- Name: atendimento_conformado; Type: TABLE; Schema: dw; Owner: -
--

CREATE TABLE dw.atendimento_conformado (
    protocolo text,
    sistema_origem text,
    id_origem_pedido text,
    cpf_normalizado text,
    data_abertura timestamp without time zone,
    data_fechamento timestamp without time zone,
    canal text,
    motivo_conformado text,
    nota_satisfacao double precision,
    horas_resolucao double precision,
    pedido_ligado boolean
);


--
-- Name: avaliacao_conformada; Type: TABLE; Schema: dw; Owner: -
--

CREATE TABLE dw.avaliacao_conformada (
    review_id text,
    id_origem_pedido text,
    product_ref text,
    data date,
    nota double precision,
    compra_verificada boolean,
    votos_uteis double precision,
    pedido_ligado boolean
);


--
-- Name: dim_canal; Type: TABLE; Schema: dw; Owner: -
--

CREATE TABLE dw.dim_canal (
    canal_sk integer NOT NULL,
    canal_origem text NOT NULL,
    canal_conformado text NOT NULL,
    sistema text NOT NULL
);


--
-- Name: dim_canal_canal_sk_seq; Type: SEQUENCE; Schema: dw; Owner: -
--

CREATE SEQUENCE dw.dim_canal_canal_sk_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dim_canal_canal_sk_seq; Type: SEQUENCE OWNED BY; Schema: dw; Owner: -
--

ALTER SEQUENCE dw.dim_canal_canal_sk_seq OWNED BY dw.dim_canal.canal_sk;


--
-- Name: dim_cliente; Type: TABLE; Schema: dw; Owner: -
--

CREATE TABLE dw.dim_cliente (
    cliente_sk bigint NOT NULL,
    cpf_normalizado character(11),
    cpf_valido boolean,
    nome_padronizado text NOT NULL,
    cidade text,
    uf character(2),
    dt_primeiro_cadastro date,
    id_legado integer,
    id_ecommerce bigint,
    origem_unificacao text NOT NULL,
    regra_pareamento text,
    CONSTRAINT ck_origem CHECK ((origem_unificacao = ANY (ARRAY['LEGADO'::text, 'ECOM'::text, 'AMBOS'::text])))
);


--
-- Name: dim_cliente_cliente_sk_seq; Type: SEQUENCE; Schema: dw; Owner: -
--

CREATE SEQUENCE dw.dim_cliente_cliente_sk_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dim_cliente_cliente_sk_seq; Type: SEQUENCE OWNED BY; Schema: dw; Owner: -
--

ALTER SEQUENCE dw.dim_cliente_cliente_sk_seq OWNED BY dw.dim_cliente.cliente_sk;


--
-- Name: dim_produto; Type: TABLE; Schema: dw; Owner: -
--

CREATE TABLE dw.dim_produto (
    produto_sk bigint NOT NULL,
    sku text,
    descricao text NOT NULL,
    categoria_nivel1 text,
    categoria_nivel2 text,
    categoria_origem text,
    preco_referencia numeric(12,2),
    ativo boolean,
    id_legado integer,
    id_ecommerce bigint,
    origem text NOT NULL
);


--
-- Name: dim_produto_produto_sk_seq; Type: SEQUENCE; Schema: dw; Owner: -
--

CREATE SEQUENCE dw.dim_produto_produto_sk_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dim_produto_produto_sk_seq; Type: SEQUENCE OWNED BY; Schema: dw; Owner: -
--

ALTER SEQUENCE dw.dim_produto_produto_sk_seq OWNED BY dw.dim_produto.produto_sk;


--
-- Name: dim_status; Type: TABLE; Schema: dw; Owner: -
--

CREATE TABLE dw.dim_status (
    status_sk integer NOT NULL,
    status_origem text NOT NULL,
    sistema text NOT NULL,
    status_conformado text NOT NULL,
    motivo_cancelamento text
);


--
-- Name: dim_status_status_sk_seq; Type: SEQUENCE; Schema: dw; Owner: -
--

CREATE SEQUENCE dw.dim_status_status_sk_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dim_status_status_sk_seq; Type: SEQUENCE OWNED BY; Schema: dw; Owner: -
--

ALTER SEQUENCE dw.dim_status_status_sk_seq OWNED BY dw.dim_status.status_sk;


--
-- Name: dim_tempo; Type: TABLE; Schema: dw; Owner: -
--

CREATE TABLE dw.dim_tempo (
    data_sk date NOT NULL,
    ano integer NOT NULL,
    trimestre integer NOT NULL,
    mes integer NOT NULL,
    dia integer NOT NULL,
    dia_semana integer NOT NULL,
    nome_mes text NOT NULL,
    eh_fim_semana boolean NOT NULL
);


--
-- Name: fato_atendimento; Type: TABLE; Schema: dw; Owner: -
--

CREATE TABLE dw.fato_atendimento (
    atendimento_sk bigint NOT NULL,
    protocolo text NOT NULL,
    cliente_sk bigint,
    pedido_sk bigint,
    data_abertura_sk date NOT NULL,
    data_fechamento_sk date,
    canal text,
    motivo_conformado text,
    nota_satisfacao integer,
    horas_resolucao numeric(10,2)
);


--
-- Name: fato_atendimento_atendimento_sk_seq; Type: SEQUENCE; Schema: dw; Owner: -
--

CREATE SEQUENCE dw.fato_atendimento_atendimento_sk_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fato_atendimento_atendimento_sk_seq; Type: SEQUENCE OWNED BY; Schema: dw; Owner: -
--

ALTER SEQUENCE dw.fato_atendimento_atendimento_sk_seq OWNED BY dw.fato_atendimento.atendimento_sk;


--
-- Name: fato_avaliacao; Type: TABLE; Schema: dw; Owner: -
--

CREATE TABLE dw.fato_avaliacao (
    avaliacao_sk bigint NOT NULL,
    review_id text NOT NULL,
    pedido_sk bigint,
    produto_sk bigint,
    data_sk date NOT NULL,
    nota integer,
    compra_verificada boolean,
    votos_uteis integer
);


--
-- Name: fato_avaliacao_avaliacao_sk_seq; Type: SEQUENCE; Schema: dw; Owner: -
--

CREATE SEQUENCE dw.fato_avaliacao_avaliacao_sk_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fato_avaliacao_avaliacao_sk_seq; Type: SEQUENCE OWNED BY; Schema: dw; Owner: -
--

ALTER SEQUENCE dw.fato_avaliacao_avaliacao_sk_seq OWNED BY dw.fato_avaliacao.avaliacao_sk;


--
-- Name: fato_item_pedido; Type: TABLE; Schema: dw; Owner: -
--

CREATE TABLE dw.fato_item_pedido (
    item_sk bigint NOT NULL,
    pedido_sk bigint NOT NULL,
    produto_sk bigint NOT NULL,
    quantidade integer NOT NULL,
    valor_unitario numeric(12,2) NOT NULL,
    valor_desconto numeric(12,2) NOT NULL,
    valor_linha numeric(12,2) NOT NULL
);


--
-- Name: fato_item_pedido_item_sk_seq; Type: SEQUENCE; Schema: dw; Owner: -
--

CREATE SEQUENCE dw.fato_item_pedido_item_sk_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fato_item_pedido_item_sk_seq; Type: SEQUENCE OWNED BY; Schema: dw; Owner: -
--

ALTER SEQUENCE dw.fato_item_pedido_item_sk_seq OWNED BY dw.fato_item_pedido.item_sk;


--
-- Name: fato_pedido; Type: TABLE; Schema: dw; Owner: -
--

CREATE TABLE dw.fato_pedido (
    pedido_sk bigint NOT NULL,
    id_origem text NOT NULL,
    sistema_origem text NOT NULL,
    cliente_sk bigint NOT NULL,
    data_pedido_sk date NOT NULL,
    data_entrega_sk date,
    canal_sk integer NOT NULL,
    status_sk integer NOT NULL,
    qtd_itens integer NOT NULL,
    valor_mercadoria numeric(12,2) NOT NULL,
    valor_frete numeric(12,2) NOT NULL,
    valor_desconto numeric(12,2) NOT NULL,
    valor_total numeric(12,2) NOT NULL,
    dias_entrega integer
);


--
-- Name: fato_pedido_pedido_sk_seq; Type: SEQUENCE; Schema: dw; Owner: -
--

CREATE SEQUENCE dw.fato_pedido_pedido_sk_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fato_pedido_pedido_sk_seq; Type: SEQUENCE OWNED BY; Schema: dw; Owner: -
--

ALTER SEQUENCE dw.fato_pedido_pedido_sk_seq OWNED BY dw.fato_pedido.pedido_sk;


--
-- Name: item_pedido_conformado; Type: TABLE; Schema: dw; Owner: -
--

CREATE TABLE dw.item_pedido_conformado (
    id_origem text,
    sistema_origem text,
    id_produto_legado bigint,
    id_produto_ecommerce bigint,
    quantidade bigint,
    valor_unitario double precision,
    valor_desconto double precision,
    valor_linha double precision
);


--
-- Name: mapa_cliente_origem; Type: TABLE; Schema: dw; Owner: -
--

CREATE TABLE dw.mapa_cliente_origem (
    sistema text NOT NULL,
    id_origem_natural bigint NOT NULL,
    id_canonico bigint NOT NULL,
    regra text NOT NULL
);


--
-- Name: pedido_conformado; Type: TABLE; Schema: dw; Owner: -
--

CREATE TABLE dw.pedido_conformado (
    id_origem text,
    sistema_origem text,
    id_cliente_legado bigint,
    id_cliente_ecommerce bigint,
    data_pedido timestamp without time zone,
    canal_origem text,
    status_origem text,
    qtd_itens bigint,
    valor_mercadoria double precision,
    valor_frete double precision,
    valor_desconto double precision,
    valor_total double precision,
    data_entrega timestamp without time zone,
    entrega_sem_data boolean,
    dias_entrega double precision
);


--
-- Name: execucao_assercao; Type: TABLE; Schema: qa; Owner: -
--

CREATE TABLE qa.execucao_assercao (
    id bigint NOT NULL,
    executado_em timestamp with time zone DEFAULT now() NOT NULL,
    etapa text NOT NULL,
    nome text NOT NULL,
    descricao text,
    valor_obtido numeric,
    valor_esperado text,
    aprovado boolean NOT NULL
);


--
-- Name: execucao_assercao_id_seq; Type: SEQUENCE; Schema: qa; Owner: -
--

CREATE SEQUENCE qa.execucao_assercao_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: execucao_assercao_id_seq; Type: SEQUENCE OWNED BY; Schema: qa; Owner: -
--

ALTER SEQUENCE qa.execucao_assercao_id_seq OWNED BY qa.execucao_assercao.id;


--
-- Name: quarentena_item_pedido; Type: TABLE; Schema: qa; Owner: -
--

CREATE TABLE qa.quarentena_item_pedido (
    id bigint NOT NULL,
    id_origem text NOT NULL,
    sistema_origem text NOT NULL,
    id_produto_legado bigint,
    id_produto_ecommerce bigint,
    quantidade integer,
    valor_unitario numeric(12,2),
    valor_desconto numeric(12,2),
    valor_linha numeric(12,2),
    motivo text NOT NULL,
    detectado_em timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: quarentena_item_pedido_id_seq; Type: SEQUENCE; Schema: qa; Owner: -
--

CREATE SEQUENCE qa.quarentena_item_pedido_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: quarentena_item_pedido_id_seq; Type: SEQUENCE OWNED BY; Schema: qa; Owner: -
--

ALTER SEQUENCE qa.quarentena_item_pedido_id_seq OWNED BY qa.quarentena_item_pedido.id;


--
-- Name: ecom_category; Type: TABLE; Schema: stg; Owner: -
--

CREATE TABLE stg.ecom_category (
    category_id bigint,
    name text,
    parent_id double precision,
    _linha_origem bigint,
    _fonte text,
    _extraido_em timestamp with time zone
);


--
-- Name: ecom_customer; Type: TABLE; Schema: stg; Owner: -
--

CREATE TABLE stg.ecom_customer (
    customer_id bigint,
    full_name text,
    tax_id text,
    email text,
    created_at timestamp with time zone,
    city text,
    state text,
    phone text,
    _linha_origem bigint,
    _fonte text,
    _extraido_em timestamp with time zone
);


--
-- Name: ecom_order_item; Type: TABLE; Schema: stg; Owner: -
--

CREATE TABLE stg.ecom_order_item (
    order_item_id bigint,
    order_id bigint,
    product_id bigint,
    quantity bigint,
    unit_price double precision,
    discount double precision,
    _linha_origem bigint,
    _fonte text,
    _extraido_em timestamp with time zone
);


--
-- Name: ecom_orders; Type: TABLE; Schema: stg; Owner: -
--

CREATE TABLE stg.ecom_orders (
    order_id bigint,
    customer_id bigint,
    placed_at timestamp with time zone,
    delivered_at timestamp with time zone,
    status text,
    total_amount double precision,
    freight_amount double precision,
    channel text,
    _linha_origem bigint,
    _fonte text,
    _extraido_em timestamp with time zone
);


--
-- Name: ecom_product; Type: TABLE; Schema: stg; Owner: -
--

CREATE TABLE stg.ecom_product (
    product_id bigint,
    sku text,
    title text,
    category_id bigint,
    list_price double precision,
    active boolean,
    _linha_origem bigint,
    _fonte text,
    _extraido_em timestamp with time zone
);


--
-- Name: legado_clientes; Type: TABLE; Schema: stg; Owner: -
--

CREATE TABLE stg.legado_clientes (
    "ID_CLIENTE" bigint,
    "NOME" text,
    "CPF" text,
    "EMAIL" text,
    "DT_CADASTRO" date,
    "CIDADE" text,
    "UF" text,
    "TELEFONE" text,
    _linha_origem bigint,
    _fonte text,
    _extraido_em timestamp with time zone
);


--
-- Name: legado_itens_pedido; Type: TABLE; Schema: stg; Owner: -
--

CREATE TABLE stg.legado_itens_pedido (
    "ID_ITEM" bigint,
    "ID_PEDIDO" bigint,
    "ID_PRODUTO" bigint,
    "QTD" bigint,
    "VL_UNITARIO" double precision,
    "VL_DESCONTO" double precision,
    _linha_origem bigint,
    _fonte text,
    _extraido_em timestamp with time zone
);


--
-- Name: legado_pedidos; Type: TABLE; Schema: stg; Owner: -
--

CREATE TABLE stg.legado_pedidos (
    "ID_PEDIDO" bigint,
    "ID_CLIENTE" bigint,
    "DT_PEDIDO" timestamp without time zone,
    "DT_ENTREGA" timestamp without time zone,
    "STATUS" text,
    "VALOR_TOTAL" double precision,
    "VALOR_FRETE" double precision,
    "CANAL" text,
    _linha_origem bigint,
    _fonte text,
    _extraido_em timestamp with time zone
);


--
-- Name: legado_produtos; Type: TABLE; Schema: stg; Owner: -
--

CREATE TABLE stg.legado_produtos (
    "ID_PRODUTO" bigint,
    "DESCRICAO" text,
    "CATEGORIA" text,
    "PRECO_TABELA" double precision,
    "ATIVO" text,
    _linha_origem bigint,
    _fonte text,
    _extraido_em timestamp with time zone
);


--
-- Name: marketplace_avaliacoes; Type: TABLE; Schema: stg; Owner: -
--

CREATE TABLE stg.marketplace_avaliacoes (
    review_id text,
    order_ref text,
    channel text,
    product_sku text,
    submitted_at text,
    rating text,
    title text,
    comment text,
    verified_purchase boolean,
    helpful_votes double precision,
    _rating_presente boolean,
    _title_presente boolean,
    _comment_presente boolean,
    _verified_presente boolean,
    _helpful_presente boolean,
    _linha_origem bigint,
    _fonte text,
    _extraido_em timestamp with time zone
);


--
-- Name: sac_atendimentos; Type: TABLE; Schema: stg; Owner: -
--

CREATE TABLE stg.sac_atendimentos (
    protocolo text,
    origem_sistema text,
    id_pedido_origem text,
    cpf_cliente text,
    data_abertura text,
    data_fechamento text,
    canal text,
    motivo text,
    nota_satisfacao text,
    tempo_resolucao_horas text,
    _linha_origem bigint,
    _fonte text,
    _extraido_em timestamp with time zone
);


--
-- Name: dim_canal canal_sk; Type: DEFAULT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.dim_canal ALTER COLUMN canal_sk SET DEFAULT nextval('dw.dim_canal_canal_sk_seq'::regclass);


--
-- Name: dim_cliente cliente_sk; Type: DEFAULT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.dim_cliente ALTER COLUMN cliente_sk SET DEFAULT nextval('dw.dim_cliente_cliente_sk_seq'::regclass);


--
-- Name: dim_produto produto_sk; Type: DEFAULT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.dim_produto ALTER COLUMN produto_sk SET DEFAULT nextval('dw.dim_produto_produto_sk_seq'::regclass);


--
-- Name: dim_status status_sk; Type: DEFAULT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.dim_status ALTER COLUMN status_sk SET DEFAULT nextval('dw.dim_status_status_sk_seq'::regclass);


--
-- Name: fato_atendimento atendimento_sk; Type: DEFAULT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_atendimento ALTER COLUMN atendimento_sk SET DEFAULT nextval('dw.fato_atendimento_atendimento_sk_seq'::regclass);


--
-- Name: fato_avaliacao avaliacao_sk; Type: DEFAULT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_avaliacao ALTER COLUMN avaliacao_sk SET DEFAULT nextval('dw.fato_avaliacao_avaliacao_sk_seq'::regclass);


--
-- Name: fato_item_pedido item_sk; Type: DEFAULT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_item_pedido ALTER COLUMN item_sk SET DEFAULT nextval('dw.fato_item_pedido_item_sk_seq'::regclass);


--
-- Name: fato_pedido pedido_sk; Type: DEFAULT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_pedido ALTER COLUMN pedido_sk SET DEFAULT nextval('dw.fato_pedido_pedido_sk_seq'::regclass);


--
-- Name: execucao_assercao id; Type: DEFAULT; Schema: qa; Owner: -
--

ALTER TABLE ONLY qa.execucao_assercao ALTER COLUMN id SET DEFAULT nextval('qa.execucao_assercao_id_seq'::regclass);


--
-- Name: quarentena_item_pedido id; Type: DEFAULT; Schema: qa; Owner: -
--

ALTER TABLE ONLY qa.quarentena_item_pedido ALTER COLUMN id SET DEFAULT nextval('qa.quarentena_item_pedido_id_seq'::regclass);


--
-- Name: recompra_90d pk_recompra_90d; Type: CONSTRAINT; Schema: abt; Owner: -
--

ALTER TABLE ONLY abt.recompra_90d
    ADD CONSTRAINT pk_recompra_90d PRIMARY KEY (cliente_sk, data_corte);


--
-- Name: recompra_90d_vazamento pk_recompra_90d_vazamento; Type: CONSTRAINT; Schema: abt; Owner: -
--

ALTER TABLE ONLY abt.recompra_90d_vazamento
    ADD CONSTRAINT pk_recompra_90d_vazamento PRIMARY KEY (cliente_sk, data_corte);


--
-- Name: dim_canal dim_canal_pkey; Type: CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.dim_canal
    ADD CONSTRAINT dim_canal_pkey PRIMARY KEY (canal_sk);


--
-- Name: dim_cliente dim_cliente_pkey; Type: CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.dim_cliente
    ADD CONSTRAINT dim_cliente_pkey PRIMARY KEY (cliente_sk);


--
-- Name: dim_produto dim_produto_pkey; Type: CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.dim_produto
    ADD CONSTRAINT dim_produto_pkey PRIMARY KEY (produto_sk);


--
-- Name: dim_status dim_status_pkey; Type: CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.dim_status
    ADD CONSTRAINT dim_status_pkey PRIMARY KEY (status_sk);


--
-- Name: dim_status dim_status_status_origem_sistema_key; Type: CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.dim_status
    ADD CONSTRAINT dim_status_status_origem_sistema_key UNIQUE (status_origem, sistema);


--
-- Name: dim_tempo dim_tempo_pkey; Type: CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.dim_tempo
    ADD CONSTRAINT dim_tempo_pkey PRIMARY KEY (data_sk);


--
-- Name: fato_atendimento fato_atendimento_pkey; Type: CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_atendimento
    ADD CONSTRAINT fato_atendimento_pkey PRIMARY KEY (atendimento_sk);


--
-- Name: fato_atendimento fato_atendimento_protocolo_key; Type: CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_atendimento
    ADD CONSTRAINT fato_atendimento_protocolo_key UNIQUE (protocolo);


--
-- Name: fato_avaliacao fato_avaliacao_pkey; Type: CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_avaliacao
    ADD CONSTRAINT fato_avaliacao_pkey PRIMARY KEY (avaliacao_sk);


--
-- Name: fato_avaliacao fato_avaliacao_review_id_key; Type: CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_avaliacao
    ADD CONSTRAINT fato_avaliacao_review_id_key UNIQUE (review_id);


--
-- Name: fato_item_pedido fato_item_pedido_pkey; Type: CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_item_pedido
    ADD CONSTRAINT fato_item_pedido_pkey PRIMARY KEY (item_sk);


--
-- Name: fato_pedido fato_pedido_id_origem_sistema_origem_key; Type: CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_pedido
    ADD CONSTRAINT fato_pedido_id_origem_sistema_origem_key UNIQUE (id_origem, sistema_origem);


--
-- Name: fato_pedido fato_pedido_pkey; Type: CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_pedido
    ADD CONSTRAINT fato_pedido_pkey PRIMARY KEY (pedido_sk);


--
-- Name: mapa_cliente_origem mapa_cliente_origem_pkey; Type: CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.mapa_cliente_origem
    ADD CONSTRAINT mapa_cliente_origem_pkey PRIMARY KEY (sistema, id_origem_natural);


--
-- Name: execucao_assercao execucao_assercao_pkey; Type: CONSTRAINT; Schema: qa; Owner: -
--

ALTER TABLE ONLY qa.execucao_assercao
    ADD CONSTRAINT execucao_assercao_pkey PRIMARY KEY (id);


--
-- Name: quarentena_item_pedido quarentena_item_pedido_pkey; Type: CONSTRAINT; Schema: qa; Owner: -
--

ALTER TABLE ONLY qa.quarentena_item_pedido
    ADD CONSTRAINT quarentena_item_pedido_pkey PRIMARY KEY (id);


--
-- Name: ix_dim_cliente_cpf; Type: INDEX; Schema: dw; Owner: -
--

CREATE INDEX ix_dim_cliente_cpf ON dw.dim_cliente USING btree (cpf_normalizado);


--
-- Name: ix_dim_cliente_id_ecommerce; Type: INDEX; Schema: dw; Owner: -
--

CREATE INDEX ix_dim_cliente_id_ecommerce ON dw.dim_cliente USING btree (id_ecommerce);


--
-- Name: ix_dim_cliente_id_legado; Type: INDEX; Schema: dw; Owner: -
--

CREATE INDEX ix_dim_cliente_id_legado ON dw.dim_cliente USING btree (id_legado);


--
-- Name: ix_dim_produto_id_ecommerce; Type: INDEX; Schema: dw; Owner: -
--

CREATE INDEX ix_dim_produto_id_ecommerce ON dw.dim_produto USING btree (id_ecommerce);


--
-- Name: ix_dim_produto_id_legado; Type: INDEX; Schema: dw; Owner: -
--

CREATE INDEX ix_dim_produto_id_legado ON dw.dim_produto USING btree (id_legado);


--
-- Name: ix_dim_produto_sku; Type: INDEX; Schema: dw; Owner: -
--

CREATE INDEX ix_dim_produto_sku ON dw.dim_produto USING btree (sku);


--
-- Name: ix_fato_pedido_cli; Type: INDEX; Schema: dw; Owner: -
--

CREATE INDEX ix_fato_pedido_cli ON dw.fato_pedido USING btree (cliente_sk);


--
-- Name: ix_fato_pedido_data; Type: INDEX; Schema: dw; Owner: -
--

CREATE INDEX ix_fato_pedido_data ON dw.fato_pedido USING btree (data_pedido_sk);


--
-- Name: recompra_90d fk_recompra_90d_cliente; Type: FK CONSTRAINT; Schema: abt; Owner: -
--

ALTER TABLE ONLY abt.recompra_90d
    ADD CONSTRAINT fk_recompra_90d_cliente FOREIGN KEY (cliente_sk) REFERENCES dw.dim_cliente(cliente_sk);


--
-- Name: recompra_90d_vazamento fk_recompra_90d_vazamento_cliente; Type: FK CONSTRAINT; Schema: abt; Owner: -
--

ALTER TABLE ONLY abt.recompra_90d_vazamento
    ADD CONSTRAINT fk_recompra_90d_vazamento_cliente FOREIGN KEY (cliente_sk) REFERENCES dw.dim_cliente(cliente_sk);


--
-- Name: fato_atendimento fato_atendimento_cliente_sk_fkey; Type: FK CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_atendimento
    ADD CONSTRAINT fato_atendimento_cliente_sk_fkey FOREIGN KEY (cliente_sk) REFERENCES dw.dim_cliente(cliente_sk);


--
-- Name: fato_atendimento fato_atendimento_data_abertura_sk_fkey; Type: FK CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_atendimento
    ADD CONSTRAINT fato_atendimento_data_abertura_sk_fkey FOREIGN KEY (data_abertura_sk) REFERENCES dw.dim_tempo(data_sk);


--
-- Name: fato_atendimento fato_atendimento_data_fechamento_sk_fkey; Type: FK CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_atendimento
    ADD CONSTRAINT fato_atendimento_data_fechamento_sk_fkey FOREIGN KEY (data_fechamento_sk) REFERENCES dw.dim_tempo(data_sk);


--
-- Name: fato_atendimento fato_atendimento_pedido_sk_fkey; Type: FK CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_atendimento
    ADD CONSTRAINT fato_atendimento_pedido_sk_fkey FOREIGN KEY (pedido_sk) REFERENCES dw.fato_pedido(pedido_sk);


--
-- Name: fato_avaliacao fato_avaliacao_data_sk_fkey; Type: FK CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_avaliacao
    ADD CONSTRAINT fato_avaliacao_data_sk_fkey FOREIGN KEY (data_sk) REFERENCES dw.dim_tempo(data_sk);


--
-- Name: fato_avaliacao fato_avaliacao_pedido_sk_fkey; Type: FK CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_avaliacao
    ADD CONSTRAINT fato_avaliacao_pedido_sk_fkey FOREIGN KEY (pedido_sk) REFERENCES dw.fato_pedido(pedido_sk);


--
-- Name: fato_avaliacao fato_avaliacao_produto_sk_fkey; Type: FK CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_avaliacao
    ADD CONSTRAINT fato_avaliacao_produto_sk_fkey FOREIGN KEY (produto_sk) REFERENCES dw.dim_produto(produto_sk);


--
-- Name: fato_item_pedido fato_item_pedido_pedido_sk_fkey; Type: FK CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_item_pedido
    ADD CONSTRAINT fato_item_pedido_pedido_sk_fkey FOREIGN KEY (pedido_sk) REFERENCES dw.fato_pedido(pedido_sk);


--
-- Name: fato_item_pedido fato_item_pedido_produto_sk_fkey; Type: FK CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_item_pedido
    ADD CONSTRAINT fato_item_pedido_produto_sk_fkey FOREIGN KEY (produto_sk) REFERENCES dw.dim_produto(produto_sk);


--
-- Name: fato_pedido fato_pedido_canal_sk_fkey; Type: FK CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_pedido
    ADD CONSTRAINT fato_pedido_canal_sk_fkey FOREIGN KEY (canal_sk) REFERENCES dw.dim_canal(canal_sk);


--
-- Name: fato_pedido fato_pedido_cliente_sk_fkey; Type: FK CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_pedido
    ADD CONSTRAINT fato_pedido_cliente_sk_fkey FOREIGN KEY (cliente_sk) REFERENCES dw.dim_cliente(cliente_sk);


--
-- Name: fato_pedido fato_pedido_data_entrega_sk_fkey; Type: FK CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_pedido
    ADD CONSTRAINT fato_pedido_data_entrega_sk_fkey FOREIGN KEY (data_entrega_sk) REFERENCES dw.dim_tempo(data_sk);


--
-- Name: fato_pedido fato_pedido_data_pedido_sk_fkey; Type: FK CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_pedido
    ADD CONSTRAINT fato_pedido_data_pedido_sk_fkey FOREIGN KEY (data_pedido_sk) REFERENCES dw.dim_tempo(data_sk);


--
-- Name: fato_pedido fato_pedido_status_sk_fkey; Type: FK CONSTRAINT; Schema: dw; Owner: -
--

ALTER TABLE ONLY dw.fato_pedido
    ADD CONSTRAINT fato_pedido_status_sk_fkey FOREIGN KEY (status_sk) REFERENCES dw.dim_status(status_sk);


--
-- PostgreSQL database dump complete
--

\unrestrict RrFiaxp8896Cd6aD8yWxoC5A6kd4AZvURyboLyc2J41MbIGgMuoQ5DCLl4cSm0D

