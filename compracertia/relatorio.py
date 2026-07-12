"""Geração do relatório em texto: recorrências, recomendações e economia."""

from __future__ import annotations

import sqlite3
from datetime import date

from . import analise

_LARGURA = 72


def _titulo(texto: str) -> str:
    return f"\n{texto}\n{'-' * len(texto)}"


def gerar_relatorio(conn: sqlite3.Connection, hoje: date | None = None) -> str:
    """Monta o relatório sob demanda a partir do histórico completo."""
    hoje = hoje or date.today()
    recorrentes = analise.identificar_recorrentes(conn)
    linhas: list[str] = [
        "=" * _LARGURA,
        f"CompraCertIA — Relatório de recorrências e economia  ({hoje.strftime('%d/%m/%Y')})",
        "=" * _LARGURA,
    ]

    if not recorrentes:
        linhas += [
            "",
            f"Nenhum item recorrente ainda (mínimo: {analise.MIN_COMPRAS_RECORRENCIA} "
            "compras do mesmo item).",
            "Continue registrando as compras — o padrão aparece com o tempo.",
        ]
        return "\n".join(linhas)

    recomendacoes: list[analise.Recomendacao] = []
    sem_recomendacao: list[analise.Recorrencia] = []
    categoria_b: list[analise.Recorrencia] = []
    for rec in recorrentes:
        if rec.categoria == "B":
            categoria_b.append(rec)
            continue
        r = analise.recomendar(conn, rec)
        if r is not None:
            recomendacoes.append(r)
        else:
            sem_recomendacao.append(rec)

    linhas.append(_titulo("Onde dá para economizar (Categoria A)"))
    if recomendacoes:
        total = 0.0
        for n, r in enumerate(recomendacoes, 1):
            rec = r.recorrencia
            total += r.economia_anual
            linhas += [
                "",
                f"{n}. {rec.item} ({rec.unidade}) — economia estimada: "
                f"R$ {r.economia_anual:.2f}/ano",
                f"   Recomendação: experimentar {r.marca_alternativa} "
                f"(R$ {r.preco_alternativa:.2f} vs. média atual de R$ {rec.preco_medio:.2f})",
                f"   Justificativa: {r.justificativa}",
            ]
        linhas += [
            "",
            f"Economia potencial total: ~R$ {total:.2f}/ano.",
            "A decisão é sempre sua — o app só sinaliza; nada aqui envolve "
            "comissão ou interesse comercial.",
        ]
    else:
        linhas += ["", "Nenhuma oportunidade identificada com os dados atuais."]

    if sem_recomendacao:
        linhas.append(_titulo("Recorrentes sem recomendação (Categoria A)"))
        for rec in sem_recomendacao:
            linhas += [
                "",
                f"- {rec.item} ({rec.unidade}): {rec.n_compras} compras, "
                f"gasto projetado de R$ {rec.gasto_anualizado:.2f}/ano.",
                "  Sem alternativa cadastrada mais barata na mesma unidade. "
                "Cadastre alternativas com 'alternativa' para habilitar a comparação.",
            ]

    if categoria_b:
        linhas.append(_titulo("Categoria B — fora da otimização, por princípio"))
        for rec in categoria_b:
            linhas.append(
                f"- {rec.item}: recorrente ({rec.n_compras} compras), mas é "
                "preferência pessoal — o app não recomenda troca."
            )

    return "\n".join(linhas)
