#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETAPA 3 — CARGA NO ESQUEMA ESTRELA

Declaração de grão:
    Uma linha de dw.fato_pedido representa UM PEDIDO de uma das duas origens.
    Uma linha de dw.fato_item_pedido representa UMA LINHA DE ITEM de um pedido
    válido (a chave surrogate é item_sk; pedido_sk + produto_sk não é único).

As dimensões são carregadas na etapa 2. Esta etapa:
  · reconstrói dw.dim_tempo;
  · troca as chaves naturais pelas surrogate keys;
  · mapeia clientes removidos na dedup usando dw.mapa_cliente_origem;
  · coloca itens sem pedido em qa.quarentena_item_pedido;
  · carrega os fatos auxiliares (SAC e avaliações);
  · registra as asserções e a reconciliação financeira.

    docker compose exec etl python 03_carga_dw.py
"""

from datetime import date, timedelta

import pandas as pd
from sqlalchemy import text

from config import eng_dw
from qualidade.assercoes import Suite


def carrega_dim_tempo(engine, ini=date(2022, 12, 1), fim=date(2026, 3, 31)):
    """Esta dimensão está pronta — é a única sem decisão a tomar."""
    MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
             "agosto", "setembro", "outubro", "novembro", "dezembro"]
    linhas = []
    d = ini
    while d <= fim:
        linhas.append(dict(data_sk=d, ano=d.year, trimestre=(d.month - 1) // 3 + 1,
                           mes=d.month, dia=d.day, dia_semana=d.isoweekday(),
                           nome_mes=MESES[d.month - 1],
                           eh_fim_semana=d.isoweekday() >= 6))
        d += timedelta(days=1)
    df = pd.DataFrame(linhas)
    with engine.begin() as cx:
        cx.execute(text("TRUNCATE dw.dim_tempo CASCADE"))
    df.to_sql("dim_tempo", engine, schema="dw", if_exists="append", index=False)
    print(f"dim_tempo: {len(df)} datas")
    return len(df)


def carrega_dimensoes(qa):
    """As dimensões vêm prontas da etapa 2; aqui só validamos o contrato."""
    dw = eng_dw()
    with dw.connect() as cx:
        contagens = {
            t: int(cx.execute(text(f"SELECT count(*) FROM dw.{t}")).scalar())
            for t in ("dim_cliente", "dim_produto", "dim_canal", "dim_status")
        }
        dup_prod_leg = int(cx.execute(text(
            "SELECT count(*) FROM (SELECT id_legado FROM dw.dim_produto "
            "WHERE id_legado IS NOT NULL GROUP BY 1 HAVING count(*) > 1) x"
        )).scalar())
        dup_prod_eco = int(cx.execute(text(
            "SELECT count(*) FROM (SELECT id_ecommerce FROM dw.dim_produto "
            "WHERE id_ecommerce IS NOT NULL GROUP BY 1 HAVING count(*) > 1) x"
        )).scalar())

    qa.maior_igual("dim_cliente carregada", contagens["dim_cliente"], 1)
    qa.maior_igual("dim_produto carregada", contagens["dim_produto"], 1)
    qa.maior_igual("dim_canal carregada", contagens["dim_canal"], 1)
    qa.maior_igual("dim_status carregada", contagens["dim_status"], 1)
    qa.igual("dim_produto: id_legado duplicado", dup_prod_leg, 0)
    qa.igual("dim_produto: id_ecommerce duplicado", dup_prod_eco, 0)
    return contagens


def carrega_fato_pedido(qa):
    dw = eng_dw()

    with dw.connect() as cx:
        n_pedidos = int(cx.execute(text(
            "SELECT count(*) FROM dw.pedido_conformado")).scalar())
        sem_cliente = int(cx.execute(text("""
            SELECT count(*)
            FROM dw.pedido_conformado p
            LEFT JOIN dw.mapa_cliente_origem ml
              ON ml.sistema = 'LEGADO'
             AND ml.id_origem_natural = p.id_cliente_legado
            LEFT JOIN dw.dim_cliente cl ON cl.id_legado = ml.id_canonico
            LEFT JOIN dw.mapa_cliente_origem me
              ON me.sistema = 'ECOM'
             AND me.id_origem_natural = p.id_cliente_ecommerce
            LEFT JOIN dw.dim_cliente ce ON ce.id_ecommerce = me.id_canonico
            WHERE COALESCE(cl.cliente_sk, ce.cliente_sk) IS NULL
        """)).scalar())
        sem_canal = int(cx.execute(text("""
            SELECT count(*) FROM dw.pedido_conformado p
            WHERE NOT EXISTS (
                SELECT 1 FROM dw.dim_canal c
                WHERE c.sistema = p.sistema_origem
                  AND c.canal_origem = p.canal_origem)
        """)).scalar())
        sem_status = int(cx.execute(text("""
            SELECT count(*) FROM dw.pedido_conformado p
            WHERE NOT EXISTS (
                SELECT 1 FROM dw.dim_status s
                WHERE s.sistema = p.sistema_origem
                  AND s.status_origem = p.status_origem)
        """)).scalar())
        data_fora = int(cx.execute(text("""
            SELECT count(*) FROM dw.pedido_conformado p
            WHERE p.data_pedido::date NOT IN (SELECT data_sk FROM dw.dim_tempo)
               OR (p.data_entrega IS NOT NULL
                   AND p.data_entrega::date NOT IN (SELECT data_sk FROM dw.dim_tempo))
        """)).scalar())

    qa.igual("fato_pedido: cliente sem mapeamento", sem_cliente, 0,
             "todo pedido deve ter cliente_sk via mapa canonico")
    qa.igual("fato_pedido: canal sem mapeamento", sem_canal, 0)
    qa.igual("fato_pedido: status sem mapeamento", sem_status, 0)
    qa.igual("fato_pedido: data fora do calendario", data_fora, 0)
    if sem_cliente or sem_canal or sem_status or data_fora:
        raise RuntimeError("carga de fato_pedido abortada: chaves sem correspondencia")

    with dw.begin() as cx:
        cx.execute(text("""
            TRUNCATE dw.fato_item_pedido, dw.fato_pedido,
                     dw.fato_atendimento, dw.fato_avaliacao
            RESTART IDENTITY CASCADE
        """))
        res = cx.execute(text("""
            INSERT INTO dw.fato_pedido (
                id_origem, sistema_origem, cliente_sk, data_pedido_sk,
                data_entrega_sk, canal_sk, status_sk, qtd_itens,
                valor_mercadoria, valor_frete, valor_desconto, valor_total,
                dias_entrega)
            SELECT
                p.id_origem,
                p.sistema_origem,
                COALESCE(cl.cliente_sk, ce.cliente_sk),
                p.data_pedido::date,
                p.data_entrega::date,
                ca.canal_sk,
                st.status_sk,
                p.qtd_itens::int,
                round(p.valor_mercadoria::numeric, 2),
                round(p.valor_frete::numeric, 2),
                round(p.valor_desconto::numeric, 2),
                round(p.valor_total::numeric, 2),
                CASE WHEN p.dias_entrega IS NOT NULL
                     THEN p.dias_entrega::int END
            FROM dw.pedido_conformado p
            LEFT JOIN dw.mapa_cliente_origem ml
              ON ml.sistema = 'LEGADO'
             AND ml.id_origem_natural = p.id_cliente_legado
            LEFT JOIN dw.dim_cliente cl ON cl.id_legado = ml.id_canonico
            LEFT JOIN dw.mapa_cliente_origem me
              ON me.sistema = 'ECOM'
             AND me.id_origem_natural = p.id_cliente_ecommerce
            LEFT JOIN dw.dim_cliente ce ON ce.id_ecommerce = me.id_canonico
            JOIN dw.dim_canal ca
              ON ca.sistema = p.sistema_origem
             AND ca.canal_origem = p.canal_origem
            JOIN dw.dim_status st
              ON st.sistema = p.sistema_origem
             AND st.status_origem = p.status_origem
        """))
        n_ins = int(res.rowcount)
    qa.igual("fato_pedido: linhas", n_ins, n_pedidos,
             "uma linha por pedido conformado")

    with dw.connect() as cx:
        fk_orfa = int(cx.execute(text("""
            SELECT count(*) FROM dw.fato_pedido f
            WHERE NOT EXISTS (SELECT 1 FROM dw.dim_cliente c
                              WHERE c.cliente_sk = f.cliente_sk)
               OR NOT EXISTS (SELECT 1 FROM dw.dim_tempo t
                              WHERE t.data_sk = f.data_pedido_sk)
               OR (f.data_entrega_sk IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM dw.dim_tempo t
                    WHERE t.data_sk = f.data_entrega_sk))
               OR NOT EXISTS (SELECT 1 FROM dw.dim_canal c
                              WHERE c.canal_sk = f.canal_sk)
               OR NOT EXISTS (SELECT 1 FROM dw.dim_status s
                              WHERE s.status_sk = f.status_sk)
        """)).scalar())
        negativos = int(cx.execute(text(
            "SELECT count(*) FROM dw.fato_pedido WHERE dias_entrega < 0"
        )).scalar())
        por_sistema = {r[0]: float(r[1]) for r in cx.execute(text("""
            SELECT sistema_origem, sum(valor_total)
            FROM dw.fato_pedido GROUP BY 1
        """))}
        origem = {
            "LEGADO": float(cx.execute(text(
                'SELECT sum("VALOR_TOTAL") FROM stg.legado_pedidos')).scalar()),
            "ECOM": float(cx.execute(text("""
                SELECT sum(total_amount + coalesce(freight_amount, 0))
                FROM stg.ecom_orders
            """)).scalar()),
        }

    qa.igual("fato_pedido: FK orfa", fk_orfa, 0)
    qa.igual("fato_pedido: dias_entrega negativo", negativos, 0)
    for sistema in ("LEGADO", "ECOM"):
        ratio = por_sistema.get(sistema, 0.0) / origem[sistema]
        qa.entre(f"reconciliacao financeira {sistema}", ratio, 0.999, 1.001,
                 "fato dentro de ±0,1% do total da origem")

    print(f"fato_pedido: {n_ins} linhas; "
          f"LEGADO={por_sistema.get('LEGADO', 0):.2f}, "
          f"ECOM={por_sistema.get('ECOM', 0):.2f}")


def carrega_fato_item(qa):
    dw = eng_dw()

    with dw.connect() as cx:
        n_total = int(cx.execute(text(
            "SELECT count(*) FROM dw.item_pedido_conformado")).scalar())
        n_validos = int(cx.execute(text("""
            SELECT count(*) FROM dw.item_pedido_conformado i
            WHERE EXISTS (
                SELECT 1 FROM dw.fato_pedido f
                WHERE f.id_origem = i.id_origem
                  AND f.sistema_origem = i.sistema_origem)
        """)).scalar())
        sem_produto = int(cx.execute(text("""
            SELECT count(*) FROM dw.item_pedido_conformado i
            WHERE NOT EXISTS (SELECT 1 FROM dw.dim_produto p
                              WHERE p.id_legado = i.id_produto_legado)
              AND NOT EXISTS (SELECT 1 FROM dw.dim_produto p
                              WHERE p.id_ecommerce = i.id_produto_ecommerce)
        """)).scalar())

    qa.igual("fato_item: produto sem mapeamento", sem_produto, 0)
    if sem_produto:
        raise RuntimeError("carga de fato_item abortada: produto sem correspondencia")

    with dw.begin() as cx:
        cx.execute(text("TRUNCATE dw.fato_item_pedido RESTART IDENTITY"))
        res = cx.execute(text("""
            INSERT INTO dw.fato_item_pedido (
                pedido_sk, produto_sk, quantidade, valor_unitario,
                valor_desconto, valor_linha)
            SELECT
                f.pedido_sk,
                coalesce(pl.produto_sk, pe.produto_sk),
                i.quantidade::int,
                round(i.valor_unitario::numeric, 2),
                round(i.valor_desconto::numeric, 2),
                round(i.valor_linha::numeric, 2)
            FROM dw.item_pedido_conformado i
            JOIN dw.fato_pedido f
              ON f.id_origem = i.id_origem
             AND f.sistema_origem = i.sistema_origem
            LEFT JOIN dw.dim_produto pl ON pl.id_legado = i.id_produto_legado
            LEFT JOIN dw.dim_produto pe ON pe.id_ecommerce = i.id_produto_ecommerce
        """))
        n_ins = int(res.rowcount)
    qa.igual("fato_item: linhas", n_ins, n_validos,
             "apenas itens com pedido entram no esquema estrela")

    with dw.begin() as cx:
        cx.execute(text("""
            CREATE TABLE IF NOT EXISTS qa.quarentena_item_pedido (
              id                   BIGSERIAL PRIMARY KEY,
              id_origem            TEXT   NOT NULL,
              sistema_origem       TEXT   NOT NULL,
              id_produto_legado    BIGINT NULL,
              id_produto_ecommerce BIGINT NULL,
              quantidade           INT    NULL,
              valor_unitario       NUMERIC(12,2) NULL,
              valor_desconto       NUMERIC(12,2) NULL,
              valor_linha          NUMERIC(12,2) NULL,
              motivo               TEXT   NOT NULL,
              detectado_em         TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """))
        cx.execute(text("TRUNCATE qa.quarentena_item_pedido RESTART IDENTITY"))
        res = cx.execute(text("""
            INSERT INTO qa.quarentena_item_pedido (
                id_origem, sistema_origem, id_produto_legado,
                id_produto_ecommerce, quantidade, valor_unitario,
                valor_desconto, valor_linha, motivo)
            SELECT
                i.id_origem, i.sistema_origem, i.id_produto_legado,
                i.id_produto_ecommerce, i.quantidade::int,
                round(i.valor_unitario::numeric, 2),
                round(i.valor_desconto::numeric, 2),
                round(i.valor_linha::numeric, 2),
                'SEM_PEDIDO'
            FROM dw.item_pedido_conformado i
            WHERE NOT EXISTS (
                SELECT 1 FROM dw.fato_pedido f
                WHERE f.id_origem = i.id_origem
                  AND f.sistema_origem = i.sistema_origem)
        """))
        n_quarentena = int(res.rowcount)

    qa.igual("quarentena: itens sem pedido", n_quarentena, n_total - n_validos)
    print(f"fato_item_pedido: {n_ins} linhas; "
          f"quarentena: {n_quarentena} linhas")


def carrega_fatos_auxiliares(qa):
    dw = eng_dw()

    with dw.connect() as cx:
        n_sac = int(cx.execute(text(
            "SELECT count(*) FROM dw.atendimento_conformado")).scalar())
        sac_sem_pedido = int(cx.execute(text("""
            SELECT count(*) FROM dw.atendimento_conformado a
            WHERE NOT EXISTS (
                SELECT 1 FROM dw.fato_pedido f
                WHERE f.id_origem = a.id_origem_pedido
                  AND f.sistema_origem = a.sistema_origem)
        """)).scalar())
        n_aval = int(cx.execute(text(
            "SELECT count(*) FROM dw.avaliacao_conformada")).scalar())
        aval_sem_pedido = int(cx.execute(text("""
            SELECT count(*) FROM dw.avaliacao_conformada a
            WHERE NOT EXISTS (
                SELECT 1 FROM dw.fato_pedido f
                WHERE f.id_origem = a.id_origem_pedido)
        """)).scalar())
        aval_data_nula = int(cx.execute(text(
            "SELECT count(*) FROM dw.avaliacao_conformada WHERE data IS NULL"
        )).scalar())

    qa.igual("fato_atendimento: SAC sem pedido", sac_sem_pedido, 0)
    qa.igual("fato_avaliacao: avaliacao sem pedido", aval_sem_pedido, 0)
    qa.igual("fato_avaliacao: data nula", aval_data_nula, 0)
    if sac_sem_pedido or aval_sem_pedido or aval_data_nula:
        raise RuntimeError("carga auxiliar abortada: chave ou data ausente")

    with dw.begin() as cx:
        res_sac = cx.execute(text("""
            INSERT INTO dw.fato_atendimento (
                protocolo, cliente_sk, pedido_sk, data_abertura_sk,
                data_fechamento_sk, canal, motivo_conformado,
                nota_satisfacao, horas_resolucao)
            SELECT
                a.protocolo, f.cliente_sk, f.pedido_sk,
                a.data_abertura::date, a.data_fechamento::date,
                a.canal, a.motivo_conformado,
                round(a.nota_satisfacao::numeric, 2),
                round(a.horas_resolucao::numeric, 2)
            FROM dw.atendimento_conformado a
            JOIN dw.fato_pedido f
              ON f.id_origem = a.id_origem_pedido
             AND f.sistema_origem = a.sistema_origem
        """))
        n_sac_ins = int(res_sac.rowcount)

        res_aval = cx.execute(text("""
            INSERT INTO dw.fato_avaliacao (
                review_id, pedido_sk, produto_sk, data_sk, nota,
                compra_verificada, votos_uteis)
            SELECT
                a.review_id, f.pedido_sk,
                coalesce(p_sku.produto_sk, p_leg.produto_sk),
                a.data::date,
                round(a.nota::numeric, 2),
                a.compra_verificada,
                a.votos_uteis::int
            FROM dw.avaliacao_conformada a
            JOIN dw.fato_pedido f
              ON f.id_origem = a.id_origem_pedido
            LEFT JOIN dw.dim_produto p_sku
              ON a.product_ref LIKE 'SKU-%'
             AND p_sku.sku = a.product_ref
            LEFT JOIN dw.dim_produto p_leg
              ON a.product_ref LIKE 'LEG-%'
             AND p_leg.id_legado = nullif(
                    regexp_replace(a.product_ref, '[^0-9]', '', 'g'), ''
                 )::bigint
        """))
        n_aval_ins = int(res_aval.rowcount)

    qa.igual("fato_atendimento: linhas", n_sac_ins, n_sac)
    qa.igual("fato_avaliacao: linhas", n_aval_ins, n_aval)

    with dw.connect() as cx:
        aval_sem_produto = int(cx.execute(text("""
            SELECT count(*) FROM dw.fato_avaliacao
            WHERE produto_sk IS NULL
        """)).scalar())
    qa.igual("fato_avaliacao: produto nao mapeado", aval_sem_produto, 0,
             "todo product_ref (SKU- ou LEG-) deve achar um produto")

    print(f"fato_atendimento: {n_sac_ins} linhas; "
          f"fato_avaliacao: {n_aval_ins} linhas")


if __name__ == "__main__":
    dw = eng_dw()
    qa = Suite(etapa="03_carga_dw")
    carrega_dim_tempo(dw)
    carrega_dimensoes(qa)
    carrega_fato_pedido(qa)
    carrega_fato_item(qa)
    carrega_fatos_auxiliares(qa)

    qa.registrar(dw)
    qa.imprimir()
