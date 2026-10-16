#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETAPA 2 — TRANSFORMAÇÃO E CONFORMAÇÃO

Esta é a etapa epistemicamente densa. Cada bloco abaixo corresponde a uma
decisão que NÃO tem resposta única. Para cada uma, o RDT traz:
    (a) as alternativas consideradas;
    (b) a escolhida e por quê;
    (c) o que se perde com ela;
    (d) o número de registros afetados.

Saída desta etapa (ver decisão de arquitetura no RDT):
    dimensões finais : dw.dim_status, dw.dim_canal, dw.dim_cliente, dw.dim_produto
    fatos conformados: dw.pedido_conformado, dw.item_pedido_conformado,
                       dw.atendimento_conformado, dw.avaliacao_conformada
As tabelas conformadas carregam CHAVES NATURAIS; a etapa 3 (carga no esquema
estrela) troca essas chaves pelas surrogate keys das dimensões e adiciona o
calendário (dw.dim_tempo) e a reconciliação financeira.

    docker compose exec etl python 02_transformacao.py
"""

import json
import re
import unicodedata
from datetime import timedelta, timezone

import numpy as np
import pandas as pd
from sqlalchemy import text

from config import eng_dw
from qualidade.assercoes import Suite

# Fuso único de padronização. America/Sao_Paulo está em UTC-3 fixo desde 2019
# (sem horário de verão), então um offset fixo é fiel e não depende do tzdata.
FUSO_SP = timezone(timedelta(hours=-3), "America/Sao_Paulo")

METRICAS = {}


# ---------------------------------------------------------------------------
# Utilitários — prontos.
# ---------------------------------------------------------------------------
def so_digitos(txt):
    return re.sub(r"\D", "", txt or "")


def cpf_valido(cpf):
    """Valida os dois dígitos verificadores. Retorna None se não tiver 11 dígitos."""
    c = so_digitos(cpf)
    if len(c) != 11 or len(set(c)) == 1:
        return None if len(c) != 11 else False
    b = [int(x) for x in c]
    s = sum((10 - i) * b[i] for i in range(9))
    d1 = 0 if (11 - s % 11) >= 10 else (11 - s % 11)
    s = sum((11 - i) * (b[:9] + [d1])[i] for i in range(10))
    d2 = 0 if (11 - s % 11) >= 10 else (11 - s % 11)
    return b[9] == d1 and b[10] == d2


def normaliza_nome(nome):
    """MAIÚSCULAS sem acento, espaços colapsados. Base para pareamento aproximado."""
    n = unicodedata.normalize("NFD", (nome or "").strip().upper())
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", n)


def cpf_normalizado(serie):
    """Série -> só dígitos, ou None quando o resultado não tem 11 dígitos."""
    def _um(v):
        d = so_digitos(v)
        return d if len(d) == 11 else None
    return serie.map(_um)


def para_sp(serie):
    """Converte TIMESTAMPTZ (UTC) para o horário local de São Paulo, sem fuso."""
    s = pd.to_datetime(serie, errors="coerce", utc=True)
    return s.dt.tz_convert(FUSO_SP).dt.tz_localize(None)


def ler(tabela, dw):
    return pd.read_sql(text(f"SELECT * FROM stg.{tabela}"), dw)


def grava_dim(df, tabela, dw, colunas):
    """Preenche uma dimensão já criada pelo DDL (trunca e insere)."""
    with dw.begin() as cx:
        cx.execute(text(f"TRUNCATE dw.{tabela} CASCADE"))
    df[colunas].to_sql(tabela, dw, schema="dw", if_exists="append",
                       index=False, method="multi", chunksize=5_000)


def grava_conformado(df, tabela, dw):
    """Recria uma tabela de fatos conformados (chaves naturais)."""
    df.to_sql(tabela, dw, schema="dw", if_exists="replace",
              index=False, method="multi", chunksize=5_000)


# ===========================================================================
# DECISÃO 1 — IDENTIDADE DO CLIENTE ENTRE OS DOIS SISTEMAS
# ===========================================================================
def unifica_clientes(qa):
    """
    RDT-02 / RDT-03.

    Regra adotada:
      · normaliza o CPF para 11 dígitos; ele é a PONTE entre os dois sistemas,
        válido ou não o DV (o mesmo CPF errado continua identificando a mesma
        pessoa — a origem repete o erro);
      · dentro do legado, colapsa em uma linha as duplicatas exatas e as
        near-duplicates (mesmo nome normalizado + cidade + UF);
      · sem CPF, pareia por nome normalizado + cidade + UF, apenas 1:1;
      · quem sobra fica com uma única origem.
    """
    dw = eng_dw()
    leg = ler("legado_clientes", dw)
    eco = ler("ecom_customer", dw)

    # ---- prepara o legado ---------------------------------------------------
    leg = pd.DataFrame({
        "id_legado": leg["ID_CLIENTE"].astype("int64"),
        "nome_padronizado": leg["NOME"].map(normaliza_nome),
        "cpf_normalizado": cpf_normalizado(leg["CPF"]),
        "cidade": leg["CIDADE"].replace({"N/A": None}),
        "uf": leg["UF"],
        "dt_cadastro": pd.to_datetime(leg["DT_CADASTRO"], errors="coerce"),
        "email": leg["EMAIL"],
        "telefone": leg["TELEFONE"],
    })
    leg["cpf_valido"] = [cpf_valido(c) for c in leg["cpf_normalizado"]]

    # colisões de CPF (em especial inválido) entre pessoas distintas: mede o
    # falso positivo latente de usar o CPF como ponte, ANTES da dedup.
    por_cpf_nomes = (leg[leg["cpf_normalizado"].notna()]
                     .groupby("cpf_normalizado")["nome_padronizado"].nunique())
    cpfs_colididos = int((por_cpf_nomes > 1).sum())

    # ---- deduplicação interna do legado (RDT-03) ---------------------------
    antes = len(leg)
    n_com_cpf_antes = int(leg["cpf_normalizado"].notna().sum())
    leg["_nc"] = (leg["nome_padronizado"] + "|" + leg["cidade"].fillna("")
                  + "|" + leg["uf"].fillna(""))
    leg = leg.sort_values("id_legado")
    # passagem 1: por CPF (colapsa duplicatas exatas e near-duplicates com máscara)
    com_cpf = leg[leg["cpf_normalizado"].notna()].drop_duplicates("cpf_normalizado", keep="first")
    sem_cpf = leg[leg["cpf_normalizado"].isna()]
    # passagem 2: linha sem CPF que casa nome+cidade+UF com uma linha com CPF
    # é a gêmea com CPF esvaziado -> descartada. As sem CPF restantes colapsam
    # entre si por nome+cidade+UF.
    chaves_com_cpf = set(com_cpf["_nc"])
    gemeas = sem_cpf["_nc"].isin(chaves_com_cpf)
    sem_cpf = sem_cpf[~gemeas].drop_duplicates("_nc", keep="first")
    leg = (pd.concat([com_cpf, sem_cpf])
             .sort_values("id_legado").reset_index(drop=True))
    removidas = antes - len(leg)
    METRICAS["RDT03"] = {
        "clientes_legado_brutos": int(antes),
        "duplicatas_removidas_total": int(removidas),
        "removidas_por_cpf": int(n_com_cpf_antes - len(com_cpf)),
        "removidas_sem_cpf_gemeas": int(gemeas.sum()),
        "clientes_legado_apos_dedup": int(len(leg)),
    }

    # ---- prepara o e-commerce ----------------------------------------------
    eco = pd.DataFrame({
        "id_ecommerce": eco["customer_id"].astype("int64"),
        "nome_padronizado": eco["full_name"].map(normaliza_nome),
        "cpf_normalizado": cpf_normalizado(eco["tax_id"]),
        "cidade": eco["city"],
        "uf": eco["state"],
        "dt_cadastro": para_sp(eco["created_at"]).dt.date,
    })
    eco["dt_cadastro"] = pd.to_datetime(eco["dt_cadastro"], errors="coerce")
    eco["cpf_valido"] = [cpf_valido(c) for c in eco["cpf_normalizado"]]

    # deduplicação interna do e-commerce (mesma regra do legado, duas passagens)
    eco_antes = len(eco)
    eco["_nc"] = (eco["nome_padronizado"] + "|" + eco["cidade"].fillna("")
                  + "|" + eco["uf"].fillna(""))
    eco = eco.sort_values("id_ecommerce")
    eco_cpf = eco[eco["cpf_normalizado"].notna()].drop_duplicates("cpf_normalizado", keep="first")
    eco_sem = eco[eco["cpf_normalizado"].isna()]
    eco_sem = eco_sem[~eco_sem["_nc"].isin(set(eco_cpf["_nc"]))]
    eco_sem = eco_sem.drop_duplicates("_nc", keep="first")
    eco = pd.concat([eco_cpf, eco_sem]).sort_values("id_ecommerce").reset_index(drop=True)
    METRICAS["RDT02_ecom_dedup"] = int(eco_antes - len(eco))

    # ---- pareamento por CPF (a ponte principal) ----------------------------
    a = leg[leg["cpf_normalizado"].notna()]
    b = eco[eco["cpf_normalizado"].notna()]
    par_cpf = a.merge(b, on="cpf_normalizado", how="inner",
                      suffixes=("_l", "_e"))

    id_leg_usado = set(par_cpf["id_legado"])
    id_eco_usado = set(par_cpf["id_ecommerce"])

    linhas = []
    for _, r in par_cpf.iterrows():
        linhas.append(dict(
            cpf_normalizado=r["cpf_normalizado"],
            cpf_valido=r["cpf_valido_l"],
            nome_padronizado=r["nome_padronizado_l"],
            cidade=r["cidade_l"] if pd.notna(r["cidade_l"]) else r["cidade_e"],
            uf=r["uf_l"] if pd.notna(r["uf_l"]) else r["uf_e"],
            dt_primeiro_cadastro=min(x for x in [r["dt_cadastro_l"], r["dt_cadastro_e"]]
                                     if pd.notna(x)),
            id_legado=int(r["id_legado"]),
            id_ecommerce=int(r["id_ecommerce"]),
            origem_unificacao="AMBOS", regra_pareamento="CPF"))

    # ---- pareamento por nome + cidade + UF (sem CPF) -----------------------
    leg_r = leg[~leg["id_legado"].isin(id_leg_usado)].copy()
    eco_r = eco[~eco["id_ecommerce"].isin(id_eco_usado)].copy()
    leg_r["_nc"] = (leg_r["nome_padronizado"] + "|" + leg_r["cidade"].fillna("")
                    + "|" + leg_r["uf"].fillna(""))
    eco_r["_nc"] = (eco_r["nome_padronizado"] + "|" + eco_r["cidade"].fillna("")
                    + "|" + eco_r["uf"].fillna(""))
    par_nc = leg_r.merge(eco_r, on="_nc", how="inner", suffixes=("_l", "_e"))
    # colisão: uma chave nome+cidade+UF que casa mais de uma pessoa distinta
    nc_colididos = int(par_nc.groupby("_nc")["id_legado"].nunique().gt(1).sum())
    id_leg_nc = set(par_nc["id_legado"])
    id_eco_nc = set(par_nc["id_ecommerce"])
    for _, r in par_nc.iterrows():
        linhas.append(dict(
            cpf_normalizado=None, cpf_valido=None,
            nome_padronizado=r["nome_padronizado_l"],
            cidade=r["cidade_l"] if pd.notna(r["cidade_l"]) else r["cidade_e"],
            uf=r["uf_l"] if pd.notna(r["uf_l"]) else r["uf_e"],
            dt_primeiro_cadastro=min(x for x in [r["dt_cadastro_l"], r["dt_cadastro_e"]]
                                     if pd.notna(x)),
            id_legado=int(r["id_legado"]), id_ecommerce=int(r["id_ecommerce"]),
            origem_unificacao="AMBOS", regra_pareamento="NOME_CIDADE_UF"))

    # ---- somente legado / somente e-commerce -------------------------------
    so_leg = leg[~leg["id_legado"].isin(id_leg_usado | id_leg_nc)]
    for _, r in so_leg.iterrows():
        linhas.append(dict(
            cpf_normalizado=r["cpf_normalizado"], cpf_valido=r["cpf_valido"],
            nome_padronizado=r["nome_padronizado"], cidade=r["cidade"], uf=r["uf"],
            dt_primeiro_cadastro=r["dt_cadastro"], id_legado=int(r["id_legado"]),
            id_ecommerce=None, origem_unificacao="LEGADO",
            regra_pareamento="SEM_PAR"))
    so_eco = eco[~eco["id_ecommerce"].isin(id_eco_usado | id_eco_nc)]
    for _, r in so_eco.iterrows():
        linhas.append(dict(
            cpf_normalizado=r["cpf_normalizado"], cpf_valido=r["cpf_valido"],
            nome_padronizado=r["nome_padronizado"], cidade=r["cidade"], uf=r["uf"],
            dt_primeiro_cadastro=r["dt_cadastro"], id_legado=None,
            id_ecommerce=int(r["id_ecommerce"]), origem_unificacao="ECOM",
            regra_pareamento="SEM_PAR"))

    dim = pd.DataFrame(linhas)
    dim = dim.sort_values(["origem_unificacao", "id_legado", "id_ecommerce"],
                          na_position="last").reset_index(drop=True)
    grava_dim(dim, "dim_cliente", dw,
              ["cpf_normalizado", "cpf_valido", "nome_padronizado", "cidade",
               "uf", "dt_primeiro_cadastro", "id_legado", "id_ecommerce",
               "origem_unificacao", "regra_pareamento"])

    # ---- métricas do RDT-02 ------------------------------------------------
    METRICAS["RDT02"] = {
        "dim_cliente_linhas": int(len(dim)),
        "origem_AMBOS": int((dim["origem_unificacao"] == "AMBOS").sum()),
        "origem_LEGADO": int((dim["origem_unificacao"] == "LEGADO").sum()),
        "origem_ECOM": int((dim["origem_unificacao"] == "ECOM").sum()),
        "pareados_por_CPF": int((dim["regra_pareamento"] == "CPF").sum()),
        "pareados_por_NOME_CIDADE_UF": int((dim["regra_pareamento"] == "NOME_CIDADE_UF").sum()),
        "cpf_valido": int((dim["cpf_valido"] == True).sum()),          # noqa: E712
        "cpf_invalido": int((dim["cpf_valido"] == False).sum()),       # noqa: E712
        "cpf_ausente": int(dim["cpf_normalizado"].isna().sum()),
        "falsos_possiveis_colisao_CPF": cpfs_colididos,
        "falsos_possiveis_colisao_NOME_CIDADE_UF": nc_colididos,
    }

    # ---- asserções (2.7) ---------------------------------------------------
    validos = dim[dim["cpf_valido"] == True]                            # noqa: E712
    qa.unico("dim_cliente: cpf valido duplicado", validos["cpf_normalizado"],
             "dois clientes validos nao podem compartilhar o mesmo CPF")
    qa.dominio("dim_cliente: origem_unificacao", dim["origem_unificacao"],
               {"LEGADO", "ECOM", "AMBOS"})
    qa.cardinalidade_preservada(
        "dim_cliente <= legado + ecommerce (pos dedup)",
        METRICAS["RDT03"]["clientes_legado_apos_dedup"] + len(eco), len(dim),
        "a unificacao so pode reduzir o numero de identidades")
    return dim


# ===========================================================================
# DECISÃO 2 — CONFORMAÇÃO DE STATUS
# ===========================================================================
MAPA_STATUS = [
    ("ENTREGUE",     "LEGADO", "ENTREGUE",         None),
    ("CANCELADO",    "LEGADO", "CANCELADO",        None),
    ("EM TRANSITO",  "LEGADO", "EM_TRANSITO",      None),
    ("SEPARACAO",    "LEGADO", "EM_PROCESSAMENTO", None),
    ("delivered",    "ECOM",   "ENTREGUE",         None),
    ("canceled",     "ECOM",   "CANCELADO",        "CLIENTE"),
    ("payment_declined", "ECOM", "CANCELADO",      "RECUSA_PAGAMENTO"),
    ("shipped",      "ECOM",   "EM_TRANSITO",      None),
    ("processing",   "ECOM",   "EM_PROCESSAMENTO", None),
]


def conforma_status(qa):
    """
    RDT-04. Alternativa (iii): nível hierárquico.
        status_conformado  em {ENTREGUE, CANCELADO, EM_TRANSITO, EM_PROCESSAMENTO}
        motivo_cancelamento preenchido só quando a origem distingue.
    """
    dw = eng_dw()
    leg = ler("legado_pedidos", dw)["STATUS"].value_counts().to_dict()
    eco = ler("ecom_orders", dw)["status"].value_counts().to_dict()

    dim = pd.DataFrame(MAPA_STATUS, columns=["status_origem", "sistema",
                                             "status_conformado", "motivo_cancelamento"])
    grava_dim(dim, "dim_status", dw, ["status_origem", "sistema",
                                      "status_conformado", "motivo_cancelamento"])

    METRICAS["RDT04"] = {
        "celulas_mapeamento": int(len(dim)),
        "legado": {k: int(v) for k, v in leg.items()},
        "ecommerce": {k: int(v) for k, v in eco.items()},
        "payment_declined": int(eco.get("payment_declined", 0)),
        "cancelado_legado_agrega_dois_motivos": int(leg.get("CANCELADO", 0)),
    }

    # asserção: todo status de origem foi mapeado
    origens = set(leg) | set(eco)
    mapeados = set(dim["status_origem"])
    qa.igual("status de origem nao mapeado", len(origens - mapeados), 0,
             "um status novo na origem quebraria a analise")
    qa.dominio("status_conformado",
               dim["status_conformado"],
               {"ENTREGUE", "CANCELADO", "EM_TRANSITO", "EM_PROCESSAMENTO"})
    return dim


# ===========================================================================
# DECISÃO 3 — SEMÂNTICA DOS VALORES MONETÁRIOS
# ===========================================================================
MAPA_CANAL = [
    ("LOJA",       "LEGADO", "FISICO"),
    ("SITE",       "LEGADO", "ONLINE_PROPRIO"),
    ("TELEVENDAS", "LEGADO", "TELEVENDAS"),
    ("web",        "ECOM",   "ONLINE_PROPRIO"),
    ("app",        "ECOM",   "ONLINE_PROPRIO"),
    ("marketplace", "ECOM",  "MARKETPLACE"),
]


def conforma_canal(qa):
    dw = eng_dw()
    dim = pd.DataFrame(MAPA_CANAL, columns=["canal_origem", "sistema", "canal_conformado"])
    grava_dim(dim, "dim_canal", dw, ["canal_origem", "canal_conformado", "sistema"])
    leg = set(ler("legado_pedidos", dw)["CANAL"].unique())
    eco = set(ler("ecom_orders", dw)["channel"].unique())
    origens = leg | eco
    qa.igual("canal de origem nao mapeado", len(origens - set(dim["canal_origem"])), 0,
             "canal novo na origem quebraria a analise")
    return dim


def agrega_itens(it, col_pedido, col_qtd, col_unit, col_desc):
    """Soma por pedido: mercadoria bruta, desconto (sentinela -1 -> 0) e nº itens."""
    it = it.copy()
    it["_gross"] = it[col_qtd] * it[col_unit]
    it["_desc"] = it[col_desc].clip(lower=0)
    g = it.groupby(col_pedido).agg(mercadoria=("_gross", "sum"),
                                   desconto=("_desc", "sum"),
                                   qtd_itens=("_gross", "size"))
    return g, it


def conforma_valores(qa):
    """
    RDT-05 / RDT-06. Descobre a semântica reconciliando com a soma dos itens:
      · legado : VALOR_TOTAL = mercadoria - desconto + FRETE   (frete incluído)
      · ecom   : total_amount = mercadoria - desconto          (frete NÃO incluído)
    """
    dw = eng_dw()
    p_leg = ler("legado_pedidos", dw)
    i_leg = ler("legado_itens_pedido", dw)
    p_eco = ler("ecom_orders", dw)
    i_eco = ler("ecom_order_item", dw)

    g_leg, i_leg2 = agrega_itens(i_leg, "ID_PEDIDO", "QTD", "VL_UNITARIO", "VL_DESCONTO")
    g_eco, i_eco2 = agrega_itens(i_eco, "order_id", "quantity", "unit_price", "discount")

    # ---- proxies brutos para reconciliar -----------------------------------
    leg = p_leg.merge(g_leg, left_on="ID_PEDIDO", right_index=True, how="left")
    leg[["mercadoria", "desconto", "qtd_itens"]] = leg[["mercadoria", "desconto", "qtd_itens"]].fillna(0)
    frete_leg = leg["VALOR_FRETE"].fillna(0)
    recon_leg_com_frete = np.isclose(leg["VALOR_TOTAL"], leg["mercadoria"] - leg["desconto"] + frete_leg, atol=0.02)
    recon_leg_sem_frete = np.isclose(leg["VALOR_TOTAL"], leg["mercadoria"] - leg["desconto"], atol=0.02)

    eco = p_eco.merge(g_eco, left_on="order_id", right_index=True, how="left")
    eco[["mercadoria", "desconto", "qtd_itens"]] = eco[["mercadoria", "desconto", "qtd_itens"]].fillna(0)
    frete_eco = eco["freight_amount"].fillna(0)
    recon_eco_sem_frete = np.isclose(eco["total_amount"], eco["mercadoria"] - eco["desconto"], atol=0.02)
    recon_eco_com_frete = np.isclose(eco["total_amount"], eco["mercadoria"] - eco["desconto"] + frete_eco, atol=0.02)

    METRICAS["RDT05"] = {
        "legado_reconcilia_COM_frete_%": round(100 * recon_leg_com_frete.mean(), 2),
        "legado_reconcilia_SEM_frete_%": round(100 * recon_leg_sem_frete.mean(), 2),
        "ecom_reconcilia_SEM_frete_%": round(100 * recon_eco_sem_frete.mean(), 2),
        "ecom_reconcilia_COM_frete_%": round(100 * recon_eco_com_frete.mean(), 2),
        "soma_VALOR_TOTAL_legado": round(float(leg["VALOR_TOTAL"].sum()), 2),
        "soma_total_amount_ecom": round(float(eco["total_amount"].sum()), 2),
        "soma_frete_legado": round(float(frete_leg.sum()), 2),
        "soma_frete_ecom": round(float(frete_eco.sum()), 2),
    }

    METRICAS["RDT06"] = {
        "frete_negativo_legado": int((p_leg["VALOR_FRETE"] < 0).sum()),
        "frete_negativo_ecom": int((p_eco["freight_amount"] < 0).sum()),
        "desconto_sentinela_-1_legado": int((i_leg["VL_DESCONTO"] < 0).sum()),
    }

    # ---- conjuntos conformados de pedidos ----------------------------------
    ped_leg = pd.DataFrame({
        "id_origem": "LEG-" + leg["ID_PEDIDO"].astype(str),
        "sistema_origem": "LEGADO",
        "id_cliente_legado": leg["ID_CLIENTE"],
        "id_cliente_ecommerce": pd.NA,
        "data_pedido": pd.to_datetime(leg["DT_PEDIDO"], errors="coerce"),
        "data_entrega_bruta": pd.to_datetime(leg["DT_ENTREGA"], errors="coerce"),
        "canal_origem": leg["CANAL"],
        "status_origem": leg["STATUS"],
        "qtd_itens": leg["qtd_itens"].astype("int64"),
        "valor_mercadoria": leg["mercadoria"].round(2),
        "valor_frete": frete_leg.abs().round(2),
        "valor_desconto": leg["desconto"].round(2),
    })
    ped_eco = pd.DataFrame({
        "id_origem": "ECOM-" + eco["order_id"].astype(str),
        "sistema_origem": "ECOM",
        "id_cliente_legado": pd.NA,
        "id_cliente_ecommerce": eco["customer_id"],
        "data_pedido": para_sp(eco["placed_at"]),
        "data_entrega_bruta": para_sp(eco["delivered_at"]),
        "canal_origem": eco["channel"],
        "status_origem": eco["status"],
        "qtd_itens": eco["qtd_itens"].astype("int64"),
        "valor_mercadoria": eco["mercadoria"].round(2),
        "valor_frete": frete_eco.abs().round(2),
        "valor_desconto": eco["desconto"].round(2),
    })
    pedidos = pd.concat([ped_leg, ped_eco], ignore_index=True)
    pedidos["valor_total"] = (pedidos["valor_mercadoria"]
                              + pedidos["valor_frete"]
                              - pedidos["valor_desconto"]).round(2)
    METRICAS["RDT05"]["soma_valor_total_conformado"] = round(float(pedidos["valor_total"].sum()), 2)

    # asserção: soma conformada por pedido == soma dos itens (por sistema)
    dif_leg = int(((ped_leg["valor_mercadoria"] - leg["mercadoria"].round(2)).abs() > 0.01).sum())
    dif_eco = int(((ped_eco["valor_mercadoria"] - eco["mercadoria"].round(2)).abs() > 0.01).sum())
    qa.igual("valor_mercadoria legado == soma itens", dif_leg, 0,
             "medida do fato deve reproduzir a soma dos itens")
    qa.igual("valor_mercadoria ecom == soma itens", dif_eco, 0,
             "medida do fato deve reproduzir a soma dos itens")

    # ---- itens conformados --------------------------------------------------
    item_leg = pd.DataFrame({
        "id_origem": "LEG-" + i_leg["ID_PEDIDO"].astype(str),
        "sistema_origem": "LEGADO",
        "id_produto_legado": i_leg["ID_PRODUTO"],
        "id_produto_ecommerce": pd.NA,
        "quantidade": i_leg["QTD"],
        "valor_unitario": i_leg["VL_UNITARIO"].round(2),
        "valor_desconto": i_leg["VL_DESCONTO"].clip(lower=0).round(2),
    })
    item_leg["valor_linha"] = (item_leg["quantidade"] * item_leg["valor_unitario"]
                               - item_leg["valor_desconto"]).round(2)
    item_eco = pd.DataFrame({
        "id_origem": "ECOM-" + i_eco["order_id"].astype(str),
        "sistema_origem": "ECOM",
        "id_produto_legado": pd.NA,
        "id_produto_ecommerce": i_eco["product_id"],
        "quantidade": i_eco["quantity"],
        "valor_unitario": i_eco["unit_price"].round(2),
        "valor_desconto": i_eco["discount"].clip(lower=0).round(2),
    })
    item_eco["valor_linha"] = (item_eco["quantidade"] * item_eco["valor_unitario"]
                               - item_eco["valor_desconto"]).round(2)
    itens = pd.concat([item_leg, item_eco], ignore_index=True)

    for c in ["id_cliente_legado", "id_cliente_ecommerce"]:
        pedidos[c] = pedidos[c].astype("Int64")
    for c in ["id_produto_legado", "id_produto_ecommerce"]:
        itens[c] = itens[c].astype("Int64")

    return pedidos, itens


# ===========================================================================
# DECISÃO 4 — TAXONOMIA DE PRODUTO
# ===========================================================================
# valor bruto do legado -> (categoria_nivel1, categoria_nivel2)
MAPA_CATEGORIA = {
    "ELETRO": ("Eletrodomésticos", None),
    "Eletro": ("Eletrodomésticos", None),
    "eletrodomesticos": ("Eletrodomésticos", None),
    "ELETRODOMÉSTICOS": ("Eletrodomésticos", None),
    "Eletro-domesticos": ("Eletrodomésticos", None),
    "INFORMATICA": ("Informática", None),
    "Informática": ("Informática", None),
    "INFO": ("Informática", None),
    "informatica e games": (None, None),          # cobre dois ramos: ambíguo
    "TELEFONIA": ("Telefonia", None),
    "Celulares": ("Telefonia", None),
    "CELULAR/SMARTPHONE": ("Telefonia", None),
    "CASA": ("Casa e Decoração", None),
    "Casa e decoracao": ("Casa e Decoração", None),
    "MOVEIS": ("Casa e Decoração", "Móveis"),
    "TV E SOM": ("Áudio e TV", None),             # cobre Televisores + Áudio
    "AUDIO/VIDEO": ("Áudio e TV", None),
    "Televisores": ("Áudio e TV", "Televisores"),
    "ESPORTE": ("Esporte e Lazer", None),
    "Esportes e lazer": ("Esporte e Lazer", None),
    "FERRAMENTAS": ("Ferramentas", None),
    "Ferramentas e construcao": ("Ferramentas", None),
    "GAMES": ("Games", None),
    "Games e consoles": ("Games", None),
    "DIVERSOS": (None, None),
    "OUTROS": (None, None),
    "": (None, None),
}


def conforma_categorias(qa):
    """RDT-07. O legado não tem taxonomia controlada; conformamos para n1/n2."""
    dw = eng_dw()
    prod_leg = ler("legado_produtos", dw)
    prod_eco = ler("ecom_product", dw)
    cat = ler("ecom_category", dw)
    nome_cat = dict(zip(cat["category_id"], cat["name"]))
    pai_cat = dict(zip(cat["category_id"], cat["parent_id"]))

    # --- legado --------------------------------------------------------------
    n1, n2 = [], []
    for valor in prod_leg["CATEGORIA"].fillna(""):
        a, b = MAPA_CATEGORIA.get(valor, (None, None))
        n1.append(a); n2.append(b)
    leg = pd.DataFrame({
        "sku": None,
        "descricao": prod_leg["DESCRICAO"],
        "categoria_nivel1": n1,
        "categoria_nivel2": n2,
        "categoria_origem": prod_leg["CATEGORIA"],
        "preco_referencia": prod_leg["PRECO_TABELA"],
        "ativo": prod_leg["ATIVO"].eq("S"),
        "id_legado": prod_leg["ID_PRODUTO"],
        "id_ecommerce": pd.NA,
        "origem": "LEGADO",
    })

    # --- e-commerce (taxonomia de dois níveis controlada) -------------------
    def niveis(cid):
        if pd.isna(cid) or cid not in nome_cat:
            return None, None
        pai = pai_cat.get(cid)
        if pai is None or pd.isna(pai):
            return nome_cat[cid], None
        return nome_cat.get(pai), nome_cat[cid]
    pares = [niveis(c) for c in prod_eco["category_id"]]
    eco = pd.DataFrame({
        "sku": prod_eco["sku"],
        "descricao": prod_eco["title"],
        "categoria_nivel1": [p[0] for p in pares],
        "categoria_nivel2": [p[1] for p in pares],
        "categoria_origem": prod_eco["category_id"].astype("Int64").astype(str),
        "preco_referencia": prod_eco["list_price"],
        "ativo": prod_eco["active"],
        "id_legado": pd.NA,
        "id_ecommerce": prod_eco["product_id"],
        "origem": "ECOM",
    })

    dim = pd.concat([leg, eco], ignore_index=True)
    dim["id_legado"] = dim["id_legado"].astype("Int64")
    dim["id_ecommerce"] = dim["id_ecommerce"].astype("Int64")
    grava_dim(dim, "dim_produto", dw,
              ["sku", "descricao", "categoria_nivel1", "categoria_nivel2",
               "categoria_origem", "preco_referencia", "ativo", "id_legado",
               "id_ecommerce", "origem"])

    sem_nivel1 = int(dim["categoria_nivel1"].isna().sum())
    ambiguos = int((dim["categoria_origem"] == "informatica e games").sum())
    METRICAS["RDT07"] = {
        "dim_produto_linhas": int(len(dim)),
        "categorias_texto_livre_distintas": int(prod_leg["CATEGORIA"].nunique()),
        "sem_nivel1_%": round(100 * sem_nivel1 / len(dim), 2),
        "sem_nivel1_total": sem_nivel1,
        "ambiguos_informatica_e_games": ambiguos,
        "origens_sem_taxonomia": int(dim["categoria_origem"].isin(["DIVERSOS", "OUTROS", ""]).sum()),
    }
    qa.igual("dim_produto: descricao nula", int(dim["descricao"].isna().sum()), 0,
             "descricao e NOT NULL na dimensao")
    return dim


# ===========================================================================
# DECISÃO 5 — DATAS, AUSÊNCIAS E SENTINELAS
# ===========================================================================
SENTINELA_DATA = pd.Timestamp("1900-01-01")


def trata_datas_e_ausencias(qa, pedidos):
    """
    RDT-08 / RDT-09. Classifica cada ausência e padroniza o fuso.
      · sentinela           : data 1900-01-01, desconto -1
      · não aplicável       : entrega vazia em pedido não entregue
      · erro de registro    : entrega anterior ao pedido
    Padronização de fuso: tudo para America/Sao_Paulo (UTC-3), sem fuso.
    """
    dw = eng_dw()
    pedidos = pedidos.copy()
    bruto = pedidos["data_entrega_bruta"]

    sentinela = bruto == SENTINELA_DATA
    anterior = bruto.notna() & (bruto < pedidos["data_pedido"]) & ~sentinela
    ausente = bruto.isna()
    valida = bruto.notna() & ~sentinela & ~anterior

    pedidos["data_entrega"] = bruto.where(valida)
    pedidos["entrega_sem_data"] = sentinela | anterior
    pedidos["dias_entrega"] = (pedidos["data_entrega"] - pedidos["data_pedido"]).dt.days
    pedidos = pedidos.drop(columns=["data_entrega_bruta"])

    METRICAS["RDT08"] = {
        "entrega_sentinela_1900": int(sentinela.sum()),
        "entrega_anterior_ao_pedido": int(anterior.sum()),
        "entrega_ausente_nao_aplicavel": int(ausente.sum()),
        "entrega_valida": int(valida.sum()),
        "entrega_sem_data_flag": int(pedidos["entrega_sem_data"].sum()),
    }
    # asserção: nenhuma data de entrega anterior ao pedido sobrou
    qa.igual("dias_entrega negativo", int((pedidos["dias_entrega"] < 0).sum()), 0,
             "entrega anterior ao pedido deve ter sido anulada")

    # ---- SAC: ausências e sentinelas ---------------------------------------
    sac = ler("sac_atendimentos", dw)
    fech = pd.to_datetime(sac["data_fechamento"], errors="coerce", dayfirst=True)
    horas = pd.to_numeric(sac["tempo_resolucao_horas"].str.replace(",", ".", regex=False),
                          errors="coerce")
    nota = pd.to_numeric(sac["nota_satisfacao"], errors="coerce")
    METRICAS["RDT08_sac"] = {
        "fechamento_vazio_em_aberto": int(sac["data_fechamento"].eq("").sum()),
        "nota_ausente": int(sac["nota_satisfacao"].eq("").sum()),
        "nota_zero_invalida": int(sac["nota_satisfacao"].eq("0").sum()),
        "horas_negativas": int((horas < 0).sum()),
    }

    # ---- avaliações: presença de chaves opcionais --------------------------
    aval = ler("marketplace_avaliacoes", dw)
    com_fuso = aval["submitted_at"].str.contains(r"(?:Z|[+-]\d{2}:\d{2})$", regex=True)
    METRICAS["RDT09"] = {
        "avaliacoes_total": int(len(aval)),
        "com_fuso": int(com_fuso.sum()),
        "sem_fuso": int((~com_fuso).sum()),
        "rating_ausente": int((~aval["_rating_presente"]).sum()),
        "rating_como_texto": int(aval["rating"].str.match(r"^\d$").sum()),
    }
    return pedidos


# ===========================================================================
# DECISÃO 6 — CHAVES DAS FONTES DE ARQUIVO
# ===========================================================================
def liga_sac_e_avaliacoes(qa, pedidos):
    """
    RDT-13 (parte da etapa 2). Liga SAC e avaliações aos pedidos por chave
    natural; quem não liga fica com pedido_sk nulo (resolvido na etapa 3).
    """
    dw = eng_dw()
    chaves_pedido = set(pedidos["id_origem"])

    # ---- SAC ----------------------------------------------------------------
    sac = ler("sac_atendimentos", dw)
    prefixo = {"LEGADO": "LEG-", "ECOM": "ECOM-"}
    id_pedido = sac["origem_sistema"].map(prefixo) + sac["id_pedido_origem"].astype(str)
    fech = pd.to_datetime(sac["data_fechamento"], errors="coerce", dayfirst=True)
    horas = pd.to_numeric(sac["tempo_resolucao_horas"].str.replace(",", ".", regex=False),
                          errors="coerce").where(lambda s: s >= 0)
    nota = pd.to_numeric(sac["nota_satisfacao"], errors="coerce").where(lambda s: s.between(1, 5))
    atend = pd.DataFrame({
        "protocolo": sac["protocolo"],
        "sistema_origem": sac["origem_sistema"],
        "id_origem_pedido": id_pedido,
        "cpf_normalizado": cpf_normalizado(sac["cpf_cliente"]),
        "data_abertura": pd.to_datetime(sac["data_abertura"], errors="coerce", dayfirst=True),
        "data_fechamento": fech,
        "canal": sac["canal"].str.upper(),
        "motivo_conformado": sac["motivo"].map(
            lambda m: re.sub(r"\s+", " ", normaliza_nome(m.split("\n")[0]))),
        "nota_satisfacao": nota,
        "horas_resolucao": horas.round(2),
    })
    atend["pedido_ligado"] = atend["id_origem_pedido"].isin(chaves_pedido)

    # ---- avaliações ---------------------------------------------------------
    aval = ler("marketplace_avaliacoes", dw)
    nota_aval = pd.to_numeric(aval["rating"], errors="coerce").where(lambda s: s.between(1, 5))
    av = pd.DataFrame({
        "review_id": aval["review_id"],
        "id_origem_pedido": aval["order_ref"],
        "product_ref": aval["product_sku"],
        "data": para_sp(aval["submitted_at"]).dt.date,
        "nota": nota_aval,
        "compra_verificada": aval["verified_purchase"],
        "votos_uteis": aval["helpful_votes"],
    })
    av["pedido_ligado"] = av["id_origem_pedido"].isin(chaves_pedido)

    METRICAS["RDT13"] = {
        "sac_total": int(len(atend)),
        "sac_ligados": int(atend["pedido_ligado"].sum()),
        "sac_sem_pedido": int((~atend["pedido_ligado"]).sum()),
        "avaliacoes_total": int(len(av)),
        "avaliacoes_ligadas": int(av["pedido_ligado"].sum()),
        "avaliacoes_sem_pedido": int((~av["pedido_ligado"]).sum()),
    }
    return atend, av


# ===========================================================================
# Orquestração
# ===========================================================================
if __name__ == "__main__":
    dw = eng_dw()
    qa = Suite(etapa="02_transformacao")

    dim_cliente = unifica_clientes(qa)
    conforma_status(qa)
    conforma_canal(qa)
    pedidos, itens = conforma_valores(qa)
    conforma_categorias(qa)
    pedidos = trata_datas_e_ausencias(qa, pedidos)
    atend, aval = liga_sac_e_avaliacoes(qa, pedidos)

    # --- grava os conformados (chaves naturais) -----------------------------
    grava_conformado(pedidos, "pedido_conformado", dw)
    grava_conformado(itens, "item_pedido_conformado", dw)
    grava_conformado(atend, "atendimento_conformado", dw)
    grava_conformado(aval, "avaliacao_conformada", dw)

    METRICAS["conformado"] = {
        "pedido_conformado": int(len(pedidos)),
        "item_pedido_conformado": int(len(itens)),
        "atendimento_conformado": int(len(atend)),
        "avaliacao_conformada": int(len(aval)),
    }

    # --- asserções de contagem ----------------------------------------------
    qa.igual("pedido_conformado total", int(len(pedidos)), 130000 + 280000,
             "todo pedido das duas origens deve existir no conformado")
    qa.igual("item_pedido_conformado total", int(len(itens)), 397086 + 995367,
             "todo item das duas origens deve existir no conformado")

    qa.registrar(dw)
    qa.imprimir()

    print("=== METRICAS (json) ===")
    print(json.dumps(METRICAS, ensure_ascii=False, indent=2, default=str))
