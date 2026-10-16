# Registro de Decisões de Transformação (RDT) — parcial · Semana 2

**Equipe:** Gustavo Curado Soares  ·  **Data:** 2026-10-16  ·  **Versão do pipeline:** `etl/01_extracao.py` + `etl/02_transformacao.py`

Este é o artefato central do projeto e vale **30% da nota**. Ele não descreve o
que o código faz — o código já faz isso. Ele registra **por que** cada decisão
foi tomada, **o que se perdeu** ao tomá-la e **quantos registros** foram
afetados.

Entrega parcial da Semana 2 (PDF §3.2): fichas **RDT-01 a RDT-09**, mais a
**RDT-13 (parte da etapa 2)** — a decisão de ligação das fontes de arquivo, cuja
função é implementada em `02_transformacao.py`. As fichas RDT-10 a RDT-12 (grão,
itens órfãos e pedidos sem cliente) dependem da carga no esquema estrela e vêm na
Semana 3.

---

## Escopo e arquitetura das camadas

A etapa 1 copia as quatro fontes, sem reinterpretar nada, para o esquema `stg`
(regra da seção 2.3 do referencial). A etapa 2 conforma e grava:

* **dimensões finais** — `dw.dim_status`, `dw.dim_canal`, `dw.dim_cliente`,
  `dw.dim_produto` (chaves surrogate já atribuídas);
* **fatos conformados** — `dw.pedido_conformado`, `dw.item_pedido_conformado`,
  `dw.atendimento_conformado`, `dw.avaliacao_conformada`, carregando **chaves
  naturais** (`id_origem`, `id_cliente_legado`, `id_cliente_ecommerce`, …).

A etapa 3 (Semana 3) troca as chaves naturais pelas surrogate keys, popula
`dw.dim_tempo` e roda a reconciliação financeira. Essa divisão mantém a etapa 2
sobre "o que o dado significa" e a etapa 3 sobre "como o dado vira estrela".

> **Nota de ambiente.** A origem MySQL 8 usa `caching_sha2_password`; o driver
> `PyMySQL` só autentica nesse plugin com o pacote `cryptography`. Sem ele, a
> extração nem conecta. Por isso `cryptography` foi acrescentado a
> `etl/requirements.txt` — é dependência de driver, não de regra de negócio.

Volume das fontes (medido na extração): legado **577.336** linhas, e-commerce
**1.372.367**, SAC **96.140**, avaliações **160.000** — **2.205.843** no total.

---

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

## Ficha RDT-13 (parte da etapa 2) — Ligação das fontes de arquivo aos pedidos

**Decisão:** ligar SAC e avaliações por **chave natural** ao pedido; quando não há
correspondência, **manter a linha** e deixar `pedido_sk` nulo (resolvido na etapa
3), nunca descartar.

**Etapa do pipeline:** 02_transformacao · `liga_sac_e_avaliacoes`.

**O que o dado mostrava:** o SAC identifica o pedido por
`(origem_sistema, id_pedido_origem)`; as avaliações usam `order.ref` no formato
`LEG-<id>`/`ECOM-<id>`. Após normalizar, **96.140** atendimentos e **160.000**
avaliações ligaram — **0** sem pedido em ambas as fontes.

**Alternativas consideradas:**

1. **Descartar o que não liga.** Descartada: apagaria sinal de SAC/avaliação de um
   cliente por causa de uma referência quebrada.
2. **Manter com `pedido_sk` nulo** (escolhida), resolvendo o `cliente_sk` pelo CPF
   quando o pedido não liga.

**Decisão:** alternativa 2.

**Justificativa:** a pergunta analítica é a recompra; um atendimento sem pedido
ainda carrega CPF e data e pode compor o comportamento do cliente. Manter a linha
com referência nula é reversível; descartar, não.

**O que se perde:** nada neste dado (0 órfãos), mas a decisão protege contra
referências inválidas futuras e mantém a contagem das fontes de arquivo intacta.

**Registros afetados:** 0 de 96.140 atendimentos e 0 de 160.000 avaliações ficaram
sem pedido.

**Asserção associada:** `pedido_conformado total` (=410.000);
`item_pedido_conformado total` (=1.392.453).

---

## Tabela-resumo

| Ficha | Decisão | Registros afetados | % da base | Informação perdida? |
|---|---|---|---|---|
| RDT-01 | Carga completa (não incremental) | 2.205.843 | 100% | Não (só tempo de reprocesso) |
| RDT-02 | CPF (válido ou não) + fallback nome+cidade+UF | 114.517 | 100% da `dim_cliente` | Sim: 13 fusões possíveis de homônimos |
| RDT-03 | Dedup interna em duas passagens | 2.295 legado + 131 ecom | 4,86% / 0,15% | Sim: homônimos sem CPF |
| RDT-04 | Status hierárquico + motivo | 13.990 + 22.413 + 15.774 | 3,4% (ecom) / 12,1% (legado) | Sim: motivo no legado é desconhecido |
| RDT-05 | Reconstruir medida dos itens | 410.000 | 100% | Sim: ajustes só de cabeçalho |
| RDT-06 | Frete negativo → abs; desconto −1 → 0 | 1.174 pedidos + 4.056 itens | 0,29% / 1,02% | Sim: estornos reais viram frete |
| RDT-07 | Taxonomia: mapeia o inequívoco, `NULL` o ambíguo | 452 produtos | 3,01% | Sim: categoria ausente em 3% |
| RDT-08 | Classificar e tratar cada ausência | 3.483 sem prazo + 1.025 sentinela | 0,85% / 0,25% | Sim: data real irrecuperável |
| RDT-09 | Padronizar fuso em America/Sao_Paulo | 410.000 + 160.000 | 100% | Sim: fuso original e 31.915 suposições |
| RDT-13 | Manter linha sem pedido (`pedido_sk` nulo) | 0 | 0% | Não (proteção preventiva) |

---

## Reflexão final (parcial)

1. **A decisão que mais mudaria o resultado do modelo** é, provavelmente, a
   **RDT-02** (identidade). Como o alvo é "este cliente recomprará?", fundir ou
   separar clientes muda diretamente quem está na base e qual o histórico de cada
   linha. É uma hipótese, ainda não testada: como o experimento do Orange só vem
   na Semana 4, não medimos o efeito de trocar a regra de pareamento. A **RDT-05**
   é a segunda mais sensível, porque define o que é "valor" do cliente.
2. **Uma decisão de conveniência com consequência sobre pessoas:** tratar o frete
   negativo como erro de sinal (RDT-06). Em produção, isso registra como cobrança
   o que pode ter sido um estorno; se o valor compõe um indicador de risco, um
   cliente que recebeu dinheiro de volta poderia ser lido como cliente de alto
   valor e — num sistema de retenção — ser priorizado indevidamente.
3. **Informação que gostaríamos de ter tido:** uma coluna de "última alteração"
   nas origens (resolveria a RDT-01 com incremental) e um carimbo de fuso
   confiável nos timestamps de avaliação (eliminaria a suposição da RDT-09). Sem
   elas, decidimos e declaramos o que se perde — que é exatamente o que o RDT
   cobra.
