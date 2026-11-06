# Registro de Decisões de Transformação - Integral

**Equipe:** Gustavo Curado Soares, Marcelo Henrique  
**Data:** 2026-11-06  
**Versão:** pipeline completo, etapas 01 a 05

Este documento reúne as quinze fichas obrigatórias. A seção de errata integra as
correções quantitativas da Semana 3 e prevalece sobre os números históricos das
fichas 02, 03 e 09.

## Ficha RDT-01 — Carga completa ou incremental

**Decisão:** carga **completa** (full load), reescrevendo o `stg` a cada execução.

**Etapa do pipeline:** 01_extracao.

**O que o dado mostrava:** nenhuma origem oferece carimbo confiável de alteração.
O legado só tem `DT_CADASTRO` (data de criação), o e-commerce só tem `created_at`
(criação) e os arquivos do SAC e do marketplace são exportações concatenadas, sem
versão nem data de corte. As contagens na origem são 577.336 (legado), 1.372.367
(e-commerce), 96.140 (SAC) e 160.000 (avaliações).

**Alternativas consideradas:**

1. **Incremental por data de criação** (`DT_CADASTRO`/`created_at`). Descartada:
   criação não indica alteração; pedidos e clientes podem mudar depois e nunca
   seriam relidos. Exigiria ainda um estado de controle de "última extração".
2. **Incremental por CDC** (log binário / triggers). Descartada: os usuários de
   origem são somente leitura e não há acesso ao log de replicação.
3. **Carga completa**, recriando o `stg` do zero a cada execução.

**Decisão:** alternativa 3.

**Justificativa:** como não existe coluna de "última modificação" e o pipeline
precisa ser reprodutível do zero (entregável 5), a leitura completa é a única que
não perde alterações nem depende de estado acumulado. O custo é de tempo, não de
informação.

**O que se perde:** nada de dado; perde-se apenas tempo de reprocessamento (a base
inteira é relida a cada execução). Em um cenário de produção com centenas de
milhões de linhas, o incremental seria obrigatório por custo.

**Registros afetados:** 2.205.843 (100% das fontes são relidos).

**Asserção associada:** contagem do `stg` igual ao `COUNT(*)` da origem, tabela a
tabela — 12 asserções na etapa 01 (todas OK).

---

## Ficha RDT-02 — Identidade do cliente entre os dois sistemas

**Decisão:** o CPF normalizado (só dígitos, **válido ou não** o dígito
verificador) é a ponte; sem CPF, pareia por **nome normalizado + cidade + UF**
apenas 1:1.

**Etapa do pipeline:** 02_transformacao · `unifica_clientes`.

**O que o dado mostrava:** o CPF é o único campo presente nos dois sistemas. No
legado ele aparece com máscara em ~94% dos casos; no e-commerce vem só em dígitos.
Parte dos CPFs está ausente (legado e e-commerce) e uma fração tem dígito
verificador inválido. Após a unificação: **114.517** identidades, das quais
**15.338** (`AMBOS`) existem nos dois sistemas — **12.605** pareadas por CPF e
**2.733** por nome+cidade+UF. Ficaram **29.635** só no legado e **69.544** só no
e-commerce. Dos 114.517: **94.560** com CPF válido, **9.282** com CPF inválido e
**10.675** sem CPF.

**Alternativas consideradas:**

1. **Parear só por CPF válido.** Descartada: jogaria fora os 9.282 vínculos com
   CPF inválido — e o mesmo CPF errado é repetido nos dois sistemas, então ele
   identifica a mesma pessoa tão bem quanto um válido (apenas está errado).
2. **Parear só por nome normalizado + cidade + UF.** Descartada como regra
   primária: homônimos na mesma cidade geram falsos positivos (a colisão medida
   foi de **13** grupos ambíguos).
3. **CPF normalizado como ponte, com fallback nome+cidade+UF quando falta CPF**
   (escolhida).

**Decisão:** alternativa 3.

**Justificativa:** o CPF errado continua sendo um identificador estável porque o
erro é sistemático e compartilhado; já o nome sozinho não distingue homônimos.
Usar o CPF primeiro e o nome só como reserva minimiza tanto a fragmentação
(mesma pessoa em duas linhas) quanto a fusão (duas pessoas em uma).

**O que se perde:** CPFs com dígito verificador inválido podem, em tese, colidir
entre pessoas diferentes — medimos **0** colisões de CPF e **13** de
nome+cidade+UF. Pessoas sem CPF e com nome/cidade/UF diferentes entre os sistemas
(por digitação) permanecem separadas. Quem decide recompra é afetado nos dois
sentidos: fundir dois clientes pode inflar a frequência de um; separar um cliente
pode reduzir a dela.

**Registros afetados:** 114.517 identidades; 15.338 pares `AMBOS` unificados
(9.282 deles com CPF inválido e 10.675 clientes sem CPF dependem da regra de
reserva ou ficam isolados).

**Asserção associada:** `dim_cliente: cpf valido duplicado` (=0); `dim_cliente:
origem_unificacao` (domínio `{LEGADO, ECOM, AMBOS}`); `dim_cliente <= legado +
ecommerce` (cardinalidade preservada).

---

## Ficha RDT-03 — Duplicatas internas do legado

**Decisão:** deduplicar em **duas passagens** — por CPF e, depois, por
nome+cidade+UF das linhas sem CPF.

**Etapa do pipeline:** 02_transformacao · `unifica_clientes`.

**O que o dado mostrava:** o legado tem **47.250** linhas para menos pessoas.
Removemos **2.295** duplicatas (**1.427** por CPF repetido e **694** "gêmeas" sem
CPF que casam nome+cidade+UF com uma linha que tem CPF), restando **44.955**
clientes. No e-commerce, a mesma regra removeu **131** linhas.

**Alternativas consideradas:**

1. **Manter tudo.** Descartada: infla a contagem de clientes e distorce
   frequência e ticket por cliente.
2. **Deduplicar só por CPF.** Descartada: deixa passar as ~694 gêmeas cujo CPF foi
   esvaziado na origem (elas não têm CPF para colidir).
3. **Duas passagens** (CPF; depois nome+cidade+UF para as sem CPF) — escolhida.

**Decisão:** alternativa 3.

**Justificativa:** a primeira passagem resolve os casos inequívocos (mesmo CPF); a
segunda captura os gémeos sem CPF sem depender de uma coluna que a origem apagou.

**O que se perde:** homônimos na mesma cidade/UF sem CPF podem ser fundidos —
**13** grupos apresentaram mais de um CPF distinto (sinal de fusão indevida). Esses
clientes podem perder compras na consolidação.

**Registros afetados:** legado **2.295** (4,86% dos 47.250); e-commerce **131**
(0,15% dos 85.000).

**Asserção associada:** `dim_cliente: cpf valido duplicado` (=0);
`dim_cliente <= legado + ecommerce (pos dedup)`.

---

## Ficha RDT-04 — Conformação de status, incluindo `payment_declined`

**Decisão:** hierarquia — `status_conformado` em
`{ENTREGUE, CANCELADO, EM_TRANSITO, EM_PROCESSAMENTO}` + `motivo_cancelamento`
preenchido só quando a origem distingue.

**Etapa do pipeline:** 02_transformacao · `conforma_status` → `dw.dim_status`.

**O que o dado mostrava:** o legado tem 4 estados (`ENTREGUE` 101.192,
`CANCELADO` 15.774, `EM TRANSITO` 7.798, `SEPARACAO` 5.236) e o e-commerce tem 5
(`delivered` 207.204, `canceled` 22.413, `shipped` 22.375, `processing` 14.018,
`payment_declined` 13.990). O `CANCELADO` do legado agrega **duas** situações que o
e-commerce separa: cancelamento pelo cliente e recusa de pagamento.

**Alternativas consideradas:**

1. **`payment_declined` → `CANCELADO`.** Simples, mas apaga a distinção
   justamente onde ela existe (13.990 pedidos).
2. **Criar `CANCELADO_CLIENTE` e `CANCELADO_PAGAMENTO`.** Preserva a informação,
   mas cria assimetria: o legado ficaria sempre com um desses vazios/`NULL`.
3. **Hierarquia de dois níveis** (`status_conformado` + `motivo_cancelamento`) —
   escolhida.

**Decisão:** alternativa 3.

**Justificativa:** separa o que é comparável (o status de alto nível) do que é
detalhe de origem (o motivo). Análises por status usam `status_conformado`; a
investigação de recusa de pagamento usa `motivo_cancelamento`.

**O que se perde:** para o legado o motivo do cancelamento é **desconhecido**
(`NULL` em 15.774 pedidos) — não há como separar recusa de pagamento ali.

**Registros afetados:** 13.990 pedidos do e-commerce receberam
`motivo_cancelamento = RECUSA_PAGAMENTO`; 22.413 receberam `CLIENTE`; 15.774 do
legado ficaram sem motivo.

**Asserção associada:** `status de origem nao mapeado` (=0); `status_conformado`
(domínio).

---

## Ficha RDT-05 — Semântica de `VALOR_TOTAL` e `total_amount`

**Decisão:** reconstruir as medidas a partir dos **itens** e definir
`valor_total = valor_mercadoria + valor_frete − valor_desconto`.

**Etapa do pipeline:** 02_transformacao · `conforma_valores` →
`dw.pedido_conformado`.

**O que o dado mostrava (a prova):** reconciliando cada cabeçalho com a soma dos
itens do próprio pedido:
`VALOR_TOTAL` do legado fecha **com** o frete em **100,00%** dos 130.000 pedidos
(e só 0,05% sem frete);
`total_amount` do e-commerce fecha **sem** o frete em **100,00%** dos 280.000
pedidos (e só 0,06% com frete).
Ou seja, **não medem a mesma coisa**. O frete embutido no legado soma
**R$ 5.760.932,57**; o frete do e-commerce, deixado de fora, soma
**R$ 10.991.760,38**.

**Alternativas consideradas:**

1. **Usar os totais como estão.** Descartada: agregaria coisas diferentes e
   inflaria o legado em ~R$ 5,7 mi e excluiria ~R$ 11 mi de frete do e-commerce.
2. **Ler mercadoria/frete só do cabeçalho.** Descartada: o e-commerce não guarda a
   mercadoria bruta no cabeçalho; não há como separar sem os itens.
3. **Reconstruir mercadoria e desconto dos itens e somar o frete do cabeçalho** —
   escolhida.

**Decisão:** alternativa 3.

**Justificativa:** a soma dos itens é a única fonte da mercadoria bruta nas duas
origens, o que torna as medidas comparáveis. A soma dos `valor_total` conformados
é **R$ 1.027.032.512,48**.

**O que se perde:** a diferença entre o total de cabeçalho e a mercadoria
reconstruída; eventuais ajustes lançados só no cabeçalho (não observados) seriam
ignorados. Pedidos sem itens ficariam com mercadoria zero — não ocorre (todos os
410.000 têm ao menos um item).

**Registros afetados:** 410.000 pedidos (100%).

**Asserção associada:** `valor_mercadoria legado == soma itens` (=0);
`valor_mercadoria ecom == soma itens` (=0); e, na Semana 3, a reconciliação
financeira (±0,1%).

---

## Ficha RDT-06 — Frete negativo e desconto `-1`

**Decisão:** frete negativo → **valor absoluto**; desconto `-1` no legado →
**0**.

**Etapa do pipeline:** 02_transformacao · `conforma_valores`.

**O que o dado mostrava:** frete negativo em **362** pedidos do legado (0,28%) e
**812** do e-commerce (0,29%); desconto exatamente `-1` em **4.056** itens do
legado (1,02% dos itens).

**Alternativas consideradas:**

1. **Frete negativo — manter.** Descartada: produz um `valor_total` que "devolve"
   frete, implausível como cobrança.
2. **Frete negativo — zerar.** Descartada: perde o valor efetivamente cobrado.
3. **Frete negativo — tomar o valor absoluto** (assumir erro de sinal) —
   escolhida.
4. **Desconto `-1` — manter.** Descartada: converteria o desconto em acréscimo.
5. **Desconto `-1` — zerar** (assumir sentinela "sem desconto") — escolhida.

**Decisão:** 3 e 5.

**Justificativa:** `-1` não é um valor de desconto possível; é o padrão de "sem
desconto" que a origem grava. O frete negativo é mais provavelmente erro de sinal
da digitação do que um crédito.

**O que se perde:** se algum frete negativo for um **estorno real**, tratá-lo como
positivo superestima o total desses pedidos; se algum `-1` for um desconto real,
zerá-lo subestima. Não há como distinguir com os dados disponíveis.

**Registros afetados:** 362 + 812 pedidos (frete); 4.056 itens (desconto).

**Asserção associada:** `valor_mercadoria legado == soma itens` (o desconto
clipado entra nessa soma).

---

## Ficha RDT-07 — Mapeamento da taxonomia de produtos

**Decisão:** mapear o texto livre do legado para a taxonomia de dois níveis do
e-commerce **quando inequívoco**; deixar `categoria_nivel1 = NULL` nos casos
ambíguos e **preservar** `categoria_origem`.

**Etapa do pipeline:** 02_transformacao · `conforma_categorias` →
`dw.dim_produto`.

**O que o dado mostrava:** o legado tem **27** valores distintos de `CATEGORIA`,
sem lista controlada (`ELETRO`, `Eletro-domesticos`, `informatica e games`,
`DIVERSOS`, `''`, …). O e-commerce tem taxonomia de dois níveis. Após o mapeamento,
**452** produtos (3,01% dos 15.000) ficaram sem `nivel1`: 340 de `DIVERSOS`,
`OUTROS` ou `''` e **112** de `informatica e games` (que cobre os ramos
Informática **e** Games). `TV E SOM` foi mapeado só até o nível 1 (`Áudio e TV`).

**Alternativas consideradas:**

1. **Descartar produtos sem taxonomia.** Descartada: perde catálogo e itens no
   fato.
2. **Forçar tudo para um nível1 "OUTROS".** Descartada: inventa uma categoria que
   a origem não tem e contamina análises.
3. **Mapear o inequívoco, deixar `NULL` o ambíguo, preservar `categoria_origem`** —
   escolhida.

**Decisão:** alternativa 3.

**Justificativa:** não se deve inventar um nível que o dado não sustenta. Manter
`categoria_origem` permite refazer o mapeamento depois sem tocar nos fatos.

**O que se perde:** qualquer análise por categoria exclui 3,01% dos produtos e,
portanto, os itens associados; `informatica e games` (112 produtos) não pode ser
atribuído a um único nível1.

**Registros afetados:** 452 produtos (3,01% da `dim_produto`; 15.000 linhas).

**Asserção associada:** `dim_produto: descricao nula` (=0) — a dimensão não
descarta o produto por falta de categoria.

---

## Ficha RDT-08 — Classificação e tratamento de cada tipo de ausência

**Decisão:** classificar toda ausência como **não coletada**, **não aplicável**,
**sentinela** ou **erro**, e tratá-las de forma distinta — nunca imputar média.
Sentinela de data e erro de data viram `NULL` **mais** o indicador
`entrega_sem_data`.

**Etapa do pipeline:** 02_transformacao · `trata_datas_e_ausencias`.

**O que o dado mostrava:**

| Campo | Tipo de ausência | Registros |
|---|---|---|
| `DT_ENTREGA` = `1900-01-01` | sentinela | 1.025 |
| `DT_ENTREGA` < `DT_PEDIDO` | erro de registro | 2.458 |
| `DT_ENTREGA` vazia em pedido não entregue | não aplicável | 101.604 |
| `CPF` ausente (legado + e-commerce) | não coletada | 10.675 |
| `VL_DESCONTO` = `-1` | sentinela | 4.056 |
| `data_fechamento` vazia no SAC | não aplicável (em aberto) | 5.856 |
| `nota_satisfacao` vazia / `'0'` | não coletada / fora do domínio | 8.682 / 2.830 |
| `tempo_resolucao_horas` negativo | erro | 353 |
| `rating` ausente (avaliações) | não coletada | 4.831 |

**Alternativas consideradas:**

1. **Imputar a média** em cada campo vazio. Descartada: inventa dado em campos que
   são sentinela ou não aplicável (a entrega de um pedido cancelado não existe).
2. **Descartar as linhas afetadas.** Descartada: perderia o pedido inteiro por
   causa de um único campo.
3. **`NULL` + indicador** para as sentinelas de entrega — escolhida.

**Decisão:** alternativa 3.

**Justificativa:** distinguir "não existe" de "não foi registrado" preserva a
hipótese de que falhas de registro se concentram em entregas problemáticas —
hipótese que o indicador `entrega_sem_data` deixa testar.

**O que se perde:** `dias_entrega` fica indisponível para **3.483** pedidos
(0,85%): 1.025 por sentinela + 2.458 por erro. Qualquer prazo médio passa a
excluí-los e fica levemente enviesado para baixo se as falhas se concentrarem em
entregas lentas.

**Registros afetados:** ver tabela (2.458 + 1.025 + 101.604 de entrega; e os
demais campos acima).

**Asserção associada:** `dias_entrega negativo` (=0) — nenhuma entrega anterior ao
pedido sobrou.

---

## Ficha RDT-09 — Padronização de fuso horário

**Decisão:** padronizar **todos** os instantes para **America/Sao_Paulo (UTC-3)**,
armazenados sem fuso.

**Etapa do pipeline:** 02_transformacao · `trata_datas_e_ausencias`.

**O que o dado mostrava:** o e-commerce grava `placed_at`/`delivered_at` como
`TIMESTAMPTZ` (com fuso); o legado grava `DATETIME` sem fuso; o SAC usa
`dd/mm/aaaa`; nas avaliações, **128.085** timestamps vêm com fuso e **31.915**
(19,95%) vêm **sem** fuso.

**Alternativas consideradas:**

1. **Guardar cada origem no seu fuso.** Descartada: comparações entre sistemas
   ficariam erradas em até 3 horas (ex.: uma compra de 31/06 23:00 viraria
   01/07 02:00 e cairia no lado errado da data de corte).
2. **Converter tudo para UTC.** Correta, mas dificulta a leitura local dos
   relatórios.
3. **Converter tudo para America/Sao_Paulo (UTC-3), sem fuso** — escolhida.

**Decisão:** alternativa 3.

**Justificativa:** um único fuso elimina as comparações ambíguas; UTC-3 fixo é
fiel porque o Brasil não usa horário de verão desde 2019, e uma data local é mais
legível para a área de marketing.

**O que se perde:** os 31.915 timestamps **sem** fuso são interpretados como UTC
antes da conversão — uma suposição que pode deslocar esses instantes em até 3
horas e, na fronteira da data de corte, trocar o lado de um pedido. A informação
de fuso original não é preservada.

**Registros afetados:** 410.000 pedidos + 160.000 avaliações (100%); suposição
aplicada a 31.915 avaliações.

**Asserção associada:** `dias_entrega negativo` (=0) — a padronização de fuso não
pode produzir entrega anterior ao pedido.

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

Uma linha de `dw.fato_pedido` representa **um pedido** de uma das duas origens,
identificado por `(id_origem, sistema_origem)`.

Uma linha de `dw.fato_item_pedido` representa **uma linha de item de um pedido
válido**. A chave surrogate é `item_sk`; `(pedido_sk, produto_sk)` não é única
quando o mesmo produto aparece em linhas separadas do mesmo pedido.

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

