"""Interface de linha de comando.

Uso rápido:
  python -m compracertia registrar --item Café --marca Melitta \
      --preco 37.80 --quantidade 2 --unidade 500g --categoria A
  python -m compracertia alternativa --item Café --marca "Três Corações" \
      --preco 15.90 --unidade 500g --atributos "100% arábica, torra média"
  python -m compracertia relatorio
"""

from __future__ import annotations

import argparse
import sys

from . import db, relatorio


def _construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="compracertia",
        description="Registra compras de supermercado e sinaliza onde uma "
        "decisão diferente economizaria sem perda de qualidade.",
    )
    parser.add_argument(
        "--db",
        help="caminho do banco SQLite (padrão: $COMPRACERTIA_DB ou ./compras.db)",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("registrar", help="registrar uma compra")
    p.add_argument("--item", required=True, help="nome genérico do produto (ex.: Café)")
    p.add_argument("--marca", required=True)
    p.add_argument("--preco", type=float, required=True, help="total pago, em R$")
    p.add_argument(
        "--quantidade", type=float, default=1, help="nº de pacotes/unidades (padrão: 1)"
    )
    p.add_argument(
        "--unidade", default="un", help="tamanho do pacote (ex.: 500g, 1L; padrão: un)"
    )
    p.add_argument("--data", help="AAAA-MM-DD (padrão: hoje)")
    p.add_argument(
        "--categoria",
        choices=["A", "B"],
        help="obrigatório só na 1ª compra do item: A = decisão técnica "
        "mensurável; B = preferência pessoal (nunca otimizado)",
    )

    p = sub.add_parser(
        "alternativa", help="cadastrar alternativa para comparação (só Categoria A)"
    )
    p.add_argument("--item", required=True)
    p.add_argument("--marca", required=True)
    p.add_argument("--preco", type=float, required=True, help="preço por pacote, em R$")
    p.add_argument("--unidade", default="un", help="deve bater com a unidade das compras")
    p.add_argument("--atributos", help="atributos técnicos relevantes (justificativa)")

    sub.add_parser("relatorio", help="gerar o relatório de recorrências e economia")

    p = sub.add_parser("compras", help="listar compras registradas")
    p.add_argument("--item", help="filtrar por item")

    sub.add_parser("itens", help="listar itens e categorias")

    p = sub.add_parser("alternativas", help="listar alternativas cadastradas")
    p.add_argument("--item", help="filtrar por item")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _construir_parser().parse_args(argv)
    conn = db.conectar(args.db)
    try:
        if args.comando == "registrar":
            db.registrar_compra(
                conn,
                item=args.item,
                marca=args.marca,
                preco=args.preco,
                quantidade=args.quantidade,
                unidade=args.unidade,
                data=args.data,
                categoria=args.categoria,
            )
            print(
                f"Compra registrada: {args.quantidade:g}x {args.item} "
                f"({args.unidade}) {args.marca} — R$ {args.preco:.2f}"
            )
        elif args.comando == "alternativa":
            db.registrar_alternativa(
                conn,
                item=args.item,
                marca=args.marca,
                preco=args.preco,
                unidade=args.unidade,
                atributos=args.atributos,
            )
            print(
                f"Alternativa cadastrada para {args.item}: {args.marca} "
                f"({args.unidade}) — R$ {args.preco:.2f}"
            )
        elif args.comando == "relatorio":
            print(relatorio.gerar_relatorio(conn))
        elif args.comando == "compras":
            linhas = db.listar_compras(conn, args.item)
            if not linhas:
                print("Nenhuma compra registrada.")
            for c in linhas:
                print(
                    f"{c['data']}  {c['item']} [{c['categoria']}]  "
                    f"{c['quantidade']:g}x {c['unidade']}  {c['marca']}  "
                    f"R$ {c['preco']:.2f}"
                )
        elif args.comando == "itens":
            linhas = db.listar_itens(conn)
            if not linhas:
                print("Nenhum item cadastrado.")
            for i in linhas:
                print(f"{i['nome']} [{i['categoria']}] — {i['n_compras']} compra(s)")
        elif args.comando == "alternativas":
            linhas = db.listar_alternativas(conn, args.item)
            if not linhas:
                print("Nenhuma alternativa cadastrada.")
            for a in linhas:
                extra = f" — {a['atributos']}" if a["atributos"] else ""
                print(f"{a['item']}: {a['marca']} ({a['unidade']}) R$ {a['preco']:.2f}{extra}")
    except ValueError as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
