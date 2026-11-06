#!/usr/bin/env python3
"""Reproduz a entrega da Semana 3 do zero.

Uso:
    python scripts/reproduzir.py

O script apaga dados/ e os artefatos gerados em saida/, recria os volumes,
roda os seis comandos do pipeline e valida o DW, as asserções, o RDT e o dump.
"""

import csv
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "saida"
DADOS = RAIZ / "dados"
BANCO = "mercatto_dw"
RESTORE = "mercatto_dw_restore"
TIMEOUT_SEED = 15 * 60
TIMEOUT_ETL = 2 * 60

GERADOS = [
    "abt_colunas.csv",
    "abt_recompra_correta.csv",
    "abt_recompra_vazamento.csv",
    "abt_resumo.csv",
    "dw_schema.sql",
    "dw_dump.sql",
    "dw_dump.sql.gz",
    "qa_execucao_assercao.csv",
    "resumo_carga.csv",
    "resumo_reconciliacao.csv",
]

PASSOS = [
    ("01_extracao", ["01_extracao.py"]),
    ("02_transformacao", ["02_transformacao.py"]),
    ("03_carga_dw", ["03_carga_dw.py"]),
    ("04_abt_correta", ["04_abt.py", "--correta"]),
    ("04_abt_vazamento", ["04_abt.py", "--vazamento"]),
    ("05_exportar_orange", ["05_exportar_orange.py"]),
]

CONTAGENS = {
    "dw.fato_pedido": 410000,
    "dw.fato_item_pedido": 1371876,
    "dw.dim_cliente": 114548,
    "dw.fato_atendimento": 95000,
    "dw.fato_avaliacao": 160000,
}


def comando(args, capturar=False, mostrar=True):
    if mostrar:
        print("  $ " + " ".join(args), flush=True)
    if capturar:
        resultado = subprocess.run(args, capture_output=True, text=True)
        if resultado.returncode != 0:
            print(resultado.stdout, end="", flush=True)
            print(resultado.stderr, end="", flush=True)
            raise subprocess.CalledProcessError(resultado.returncode, args)
        return resultado.stdout.strip()
    subprocess.run(args, check=True)


def psql(sql, banco=BANCO):
    return comando(
        ["docker", "compose", "exec", "-T", "pg_dw", "psql",
         "-U", "postgres", "-d", banco, "-tA", "-F", "|", "-c", sql],
        capturar=True, mostrar=False,
    )


def exigir(condicao, mensagem):
    if not condicao:
        raise RuntimeError(mensagem)
    print(f"  OK  {mensagem}", flush=True)


def duracao(segundos):
    minutos = int(segundos // 60)
    resto = int(segundos % 60)
    return f"{minutos}m {resto}s" if minutos else f"{resto}s"


def preparar():
    print("== preparação ==", flush=True)
    os.chdir(RAIZ)
    if not (RAIZ / "docker-compose.yml").exists():
        raise RuntimeError("docker-compose.yml não encontrado")

    comando(["docker", "--version"], capturar=True)
    comando(["docker", "compose", "version"], capturar=True)
    comando(["docker", "info"], capturar=True)

    env = RAIZ / ".env"
    if not env.exists():
        exemplo = RAIZ / ".env.example"
        if not exemplo.exists():
            raise RuntimeError(".env e .env.example não encontrados")
        shutil.copyfile(exemplo, env)
        print("  .env criado a partir de .env.example", flush=True)

    escala = "1.0"
    for linha in env.read_text(encoding="utf-8").splitlines():
        if linha.strip().startswith("ESCALA="):
            escala = linha.split("=", 1)[1].strip()
    if escala != "1.0":
        raise RuntimeError(f"ESCALA={escala}; ajuste para 1.0 antes da entrega")
    print("  ESCALA=1.0", flush=True)


def resetar():
    print("== reset ==", flush=True)
    comando(["docker", "compose", "down", "-v", "--remove-orphans"])
    shutil.rmtree(DADOS, ignore_errors=True)
    for nome in GERADOS:
        (SAIDA / nome).unlink(missing_ok=True)
    SAIDA.mkdir(exist_ok=True)
    print("  dados/ e artefatos gerados removidos", flush=True)


def esperar_seed():
    print("  aguardando o seed...", flush=True)
    inicio = time.monotonic()
    while time.monotonic() - inicio < TIMEOUT_SEED:
        resultado = subprocess.run(
            ["docker", "inspect", "lab_seed",
             "--format", "{{.State.Status}}|{{.State.ExitCode}}"],
            capture_output=True, text=True,
        )
        if resultado.returncode == 0:
            estado, codigo = resultado.stdout.strip().split("|")
            if estado == "exited":
                if codigo != "0":
                    comando(["docker", "compose", "logs", "seed"], mostrar=False)
                    raise RuntimeError(f"seed terminou com código {codigo}")
                print("  seed concluído", flush=True)
                return
        time.sleep(3)
    comando(["docker", "compose", "logs", "seed"], mostrar=False)
    raise RuntimeError("timeout aguardando o seed")


def esperar_etl():
    print("  aguardando o etl...", flush=True)
    inicio = time.monotonic()
    while time.monotonic() - inicio < TIMEOUT_ETL:
        resultado = subprocess.run(
            ["docker", "inspect", "lab_etl", "--format", "{{.State.Status}}"],
            capture_output=True, text=True,
        )
        if resultado.returncode == 0:
            estado = resultado.stdout.strip()
            if estado == "running":
                print("  etl disponível", flush=True)
                return
            if estado == "exited":
                raise RuntimeError("etl encerrou antes do pipeline")
        time.sleep(2)
    raise RuntimeError("timeout aguardando o etl")


def subir():
    print("== subida ==", flush=True)
    comando(["docker", "compose", "up", "-d", "--build"])
    esperar_seed()
    esperar_etl()


def executar_pipeline():
    print("== pipeline ==", flush=True)
    for nome, argumentos in PASSOS:
        print(f"-- {nome}", flush=True)
        inicio = time.monotonic()
        comando(["docker", "compose", "exec", "-T", "etl", "python", *argumentos])
        print(f"   {duracao(time.monotonic() - inicio)}", flush=True)


def verificar_restore(dump):
    print("  restaurando o dump...", flush=True)
    try:
        psql(f"DROP DATABASE IF EXISTS {RESTORE};", banco="postgres")
        comando(["docker", "compose", "exec", "-T", "pg_dw",
                 "createdb", "-U", "postgres", RESTORE], mostrar=False)
        dsn = f"postgresql://postgres:postgres@pg_dw:5432/{RESTORE}"
        if dump.suffix == ".gz":
            script = (f"gzip -dc /saida/{dump.name} | "
                      f"psql '{dsn}' -v ON_ERROR_STOP=1 -q -o /dev/null")
        else:
            script = (f"psql '{dsn}' -v ON_ERROR_STOP=1 -q -o /dev/null "
                      f"-f /saida/{dump.name}")
        comando(["docker", "compose", "exec", "-T", "etl", "sh", "-c", script],
                mostrar=False)
        pedidos = int(psql("SELECT count(*) FROM dw.fato_pedido;", banco=RESTORE))
        assercoes = int(psql("SELECT count(*) FROM qa.execucao_assercao;", banco=RESTORE))
        exigir(pedidos == 410000 and assercoes == 77,
               f"restore: {pedidos} pedidos, {assercoes} asserções")
    finally:
        psql(f"DROP DATABASE IF EXISTS {RESTORE};", banco="postgres")


def verificar():
    print("== verificação ==", flush=True)

    total, falhas = (int(x) for x in psql(
        "SELECT count(*) || '|' || count(*) FILTER (WHERE NOT aprovado) "
        "FROM qa.execucao_assercao;"
    ).split("|"))
    exigir(total == 77 and falhas == 0,
           f"qa.execucao_assercao: {total} asserções, {falhas} falhas")

    for tabela, esperado in CONTAGENS.items():
        obtido = int(psql(f"SELECT count(*) FROM {tabela};"))
        exigir(obtido == esperado, f"{tabela}: {obtido}")

    reconciliacao = SAIDA / "resumo_reconciliacao.csv"
    if not reconciliacao.exists():
        raise RuntimeError("saida/resumo_reconciliacao.csv não encontrado")
    with open(reconciliacao, encoding="utf-8") as arquivo:
        for linha in csv.DictReader(arquivo):
            desvio = abs(float(linha["desvio_pct"]))
            exigir(desvio < 0.1, f"{linha['sistema']}: desvio {desvio:.6f}%")

    rdt = RAIZ / "docs" / "RDT_semana3.md"
    if not rdt.exists():
        raise RuntimeError("docs/RDT_semana3.md não encontrado")
    texto_rdt = rdt.read_text(encoding="utf-8")
    for numero in range(10, 14):
        exigir(f"## Ficha RDT-{numero}" in texto_rdt, f"RDT-{numero} presente")

    dump = SAIDA / "dw_dump.sql.gz"
    if not dump.exists():
        dump = SAIDA / "dw_dump.sql"
    if not dump.exists():
        raise RuntimeError("dump SQL não encontrado")
    exigir(dump.stat().st_size > 0,
           f"dump {dump.name} ({dump.stat().st_size / 1024 / 1024:.1f} MB)")
    verificar_restore(dump)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    inicio = time.perf_counter()
    try:
        preparar()
        resetar()
        subir()
        executar_pipeline()
        verificar()
    except subprocess.CalledProcessError as erro:
        print(f"\nFALHOU: comando retornou {erro.returncode}", flush=True)
        return 1
    except RuntimeError as erro:
        print(f"\nFALHOU: {erro}", flush=True)
        return 1
    except KeyboardInterrupt:
        print("\nInterrompido.", flush=True)
        return 130
    print(f"\nReprodução concluída em {duracao(time.perf_counter() - inicio)}.",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
