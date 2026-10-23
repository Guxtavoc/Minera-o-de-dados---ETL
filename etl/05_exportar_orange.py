#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETAPA 5 — EXPORTAÇÃO PARA O ORANGE E EVIDÊNCIAS DA CARGA

Gera dois CSVs em /saida, prontos para o widget File do Orange:

    abt_recompra_correta.csv
    abt_recompra_vazamento.csv

O cabeçalho sai no formato de três linhas do Orange, que já declara tipo e
papel de cada coluna — assim vocês não precisam reconfigurar o widget a cada
recarga, e o alvo nunca entra como atributo por engano.

No fim, também recria as evidências da Semana 3 (resumos, asserções, perfil
da ABT e dump SQL do dw/qa/abt), para que os seis comandos do README sejam
suficientes para reproduzir os artefatos.

    docker compose exec etl python 05_exportar_orange.py
"""

import os

import pandas as pd
from sqlalchemy import text

from config import DIR_SAIDA, eng_dw
from evidencias import exporta_evidencias

ALVO = "alvo_recompra_90d"
IGNORAR = {"cliente_sk", "data_corte"}


def tipo_orange(serie):
    if pd.api.types.is_bool_dtype(serie):
        return "discrete"
    if pd.api.types.is_numeric_dtype(serie):
        return "continuous"
    return "discrete" if serie.nunique(dropna=True) <= 30 else "string"


def exporta(tabela, arquivo, dw):
    try:
        df = pd.read_sql(
            text(f"SELECT * FROM abt.{tabela} ORDER BY cliente_sk"), dw)
    except Exception as e:                                   # noqa: BLE001
        print(f"  [pular] abt.{tabela} indisponível: {type(e).__name__}")
        return

    colunas = list(df.columns)
    tipos, papeis = [], []
    for c in colunas:
        if c == ALVO:
            tipos.append("discrete")
            papeis.append("class")
        elif c in IGNORAR:
            tipos.append(tipo_orange(df[c]))
            papeis.append("meta")
        else:
            tipos.append(tipo_orange(df[c]))
            papeis.append("")

    destino = os.path.join(DIR_SAIDA, arquivo)
    with open(destino, "w", encoding="utf-8", newline="") as f:
        f.write(",".join(colunas) + "\n")
        f.write(",".join(tipos) + "\n")
        f.write(",".join(papeis) + "\n")
    df.to_csv(destino, mode="a", header=False, index=False, encoding="utf-8")

    print(f"  {destino}  ({len(df)} linhas, {len(colunas)} colunas)")
    print(f"     alvo: {df[ALVO].mean():.3f} de positivos")


if __name__ == "__main__":
    os.makedirs(DIR_SAIDA, exist_ok=True)
    dw = eng_dw()
    print("exportando para o Orange:")
    exporta("recompra_90d", "abt_recompra_correta.csv", dw)
    exporta("recompra_90d_vazamento", "abt_recompra_vazamento.csv", dw)
    exporta_evidencias(dw)
    print("""
No Orange, monte o mesmo fluxo para os dois arquivos:

    File -> Data Sampler (70/30, estratificado) -> Naive Bayes -> Test & Score
                                               -> Logistic Regression
                                               -> Tree
            Test & Score -> Confusion Matrix
                         -> ROC Analysis

Use o MESMO conjunto de teste e as MESMAS configurações nos dois. A única
diferença entre os fluxos deve ser o arquivo de entrada.
""")
