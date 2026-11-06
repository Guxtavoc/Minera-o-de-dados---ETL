# Registro de Decisões de Transformação - Semana 4

**Equipe:** Gustavo Curado Soares, Marcelo Henrique  
**Data:** 2026-11-06  
**Versão do pipeline:** `etl/01_extracao.py` a `etl/05_exportar_orange.py`

Este documento completa as fichas RDT-14 e RDT-15. O PDF integral reúne estas
fichas às RDT-01 a RDT-13 e às erratas quantitativas registradas na Semana 3.

## Ficha RDT-14 - Desenho dos atributos da ABT e ausência de vazamento

**Decisão:** adotar uma fotografia por cliente em `2025-06-30`, incluindo apenas
clientes com algum pedido até o corte. O alvo é recompra não cancelada entre
`2025-07-01` e `2025-09-28`; todos os atributos da versão correta usam somente
eventos disponíveis até o corte.

**Etapa do pipeline:** `04_abt.py --correta`.

**O que o dado mostrava:** a população elegível contém **107.091 clientes** dos
114.548 clientes conformados (**93,49%**). Há **24.008 positivos**
(**22,42%**). A ABT possui 12 atributos preditivos: recência, frequência, valor
monetário, ticket médio, prazo médio, taxa de cancelamento, categorias distintas,
canal predominante, atendimentos SAC, nota média, tempo como cliente e quantidade
de itens. Existem 2.945 recências nulas (2,75%), 7.388 prazos nulos (6,90%) e
38.876 notas nulas (36,30%); esses nulos significam ausência de evento aplicável,
e não zero.

**Alternativas consideradas:**

1. Incluir todos os 114.548 clientes. Descartada porque 7.457 ainda não tinham
   histórico de pedido no instante da previsão; seriam linhas sem exposição ao
   fenômeno estudado.
2. Imputar zero em recência, prazo e nota. Descartada porque zero teria conteúdo
   semântico falso: recência zero significa compra no dia do corte e nota zero
   nem pertence à escala observada.
3. Manter nulos semanticamente corretos, usar zero apenas em contagens sem evento
   e limitar cada consulta à data de corte. Escolhida.

**Decisão e justificativa:** alternativa 3. Ela preserva a diferença entre
"nenhum evento" e "valor igual a zero" e garante que cada atributo pudesse ser
conhecido quando a campanha fosse dimensionada.

**O que se perde:** os 7.457 clientes sem pedido anterior ao corte não recebem
previsão. Modelos que não tratam nulos exigem imputação dentro de cada partição;
isso acrescenta uma hipótese ao treinamento, mas evita inventar valores no ETL.

**Registros afetados:** 107.091 linhas construídas; 7.457 clientes excluídos da
população por falta de histórico (6,51% da dimensão). Nulos preservados: 2.945,
7.388 e 38.876 nos três atributos citados.

**Asserção associada:** unicidade de `cliente_sk`, cardinalidade da junção,
`data_corte = 2025-06-30`, alvo em `{0,1}`, frequências não negativas, zero
recências negativas e recálculo amostral de frequência, recência e prazo apenas
com pedidos anteriores ao corte.

## Ficha RDT-15 - Vazamentos deliberados na versão de comparação

**Decisão:** produzir um contraexemplo controlado no qual somente três aspectos
mudam: `recencia_dias` e `frequencia_pedidos` passam a consultar toda a série de
pedidos; `valor_monetario_z` usa média e desvio calculados na base inteira antes
da separação treino/teste. Os demais atributos, população, alvo e fluxo de
avaliação permanecem iguais.

**Etapa do pipeline:** `04_abt.py --vazamento` e fluxos do Orange.

**O que o dado mostrava:** **43.095 clientes** (**40,24%** da ABT) mudam em
recência e frequência por possuírem pedido posterior ao corte; nessas linhas a
recência fica negativa, revelando diretamente o futuro. O z-score global afeta
as **107.091 linhas** e varia de -1,352655 a 7,700743. No teste estratificado
70/30 no Orange, a Árvore sobe de AUC **0,484417** para **0,955662** e de
acurácia balanceada **0,523317** para **0,951820**.

**Alternativas consideradas:**

1. Introduzir o próprio alvo como atributo. Descartada por ser um vazamento
   trivial, sem valor didático.
2. Alterar datas, população e atributos ao mesmo tempo. Descartada porque
   impediria atribuir a diferença observada ao vazamento.
3. Alterar apenas dois atributos temporais e acrescentar uma normalização global,
   mantendo todo o restante idêntico. Escolhida.

**Decisão e justificativa:** alternativa 3. O desenho isola um vazamento óbvio
(atributos temporais que olham o futuro) e um sutil (parâmetros de transformação
estimados antes da partição), permitindo medir ambos.

**O que se perde:** a versão vazada não responde à pergunta de negócio e não pode
ser usada em produção. O bom desempenho aparente perde validade causal e
operacional; ele serve somente como evidência experimental.

**Registros afetados:** 43.095 de 107.091 linhas nos dois atributos temporais
(40,24%); 107.091 de 107.091 no z-score global (100%).

**Asserção associada:** a versão vazada deve conter ao menos uma recência
negativa e o z-score global deve ter média aproximadamente zero. Essas asserções
confirmam que o contraexemplo foi realmente introduzido; elas não o aprovam como
dado de produção.

## Tabela-resumo integral

| Ficha | Decisão principal | Registros afetados | Percentual | Informação perdida ou risco |
|---|---|---:|---:|---|
| 01 | Carga completa | 2.205.843 | 100% | Tempo de reprocessamento |
| 02 | Identidade por CPF; fallback 1:1 por nome+cidade+UF | 132.250 brutos | 100% | Possíveis homônimos não pareados |
| 03 | Deduplicação interna com mapa de procedência | 2.426 removidos | 1,83% | Possíveis homônimos fundidos |
| 04 | Status hierárquico e motivo | 52.177 pedidos | 12,73% | Motivo desconhecido no legado |
| 05 | Valor comparável reconstruído pelos itens + frete | 410.000 | 100% | Ajustes só de cabeçalho |
| 06 | Frete negativo em módulo; desconto -1 vira zero | 5.230 eventos | - | Possível estorno reinterpretado |
| 07 | Taxonomia só quando inequívoca | 452 produtos | 3,01% | Categoria analítica ausente |
| 08 | Ausências classificadas, sem imputação média | 3.483 sem prazo | 0,85% pedidos | Data real irrecuperável |
| 09 | Horários em America/Sao_Paulo | 570.000 eventos | 100% | Fuso original não preservado |
| 10 | Itens órfãos em quarentena | 20.577 itens | 1,48% | Valor fora dos fatos |
| 11 | Fatos separados por grão | 1.781.876 fatos | 100% | Nenhuma perda adicional |
| 12 | Pedido ligado pelo mapa canônico | 6.836 pedidos | 1,67% | Propaga eventual fusão de identidade |
| 13 | SAC/avaliação ligados pelo pedido | 256.140 brutos | 100% | 1.140 repetições exatas removidas |
| 14 | Fotografia da ABT no corte | 107.091 clientes | 93,49% da dimensão | 7.457 sem histórico fora da população |
| 15 | Dois vazamentos temporais + z-score global | 43.095 / 107.091 | 40,24% / 100% | Versão inválida para produção |

## Reflexão final

A decisão com maior potencial para alterar o modelo é a RDT-02. Fundir duas
pessoas soma históricos e pode transformar dois não recompradores em uma linha
positiva; separar uma pessoa em dois IDs faz o inverso. Não executamos uma análise
de sensibilidade completa para outra regra de identidade, portanto esta conclusão
é uma hipótese fundamentada, não um resultado medido.

A RDT-06 mostra uma conveniência técnica com efeito sobre pessoas. Interpretar
frete negativo como erro de sinal pode converter um estorno real em gasto. Em uma
campanha, esse cliente pareceria mais valioso e poderia receber tratamento
diferente. A regra é defensável nos dados disponíveis, mas exigiria validação com
a área financeira antes de produção.

As informações mais valiosas que faltaram foram: identificador corporativo único
do cliente, histórico de alterações, semântica formal dos totais e motivo do
cancelamento no legado, além do fuso nos timestamps incompletos. Elas reduziriam
as decisões por aproximação justamente nos pontos que mais afetam identidade,
tempo e dinheiro. O experimento final reforça a principal lição: uma métrica alta
não valida o processo. A Árvore quase dobrou a AUC ao receber informação futura;
o resultado mais impressionante era o menos utilizável.
