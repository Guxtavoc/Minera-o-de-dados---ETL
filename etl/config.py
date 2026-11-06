# -*- coding: utf-8 -*-
"""Conexões e parâmetros do laboratório. Não altere sem registrar no RDT."""

import os
from sqlalchemy import create_engine

DIR_DADOS = os.environ.get("DIR_DADOS", "/dados")
DIR_SAIDA = os.environ.get("DIR_SAIDA", "/saida")

# MySQL legado em latin1.
MYSQL_DSN = os.environ.get(
    "MYSQL_DSN",
    "mysql+pymysql://etl_ro:etl_ro@mysql_legado:3306/loja_legado?charset=latin1")

# PostgreSQL de e-commerce, somente leitura.
PG_ORIGEM_DSN = os.environ.get(
    "PG_ORIGEM_DSN",
    "postgresql+psycopg2://etl_ro:etl_ro@pg_ecommerce:5432/ecommerce")

# PostgreSQL analítico, com leitura e escrita.
PG_DW_DSN = os.environ.get(
    "PG_DW_DSN",
    "postgresql+psycopg2://postgres:postgres@pg_dw:5432/mercatto_dw")

# CSV do SAC: latin-1, separador ';', decimal ',' e data dd/mm/aaaa.
ARQ_SAC = os.path.join(DIR_DADOS, "atendimentos_sac.csv")

# NDJSON de avaliações: UTF-8, um objeto por linha.
ARQ_AVALIACOES = os.path.join(DIR_DADOS, "avaliacoes_marketplace.json")

# Parâmetros analíticos fixados pelo enunciado.
DATA_CORTE = "2025-06-30"  # Limite dos atributos preditivos.
JANELA_ALVO_DIAS = 90  # Janela de observação da recompra.
DATA_FIM_ALVO = "2025-09-28"


def eng_mysql():
    return create_engine(MYSQL_DSN, pool_pre_ping=True)


def eng_origem():
    return create_engine(PG_ORIGEM_DSN, pool_pre_ping=True)


def eng_dw():
    return create_engine(PG_DW_DSN, pool_pre_ping=True)
