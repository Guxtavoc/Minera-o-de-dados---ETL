#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETAPA 4 — TABELA-BASE DE ANÁLISE (ABT) E O EXPERIMENTO DE VAZAMENTO

Pergunta analítica:
    dado o comportamento do cliente ATÉ 2025-06-30, ele comprará de novo
    entre 2025-07-01 e 2025-09-28?

Esta etapa produz DUAS versões da mesma tabela:

    --correta     todos os atributos calculados apenas com dados até a data
                  de corte. É a versão que vale.

    --vazamento   a mesma coisa, só que com dois ou três atributos calculados
                  sobre a base inteira. É a versão errada, que vocês vão
                  construir de propósito, rodar no Orange e comparar.

    docker compose exec etl python 04_abt.py --correta
    docker compose exec etl python 04_abt.py --vazamento
"""

import argparse

import pandas as pd
from sqlalchemy import text

from config import DATA_CORTE, DATA_FIM_ALVO, eng_dw
from qualidade.assercoes import Suite


# ---------------------------------------------------------------------------
# ALVO — este está pronto, e é o único ponto do pipeline em que é legítimo
# olhar para o futuro, porque é exatamente isso que se quer prever.
# ---------------------------------------------------------------------------
SQL_ALVO = f"""
WITH base AS (
    SELECT DISTINCT c.cliente_sk
    FROM dw.dim_cliente c
    JOIN dw.fato_pedido p ON p.cliente_sk = c.cliente_sk
    WHERE p.data_pedido_sk <= DATE '{DATA_CORTE}'
),
compras_na_janela AS (
    SELECT DISTINCT p.cliente_sk
    FROM dw.fato_pedido p
    JOIN dw.dim_status s ON s.status_sk = p.status_sk
    WHERE p.data_pedido_sk >  DATE '{DATA_CORTE}'
      AND p.data_pedido_sk <= DATE '{DATA_FIM_ALVO}'
      AND s.status_conformado <> 'CANCELADO'
)
SELECT b.cliente_sk,
       DATE '{DATA_CORTE}' AS data_corte,
       CASE WHEN j.cliente_sk IS NOT NULL THEN 1 ELSE 0 END AS alvo_recompra_90d
FROM base b
LEFT JOIN compras_na_janela j ON j.cliente_sk = b.cliente_sk
"""


# ---------------------------------------------------------------------------
# ATRIBUTOS — a única diferença entre a versão correta e a com vazamento é
# a base usada para frequência e recência. Na correta, ped_corte; na outra,
# ped_all. O resto dos agregados continua explicitamente limitado ao corte.
# ---------------------------------------------------------------------------
_SQL_ATRIBUTOS = f"""
WITH alvo AS (
{SQL_ALVO}
),
ped_corte AS (
    SELECT p.cliente_sk, p.pedido_sk, p.data_pedido_sk, p.data_entrega_sk,
           p.dias_entrega, p.valor_total, p.canal_sk, s.status_conformado
    FROM dw.fato_pedido p
    JOIN dw.dim_status s ON s.status_sk = p.status_sk
    WHERE p.data_pedido_sk <= DATE '{DATA_CORTE}'
),
ped_all AS (
    SELECT p.cliente_sk, p.pedido_sk, p.data_pedido_sk, p.data_entrega_sk,
           p.dias_entrega, p.valor_total, p.canal_sk, s.status_conformado
    FROM dw.fato_pedido p
    JOIN dw.dim_status s ON s.status_sk = p.status_sk
),
agg AS (
    SELECT cliente_sk,
           count(*) FILTER (WHERE status_conformado <> 'CANCELADO') AS frequencia,
           max(data_pedido_sk) FILTER (WHERE status_conformado <> 'CANCELADO') AS ultima,
           min(data_pedido_sk) AS primeira,
           coalesce(sum(valor_total) FILTER (
               WHERE status_conformado <> 'CANCELADO'
                 AND data_pedido_sk <= DATE '{DATA_CORTE}'), 0) AS valor,
           avg(dias_entrega) FILTER (
               WHERE status_conformado <> 'CANCELADO'
                 AND data_entrega_sk IS NOT NULL
                 AND data_pedido_sk <= DATE '{DATA_CORTE}'
                 AND data_entrega_sk <= DATE '{DATA_CORTE}') AS prazo,
           count(*) FILTER (
               WHERE status_conformado = 'CANCELADO'
                 AND data_pedido_sk <= DATE '{DATA_CORTE}') AS cancelados,
           count(*) FILTER (
               WHERE data_pedido_sk <= DATE '{DATA_CORTE}') AS total
    FROM {{ped_base}}
    GROUP BY cliente_sk
),
canal AS (
    SELECT p.cliente_sk,
           mode() WITHIN GROUP (ORDER BY c.canal_conformado) AS canal
    FROM ped_corte p
    JOIN dw.dim_canal c ON c.canal_sk = p.canal_sk
    GROUP BY p.cliente_sk
),
itens AS (
    SELECT p.cliente_sk,
           count(DISTINCT d.categoria_nivel1) AS categorias,
           coalesce(sum(i.quantidade), 0) AS qtd_itens
    FROM ped_corte p
    JOIN dw.fato_item_pedido i ON i.pedido_sk = p.pedido_sk
    JOIN dw.dim_produto d ON d.produto_sk = i.produto_sk
    WHERE p.status_conformado <> 'CANCELADO'
    GROUP BY p.cliente_sk
),
sac AS (
    SELECT cliente_sk, count(*) AS qtd
    FROM dw.fato_atendimento
    WHERE data_abertura_sk <= DATE '{DATA_CORTE}'
    GROUP BY cliente_sk
),
aval AS (
    SELECT p.cliente_sk, avg(a.nota) AS nota
    FROM dw.fato_avaliacao a
    JOIN dw.fato_pedido p ON p.pedido_sk = a.pedido_sk
    WHERE a.data_sk <= DATE '{DATA_CORTE}'
    GROUP BY p.cliente_sk
)
SELECT a.cliente_sk,
       (DATE '{DATA_CORTE}' - g.ultima) AS recencia_dias,
       coalesce(g.frequencia, 0)::int AS frequencia_pedidos,
       coalesce(g.valor, 0)::numeric(14,2) AS valor_monetario,
       CASE WHEN coalesce(g.frequencia, 0) > 0
            THEN round(g.valor / g.frequencia, 2) ELSE 0 END AS ticket_medio,
       round(g.prazo::numeric, 2) AS prazo_medio_entrega,
       CASE WHEN coalesce(g.total, 0) > 0
            THEN round(g.cancelados::numeric / g.total, 4) ELSE 0 END
            AS taxa_cancelamento,
       coalesce(it.categorias, 0)::int AS categorias_distintas,
       ca.canal AS canal_predominante,
       coalesce(s.qtd, 0)::int AS qtd_atendimentos_sac,
       round(av.nota::numeric, 2) AS nota_media_avaliacoes,
       (DATE '{DATA_CORTE}' - g.primeira) AS tempo_como_cliente,
       coalesce(it.qtd_itens, 0)::int AS qtd_itens
FROM alvo a
LEFT JOIN agg g   ON g.cliente_sk = a.cliente_sk
LEFT JOIN canal ca ON ca.cliente_sk = a.cliente_sk
LEFT JOIN itens it ON it.cliente_sk = a.cliente_sk
LEFT JOIN sac s    ON s.cliente_sk = a.cliente_sk
LEFT JOIN aval av  ON av.cliente_sk = a.cliente_sk
"""


def _sql_atributos(com_vazamento):
    return _SQL_ATRIBUTOS.format(ped_base="ped_all" if com_vazamento else "ped_corte")


def monta_atributos_corretos(dw):
    """
    Atributos calculados somente com pedidos até 2025-06-30.

    Decisões de ausência:
      · cliente sem pedido não cancelado: frequência/valor/itens = 0 e
        recência = NULL (não é zero: ele não tem última compra válida);
      · prazo_medio_entrega e nota_media_avaliacoes = NULL quando não há
        entrega/avaliação até o corte;
      · taxa_cancelamento = 0 quando não há pedido no período.
    """
    return pd.read_sql(text(_sql_atributos(False)), dw)


def monta_atributos_com_vazamento(dw):
    """
    Duas fugas deliberadas:
      1. frequencia_pedidos e recencia_dias usam pedidos de TODA a série,
         inclusive os da janela do alvo e posteriores a ela;
      2. valor_monetario_z é normalizado com média/desvio de todas as linhas,
         incluindo o futuro.
    """
    atributos = pd.read_sql(text(_sql_atributos(True)), dw)
    media = atributos["valor_monetario"].mean()
    desvio = atributos["valor_monetario"].std(ddof=0)
    if desvio and desvio > 0:
        atributos["valor_monetario_z"] = (
            (atributos["valor_monetario"] - media) / desvio
        ).round(6)
    else:
        atributos["valor_monetario_z"] = 0.0
    return atributos


def verifica_sem_vazamento(qa, abt, dw):
    """Recalcula recência/frequência/prazo em uma amostra, só com dados até o corte."""
    amostra = abt.sample(min(500, len(abt)), random_state=42)
    ids = [int(x) for x in amostra["cliente_sk"]]
    ref = pd.read_sql(text(f"""
        SELECT p.cliente_sk,
               DATE '{DATA_CORTE}' - max(p.data_pedido_sk) FILTER (
                   WHERE s.status_conformado <> 'CANCELADO') AS recencia_ref,
               count(*) FILTER (
                   WHERE s.status_conformado <> 'CANCELADO') AS frequencia_ref,
               round(avg(p.dias_entrega) FILTER (
                   WHERE s.status_conformado <> 'CANCELADO'
                     AND p.data_entrega_sk IS NOT NULL
                     AND p.data_entrega_sk <= DATE '{DATA_CORTE}'
               )::numeric, 2) AS prazo_ref
        FROM dw.fato_pedido p
        JOIN dw.dim_status s ON s.status_sk = p.status_sk
        WHERE p.data_pedido_sk <= DATE '{DATA_CORTE}'
          AND p.cliente_sk = ANY(:ids)
        GROUP BY p.cliente_sk
    """), dw, params={"ids": ids})

    m = amostra.merge(ref, on="cliente_sk", how="left")
    m["frequencia_ref"] = m["frequencia_ref"].fillna(0).astype(int)
    dif_freq = int((m["frequencia_pedidos"] != m["frequencia_ref"]).sum())
    iguais_rec = (
        (m["recencia_dias"].isna() & m["recencia_ref"].isna())
        | (m["recencia_dias"] == m["recencia_ref"])
    )
    dif_rec = int((~iguais_rec).sum())
    m["prazo_ref"] = pd.to_numeric(m["prazo_ref"], errors="coerce").round(2)
    m["prazo_medio_entrega"] = pd.to_numeric(
        m["prazo_medio_entrega"], errors="coerce").round(2)
    iguais_prazo = (
        (m["prazo_medio_entrega"].isna() & m["prazo_ref"].isna())
        | (m["prazo_medio_entrega"] == m["prazo_ref"])
    )
    dif_prazo = int((~iguais_prazo).sum())
    qa.igual("ABT correta: frequencia (amostra)", dif_freq, 0,
             "frequencia deve ignorar pedidos posteriores ao corte")
    qa.igual("ABT correta: recencia (amostra)", dif_rec, 0,
             "recencia deve ignorar pedidos posteriores ao corte")
    qa.igual("ABT correta: prazo (amostra)", dif_prazo, 0,
             "prazo deve ignorar entregas posteriores ao corte")


def garante_contrato_abt(dw, tabela):
    """Recria PK/FK/CHECK removidos pelo replace do pandas."""
    with dw.begin() as cx:
        for nome in (f"{tabela}_pkey", f"pk_{tabela}",
                     f"fk_{tabela}_cliente", f"ck_{tabela}_alvo"):
            cx.execute(text(
                f'ALTER TABLE abt.{tabela} DROP CONSTRAINT IF EXISTS "{nome}"'))
        cx.execute(text(f"""
            ALTER TABLE abt.{tabela}
              ALTER COLUMN cliente_sk SET NOT NULL,
              ALTER COLUMN data_corte SET NOT NULL,
              ALTER COLUMN alvo_recompra_90d SET NOT NULL,
              ALTER COLUMN alvo_recompra_90d TYPE SMALLINT
                USING alvo_recompra_90d::smallint
        """))
        cx.execute(text(f"""
            ALTER TABLE abt.{tabela}
              ADD CONSTRAINT pk_{tabela} PRIMARY KEY (cliente_sk, data_corte),
              ADD CONSTRAINT fk_{tabela}_cliente FOREIGN KEY (cliente_sk)
                REFERENCES dw.dim_cliente (cliente_sk),
              ADD CONSTRAINT ck_{tabela}_alvo
                CHECK (alvo_recompra_90d IN (0, 1))
        """))


def grava(df, dw, sufixo):
    tabela = "recompra_90d" if sufixo == "correta" else "recompra_90d_vazamento"
    df.to_sql(tabela, dw, schema="abt", if_exists="replace",
              index=False, method="multi", chunksize=5_000)
    garante_contrato_abt(dw, tabela)
    print(f"abt.{tabela}: {len(df)} linhas, {df.shape[1]} colunas")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--correta", action="store_true")
    ap.add_argument("--vazamento", action="store_true")
    args = ap.parse_args()
    if not (args.correta or args.vazamento):
        ap.error("escolha --correta ou --vazamento")

    dw = eng_dw()
    alvo = pd.read_sql(text(SQL_ALVO), dw)
    print(f"alvo: {len(alvo)} clientes | taxa de recompra = "
          f"{alvo['alvo_recompra_90d'].mean():.3f}")

    qa = Suite(etapa="04_abt_" + ("correta" if args.correta else "vazamento"))
    qa.entre("taxa do alvo", float(alvo["alvo_recompra_90d"].mean()), 0.02, 0.60,
             "classe extremamente desbalanceada indica erro na janela")
    qa.unico("cliente_sk no alvo", alvo["cliente_sk"])

    atributos = (monta_atributos_corretos(dw) if args.correta
                 else monta_atributos_com_vazamento(dw))

    antes = len(alvo)
    abt = alvo.merge(atributos, on="cliente_sk", how="left")
    qa.cardinalidade_preservada("junção alvo x atributos", antes, len(abt))

    if args.correta:
        verifica_sem_vazamento(qa, abt, dw)

    grava(abt, dw, "correta" if args.correta else "vazamento")
    qa.registrar(dw)
    qa.imprimir()
