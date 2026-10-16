#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETAPA 1 — EXTRAÇÃO

Objetivo: trazer as quatro fontes para o esquema `stg` do DW, SEM transformar
significado. Renomear, converter tipo e decidir o que é nulo vem depois.

Regra da camada stg (seção 2.3 do referencial):
  · nomes de coluna espelham a origem;
  · nenhum valor é descartado, corrigido ou reinterpretado;
  · acrescente apenas metadados de procedência:
        _fonte           de onde veio
        _extraido_em     quando
        _linha_origem    posição na origem

Decisão registrada no RDT-01: CARGA COMPLETA (full load), não incremental.
Nenhuma das quatro origens oferece coluna confiável de "última alteração" e o
pipeline precisa ser reprodutível do zero; então a cada execução o `stg` é
reescrito por inteiro (if_exists="replace" no primeiro bloco de cada tabela).

    docker compose exec etl python 01_extracao.py
"""

import json
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import text

from config import (ARQ_AVALIACOES, ARQ_SAC, eng_dw, eng_mysql, eng_origem)
from qualidade.assercoes import Suite

AGORA = datetime.now(timezone.utc)
LOTE = 50_000          # leia em blocos: a base não cabe confortavelmente na RAM


def grava_stg(df, tabela, engine, primeiro_bloco):
    """Grava um bloco no stg. O primeiro bloco recria a tabela (carga full)."""
    df["_fonte"] = tabela.split("_")[0]
    df["_extraido_em"] = AGORA
    df.to_sql(tabela, engine, schema="stg",
              if_exists="replace" if primeiro_bloco else "append",
              index=False, method="multi", chunksize=5_000)


def extrai_tabela(engine_origem, sql, tabela_stg, engine_dw):
    """Lê a origem em blocos e devolve o total de linhas gravadas no stg."""
    primeiro = True
    total = 0
    with engine_origem.connect() as cx:
        for bloco in pd.read_sql(text(sql), cx, chunksize=LOTE):
            bloco["_linha_origem"] = range(total, total + len(bloco))
            grava_stg(bloco, tabela_stg, engine_dw, primeiro)
            primeiro = False
            total += len(bloco)
    print(f"  stg.{tabela_stg}: {total} linhas")
    return total


def conta_origem(engine_origem, sql):
    with engine_origem.connect() as cx:
        return int(cx.execute(text(sql)).scalar())


# ---------------------------------------------------------------------------
# Fonte 1 — MySQL legado (charset latin1 definido em config.py)
# ---------------------------------------------------------------------------
def extrai_mysql(qa):
    eng, dw = eng_mysql(), eng_dw()
    mapa = [
        ("CLIENTES", "legado_clientes"),
        ("PRODUTOS", "legado_produtos"),
        ("PEDIDOS", "legado_pedidos"),
        ("ITENS_PEDIDO", "legado_itens_pedido"),
    ]
    for origem, destino in mapa:
        n = extrai_tabela(eng, f"SELECT * FROM {origem}", destino, dw)
        esperado = conta_origem(eng, f"SELECT COUNT(*) FROM {origem}")
        qa.igual(f"linhas {destino}", n, esperado,
                 "extração que perde linha silenciosamente é o defeito mais caro")


# ---------------------------------------------------------------------------
# Fonte 2 — PostgreSQL e-commerce (TIMESTAMPTZ)
# ---------------------------------------------------------------------------
def extrai_postgres(qa):
    eng, dw = eng_origem(), eng_dw()
    # category entra aqui porque a taxonomia controlada é insumo da DECISÃO 4.
    mapa = [
        ("category", "ecom_category"),
        ("customer", "ecom_customer"),
        ("product", "ecom_product"),
        ("orders", "ecom_orders"),
        ("order_item", "ecom_order_item"),
    ]
    for origem, destino in mapa:
        n = extrai_tabela(eng, f"SELECT * FROM shop.{origem}", destino, dw)
        esperado = conta_origem(eng, f"SELECT COUNT(*) FROM shop.{origem}")
        qa.igual(f"linhas {destino}", n, esperado,
                 "contagem do stg deve bater com a origem")
    # Fuso: no stg os TIMESTAMPTZ são preservados com fuso; a padronização
    # (DECISÃO 5) acontece na etapa 2.


# ---------------------------------------------------------------------------
# Fonte 3 — CSV do SAC (latin-1, ';', decimal com vírgula, dd/mm/aaaa)
# ---------------------------------------------------------------------------
def extrai_sac(qa):
    dw = eng_dw()
    # dtype=str: conversão de tipo é transformação e ocorre na etapa 2.
    # keep_default_na=False: string vazia fica vazia; NULL é o que não existe.
    df = pd.read_csv(ARQ_SAC, sep=";", encoding="latin-1", dtype=str,
                     keep_default_na=False)
    df["_linha_origem"] = range(len(df))
    grava_stg(df, "sac_atendimentos", dw, True)
    print(f"  stg.sac_atendimentos: {len(df)} linhas")
    return len(df)


# ---------------------------------------------------------------------------
# Fonte 4 — NDJSON de avaliações do marketplace
# ---------------------------------------------------------------------------
def extrai_avaliacoes(qa):
    dw = eng_dw()
    registros = []
    with open(ARQ_AVALIACOES, encoding="utf-8") as f:
        for i, linha in enumerate(f):
            o = json.loads(linha)
            ped = o.get("order") or {}
            prod = o.get("product") or {}
            registros.append({
                "review_id": o.get("review_id"),
                "order_ref": ped.get("ref"),
                "channel": ped.get("channel"),
                "product_sku": prod.get("sku"),
                "submitted_at": o.get("submitted_at"),
                # rating vem ora número, ora texto: no stg guardamos como texto.
                "rating": str(o["rating"]) if "rating" in o else "",
                "title": o.get("title", ""),
                "comment": o.get("comment", ""),
                "verified_purchase": o.get("verified_purchase"),
                "helpful_votes": o.get("helpful_votes"),
                # presença das chaves opcionais: chave omitida != valor nulo
                "_rating_presente": "rating" in o,
                "_title_presente": "title" in o,
                "_comment_presente": "comment" in o,
                "_verified_presente": "verified_purchase" in o,
                "_helpful_presente": "helpful_votes" in o,
                "_linha_origem": i,
            })
    df = pd.DataFrame(registros)
    grava_stg(df, "marketplace_avaliacoes", dw, True)
    print(f"  stg.marketplace_avaliacoes: {len(df)} linhas")
    return df


if __name__ == "__main__":
    qa = Suite(etapa="01_extracao")

    print("extraindo fontes:")
    extrai_mysql(qa)
    extrai_postgres(qa)
    extrai_sac(qa)
    df_aval = extrai_avaliacoes(qa)

    dw = eng_dw()
    qa.igual("linhas stg.sac_atendimentos",
             int(pd.read_sql(text("SELECT COUNT(*) FROM stg.sac_atendimentos"),
                             dw).iloc[0, 0]), 96140,
             "contagem total do CSV concatenado")
    qa.sem_nulos("protocolo do SAC",
                 pd.read_sql(text("SELECT protocolo FROM stg.sac_atendimentos"),
                             dw)["protocolo"])
    qa.unico("review_id", df_aval["review_id"])

    qa.registrar(dw)
    qa.imprimir()
