# Perfilamento — ecommerce

## customer

| coluna      |   linhas |   nulos |   %_nulos |   vazios |   distintos |   min |   max |   media |   negativos | tipo                | mais_frequentes                                                                                   |   tam_min |   tam_max |
|:------------|---------:|--------:|----------:|---------:|------------:|------:|------:|--------:|------------:|:--------------------|:--------------------------------------------------------------------------------------------------|----------:|----------:|
| customer_id |    85000 |       0 |      0    |        0 |       85000 |     1 | 85000 | 42500.5 |           0 | int64               | nan                                                                                               |       nan |       nan |
| full_name   |    85000 |       0 |      0    |        0 |       66802 |   nan |   nan |   nan   |         nan | object              | Antônio Oliveira Soares (6); Patrícia Fonseca Nascimento (6); Thiago Gonçalves Teixeira (6)       |        13 |        32 |
| tax_id      |    85000 |    6855 |      8.06 |        0 |       78142 |   nan |   nan |   nan   |         nan | object              | 86527372230 (2); 84390192973 (2); 66928971061 (2)                                                 |        11 |        11 |
| email       |    85000 |       0 |      0    |        0 |       85000 |   nan |   nan |   nan   |         nan | object              | cliente84999@correio.com.br (1); cliente0@correio.com.br (1); cliente1@correio.com.br (1)         |        23 |        27 |
| created_at  |    85000 |       0 |      0    |        0 |        1095 |   nan |   nan |   nan   |         nan | datetime64[ns, UTC] | 2023-12-07 03:00:00+00:00 (105); 2025-05-09 03:00:00+00:00 (105); 2024-07-04 03:00:00+00:00 (101) |        25 |        25 |
| city        |    85000 |       0 |      0    |        0 |          23 |   nan |   nan |   nan   |         nan | object              | Fortaleza (3805); Goiânia (3786); Curitiba (3773)                                                 |         5 |        14 |
| state       |    85000 |       0 |      0    |        0 |          16 |   nan |   nan |   nan   |         nan | object              | MT (14630); SP (11079); PR (7529)                                                                 |         2 |         2 |
| phone       |    85000 |       0 |      0    |        0 |       84958 |   nan |   nan |   nan   |         nan | object              | +5566982575873 (2); +5566947313261 (2); +5566927372761 (2)                                        |        14 |        14 |

## product

| coluna      |   linhas |   nulos |   %_nulos |   vazios |   distintos |    min |     max |   media |   negativos | tipo    | mais_frequentes                                                      |   tam_min |   tam_max |
|:------------|---------:|--------:|----------:|---------:|------------:|-------:|--------:|--------:|------------:|:--------|:---------------------------------------------------------------------|----------:|----------:|
| product_id  |    12000 |       0 |         0 |        0 |       12000 |   1    | 12000   | 6000.5  |           0 | int64   | nan                                                                  |       nan |       nan |
| sku         |    12000 |       0 |         0 |        0 |       12000 | nan    |   nan   |  nan    |         nan | object  | SKU-111983 (1); SKU-111982 (1); SKU-111981 (1)                       |        10 |        10 |
| title       |    12000 |       0 |         0 |        0 |       11923 | nan    |   nan   |  nan    |         nan | object  | Desktop Nordic 610 (2); Jogo Vertex 915 (2); Soundbar Veloce 136 (2) |        12 |        27 |
| category_id |    12000 |       0 |         0 |        0 |          15 |   2    |    21   |   11.55 |           0 | int64   | nan                                                                  |       nan |       nan |
| list_price  |    12000 |       0 |         0 |        0 |       11069 |  42.93 |  5477.8 |  419.58 |           0 | float64 | nan                                                                  |       nan |       nan |
| active      |    12000 |       0 |         0 |        0 |           2 |   0    |     1   |    0.92 |           0 | bool    | nan                                                                  |       nan |       nan |

## orders

| coluna         |   linhas |   nulos |   %_nulos |   vazios |   distintos |    min |      max |     media |   negativos | tipo                | mais_frequentes                                                                             |   tam_min |   tam_max |
|:---------------|---------:|--------:|----------:|---------:|------------:|-------:|---------:|----------:|------------:|:--------------------|:--------------------------------------------------------------------------------------------|----------:|----------:|
| order_id       |   200000 |       0 |      0    |        0 |      200000 |   1    | 200000   | 100000    |           0 | int64               | nan                                                                                         |       nan |       nan |
| customer_id    |   200000 |       0 |      0    |        0 |       76898 |   1    |  85000   |  42474.6  |           0 | int64               | nan                                                                                         |       nan |       nan |
| placed_at      |   200000 |       0 |      0    |        0 |      187778 | nan    |    nan   |    nan    |         nan | datetime64[ns, UTC] | 2023-08-11 23:10:00+00:00 (4); 2025-12-24 19:33:00+00:00 (4); 2023-04-29 21:43:00+00:00 (4) |        25 |        25 |
| delivered_at   |   200000 |   51877 |     25.94 |        0 |      141491 | nan    |    nan   |    nan    |         nan | datetime64[ns, UTC] | 2023-02-02 16:31:00+00:00 (4); 2024-02-20 17:18:00+00:00 (4); 2023-11-29 09:44:00+00:00 (4) |        25 |        25 |
| status         |   200000 |       0 |      0    |        0 |           5 | nan    |    nan   |    nan    |         nan | object              | delivered (148123); shipped (16064); canceled (15991)                                       |         7 |        16 |
| total_amount   |   200000 |       0 |      0    |        0 |      168163 |  37.37 |  29403.9 |   2626.06 |           0 | float64             | nan                                                                                         |       nan |       nan |
| freight_amount |   200000 |       0 |      0    |        0 |        8489 | -78.86 |     79   |     39.22 |         612 | float64             | nan                                                                                         |       nan |       nan |
| channel        |   200000 |       0 |      0    |        0 |           3 | nan    |    nan   |    nan    |         nan | object              | web (83722); app (80294); marketplace (35984)                                               |         3 |        11 |

## order_item

| coluna        |   linhas |   nulos |   %_nulos |   vazios |   distintos |   min |       max |     media |   negativos | tipo    |
|:--------------|---------:|--------:|----------:|---------:|------------:|------:|----------:|----------:|------------:|:--------|
| order_item_id |   200000 |       0 |         0 |        0 |      200000 |  1    | 984845    | 101328    |           0 | int64   |
| order_id      |   200000 |       0 |         0 |        0 |       57499 |  1    | 289902    |  29051.6  |           0 | int64   |
| product_id    |   200000 |       0 |         0 |        0 |       12000 |  1    |  12000    |   6001.82 |           0 | int64   |
| quantity      |   200000 |       0 |         0 |        0 |           3 |  1    |      3    |      2    |           0 | int64   |
| unit_price    |   200000 |       0 |         0 |        0 |       75958 | 39.13 |   5617.33 |    403.57 |           0 | float64 |
| discount      |   200000 |       0 |         0 |        0 |       25578 |  0    |   2050.62 |     60.52 |           0 | float64 |

