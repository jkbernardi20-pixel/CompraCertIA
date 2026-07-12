"""Importação de compras em lote a partir de um arquivo CSV.

Colunas reconhecidas (cabeçalho obrigatório, ordem livre):
  item, marca, preco, quantidade, unidade, data, categoria

Só 'item', 'marca' e 'preco' são obrigatórios em cada linha. As demais
seguem os mesmos padrões do registro manual: quantidade=1, unidade='un',
data=hoje. A 'categoria' (A/B) só é necessária na primeira vez que um
item aparece — depois o banco já a conhece.
"""

from __future__ import annotations

import csv
import io
import sqlite3
from dataclasses import dataclass, field

from . import db

COLUNAS_OBRIGATORIAS = {"item", "marca", "preco"}
_COLUNAS_CONHECIDAS = {
    "item", "marca", "preco", "quantidade", "unidade", "data", "categoria",
}


@dataclass
class ResultadoImportacao:
    importadas: int = 0
    erros: list[tuple[int, str]] = field(default_factory=list)  # (linha, motivo)

    @property
    def total_erros(self) -> int:
        return len(self.erros)


def _valor(bruto: str | None) -> str | None:
    """Normaliza uma célula: espaços aparados; vazio vira None (usa padrão)."""
    if bruto is None:
        return None
    limpo = bruto.strip()
    return limpo or None


def importar_csv(conn: sqlite3.Connection, texto: str) -> ResultadoImportacao:
    """Importa compras de um CSV em memória, linha a linha.

    Cada linha é registrada em sua própria transação: uma linha inválida é
    anotada em `erros` (com o número da linha no arquivo) e não impede as
    demais. O cabeçalho conta como linha 1.
    """
    leitor = csv.DictReader(io.StringIO(texto))
    if leitor.fieldnames is None:
        raise ValueError("CSV vazio: esperado um cabeçalho com as colunas.")
    cabecalho = {c.strip().lower() for c in leitor.fieldnames}
    faltando = COLUNAS_OBRIGATORIAS - cabecalho
    if faltando:
        raise ValueError(
            "CSV sem as colunas obrigatórias: " + ", ".join(sorted(faltando)) + "."
        )
    desconhecidas = cabecalho - _COLUNAS_CONHECIDAS
    if desconhecidas:
        raise ValueError(
            "Colunas não reconhecidas no CSV: " + ", ".join(sorted(desconhecidas)) + "."
        )

    resultado = ResultadoImportacao()
    for n, bruto in enumerate(leitor, start=2):  # linha 1 é o cabeçalho
        linha = {(c or "").strip().lower(): v for c, v in bruto.items()}
        try:
            item = _valor(linha.get("item"))
            marca = _valor(linha.get("marca"))
            preco = _valor(linha.get("preco"))
            if not item or not marca or preco is None:
                raise ValueError("faltam campos obrigatórios (item, marca, preco).")
            quantidade = _valor(linha.get("quantidade"))
            db.registrar_compra(
                conn,
                item=item,
                marca=marca,
                preco=float(preco),
                quantidade=float(quantidade) if quantidade is not None else 1,
                unidade=_valor(linha.get("unidade")) or "un",
                data=_valor(linha.get("data")),
                categoria=_valor(linha.get("categoria")),
            )
            resultado.importadas += 1
        except (ValueError, TypeError, AttributeError, sqlite3.IntegrityError) as erro:
            resultado.erros.append((n, str(erro) or type(erro).__name__))
    return resultado
