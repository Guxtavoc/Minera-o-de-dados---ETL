# -*- coding: utf-8 -*-
"""Gera as evidências da carga diretamente do banco.

Chamado ao final de ``05_exportar_orange.py`` para que uma execução do
pipeline (os seis comandos do README) recrie:

    saida/resumo_carga.csv
    saida/resumo_reconciliacao.csv
    saida/qa_execucao_assercao.csv
    saida/abt_resumo.csv
    saida/abt_colunas.csv
    saida/dw_schema.sql
    saida/dw_dump.sql (ou .sql.gz, se o arquivo for muito grande)

O dump de dados contém o esquema estrela, a quarentena, as asserções e a ABT.
Staging e tabelas conformadas intermediárias ficam de fora: são reconstruídas
pelo próprio pipeline.
"""

import gzip
import os
import shutil
import subprocess

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import make_url

from config import DIR_SAIDA, PG_DW_DSN

TABELAS_RESUMO = [
    ("dim_status", "dw", None),
    ("dim_canal", "dw", None),
    ("dim_tempo", "dw", None),
    ("dim_produto", "dw", None),
    ("quarentena_item_pedido", "qa", "valor_linha"),
    ("fato_atendimento", "dw", None),
    ("mapa_cliente_origem", "dw", None),
    ("dim_cliente", "dw", None),
    ("recompra_90d", "abt", None),
    ("recompra_90d_vazamento", "abt", None),
    ("fato_avaliacao", "dw", None),
    ("fato_pedido", "dw", "valor_total"),
    ("fato_item_pedido", "dw", "valor_linha"),
]

SCHEMAS_DUMP = ("dw", "qa", "abt")
# As tabelas conformadas são intermediárias: o dump de dados entrega o
# esquema estrela final, a quarentena, as asserções e a ABT.
TABELAS_INTERMEDIARIAS = (
    "dw.pedido_conformado",
    "dw.item_pedido_conformado",
    "dw.atendimento_conformado",
    "dw.avaliacao_conformada",
)
LIMITE_DUMP_PLAIN = 95 * 1024 * 1024


def _caminho(nome):
    return os.path.join(DIR_SAIDA, nome)


def _grava_csv(df, nome):
    destino = _caminho(nome)
    df.to_csv(destino, index=False, encoding="utf-8")
    print(f"  {destino} ({len(df)} linhas)")
    return destino


def exporta_resumo_carga(dw):
    linhas = []
    with dw.connect() as cx:
        for tabela, schema, coluna_valor in TABELAS_RESUMO:
            nome = tabela if schema == "dw" else f"{schema}.{tabela}"
            n = int(cx.execute(
                text(f"SELECT count(*) FROM {schema}.{tabela}")).scalar())
            soma = None
            if coluna_valor:
                soma = float(cx.execute(
                    text(f"SELECT sum({coluna_valor}) FROM {schema}.{tabela}")
                ).scalar())
            linhas.append({"tabela": nome, "linhas": n, "soma": soma})
    return _grava_csv(pd.DataFrame(linhas), "resumo_carga.csv")


def exporta_reconciliacao(dw):
    sql = text("""
        WITH dw_total AS (
            SELECT sistema_origem, sum(valor_total) AS valor
            FROM dw.fato_pedido
            GROUP BY sistema_origem
        ),
        origem AS (
            SELECT 'LEGADO' AS sistema,
                   sum("VALOR_TOTAL") AS valor
            FROM stg.legado_pedidos
            UNION ALL
            SELECT 'ECOM' AS sistema,
                   sum(total_amount + coalesce(freight_amount, 0)) AS valor
            FROM stg.ecom_orders
        )
        SELECT o.sistema,
               o.valor AS origem,
               d.valor AS dw,
               d.valor - o.valor AS diferenca,
               d.valor / o.valor AS razao,
               abs(d.valor / o.valor - 1) * 100 AS desvio_pct
        FROM origem o
        JOIN dw_total d ON d.sistema_origem = o.sistema
        ORDER BY o.sistema
    """)
    df = pd.read_sql(sql, dw)
    for c in ("origem", "dw", "diferenca"):
        df[c] = df[c].astype(float).round(6)
    df["razao"] = df["razao"].astype(float).round(8)
    df["desvio_pct"] = df["desvio_pct"].astype(float).round(6)
    return _grava_csv(df, "resumo_reconciliacao.csv")


def exporta_assercoes(dw):
    sql = text("""
        SELECT id, executado_em, etapa, nome, descricao,
               valor_obtido, valor_esperado,
               CASE WHEN aprovado THEN 't' ELSE 'f' END AS aprovado
        FROM qa.execucao_assercao
        ORDER BY id
    """)
    return _grava_csv(pd.read_sql(sql, dw), "qa_execucao_assercao.csv")


def exporta_abt_resumo(dw):
    with dw.connect() as cx:
        correta = cx.execute(text("""
            SELECT count(*) AS linhas,
                   count(*) FILTER (WHERE alvo_recompra_90d = 1) AS positivos,
                   avg(alvo_recompra_90d::numeric) AS taxa,
                   count(*) FILTER (WHERE recencia_dias IS NULL) AS recencia_nula,
                   count(*) FILTER (WHERE nota_media_avaliacoes IS NULL) AS nota_nula,
                   count(*) FILTER (WHERE prazo_medio_entrega IS NULL) AS prazo_nulo,
                   min(recencia_dias) AS recencia_min,
                   max(recencia_dias) AS recencia_max
            FROM abt.recompra_90d
        """)).mappings().one()
        vazamento = cx.execute(text("""
            SELECT count(*) FILTER (WHERE recencia_dias < 0) AS recencia_negativa,
                   min(valor_monetario_z) AS z_min,
                   max(valor_monetario_z) AS z_max
            FROM abt.recompra_90d_vazamento
        """)).mappings().one()
        diferentes = cx.execute(text("""
            SELECT count(*) FILTER (
                       WHERE c.recencia_dias IS DISTINCT FROM v.recencia_dias
                   ) AS recencia_diferente,
                   count(*) FILTER (
                       WHERE c.frequencia_pedidos IS DISTINCT FROM v.frequencia_pedidos
                   ) AS frequencia_diferente
            FROM abt.recompra_90d c
            JOIN abt.recompra_90d_vazamento v
              ON v.cliente_sk = c.cliente_sk
             AND v.data_corte = c.data_corte
        """)).mappings().one()

    metricas = [
        ("abt_linhas", correta["linhas"]),
        ("abt_positivos", correta["positivos"]),
        ("abt_taxa_alvo", correta["taxa"]),
        ("abt_recencia_nula", correta["recencia_nula"]),
        ("abt_nota_nula", correta["nota_nula"]),
        ("abt_prazo_nulo", correta["prazo_nulo"]),
        ("abt_recencia_min", correta["recencia_min"]),
        ("abt_recencia_max", correta["recencia_max"]),
        ("vaz_recencia_negativa", vazamento["recencia_negativa"]),
        ("vaz_recencia_diferente", diferentes["recencia_diferente"]),
        ("vaz_frequencia_diferente", diferentes["frequencia_diferente"]),
        ("vaz_z_min", vazamento["z_min"]),
        ("vaz_z_max", vazamento["z_max"]),
    ]
    df = pd.DataFrame(metricas, columns=["metrica", "valor"])
    df["valor"] = df["valor"].astype(float)
    return _grava_csv(df, "abt_resumo.csv")


def exporta_abt_colunas(dw):
    df = pd.read_sql(text("SELECT * FROM abt.recompra_90d ORDER BY cliente_sk"), dw)
    linhas = []
    for coluna in df.columns:
        serie = df[coluna]
        numerica = pd.api.types.is_numeric_dtype(serie)
        linhas.append({
            "coluna": coluna,
            "tipo": str(serie.dtype),
            "nao_nulos": int(serie.notna().sum()),
            "nulos": int(serie.isna().sum()),
            "distintos": int(serie.nunique(dropna=True)),
            "minimo": float(serie.min()) if numerica else None,
            "maximo": float(serie.max()) if numerica else None,
            "media": float(serie.mean()) if numerica else None,
        })
    return _grava_csv(pd.DataFrame(linhas), "abt_colunas.csv")


def _dsn_pg_dump():
    url = make_url(PG_DW_DSN).set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


def _remove_parametro_incompativel(caminho):
    """O cliente pg_dump pode ser 17 e o servidor 16.

    O pg_dump 17 grava ``SET transaction_timeout = 0;``, parâmetro que o
    PostgreSQL 16 não reconhece. Removemos a linha para o dump restaurar no
    servidor usado pelo projeto.
    """
    temporario = caminho + ".tmp"
    with open(caminho, encoding="utf-8") as origem, open(
            temporario, "w", encoding="utf-8", newline="") as destino:
        for linha in origem:
            if linha.strip() == "SET transaction_timeout = 0;":
                continue
            destino.write(linha)
    os.replace(temporario, caminho)


def _executa_pg_dump(argumentos, destino):
    comando = [
        "pg_dump",
        "--no-owner",
        "--no-privileges",
        "--clean",
        "--if-exists",
        *argumentos,
        "--file", destino,
        _dsn_pg_dump(),
    ]
    subprocess.run(comando, check=True)
    _remove_parametro_incompativel(destino)


def exporta_dumps():
    for nome in ("dw_dump.sql", "dw_dump.sql.gz"):
        antigo = _caminho(nome)
        if os.path.exists(antigo):
            os.remove(antigo)

    schema_dump = _caminho("dw_schema.sql")
    argumentos = []
    for schema in SCHEMAS_DUMP:
        argumentos.append(f"--schema={schema}")
    _executa_pg_dump(["--schema-only", *argumentos], schema_dump)
    print(f"  {schema_dump} (schema somente)")

    data_dump = _caminho("dw_dump.sql")
    excluir = [f"--exclude-table={t}" for t in TABELAS_INTERMEDIARIAS]
    _executa_pg_dump([*excluir, *argumentos], data_dump)
    tamanho = os.path.getsize(data_dump)
    if tamanho <= LIMITE_DUMP_PLAIN:
        print(f"  {data_dump} ({tamanho / 1024 / 1024:.1f} MB, com dados)")
        return data_dump

    comprimido = data_dump + ".gz"
    with open(data_dump, "rb") as origem, gzip.open(
            comprimido, "wb", compresslevel=6) as destino:
        shutil.copyfileobj(origem, destino)
    os.remove(data_dump)
    tamanho_gz = os.path.getsize(comprimido)
    print(f"  {comprimido} ({tamanho_gz / 1024 / 1024:.1f} MB comprimido; "
          f"dump SQL original com {tamanho / 1024 / 1024:.1f} MB)")
    return comprimido


def exporta_evidencias(dw):
    print("exportando evidências:")
    exporta_resumo_carga(dw)
    exporta_reconciliacao(dw)
    exporta_assercoes(dw)
    exporta_abt_resumo(dw)
    exporta_abt_colunas(dw)
    exporta_dumps()
