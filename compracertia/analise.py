"""Análise do histórico: recorrência, comparação e economia anualizada.

Regras que não mudam:
  - Só itens de Categoria A recebem recomendação. Categoria B é
    preferência pessoal e fica de fora por princípio.
  - Toda recomendação carrega justificativa técnica explícita.
  - A decisão final é sempre do usuário: a saída é um sinal, não uma ação.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

# Uma compra repetida menos de 3 vezes ainda não é padrão.
MIN_COMPRAS_RECORRENCIA = 3
# Abaixo disso a anualização extrapola demais e o relatório avisa.
MIN_DIAS_HISTORICO = 30
DIAS_NO_ANO = 365


@dataclass
class Recorrencia:
    item: str
    categoria: str
    n_compras: int
    quantidade_total: float
    unidade: str  # unidade predominante nas compras do item
    preco_medio: float  # média ponderada por pacote/unidade (R$)
    primeira_data: date
    ultima_data: date

    @property
    def dias_historico(self) -> int:
        return (self.ultima_data - self.primeira_data).days

    @property
    def quantidade_anualizada(self) -> float:
        """Projeção de pacotes/ano com base na frequência real observada."""
        dias = max(self.dias_historico, 1)
        return self.quantidade_total * DIAS_NO_ANO / dias

    @property
    def historico_curto(self) -> bool:
        return self.dias_historico < MIN_DIAS_HISTORICO

    @property
    def gasto_anualizado(self) -> float:
        return self.quantidade_anualizada * self.preco_medio


@dataclass
class Recomendacao:
    recorrencia: Recorrencia
    marca_alternativa: str
    preco_alternativa: float
    atributos: str | None
    economia_anual: float

    @property
    def justificativa(self) -> str:
        r = self.recorrencia
        partes = [
            f"Você comprou {r.quantidade_total:g} pacote(s) de {r.item} "
            f"({r.unidade}) em {r.n_compras} compras entre "
            f"{r.primeira_data.strftime('%d/%m/%Y')} e {r.ultima_data.strftime('%d/%m/%Y')}, "
            f"pagando em média R$ {r.preco_medio:.2f} por pacote.",
            f"A alternativa {self.marca_alternativa} custa R$ {self.preco_alternativa:.2f} "
            f"na mesma unidade ({r.unidade}) — "
            f"R$ {r.preco_medio - self.preco_alternativa:.2f} a menos por pacote.",
            f"No seu ritmo real de consumo (~{r.quantidade_anualizada:.0f} pacotes/ano), "
            f"isso representa ~R$ {self.economia_anual:.2f}/ano.",
        ]
        if self.atributos:
            partes.append(f"Atributos técnicos da alternativa: {self.atributos}.")
        if r.historico_curto:
            partes.append(
                f"Atenção: histórico de apenas {r.dias_historico} dia(s) — "
                "a projeção anual ainda tem pouca base."
            )
        return " ".join(partes)


def identificar_recorrentes(
    conn: sqlite3.Connection, min_compras: int = MIN_COMPRAS_RECORRENCIA
) -> list[Recorrencia]:
    """Itens comprados repetidamente, com estatísticas na unidade predominante.

    Compras registradas em outra unidade do mesmo item não entram na média
    de preço, para nunca comparar R$/500g com R$/1kg.
    """
    linhas = conn.execute(
        """
        WITH unidade_top AS (
            SELECT item_id, unidade,
                   ROW_NUMBER() OVER (
                       PARTITION BY item_id
                       ORDER BY COUNT(*) DESC, unidade
                   ) AS pos
            FROM compras GROUP BY item_id, unidade
        )
        SELECT i.nome, i.categoria, c.unidade,
               COUNT(*)          AS n_compras,
               SUM(c.quantidade) AS quantidade_total,
               SUM(c.preco) / SUM(c.quantidade) AS preco_medio,
               MIN(c.data) AS primeira, MAX(c.data) AS ultima
        FROM compras c
        JOIN itens i ON i.id = c.item_id
        JOIN unidade_top u ON u.item_id = c.item_id
                          AND u.unidade = c.unidade AND u.pos = 1
        GROUP BY c.item_id
        HAVING n_compras >= ?
        ORDER BY SUM(c.preco) DESC
        """,
        (min_compras,),
    ).fetchall()
    return [
        Recorrencia(
            item=l["nome"],
            categoria=l["categoria"],
            n_compras=l["n_compras"],
            quantidade_total=l["quantidade_total"],
            unidade=l["unidade"],
            preco_medio=l["preco_medio"],
            primeira_data=date.fromisoformat(l["primeira"]),
            ultima_data=date.fromisoformat(l["ultima"]),
        )
        for l in linhas
    ]


def recomendar(conn: sqlite3.Connection, rec: Recorrencia) -> Recomendacao | None:
    """Melhor alternativa mais barata para um item recorrente de Categoria A.

    Retorna None quando não há o que recomendar: item de Categoria B,
    nenhuma alternativa cadastrada na mesma unidade, ou nenhuma mais
    barata que a média que o usuário já paga.
    """
    if rec.categoria != "A":
        return None
    alt = conn.execute(
        """
        SELECT a.marca, a.preco, a.atributos
        FROM alternativas a JOIN itens i ON i.id = a.item_id
        WHERE i.nome = ? COLLATE NOCASE AND a.unidade = ? AND a.preco < ?
        ORDER BY a.preco LIMIT 1
        """,
        (rec.item, rec.unidade, rec.preco_medio),
    ).fetchone()
    if alt is None:
        return None
    return Recomendacao(
        recorrencia=rec,
        marca_alternativa=alt["marca"],
        preco_alternativa=alt["preco"],
        atributos=alt["atributos"],
        economia_anual=(rec.preco_medio - alt["preco"]) * rec.quantidade_anualizada,
    )
