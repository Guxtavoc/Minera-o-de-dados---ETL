#!/usr/bin/env python3
"""Gera e valida os dois fluxos Orange e suas capturas de canvas."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from AnyQt.QtCore import QRectF, Qt
from AnyQt.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter
from AnyQt.QtWidgets import QApplication
from orangecanvas.canvas.scene import CanvasScene
from orangecanvas.registry import WidgetDescription
from orangecanvas.scheme import Scheme, SchemeLink, SchemeNode
from orangewidget.utils.filedialogs import RecentPath

from Orange.widgets.data.owdatasampler import OWDataSampler
from Orange.widgets.data.owfile import OWFile
from Orange.widgets.evaluate.owconfusionmatrix import OWConfusionMatrix
from Orange.widgets.evaluate.owrocanalysis import OWROCAnalysis
from Orange.widgets.evaluate.owtestandscore import OWTestAndScore
from Orange.widgets.model.owlogisticregression import OWLogisticRegression
from Orange.widgets.model.ownaivebayes import OWNaiveBayes
from Orange.widgets.model.owtree import OWTreeLearner


RAIZ = Path(__file__).resolve().parents[1]
DIR_ORANGE = RAIZ / "orange"
DIR_SAIDA = RAIZ / "saida"


def descricao(classe):
    return WidgetDescription(**classe.get_widget_description())


def no(classe, titulo, x, y, propriedades=None):
    return SchemeNode(
        descricao(classe), title=titulo, position=(float(x), float(y)),
        properties=propriedades or {},
    )


def ligar(esquema, origem, canal_origem, destino, canal_destino):
    esquema.add_link(
        SchemeLink(
            origem,
            origem.output_channel(canal_origem),
            destino,
            destino.input_channel(canal_destino),
        )
    )


def construir(nome_csv: str, titulo: str) -> Scheme:
    caminho_csv = DIR_SAIDA / nome_csv
    recente = RecentPath.create(
        str(caminho_csv), [("basedir", str(DIR_ORANGE))]
    )
    esquema = Scheme(title=titulo, description=(
        "Separação estratificada e replicável 70/30. Data Sample treina e "
        "Remaining Data testa; AUC, acurácia balanceada, matriz de confusão e ROC."
    ))

    arquivo = no(
        OWFile, "ABT correta" if "correta" in nome_csv else "ABT com vazamento",
        80, 225,
        {"source": 0, "recent_paths": [recente], "url": "", "__version__": 3},
    )
    amostra = no(
        OWDataSampler, "Amostra 70/30 estratificada", 280, 225,
        {
            "sampling_type": 0,
            "sampleSizePercentage": 70,
            "stratify": True,
            "use_seed": True,
            "__version__": 2,
        },
    )
    nb = no(OWNaiveBayes, "Naive Bayes", 470, 70)
    lr = no(OWLogisticRegression, "Logistic Regression", 470, 155)
    arvore = no(OWTreeLearner, "Tree", 470, 240)
    teste = no(
        OWTestAndScore, "Test & Score - teste separado", 700, 190,
        {"resampling": 5, "__version__": 4},
    )
    matriz = no(OWConfusionMatrix, "Confusion Matrix", 920, 125)
    roc = no(OWROCAnalysis, "ROC Analysis", 920, 260)

    for item in (arquivo, amostra, nb, lr, arvore, teste, matriz, roc):
        esquema.add_node(item)

    ligar(esquema, arquivo, "Data", amostra, "Data")
    ligar(esquema, amostra, "Data Sample", teste, "Data")
    ligar(esquema, amostra, "Remaining Data", teste, "Test Data")
    for aprendiz in (nb, lr, arvore):
        ligar(esquema, aprendiz, "Learner", teste, "Learner")
    ligar(esquema, teste, "Evaluation Results", matriz, "Evaluation Results")
    ligar(esquema, teste, "Evaluation Results", roc, "Evaluation Results")
    return esquema


def capturar(esquema: Scheme, destino: Path) -> None:
    cena = CanvasScene()
    cena.set_scheme(esquema)
    cena.set_channel_names_visible(False)
    retangulo = cena.itemsBoundingRect().adjusted(-35, -35, 35, 35)
    escala = 1.6
    imagem = QImage(
        int(retangulo.width() * escala), int(retangulo.height() * escala),
        QImage.Format.Format_ARGB32,
    )
    imagem.fill(QColor("white"))
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    cena.render(pintor, QRectF(imagem.rect()), retangulo, Qt.AspectRatioMode.KeepAspectRatio)
    pintor.end()
    if not imagem.save(str(destino)):
        raise RuntimeError(f"não foi possível salvar {destino}")


def main() -> None:
    DIR_ORANGE.mkdir(exist_ok=True)
    app = QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont(r"C:\Windows\Fonts\arial.ttf")
    app.setFont(QFont("Arial", 10))
    for base, csv, titulo in (
        ("fluxo_abt_correta", "abt_recompra_correta.csv", "Mercatto - ABT correta"),
        ("fluxo_abt_vazamento", "abt_recompra_vazamento.csv", "Mercatto - ABT com vazamento"),
    ):
        esquema = construir(csv, titulo)
        arquivo_ows = DIR_ORANGE / f"{base}.ows"
        with arquivo_ows.open("wb") as fluxo:
            esquema.save_to(fluxo, pretty=True, pickle_fallback=True)
        capturar(esquema, DIR_ORANGE / f"{base}.png")
        print(arquivo_ows)
    app.processEvents()


if __name__ == "__main__":
    main()
