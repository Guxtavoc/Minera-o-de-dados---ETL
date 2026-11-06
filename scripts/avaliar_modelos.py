#!/usr/bin/env python3
"""Reproduz a avaliação 70/30 usada nos fluxos Orange da Semana 4.

O script não substitui os arquivos .ows: ele registra, de forma auditável, as
métricas usadas no relatório e executa a ablação do vazamento sutil.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier


RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "saida"
ALVO = "alvo_recompra_90d"
IGNORAR = {"cliente_sk", "data_corte"}
# Mesmo valor fixo usado pelo widget Data Sampler quando "Replicable" está ativo.
SEMENTE = 42


def ler_orange(nome: str) -> pd.DataFrame:
    """Lê CSV com as três linhas de cabeçalho do Orange."""
    return pd.read_csv(SAIDA / nome, skiprows=[1, 2])


def pre_processador(x: pd.DataFrame, escalar: bool) -> ColumnTransformer:
    numericas = x.select_dtypes(include=np.number).columns.tolist()
    categoricas = [c for c in x.columns if c not in numericas]
    passos_num = [("imputar", SimpleImputer(strategy="median"))]
    if escalar:
        passos_num.append(("escalar", StandardScaler()))
    return ColumnTransformer(
        [
            ("num", Pipeline(passos_num), numericas),
            (
                "cat",
                Pipeline(
                    [
                        ("imputar", SimpleImputer(strategy="most_frequent")),
                        (
                            "onehot",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                categoricas,
            ),
        ],
        sparse_threshold=0,
    )


def avaliar(df: pd.DataFrame, versao: str, remover_z: bool = False) -> list[dict]:
    colunas = [c for c in df.columns if c != ALVO and c not in IGNORAR]
    if remover_z:
        colunas = [c for c in colunas if c != "valor_monetario_z"]
    x, y = df[colunas], df[ALVO].astype(int)
    x_treino, x_teste, y_treino, y_teste = train_test_split(
        x, y, test_size=0.30, random_state=SEMENTE, stratify=y
    )

    modelos = {
        "Naive Bayes": GaussianNB(),
        "Logistic Regression": LogisticRegression(max_iter=2_000, random_state=SEMENTE),
        "Tree": DecisionTreeClassifier(
            max_depth=100, min_samples_leaf=2, random_state=SEMENTE
        ),
    }
    linhas = []
    for nome, estimador in modelos.items():
        pipeline = Pipeline(
            [
                ("preparar", pre_processador(x, escalar=nome == "Logistic Regression")),
                ("modelo", estimador),
            ]
        )
        pipeline.fit(x_treino, y_treino)
        prob = pipeline.predict_proba(x_teste)[:, 1]
        pred = pipeline.predict(x_teste)
        linhas.append(
            {
                "versao": versao,
                "modelo": nome,
                "linhas_treino": len(x_treino),
                "linhas_teste": len(x_teste),
                "auc": round(roc_auc_score(y_teste, prob), 6),
                "acuracia_balanceada": round(
                    balanced_accuracy_score(y_teste, pred), 6
                ),
                "acuracia": round(accuracy_score(y_teste, pred), 6),
            }
        )
    return linhas


def main() -> None:
    correta = ler_orange("abt_recompra_correta.csv")
    vazamento = ler_orange("abt_recompra_vazamento.csv")
    linhas = avaliar(correta, "correta")
    linhas += avaliar(vazamento, "vazamento_completo")
    linhas += avaliar(vazamento, "vazamento_sem_normalizacao", remover_z=True)

    destino = SAIDA / "metricas_modelos.csv"
    with destino.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=linhas[0].keys())
        escritor.writeheader()
        escritor.writerows(linhas)
    print(pd.DataFrame(linhas).to_string(index=False))
    print(f"\n{destino}")


if __name__ == "__main__":
    main()
