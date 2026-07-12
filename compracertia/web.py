"""Interface web mínima, local, sem dependências (stdlib http.server).

Uma única página que permite registrar uma compra e ver o relatório —
a prioridade do MVP. Sem deploy.

    python -m compracertia web
    # abre em http://127.0.0.1:8000

Para testar no celular (mesmo Wi-Fi), rode com --host 0.0.0.0: o servidor
detecta e imprime o endereço da máquina na rede local para abrir no navegador
do telefone.

A página inclui leitura de código de barras pela câmera (BarcodeDetector do
navegador) que preenche o produto a partir da memória pessoal de códigos. A
câmera exige conexão segura (https): funciona no modo 'compartilhar' (túnel)
ou em localhost, mas não no endereço http da rede local — por isso há também
um campo para digitar o código manualmente.
"""

from __future__ import annotations

import html
import http.server
import json
import socket
import urllib.parse

from . import db, relatorio

# Placeholders trocados por str.replace (não .format) para não conflitar com
# as chaves do CSS/JavaScript embutidos.
_PAGINA = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CompraCertIA</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, sans-serif; max-width: 820px; margin: 2rem auto;
         padding: 0 1rem; line-height: 1.5; }
  h1 { margin-bottom: 0; }
  p.sub { color: #666; margin-top: .25rem; }
  form { display: grid; grid-template-columns: repeat(2, 1fr); gap: .75rem 1rem;
          border: 1px solid #8884; border-radius: 8px; padding: 1rem; margin: 1rem 0; }
  label { display: flex; flex-direction: column; font-size: .85rem; gap: .2rem; }
  input, select { padding: .4rem; font-size: 1rem; }
  .full { grid-column: 1 / -1; }
  button { padding: .55rem 1rem; font-size: 1rem; border-radius: 6px;
            border: 1px solid #8886; cursor: pointer; background: #8881; }
  .msg { padding: .6rem .8rem; border-radius: 6px; margin: 1rem 0; }
  .ok { background: #1a7f3720; border: 1px solid #1a7f37; }
  .err { background: #cf222e20; border: 1px solid #cf222e; }
  pre { background: #8881; padding: 1rem; border-radius: 8px; overflow-x: auto;
         white-space: pre-wrap; word-break: break-word; }
  small { color: #666; }
  .scan { border: 1px dashed #8886; border-radius: 8px; padding: 1rem; margin: 1rem 0; }
  .scan-linha { display: flex; gap: .5rem; flex-wrap: wrap; align-items: center; }
  #video { width: 100%; max-width: 420px; border-radius: 8px; margin-top: .75rem;
           display: block; background: #0003; }
  #scan-status { margin: .5rem 0 0; min-height: 1.2em; }
</style>
</head>
<body>
<h1>CompraCertIA</h1>
<p class="sub">Registre uma compra e veja onde dá para economizar sem perder qualidade.</p>
%%MENSAGEM%%

<div class="scan">
  <div class="scan-linha">
    <button type="button" id="btn-scan">📷 Escanear código de barras</button>
    <button type="button" id="btn-parar" hidden>Parar</button>
    <span class="sub">ou digite:</span>
    <input id="codigo-manual" inputmode="numeric" placeholder="código de barras"
           style="max-width:170px">
    <button type="button" id="btn-buscar">Buscar</button>
  </div>
  <video id="video" playsinline hidden></video>
  <p id="scan-status" class="sub"></p>
</div>

<form method="post" action="/registrar">
  <input type="hidden" name="codigo" id="codigo">
  <label>Item<input name="item" id="item" required placeholder="Café"></label>
  <label>Marca<input name="marca" id="marca" required placeholder="Melitta"></label>
  <label>Preço total pago (R$)<input name="preco" type="number" step="0.01" min="0" required></label>
  <label>Quantidade (pacotes)<input name="quantidade" type="number" step="0.01" min="0" value="1"></label>
  <label>Unidade do pacote<input name="unidade" id="unidade" value="un" placeholder="500g, 1L, un"></label>
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
<pre>%%RELATORIO%%</pre>
<script>
(function () {
  const status = document.getElementById('scan-status');
  const btnScan = document.getElementById('btn-scan');
  const btnParar = document.getElementById('btn-parar');
  const btnBuscar = document.getElementById('btn-buscar');
  const video = document.getElementById('video');
  const temDetector = ('BarcodeDetector' in window);
  let stream = null, escaneando = false;

  if (!temDetector) {
    btnScan.disabled = true;
    status.textContent = 'Este navegador não lê código de barras pela câmera. ' +
      'Digite o código na caixa ao lado (funciona igual).';
  }

  function preencher(codigo, dados) {
    document.getElementById('codigo').value = codigo;
    if (dados && dados.conhecido) {
      document.getElementById('item').value = dados.item || '';
      document.getElementById('marca').value = dados.marca || '';
      document.getElementById('unidade').value = dados.unidade || 'un';
      status.textContent = 'Reconhecido: ' + dados.item + ' (' + dados.marca +
        '). Confira e informe o preço.';
    } else {
      status.textContent = 'Código novo (' + codigo + '). Digite o nome e a marca ' +
        'uma vez — o app vai memorizar para as próximas.';
      document.getElementById('item').focus();
    }
  }

  async function consultar(codigo) {
    try {
      const r = await fetch('/codigo?valor=' + encodeURIComponent(codigo));
      preencher(codigo, await r.json());
    } catch (e) {
      preencher(codigo, null);
    }
  }

  function parar() {
    escaneando = false;
    if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
    video.hidden = true;
    btnParar.hidden = true;
  }

  async function loop(detector) {
    if (!escaneando) return;
    try {
      const codes = await detector.detect(video);
      if (codes.length) {
        const codigo = codes[0].rawValue;
        parar();
        consultar(codigo);
        return;
      }
    } catch (e) { /* quadro sem código; segue tentando */ }
    requestAnimationFrame(() => loop(detector));
  }

  btnScan.addEventListener('click', async () => {
    if (!window.isSecureContext) {
      status.textContent = 'A câmera só funciona em conexão segura (https). ' +
        'Use o modo "compartilhar" para um endereço https, ou digite o código ao lado.';
      return;
    }
    try {
      const detector = new BarcodeDetector(
        { formats: ['ean_13', 'ean_8', 'upc_a', 'upc_e'] });
      stream = await navigator.mediaDevices.getUserMedia(
        { video: { facingMode: 'environment' } });
      video.srcObject = stream;
      video.hidden = false;
      btnParar.hidden = false;
      await video.play();
      escaneando = true;
      status.textContent = 'Aponte para o código de barras...';
      loop(detector);
    } catch (e) {
      status.textContent = 'Não consegui abrir a câmera: ' + e.message +
        '. Você pode digitar o código ao lado.';
    }
  });

  btnParar.addEventListener('click', parar);
  btnBuscar.addEventListener('click', () => {
    const codigo = document.getElementById('codigo-manual').value.trim();
    if (codigo) consultar(codigo);
  });
})();
</script>
</body>
</html>
"""


def _render(conn, mensagem_html: str = "") -> bytes:
    corpo = html.escape(relatorio.gerar_relatorio(conn))
    pagina = _PAGINA.replace("%%MENSAGEM%%", mensagem_html).replace(
        "%%RELATORIO%%", corpo
    )
    return pagina.encode("utf-8")


def _msg(texto: str, classe: str) -> str:
    return f'<div class="msg {classe}">{html.escape(texto)}</div>'


class _Handler(http.server.BaseHTTPRequestHandler):
    # `caminho_db` é injetado via functools.partial em criar_servidor.
    caminho_db: str | None = None

    def _responder(self, corpo: bytes, status: int = 200,
                   tipo: str = "text/html; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _responder_json(self, dados: dict, status: int = 200) -> None:
        corpo = json.dumps(dados).encode("utf-8")
        self._responder(corpo, status=status, tipo="application/json; charset=utf-8")

    def do_GET(self) -> None:
        partes = urllib.parse.urlparse(self.path)
        if partes.path == "/codigo":
            self._responder_codigo(partes.query)
            return
        if partes.path != "/":
            self._responder(b"Nao encontrado", status=404)
            return
        conn = db.conectar(self.caminho_db)
        try:
            self._responder(_render(conn))
        finally:
            conn.close()

    def _responder_codigo(self, query: str) -> None:
        """Consulta a memória de códigos de barras e devolve JSON para a câmera."""
        valor = (urllib.parse.parse_qs(query).get("valor", [""])[0]).strip()
        if not valor:
            self._responder_json({"conhecido": False})
            return
        conn = db.conectar(self.caminho_db)
        try:
            linha = db.buscar_codigo(conn, valor)
        finally:
            conn.close()
        if linha is None:
            self._responder_json({"conhecido": False, "codigo": valor})
            return
        self._responder_json({
            "conhecido": True,
            "codigo": valor,
            "item": linha["item"],
            "marca": linha["marca"],
            "unidade": linha["unidade"],
            "categoria": linha["categoria"],
        })

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
            codigo = campo("codigo")
            db.registrar_compra(
                conn,
                item=campo("item") or "",
                marca=campo("marca") or "",
                preco=float(preco) if preco else 0,
                quantidade=float(quantidade) if quantidade else 1,
                unidade=campo("unidade") or "un",
                data=campo("data"),
                categoria=campo("categoria"),
                codigo=codigo,
            )
            item = campo("item")
            extra = " Código de barras memorizado." if codigo else ""
            mensagem = _msg(f"Compra de {item} registrada.{extra}", "ok")
        except (ValueError, TypeError) as erro:
            mensagem = _msg(f"Não foi possível registrar: {erro}", "err")
        self._responder(_render(conn, mensagem))
        conn.close()

    def log_message(self, *args) -> None:  # silencia o log padrão no terminal
        pass


def criar_servidor(host: str, porta: int, caminho_db: str | None):
    _Handler.caminho_db = caminho_db  # compartilhado por todas as requisições
    return http.server.ThreadingHTTPServer((host, porta), _Handler)


def _ip_lan() -> str | None:
    """Descobre o IP da máquina na rede local, para acesso pelo celular.

    Não envia nada — só usa um socket UDP para saber qual interface o SO
    escolheria para sair à rede, e lê o IP dessa interface.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def servir(host: str = "127.0.0.1", porta: int = 8000, caminho_db: str | None = None) -> None:
    servidor = criar_servidor(host, porta, caminho_db)
    print("CompraCertIA rodando  (Ctrl+C para parar)")
    print(f"  Neste computador:  http://127.0.0.1:{porta}")
    if host in ("0.0.0.0", "::"):
        ip = _ip_lan()
        if ip:
            print(f"  No celular (mesmo Wi-Fi):  http://{ip}:{porta}")
        else:
            print("  No celular: use o IP deste computador na rede local.")
    else:
        print(
            "  Para abrir no celular, reinicie com --host 0.0.0.0 "
            "(expõe o app na sua rede local)."
        )
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    finally:
        servidor.server_close()
