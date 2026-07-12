"""Armazenamento local em SQLite.

Três tabelas:
  itens        — cada item conhecido, marcado como Categoria A ou B
  compras      — histórico de compras (entrada manual no MVP)
  alternativas — base de alternativas alimentada manualmente
                 (preço + atributos técnicos relevantes)
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date
from pathlib import Path

BANCO_PADRAO = "compras.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS itens (
    id        INTEGER PRIMARY KEY,
    nome      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    categoria TEXT NOT NULL CHECK (categoria IN ('A', 'B'))
);

CREATE TABLE IF NOT EXISTS compras (
    id         INTEGER PRIMARY KEY,
    item_id    INTEGER NOT NULL REFERENCES itens(id),
    marca      TEXT NOT NULL,
    preco      REAL NOT NULL CHECK (preco > 0),      -- total pago (R$)
    quantidade REAL NOT NULL CHECK (quantidade > 0), -- nº de pacotes/unidades
    unidade    TEXT NOT NULL DEFAULT 'un',           -- ex.: '500g', '1L', 'un'
    data       TEXT NOT NULL                          -- ISO: AAAA-MM-DD
);

CREATE TABLE IF NOT EXISTS alternativas (
    id        INTEGER PRIMARY KEY,
    item_id   INTEGER NOT NULL REFERENCES itens(id),
    marca     TEXT NOT NULL,
    preco     REAL NOT NULL CHECK (preco > 0),       -- preço por pacote/unidade (R$)
    unidade   TEXT NOT NULL DEFAULT 'un',
    atributos TEXT,                                   -- atributos técnicos relevantes
    UNIQUE (item_id, marca, unidade)
);

CREATE INDEX IF NOT EXISTS idx_compras_item ON compras(item_id);
CREATE INDEX IF NOT EXISTS idx_alternativas_item ON alternativas(item_id);
"""


def caminho_banco(caminho: str | None = None) -> Path:
    """Resolve o caminho do banco: argumento > variável de ambiente > padrão."""
    return Path(caminho or os.environ.get("COMPRACERTIA_DB", BANCO_PADRAO)).expanduser()


def conectar(caminho: str | None = None) -> sqlite3.Connection:
    destino = caminho_banco(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(destino)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    return conn


def buscar_item(conn: sqlite3.Connection, nome: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM itens WHERE nome = ? COLLATE NOCASE", (nome.strip(),)
    ).fetchone()


def obter_ou_criar_item(
    conn: sqlite3.Connection, nome: str, categoria: str | None
) -> sqlite3.Row:
    """Retorna o item existente ou cria um novo.

    A categoria só é exigida no primeiro registro do item; depois disso
    o valor armazenado prevalece, mantendo a marcação consistente.
    """
    item = buscar_item(conn, nome)
    if item is not None:
        return item
    if categoria not in ("A", "B"):
        raise ValueError(
            f"Item novo '{nome}': informe a categoria (A = decisão técnica "
            "mensurável; B = preferência pessoal, nunca otimizado)."
        )
    conn.execute(
        "INSERT INTO itens (nome, categoria) VALUES (?, ?)", (nome.strip(), categoria)
    )
    conn.commit()
    return buscar_item(conn, nome)


def registrar_compra(
    conn: sqlite3.Connection,
    item: str,
    marca: str,
    preco: float,
    quantidade: float,
    unidade: str = "un",
    data: str | None = None,
    categoria: str | None = None,
) -> int:
    linha = obter_ou_criar_item(conn, item, categoria)
    quando = date.fromisoformat(data) if data else date.today()
    cur = conn.execute(
        "INSERT INTO compras (item_id, marca, preco, quantidade, unidade, data)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (linha["id"], marca.strip(), preco, quantidade, unidade.strip(), quando.isoformat()),
    )
    conn.commit()
    return cur.lastrowid


def obter_compra(conn: sqlite3.Connection, compra_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT c.id, i.nome AS item, i.categoria, c.marca, c.preco,"
        "       c.quantidade, c.unidade, c.data"
        " FROM compras c JOIN itens i ON i.id = c.item_id"
        " WHERE c.id = ?",
        (compra_id,),
    ).fetchone()


# Campos de uma compra que podem ser corrigidos sem mexer no item/categoria.
_CAMPOS_EDITAVEIS = {"marca", "preco", "quantidade", "unidade", "data"}


def editar_compra(conn: sqlite3.Connection, compra_id: int, **campos) -> None:
    """Corrige campos de uma compra registrada errada.

    Só altera marca, preço, quantidade, unidade e data — trocar o item em si
    (e sua categoria) não é edição: remova a compra e registre de novo.
    Valores None são ignorados, então dá para atualizar só o que mudou.
    """
    if obter_compra(conn, compra_id) is None:
        raise ValueError(f"Compra #{compra_id} não existe.")
    mudancas = {c: v for c, v in campos.items() if v is not None}
    invalidos = set(mudancas) - _CAMPOS_EDITAVEIS
    if invalidos:
        raise ValueError(f"Campos que não podem ser editados: {', '.join(sorted(invalidos))}.")
    if not mudancas:
        raise ValueError("Informe pelo menos um campo para editar.")
    if "preco" in mudancas and mudancas["preco"] <= 0:
        raise ValueError("Preço deve ser maior que zero.")
    if "quantidade" in mudancas and mudancas["quantidade"] <= 0:
        raise ValueError("Quantidade deve ser maior que zero.")
    if "data" in mudancas:
        mudancas["data"] = date.fromisoformat(mudancas["data"]).isoformat()
    for texto in ("marca", "unidade"):
        if texto in mudancas:
            mudancas[texto] = mudancas[texto].strip()
    atribuicoes = ", ".join(f"{c} = ?" for c in mudancas)
    conn.execute(
        f"UPDATE compras SET {atribuicoes} WHERE id = ?",
        (*mudancas.values(), compra_id),
    )
    conn.commit()


def remover_compra(conn: sqlite3.Connection, compra_id: int) -> None:
    if obter_compra(conn, compra_id) is None:
        raise ValueError(f"Compra #{compra_id} não existe.")
    conn.execute("DELETE FROM compras WHERE id = ?", (compra_id,))
    conn.commit()


def registrar_alternativa(
    conn: sqlite3.Connection,
    item: str,
    marca: str,
    preco: float,
    unidade: str = "un",
    atributos: str | None = None,
) -> int:
    linha = buscar_item(conn, item)
    if linha is None:
        raise ValueError(
            f"Item '{item}' ainda não existe no histórico. Registre uma compra "
            "dele primeiro — alternativas só fazem sentido para itens que você compra."
        )
    if linha["categoria"] == "B":
        raise ValueError(
            f"'{item}' é Categoria B (preferência pessoal): o app não compara "
            "nem recomenda alternativas para esses itens."
        )
    cur = conn.execute(
        "INSERT INTO alternativas (item_id, marca, preco, unidade, atributos)"
        " VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT (item_id, marca, unidade) DO UPDATE SET"
        "   preco = excluded.preco, atributos = excluded.atributos",
        (linha["id"], marca.strip(), preco, unidade.strip(), atributos),
    )
    conn.commit()
    return cur.lastrowid


def listar_compras(conn: sqlite3.Connection, item: str | None = None) -> list[sqlite3.Row]:
    sql = (
        "SELECT c.id, i.nome AS item, i.categoria, c.marca, c.preco,"
        "       c.quantidade, c.unidade, c.data"
        " FROM compras c JOIN itens i ON i.id = c.item_id"
    )
    params: tuple = ()
    if item:
        sql += " WHERE i.nome = ? COLLATE NOCASE"
        params = (item.strip(),)
    sql += " ORDER BY c.data, c.id"
    return conn.execute(sql, params).fetchall()


def listar_itens(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT i.nome, i.categoria, COUNT(c.id) AS n_compras"
        " FROM itens i LEFT JOIN compras c ON c.item_id = i.id"
        " GROUP BY i.id ORDER BY i.nome"
    ).fetchall()


def listar_alternativas(
    conn: sqlite3.Connection, item: str | None = None
) -> list[sqlite3.Row]:
    sql = (
        "SELECT i.nome AS item, a.marca, a.preco, a.unidade, a.atributos"
        " FROM alternativas a JOIN itens i ON i.id = a.item_id"
    )
    params: tuple = ()
    if item:
        sql += " WHERE i.nome = ? COLLATE NOCASE"
        params = (item.strip(),)
    sql += " ORDER BY i.nome, a.preco"
    return conn.execute(sql, params).fetchall()
