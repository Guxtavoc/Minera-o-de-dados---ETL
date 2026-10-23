# Registro de Decisões de Transformação (RDT) — Semana 3

**Equipe:** Gustavo Curado Soares, Marcelo Henrique  **Data:** 2026-10-23  **Versão do pipeline:** `etl/02_transformacao.py` + `etl/03_carga_dw.py` + `etl/04_abt.py`

Esta é a continuação do RDT da Semana 2. O documento anterior é preservado como
foi entregue; esta versão corrige os números que mudaram depois da carga no
esquema estrela e registra as decisões das fichas **RDT-10 a RDT-13**. As fichas
RDT-14 e RDT-15 pertencem à Semana 4 e não são antecipadas aqui.

---

## Errata da Semana 2

### Errata RDT-02 — identidade do cliente

A regra de identidade não mudou: CPF normalizado (válido ou não) é a ponte e,
sem CPF, o fallback é nome normalizado + cidade + UF. O que mudou foi a
**execução do fallback**: ele passou a aceitar apenas pares **1:1**. A versão
anterior permitia que uma chave nome+cidade+UF casasse vários clientes de um
lado com vários do outro, o que criava linhas ambíguas e **31 IDs naturais
duplicados** na dimensão (18 `id_legado` e 13 `id_ecommerce`).

Números finais, substituindo os da Semana 2:

| Medida | Valor final |
|---|---:|
| `dim_cliente` | **114.548** |
| `AMBOS` | **15.276** |
| somente `LEGADO` | **29.679** |
| somente `ECOM` | **69.593** |
| pareados por CPF | **12.605** |
| pareados por nome+cidade+UF | **2.671** |
| CPF válido | **94.620** |
| CPF inválido | **9.289** |
| sem CPF | **10.639** |
| colisões de CPF entre pessoas | **0** |
| grupos ambíguos de nome+cidade+UF | **13** |
| pares nome+cidade+UF descartados por não serem 1:1 | **62** |

A dimensão cresceu de 114.517 para 114.548 (+31) e os 31 IDs naturais
duplicados desapareceram. O risco declarado agora é mais estreito: 13 grupos de
homônimos não foram pareados entre origens pelo fallback 1:1; eventuais fusões
dentro de cada origem por nome+cidade+UF continuam possíveis e ficam
registradas. Quem ficou sem par continua como uma linha de origem única.

**Asserções associadas:** `dim_cliente: id_legado duplicado` (=0),
`dim_cliente: id_ecommerce duplicado` (=0), `mapa_cliente_origem: chave
duplicada` (=0), `mapa_cliente_origem: linhas` (=132.250).

### Errata RDT-03 — duplicatas internas

A decomposição final é:

| Origem | Linhas brutas | Removidas por CPF | Removidas por nome+cidade+UF | Linhas após dedup |
|---|---:|---:|---:|---:|
| LEGADO | 47.250 | 1.427 | 694 gêmeas sem CPF + 174 duplicatas sem CPF | **44.955** |
| ECOM | 85.000 | 3 | 122 gêmeas sem CPF + 6 duplicatas sem CPF | **84.869** |

Total removido: **2.295** no legado (4,86%) e **131** no e-commerce (0,15%).
A Semana 2 já registrava 2.295 e 131, mas não separava as 174 duplicatas sem
CPF do legado; a separação está agora explícita.

O mapa de procedência `dw.mapa_cliente_origem` tem **132.250** linhas, uma para
cada cliente bruto das duas origens (47.250 + 85.000). Ele preserva a ligação
`id original → id canônico` para todos os clientes, inclusive os 2.426 que
saíram da dimensão (2.295 + 131).

**Asserção associada:** `mapa LEGADO: canonico ausente na dim` (=0),
`mapa ECOM: canonico ausente na dim` (=0).

### Errata RDT-09 — fuso horário

A Semana 2 dizia que os 31.915 timestamps sem fuso eram interpretados como UTC.
Isso estava errado e foi corrigido: timestamps **sem offset** são interpretados
como **hora local de America/Sao_Paulo (UTC-3)**; timestamps com offset são
convertidos para UTC-3. A implementação anterior usava `utc=True` diretamente e
transformava os 31.915 valores sem offset em `NaT`, deixando 128.085 avaliações
com data e 31.915 sem data. Após a correção, **160.000** avaliações têm data,
no intervalo **2023-01-01 a 2025-12-30**.

Distribuição real: **128.085** timestamps com fuso e **31.915** sem fuso
(19,95%). A hipótese de que o horário sem offset é local é declarada; ela pode
deslocar um instante em até 3 horas na fronteira do dia.

**Asserção associada:** `avaliacoes: data nula` (=0).

### Errata RDT-13 — SAC e avaliações na etapa 2

O CSV do SAC contém **1.140 linhas exatamente repetidas** (mesmo protocolo e
mesmos campos). O grão de `fato_atendimento` é **um atendimento**, então o
protocolo foi deduplicado: **96.140 linhas de origem → 95.000 atendimentos**.
As 1.140 linhas removidas não representam atendimentos distintos.

As avaliações continuam **160.000**, todas ligadas a um pedido. A ligação não é
só com o e-commerce: **119.984** avaliações pertencem a pedidos ECOM e
**40.016** a pedidos LEGADO (os `product_ref` no formato `LEG-<id>`).

---

## Ficha RDT-10 — Itens órfãos

**Decisão:** itens cujo pedido não existe no `fato_pedido` vão para
`qa.quarentena_item_pedido`; **não entram** em `dw.fato_item_pedido` e **não**
geram pedido sintético.

**Etapa do pipeline:** 03_carga_dw → `carrega_fato_item`.

**O que o dado mostrava:** dos **1.392.453** itens conformados, **20.577**
(1,48%) não tinham pedido correspondente:

| Origem | Itens órfãos | Valor da linha |
|---|---:|---:|
| ECOM | 14.709 | R$ 2.204.879,10 |
| LEGADO | 5.868 | R$ 586.213,20 |
| **Total** | **20.577** | **R$ 2.791.092,30** |

**Alternativas consideradas:**

1. **Descartar os itens.** Perde definitivamente a única evidência de demanda
   desses produtos; não é reversível.
2. **Criar um pedido sintético “desconhecido”.** Preserva o valor no esquema
   estrela, mas inventa um pedido e contamina contagens, ticket médio e
   frequência.
3. **Quarentena com a chave natural e o valor.** Mantém a evidência fora do
   esquema estrela, sem inventar pedido.

**Decisão:** alternativa 3.

**Justificativa:** o esquema estrela só deve conter fatos com dimensões
válidas; um item sem pedido não tem `pedido_sk` legítimo. A quarentena
preserva o dado e deixa explícito que 1,48% dos itens não foram analisados.

**O que se perde:** esses itens não entram em análises de produto, categoria
ou receita do DW. O valor de R$ 2.791.092,30 (0,28% do valor conformado dos
itens) fica fora dos indicadores. A perda é reversível porque a quarentena
guarda as chaves e os valores.

**Registros afetados:** 20.577 itens (1,48% de 1.392.453); R$ 2.791.092,30.

**Asserções associadas:** `quarentena: itens sem pedido` (=20.577),
`fato_item: linhas` (=1.371.876), `fato_item: produto sem mapeamento` (=0).

---

## Ficha RDT-11 — Declaração de grão

**Decisão:** o grão é declarado antes da carga:

> **Uma linha de `dw.fato_pedido` representa UM PEDIDO** de uma das duas
> origens, identificado por `(id_origem, sistema_origem)`.
>
> **Uma linha de `dw.fato_item_pedido` representa UMA LINHA DE ITEM de um
> pedido válido.** A chave surrogate é `item_sk`; `(pedido_sk, produto_sk)`
> **não** é única quando o mesmo produto aparece em linhas separadas do mesmo
> pedido.

**Etapa do pipeline:** 03_carga_dw → `carrega_fato_pedido` e
`carrega_fato_item`.

**O que o dado mostrava:** 130.000 pedidos LEGADO + 280.000 ECOM = **410.000**
pedidos; 1.392.453 itens conformados, dos quais 1.371.876 têm pedido. A soma de
`qtd_itens` dos pedidos é exatamente **1.371.876**, igual à contagem de itens
válidos, o que confirma que o grão do pedido não foi multiplicado pela junção
com itens.

**Alternativas consideradas:**

1. **Grão de pedido com uma linha por item.** Seria grão de item disfarçado:
   duplicaria o valor do pedido e destruiria a soma de receita.
2. **Grão de item com o pedido agregado.** Perderia a possibilidade de separar
   frete/desconto no nível do pedido.
3. **Dois fatos explícitos**, um por grão, ligados por `pedido_sk`.

**Decisão:** alternativa 3.

**Justificativa:** a pergunta de recompra é por cliente/pedido; a análise de
produto é por item. Separar os grãos mantém as duas perguntas possíveis sem
misturar unidades de medida.

**O que se perde:** não há perda de pedidos válidos; os 20.577 itens sem pedido
ficam na quarentena (RDT-10). O item órfão não pode ser somado ao pedido, mas
essa soma seria inválida de qualquer forma.

**Registros afetados:** 410.000 pedidos (**100%** dos pedidos); 1.371.876 itens
válidos (**98,52%** de 1.392.453); 20.577 itens em quarentena (**1,48%**).

**Asserções associadas:** `fato_pedido: linhas` (=410.000), `fato_item: linhas`
(=1.371.876), `fato_pedido: FK orfa` (=0), `fato_pedido: dias_entrega
negativo` (=0).

---

## Ficha RDT-12 — Pedidos sem cliente correspondente

**Decisão:** resolver a identidade pelo mapa canônico
`dw.mapa_cliente_origem`; **não** criar cliente sentinela “DESCONHECIDO”.

**Etapa do pipeline:** 02_transformacao → `grava_mapa_clientes`;
03_carga_dw → `carrega_fato_pedido`.

**O que o dado mostrava:** depois da deduplicação, **6.388 pedidos LEGADO** e
**448 pedidos ECOM** referenciavam IDs de clientes que não existiam mais na
dimensão — 6.836 pedidos aparentemente órfãos. A causa não era dado faltante:
era a deduplicação sem mapa de procedência. Os clientes removidos tinham sido
fundidos em outro ID canônico.

**Alternativas consideradas:**

1. **Criar um cliente sentinela.** Fácil, mas joga 6.836 pedidos em uma
   identidade falsa e distorce frequência, recência e ticket.
2. **Descartar os pedidos.** Perde 1,67% dos pedidos e receita real.
3. **Mapa `id original → id canônico`**, mantendo todos os pedidos ligados ao
   cliente que absorveu a linha duplicada.

**Decisão:** alternativa 3.

**Justificativa:** a deduplicação é uma decisão sobre a dimensão; o pedido não
deve pagar por ela. O mapa é uma ponte explícita e auditável entre a chave da
origem e a identidade final.

**O que se perde:** nada de pedido. Se a regra de deduplicação tiver fundido
duas pessoas, o mapa propaga essa fusão para os pedidos — o risco já declarado
na RDT-02. O mapa não corrige a decisão; apenas a torna rastreável.

**Registros afetados:** 6.836 pedidos inicialmente sem cliente (**1,67%** de
410.000); **0** após o mapa. O mapa cobre 132.250 clientes brutos e foi usado em
410.000 pedidos.

**Asserções associadas:** `fato_pedido: cliente sem mapeamento` (=0),
`fato_pedido: FK orfa` (=0), `mapa_cliente_origem: linhas` (=132.250).

---

## Ficha RDT-13 — Atendimentos e avaliações sem pedido

**Decisão:** manter SAC e avaliações ligados por chave natural ao pedido; na
carga, usar o `cliente_sk` do pedido para o SAC e mapear o produto por `SKU-` ou
`LEG-` para as avaliações. Não há fallback nulo: os dados atuais têm **0** casos
sem pedido, e a carga aborta explicitamente se aparecer um.

**Etapa do pipeline:** 02_transformacao → `liga_sac_e_avaliacoes`;
03_carga_dw → `carrega_fatos_auxiliares`.

**O que o dado mostrava:**

* SAC: **96.140** linhas de origem, **1.140 duplicatas exatas**, **95.000**
  atendimentos distintos; **5.791** sem data de fechamento (em aberto);
  **0** sem pedido após a ligação.
* Avaliações: **160.000**; **0** sem pedido; **119.984** de pedidos ECOM e
  **40.016** de pedidos LEGADO; **40.016** `product_ref` no formato `LEG-<id>`
  e **119.984** no formato `SKU-<id>`; todas as 160.000 encontraram produto.
* Datas das avaliações: **2023-01-01 a 2025-12-30**, sem nulos após a correção
  de fuso (Errata RDT-09).

**Alternativas consideradas:**

1. **Descartar as linhas sem pedido.** Perderia sinal de atendimento/avaliação
   por causa de uma referência quebrada.
2. **Manter com `pedido_sk` nulo e resolver o cliente pelo CPF.** Funciona para
   o SAC, mas o CPF tem 9.882 casos sem correspondência na dimensão; o pedido é
   uma ponte melhor.
3. **Manter a linha e usar o pedido para obter `cliente_sk`** (escolhida).

**Decisão:** alternativa 3.

**Justificativa:** o pedido é a chave que liga o evento ao cliente de forma
consistente com o fato principal; o CPF é uma ponte secundária e falha em
9.882 atendimentos. As avaliações de pedidos LEGADO também precisam ser
tratadas — assumir que toda avaliação é ECOM perderia 40.016 linhas.

**O que se perde:** as 1.140 linhas duplicadas do SAC não representam
atendimentos distintos; a deduplicação não perde informação, apenas remove
repetição exata. Nenhuma avaliação é descartada. O `cliente_sk` do SAC vem do
pedido, não do CPF; se o CPF do SAC divergir do cliente do pedido, prevalece o
pedido — uma escolha declarada.

**Registros afetados:** 1.140 linhas de SAC removidas (**1,19%** de 96.140);
95.000 atendimentos e 160.000 avaliações carregados; **0** sem pedido.

**Asserções associadas:** `fato_atendimento: SAC sem pedido` (=0),
`fato_atendimento: linhas` (=95.000), `fato_avaliacao: avaliacao sem pedido`
(=0), `fato_avaliacao: linhas` (=160.000), `fato_avaliacao: produto nao
mapeado` (=0).

---

## Resultado da carga e reconciliação

| Fato | Linhas | Soma |
|---|---:|---:|
| `dw.fato_pedido` | 410.000 | R$ 1.027.032.512,48 |
| `dw.fato_item_pedido` | 1.371.876 | R$ 1.010.183.124,51 |
| `qa.quarentena_item_pedido` | 20.577 | R$ 2.791.092,30 |
| `dw.fato_atendimento` | 95.000 | — |
| `dw.fato_avaliacao` | 160.000 | — |

Reconciliação financeira contra a origem (tolerância de ±0,1%):

| Sistema | Origem | DW | Desvio |
|---|---:|---:|---:|
| LEGADO | R$ 281.084.957,13 | R$ 281.117.154,85 | +0,011455% |
| ECOM | R$ 745.850.860,33 | R$ 745.915.357,63 | +0,008647% |

As diferenças vêm do tratamento de frete negativo (RDT-06) e ficam dentro da
tolerância.

---

## ABT — resultado observado

A ABT correta tem **107.091 clientes**, **24.008 positivos** e taxa de alvo
**0,2242**. A taxa ficou **abaixo da faixa 0,30–0,45** sugerida no gabarito do
docente. Não alteramos o `SQL_ALVO` fornecido nem a janela; a hipótese é que a
base inclui todos os clientes com alguma compra até o corte, inclusive os de
baixa frequência, o que reduz a taxa. A taxa com qualquer pedido na janela
(inclusive cancelado) seria 0,2526; portanto o filtro de cancelados não explica
sozinho a diferença. O resultado é registrado como observado, não ajustado.

Atributos com ausência: `recencia_dias` nula em 2.945 clientes sem compra
válida; `nota_media_avaliacoes` nula em 38.876; `prazo_medio_entrega` nulo em
**7.388** após excluir 2.338 pedidos com entrega posterior ao corte (2.245
valores corrigidos). A ABT com vazamento usa os mesmos clientes e a mesma taxa, mas
`recencia_dias` fica negativa para **43.095** clientes (mínimo −183), a
frequência máxima sobe de 17 para 19 e `valor_monetario_z` tem mínimo −1,3527
e máximo 7,7007. `recencia_dias` difere da versão correta em 44.932 clientes e
`frequencia_pedidos` em 43.095.

A materialização usa `to_sql(if_exists="replace")`, que remove as constraints
do DDL; após a carga, `04_abt.py` restaura PK `(cliente_sk, data_corte)`, FK
para `dw.dim_cliente` e CHECK do alvo nas duas ABTs. O `saida/dw_schema.sql`
foi regerado com esse contrato.

---

## Tabela-resumo

| Ficha | Decisão | Registros afetados | % da base | Informação perdida? |
|---|---|---:|---:|---|
| RDT-02 (errata) | Fallback nome+cidade+UF apenas 1:1 + mapa canônico | 114.548 identidades; 132.250 no mapa | 100% | Sim: 13 grupos ambíguos não pareados; risco de fusão interna |
| RDT-03 (errata) | Dedup em duas passagens; decomposição explícita | 2.295 LEGADO + 131 ECOM | 4,86% / 0,15% | Sim: homônimos sem CPF |
| RDT-09 (errata) | Sem offset = hora local SP; não UTC | 31.915 avaliações | 19,95% | Sim: fuso original não preservado |
| RDT-10 | Itens órfãos em quarentena | 20.577 itens; R$ 2.791.092,30 | 1,48% dos itens | Sim: fora das análises do DW |
| RDT-11 | Dois grãos explícitos (pedido e item) | 410.000 pedidos + 1.371.876 itens | 100% dos pedidos; 98,52% dos itens | Não para pedidos válidos |
| RDT-12 | Mapa canônico; sem cliente sentinela | 6.836 pedidos inicialmente órfãos → 0 | 1,67% | Não; risco de fusão da RDT-02 |
| RDT-13 | SAC deduplicado; avaliações por pedido e produto | 1.140 SAC; 95.000 + 160.000 | 1,19% do SAC | Não; duplicatas exatas |
| RDT-14 | ABT: atributos e ausência de vazamento | 107.091 clientes | 100% | Semana 4 |
| RDT-15 | Vazamento deliberado | 43.095 clientes afetados | 40,2% | Semana 4 |

---

## Evidências

* `saida/qa_execucao_assercao.csv` — todas as asserções executadas;
* `saida/resumo_carga.csv` — contagens e somas por tabela;
* `saida/resumo_reconciliacao.csv` — origem × DW;
* `saida/abt_resumo.csv` e `saida/abt_colunas.csv` — perfil da ABT;
* `saida/dw_schema.sql` — DDL do DW, QA e ABT;
* `saida/abt_recompra_correta.csv` e `saida/abt_recompra_vazamento.csv` — ABTs
  no formato do Orange.

Asserções da última execução: **01 = 24**, **02 = 21**, **03 = 24**,
**04 correta = 5**, **04 vazamento = 3**; nenhuma falha. Os totais históricos
são 83, 10 e 6 para 02, 04 correta e 04 vazamento porque essas etapas foram
reexecutadas durante a correção; todas as execuções terminaram sem falha.

---

## Pendências da Semana 4

* RDT-14 (desenho final dos atributos e verificação de vazamento) e RDT-15
  (vazamentos deliberados) serão fechadas com o experimento no Orange.
* O resultado do Orange não é pré-requisito da carga; a ABT correta e a de
  vazamento já estão materializadas e exportadas.
