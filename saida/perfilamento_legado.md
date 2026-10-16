# Perfilamento — legado

## CLIENTES

| coluna      |   linhas |   nulos |   %_nulos |   vazios |   distintos |   min |   max |   media |   negativos | tipo   | mais_frequentes                                                                           |   tam_min |   tam_max |
|:------------|---------:|--------:|----------:|---------:|------------:|------:|------:|--------:|------------:|:-------|:------------------------------------------------------------------------------------------|----------:|----------:|
| ID_CLIENTE  |    47250 |       0 |         0 |        0 |       47250 |     1 | 47250 | 23625.5 |           0 | int64  | nan                                                                                       |       nan |       nan |
| NOME        |    47250 |       0 |         0 |        0 |       40813 |   nan |   nan |   nan   |         nan | object | CARLA COSTA MARTINS (5); ANA NASCIMENTO MACHADO (5); HELENA MOREIRA MOREIRA (5)           |        13 |        32 |
| CPF         |    47250 |       0 |         0 |     4423 |       41955 |   nan |   nan |   nan   |         nan | object | (4423); 842.466.587-23 (2); 875.643.768-48 (2)                                            |         0 |        14 |
| EMAIL       |    47250 |       0 |         0 |        0 |       45000 |   nan |   nan |   nan   |         nan | object | mariana44974@exemplo.com.br (2); helena23@exemplo.com.br (2); marcia18@exemplo.com.br (2) |        20 |        30 |
| DT_CADASTRO |    47250 |       0 |         0 |        0 |        1095 |   nan |   nan |   nan   |         nan | object | 2023-04-28 (66); 2024-06-29 (64); 2023-05-07 (64)                                         |        10 |        10 |
| CIDADE      |    47250 |       0 |         0 |        0 |          24 |   nan |   nan |   nan   |         nan | object | Salvador (2174); Curitiba (2072); São Paulo (2065)                                        |         3 |        14 |
| UF          |    47250 |       0 |         0 |        0 |          16 |   nan |   nan |   nan   |         nan | object | MT (8227); SP (6151); PR (4180)                                                           |         2 |         2 |
| TELEFONE    |    47250 |       0 |         0 |        0 |       45000 |   nan |   nan |   nan   |         nan | object | (98) 96480-1892 (2); (16) 92350-6536 (2); (40) 99109-5422 (2)                             |        15 |        15 |

## PRODUTOS

| coluna       |   linhas |   nulos |   %_nulos |   vazios |   distintos |    min |    max |   media |   negativos | tipo    | mais_frequentes                                                          |   tam_min |   tam_max |
|:-------------|---------:|--------:|----------:|---------:|------------:|-------:|-------:|--------:|------------:|:--------|:-------------------------------------------------------------------------|----------:|----------:|
| ID_PRODUTO   |     3000 |       0 |         0 |        0 |        3000 |   1    | 3000   | 1500.5  |           0 | int64   | nan                                                                      |       nan |       nan |
| DESCRICAO    |     3000 |       0 |         0 |        0 |        2996 | nan    |  nan   |  nan    |         nan | object  | DESKTOP NORDIC 270 (2); PARAFUSADEIRA BRAVA 396 (2); MESA AURORA 514 (2) |        12 |        27 |
| CATEGORIA    |     3000 |       0 |         0 |      103 |          27 | nan    |  nan   |  nan    |         nan | object  | FERRAMENTAS (138); CASA (134); MOVEIS (131)                              |         0 |        24 |
| PRECO_TABELA |     3000 |       0 |         0 |        0 |        2934 |  37.32 | 3497.3 |  380.07 |           0 | float64 | nan                                                                      |       nan |       nan |
| ATIVO        |     3000 |       0 |         0 |        0 |           2 | nan    |  nan   |  nan    |         nan | object  | S (2660); N (340)                                                        |         1 |         1 |

## PEDIDOS

| coluna      |   linhas |   nulos |   %_nulos |   vazios |   distintos |    min |    max |    media |   negativos | tipo           | mais_frequentes                                                              |   tam_min |   tam_max |
|:------------|---------:|--------:|----------:|---------:|------------:|-------:|-------:|---------:|------------:|:---------------|:-----------------------------------------------------------------------------|----------:|----------:|
| ID_PEDIDO   |   130000 |       0 |      0    |        0 |      130000 |   1    | 130000 | 65000.5  |           0 | int64          | nan                                                                          |       nan |       nan |
| ID_CLIENTE  |   130000 |       0 |      0    |        0 |       44253 |   1    |  47250 | 23667.8  |           0 | int64          | nan                                                                          |       nan |       nan |
| DT_PEDIDO   |   130000 |       0 |      0    |        0 |      121077 | nan    |    nan |   nan    |         nan | datetime64[ns] | 2023-05-01 11:32:00 (5); 2024-06-18 21:15:00 (4); 2023-08-13 20:03:00 (4)    |        19 |        19 |
| DT_ENTREGA  |   130000 |   28808 |     22.16 |        0 |       95057 | nan    |    nan |   nan    |         nan | datetime64[ns] | 1900-01-01 00:00:00 (1025); 2025-03-15 11:34:00 (3); 2023-01-19 16:07:00 (3) |        19 |        19 |
| STATUS      |   130000 |       0 |      0    |        0 |           4 | nan    |    nan |   nan    |         nan | object         | ENTREGUE (101192); CANCELADO (15774); EM TRANSITO (7798)                     |         8 |        11 |
| VALOR_TOTAL |   130000 |       0 |      0    |        0 |      112745 |   4.78 |  14811 |  2162.19 |           0 | float64        | nan                                                                          |       nan |       nan |
| VALOR_FRETE |   130000 |       0 |      0    |        0 |        9258 | -88.78 |     89 |    44.31 |         362 | float64        | nan                                                                          |       nan |       nan |
| CANAL       |   130000 |       0 |      0    |        0 |           3 | nan    |    nan |   nan    |         nan | object         | LOJA (58392); SITE (45368); TELEVENDAS (26240)                               |         4 |        10 |

## ITENS_PEDIDO

| coluna      |   linhas |   nulos |   %_nulos |   vazios |   distintos |   min |       max |     media |   negativos | tipo    |
|:------------|---------:|--------:|----------:|---------:|------------:|------:|----------:|----------:|------------:|:--------|
| ID_ITEM     |   200000 |       0 |         0 |        0 |      200000 |  1    | 200000    | 100000    |           0 | int64   |
| ID_PEDIDO   |   200000 |       0 |         0 |        0 |       66493 |  1    |  66493    |  33273.1  |           0 | int64   |
| ID_PRODUTO  |   200000 |       0 |         0 |        0 |        3000 |  1    |   3000    |   1499.08 |           0 | int64   |
| QTD         |   200000 |       0 |         0 |        0 |           3 |  1    |      3    |      2    |           0 | int64   |
| VL_UNITARIO |   200000 |       0 |         0 |        0 |       73258 | 34.37 |   3670.09 |    373.69 |           0 | float64 |
| VL_DESCONTO |   200000 |       0 |         0 |        0 |       20528 | -1    |   1280.88 |     44.37 |        2009 | float64 |

