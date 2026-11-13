#!/usr/bin/env python3
"""Gera os gráficos de contribuição (SVG) usados no README de perfil.

Os dados vêm da página pública de contribuições do GitHub, que já inclui as
contribuições privadas de forma agregada. O script não usa dependências
externas e é executado diariamente pelo GitHub Actions.
"""

from __future__ import annotations

import os
import re
import sys
import urllib.request
from datetime import date, timedelta

USUARIO = os.environ.get("GH_USER", "JS171555")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "assets")

MESES = [
    "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
]

# Geometria do gráfico
CELULA = 11
ESPACO = 3
PASSO = CELULA + ESPACO
MARGEM_ESQ = 32
MARGEM_TOPO = 20
MARGEM_DIR = 8
MARGEM_BASE = 42

FONTE = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', "
    "Helvetica, Arial, sans-serif"
)

TEMAS = {
    "claro": {
        "cores": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "texto": "#57606a",
    },
    "escuro": {
        "cores": ["#21262d", "#0e4429", "#006d32", "#26a641", "#39d353"],
        "texto": "#8b949e",
    },
}


def baixar(url: str) -> str:
    pedido = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; perfil-readme/1.0)",
            "Accept": "text/html",
        },
    )
    with urllib.request.urlopen(pedido, timeout=45) as resposta:
        return resposta.read().decode("utf-8", "replace")


def extrair_dias(html: str) -> list[dict]:
    """Lê data, nível e quantidade de cada célula do calendário."""
    dias = []
    padrao = re.compile(
        r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*?data-level="([0-4])"(.*?)'
        r'(?=data-date="|\Z)',
        re.S,
    )
    for achado in padrao.finditer(html):
        dia, nivel, resto = achado.group(1), int(achado.group(2)), achado.group(3)
        quantidade = 0
        tooltip = re.search(r"<tool-tip[^>]*>(.*?)</tool-tip>", resto, re.S)
        if tooltip:
            texto = " ".join(tooltip.group(1).split())
            numero = re.match(r"(No|\d+)\s+contribution", texto)
            if numero:
                quantidade = 0 if numero.group(1) == "No" else int(numero.group(1))
        dias.append(
            {"data": date.fromisoformat(dia), "nivel": nivel, "total": quantidade}
        )
    return dias


def montar_semanas(dias: list[dict]) -> list[list[dict | None]]:
    """Agrupa os dias em colunas de domingo a sábado."""
    por_data = {dia["data"]: dia for dia in dias}
    inicio = min(por_data)
    inicio -= timedelta(days=inicio.isoweekday() % 7)  # volta para domingo
    fim = max(por_data)

    semanas = []
    atual = inicio
    while atual <= fim:
        semanas.append(
            [por_data.get(atual + timedelta(days=i)) for i in range(7)]
        )
        atual += timedelta(days=7)
    return semanas


def gerar_svg(semanas: list[list[dict | None]], total: int, tema: str) -> str:
    cores = TEMAS[tema]["cores"]
    texto = TEMAS[tema]["texto"]

    largura_grade = len(semanas) * PASSO - ESPACO
    altura_grade = 7 * PASSO - ESPACO
    largura = MARGEM_ESQ + largura_grade + MARGEM_DIR
    altura = MARGEM_TOPO + altura_grade + MARGEM_BASE

    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" '
        f'height="{altura}" viewBox="0 0 {largura} {altura}" role="img" '
        f'font-family="{FONTE}" font-size="10">',
        f"<title>{total} contribuições no último ano</title>",
        "<g>",
    ]

    # Rótulos dos meses
    ultimo_mes = None
    ultima_semana = -10
    for indice, semana in enumerate(semanas):
        dias = [d for d in semana if d]
        if not dias:
            continue
        mes = dias[0]["data"].month
        if mes != ultimo_mes and indice - ultima_semana >= 3:
            x = MARGEM_ESQ + indice * PASSO
            partes.append(
                f'<text x="{x}" y="{MARGEM_TOPO - 7}" fill="{texto}">'
                f"{MESES[mes - 1]}</text>"
            )
            ultimo_mes = mes
            ultima_semana = indice

    # Rótulos dos dias da semana
    for linha, rotulo in ((1, "seg"), (3, "qua"), (5, "sex")):
        y = MARGEM_TOPO + linha * PASSO + CELULA - 2
        partes.append(
            f'<text x="{MARGEM_ESQ - 6}" y="{y}" fill="{texto}" '
            f'text-anchor="end">{rotulo}</text>'
        )

    # Células
    partes.append("<g>")
    for coluna, semana in enumerate(semanas):
        for linha, dia in enumerate(semana):
            if not dia:
                continue
            x = MARGEM_ESQ + coluna * PASSO
            y = MARGEM_TOPO + linha * PASSO
            partes.append(
                f'<rect x="{x}" y="{y}" width="{CELULA}" height="{CELULA}" '
                f'rx="2" fill="{cores[dia["nivel"]]}"/>'
            )
    partes.append("</g>")

    # Legenda e total
    base_texto = MARGEM_TOPO + altura_grade + 26
    partes.append(
        f'<text x="2" y="{base_texto}" fill="{texto}" font-size="12">'
        f"<tspan font-weight=\"600\">{total}</tspan> contribuições no último ano"
        "</text>"
    )

    lado = 9
    passo_legenda = lado + 3
    x_mais = largura - MARGEM_DIR
    x_fim_quadrados = x_mais - 24
    x_quadrados = x_fim_quadrados - (4 * passo_legenda + lado)
    partes.append(
        f'<text x="{x_quadrados - 8}" y="{base_texto}" fill="{texto}" '
        f'text-anchor="end">menos</text>'
    )
    for nivel in range(5):
        partes.append(
            f'<rect x="{x_quadrados + nivel * passo_legenda}" '
            f'y="{base_texto - lado + 1}" width="{lado}" height="{lado}" '
            f'rx="2" fill="{cores[nivel]}"/>'
        )
    partes.append(
        f'<text x="{x_mais}" y="{base_texto}" fill="{texto}" '
        f'text-anchor="end">mais</text>'
    )

    partes.append("</g></svg>")
    return "".join(partes)


def main() -> int:
    html = baixar(f"https://github.com/users/{USUARIO}/contributions")
    dias = extrair_dias(html)

    if len(dias) < 300:
        print(
            f"Erro: apenas {len(dias)} dias encontrados no calendário.",
            file=sys.stderr,
        )
        return 1

    total = sum(dia["total"] for dia in dias)
    semanas = montar_semanas(dias)

    os.makedirs(SAIDA, exist_ok=True)
    for tema in TEMAS:
        caminho = os.path.join(SAIDA, f"contribuicoes-{tema}.svg")
        with open(caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write(gerar_svg(semanas, total, tema))
        print(f"Gerado: {caminho}")

    print(f"{total} contribuições em {len(semanas)} semanas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
