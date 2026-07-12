"""Interface web mínima, local, sem dependências (stdlib http.server).

Uma única página que permite registrar uma compra e ver o relatório —
a prioridade do MVP. Roda só na sua máquina (127.0.0.1), sem deploy.

    python -m compracertia web
    # abre em http://127.0.0.1:8000
"""

from __future__ import annotations

import html
import http.server
import urllib.parse

from . import db, relatorio

_PAGINA = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CompraCertIA</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: system-ui, sans-serif; max-width: 820px; margin: 2rem auto;
         padding: 0 1rem; line-height: 1.5; }}
  h1 {{ margin-bottom: 0; }}
  p.sub {{ color: #666; margin-top: .25rem; }}
  form {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: .75rem 1rem;
          border: 1px solid #8884; border-radius: 8px; padding: 1rem; margin: 1rem 0; }}
  label {{ display: flex; flex-direction: column; font-size: .85rem; gap: .2rem; }}
  input, select {{ padding: .4rem; font-size: 1rem; }}
  .full {{ grid-column: 1 / -1; }}
  button {{ padding: .55rem 1rem; font-size: 1rem; border-radius: 6px;
            border: 1px solid #8886; cursor: pointer; }}
  .msg {{ padding: .6rem .8rem; border-radius: 6px; margin: 1rem 0; }}
  .ok {{ background: #1a7f3720; border: 1px solid #1a7f37; }}
  .err {{ background: #cf222e20; border: 1px solid #cf222e; }}
  pre {{ background: #8881; padding: 1rem; border-radius: 8px; overflow-x: auto;
         white-space: pre-wrap; word-break: break-word; }}
  small {{ color: #666; }}
</style>
</head>
<body>
<h1>CompraCertIA</h1>
<p class="sub">Registre uma compra e veja onde dá para economizar sem perder qualidade.</p>
{mensagem}
<form method="post" action="/registrar">
  <label>Item<input name="item" required placeholder="Café"></label>
  <label>Marca<input name="marca" required placeholder="Melitta"></label>
  <label>Preço total pago (R$)<input name="preco" type="number" step="0.01" min="0" required></label>
  <label>Quantidade (pacotes)<input name="quantidade" type="number" step="0.01" min="0" value="1"></label>
  <label>Unidade do pacote<input name="unidade" value="un" placeholder="500g, 1L, un"></label>
  <label>Data<input name="data" type="date"></label>
  <label class="full">Categoria <small>(só na 1ª compra do item)</small>
    <select name="categoria">
      <option value="">— manter a já cadastrada —</option>
      <option value="A">A — decisão técnica mensurável</option>
      <option value="B">B — preferência pessoal (nunca otimizado)</option>
    </select>
  </label>
  <div class="full"><button type="submit">Registrar compra</button></div>
</form>
<h2>Relatório</h2>
<pre>{relatorio}</pre>
</body>
</html>
"""


def _render(conn, mensagem_html: str = "") -> bytes:
    corpo = relatorio.gerar_relatorio(conn)
    pagina = _PAGINA.format(
        mensagem=mensagem_html,
        relatorio=html.escape(corpo),
    )
    return pagina.encode("utf-8")


def _msg(texto: str, classe: str) -> str:
    return f'<div class="msg {classe}">{html.escape(texto)}</div>'


class _Handler(http.server.BaseHTTPRequestHandler):
    # `caminho_db` é injetado via functools.partial em criar_servidor.
    caminho_db: str | None = None

    def _responder(self, corpo: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self) -> None:
        if urllib.parse.urlparse(self.path).path != "/":
            self._responder(b"Nao encontrado", status=404)
            return
        conn = db.conectar(self.caminho_db)
        try:
            self._responder(_render(conn))
        finally:
            conn.close()

    def do_POST(self) -> None:
        if urllib.parse.urlparse(self.path).path != "/registrar":
            self._responder(b"Nao encontrado", status=404)
            return
        tamanho = int(self.headers.get("Content-Length", 0))
        dados = urllib.parse.parse_qs(self.rfile.read(tamanho).decode("utf-8"))

        def campo(nome: str) -> str | None:
            valor = dados.get(nome, [""])[0].strip()
            return valor or None

        conn = db.conectar(self.caminho_db)
        try:
            preco = campo("preco")
            quantidade = campo("quantidade")
            db.registrar_compra(
                conn,
                item=campo("item") or "",
                marca=campo("marca") or "",
                preco=float(preco) if preco else 0,
                quantidade=float(quantidade) if quantidade else 1,
                unidade=campo("unidade") or "un",
                data=campo("data"),
                categoria=campo("categoria"),
            )
            item = campo("item")
            mensagem = _msg(f"Compra de {item} registrada.", "ok")
        except (ValueError, TypeError) as erro:
            mensagem = _msg(f"Não foi possível registrar: {erro}", "err")
        self._responder(_render(conn, mensagem))
        conn.close()

    def log_message(self, *args) -> None:  # silencia o log padrão no terminal
        pass


def criar_servidor(host: str, porta: int, caminho_db: str | None):
    _Handler.caminho_db = caminho_db  # compartilhado por todas as requisições
    return http.server.ThreadingHTTPServer((host, porta), _Handler)


def servir(host: str = "127.0.0.1", porta: int = 8000, caminho_db: str | None = None) -> None:
    servidor = criar_servidor(host, porta, caminho_db)
    print(f"CompraCertIA rodando em http://{host}:{porta}  (Ctrl+C para parar)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    finally:
        servidor.server_close()
