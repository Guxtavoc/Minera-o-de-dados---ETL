# Experimento de vazamento - resultados da Semana 4

**Equipe:** Gustavo Curado Soares, Marcelo Henrique  
**Data:** 2026-11-06

## Pergunta e desenho

Predizer se um cliente com histórico até 30/06/2025 fará ao menos uma compra não
cancelada de 01/07/2025 a 28/09/2025. A população possui 107.091 clientes e
24.008 positivos (22,42%). Foi aplicada uma separação estratificada e replicável:
70% para treino (74.964 linhas) e 30% para teste (32.127), com a mesma semente,
modelos e tratamento de ausências nas duas versões.

A versão correta limita todos os atributos ao corte. A versão de comparação usa
o futuro em recência e frequência e calcula um z-score global antes da partição.
Os três modelos exigidos são Naive Bayes, Logistic Regression e Tree. AUC é a
métrica principal; acurácia balanceada impede que a classe majoritária esconda o
desempenho sobre os recompradores. As métricas abaixo foram executadas pelo
Orange 3.39 com o mesmo particionamento configurado nos arquivos `.ows`.

## Resultados

| Modelo | AUC correta | AUC vazada | Diferença | Bal. correta | Bal. vazada | Diferença |
|---|---:|---:|---:|---:|---:|---:|
| Naive Bayes | 0,576802 | 0,879834 | +0,303032 | 0,524992 | 0,767283 | +0,242291 |
| Logistic Regression | 0,536168 | 0,841793 | +0,305625 | 0,500393 | 0,606365 | +0,105972 |
| Tree | 0,484417 | 0,955662 | +0,471245 | 0,523317 | 0,951820 | +0,428503 |

Na ABT correta, o melhor AUC foi o do Naive Bayes (0,576802), ainda
modesto. Isso é aceitável: o projeto avalia a validade do processo, não uma meta
arbitrária de desempenho. Na ABT vazada, a Árvore atinge AUC 0,955662 e acurácia
balanceada 0,951820. O salto não representa melhor generalização; representa
acesso a pedidos posteriores ao instante de previsão.

## O vazamento sutil

Foi repetida a avaliação da ABT vazada removendo somente `valor_monetario_z`.

| Modelo | Delta AUC ao incluir z global | Delta acurácia balanceada |
|---|---:|---:|
| Naive Bayes | -0,004052 | -0,007237 |
| Logistic Regression | +0,001260 | -0,001638 |
| Tree | 0,000000 | 0,000000 |

O efeito foi pequeno e inconsistente: imperceptível na regressão e na árvore e
ligeiramente negativo no Naive Bayes. Isso não torna a prática aceitável. A
transformação aprendeu parâmetros do conjunto de teste e viola o contrato de
avaliação, ainda que esta base específica não tenha produzido ganho.

## Como detectar o erro sem conhecer a origem

Primeiro, reconstruir cada atributo para uma amostra usando apenas dados
disponíveis em 30/06/2025. Essa auditoria encontra 43.095 divergências em
recência e frequência. Segundo, verificar domínios temporais: recência negativa é
impossível numa fotografia do passado, e há exatamente 43.095 casos na versão
vazada. Terceiro, executar validação temporal, treinando em períodos antigos e
testando em períodos posteriores; uma queda abrupta em relação à partição
aleatória é sinal de informação indisponível. Quarto, encapsular imputação,
normalização e seleção de atributos dentro de cada partição. Por fim, desconfiar
de saltos grandes sem nova fonte operacional: a Árvore passou de AUC 0,484 para
0,956 apenas trocando o arquivo.

## Conclusão

O modelo correto é o único candidato a uso. Seu desempenho modesto pede novos
atributos disponíveis no corte ou outra formulação de negócio, nunca a inclusão
do futuro. O experimento mostra que métricas excelentes podem ser evidência de
erro: a rastreabilidade temporal e as asserções da ABT são mais importantes que
o placar isolado.
