#!/usr/bin/env python3
"""Executa programaticamente o mesmo teste separado configurado nos .ows."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from Orange.classification import (
    LogisticRegressionLearner, NaiveBayesLearner, TreeLearner,
)
from Orange.data import Domain, Table
from Orange.evaluation import AUC, CA, TestOnTestData
from Orange.widgets.data.owdatasampler import SampleRandomN
from sklearn.metrics import balanced_accuracy_score


RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "saida"


def sem_z(data: Table) -> Table:
    atributos = [a for a in data.domain.attributes if a.name != "valor_monetario_z"]
    return data.transform(Domain(atributos, data.domain.class_vars, data.domain.metas))


def avaliar(arquivo: str, versao: str, remover_z=False):
    data = Table(str(SAIDA / arquivo))
    if remover_z:
        data = sem_z(data)
    restantes, amostra = SampleRandomN(
        n=math.ceil(0.70 * len(data)), stratified=True, random_state=42
    )(data)
    treino, teste = data[amostra], data[restantes]
    aprendizes = [
        NaiveBayesLearner(), LogisticRegressionLearner(),
        TreeLearner(),
    ]
    nomes = ["Naive Bayes", "Logistic Regression", "Tree"]
    resultado = TestOnTestData(treino, teste, aprendizes, store_data=True)
    aucs, acuracias = AUC(resultado), CA(resultado)
    linhas = []
    for i, nome in enumerate(nomes):
        linhas.append({
            "versao": versao,
            "modelo": nome,
            "linhas_treino": len(treino),
            "linhas_teste": len(teste),
            "auc": round(float(aucs[i]), 6),
            "acuracia_balanceada": round(
                balanced_accuracy_score(resultado.actual, resultado.predicted[i]), 6
            ),
            "acuracia": round(float(acuracias[i]), 6),
        })
    return linhas


def main():
    linhas = avaliar("abt_recompra_correta.csv", "correta")
    linhas += avaliar("abt_recompra_vazamento.csv", "vazamento_completo")
    linhas += avaliar(
        "abt_recompra_vazamento.csv", "vazamento_sem_normalizacao", True
    )
    destino = SAIDA / "metricas_orange.csv"
    with destino.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=linhas[0].keys())
        escritor.writeheader(); escritor.writerows(linhas)
    for linha in linhas:
        print(linha)


if __name__ == "__main__":
    main()
