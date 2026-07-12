"""Acesso externo temporário via túnel Cloudflare (cloudflared).

Sobe a interface web local e a expõe numa URL pública provisória
(https://...trycloudflare.com), para testar no celular em qualquer lugar
(4G, fora de casa) sem deploy, sem conta e sem abrir portas no roteador.
Como o túnel é uma conexão de saída do PC, também contorna os casos em que
o acesso pela rede local (mesmo Wi-Fi) não funciona — firewall do PC ou
roteador isolando os dispositivos.

Requer o cloudflared instalado (binário externo, não é dependência Python):
  https://developers.cloudflare.com/cloudflare-tunnel/downloads/

    python -m compracertia compartilhar
"""

from __future__ import annotations

import re
import shutil
import subprocess
import threading

from . import web

# URL efêmera que o cloudflared imprime nos logs ao abrir um "quick tunnel".
URL_PUBLICA_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

_INSTRUCAO_INSTALAR = (
    "cloudflared não encontrado no PATH. Instale o Cloudflare Tunnel em "
    "https://developers.cloudflare.com/cloudflare-tunnel/downloads/ e rode de novo. "
    "(macOS: 'brew install cloudflared'; Windows: 'winget install "
    "Cloudflare.cloudflared'.)"
)


def _mostrar_qr_terminal(url: str) -> None:
    """Desenha um QR no terminal, se a lib opcional 'segno' estiver instalada."""
    try:
        import segno  # opcional: 'pip install segno' para escanear direto
    except ImportError:
        print("(Dica: 'pip install segno' desenha um QR aqui para escanear.)")
        return
    segno.make(url, error="m").terminal(compact=True)


def compartilhar(porta: int = 8000, caminho_db: str | None = None) -> None:
    """Sobe o servidor local numa thread e abre um túnel público via cloudflared."""
    if shutil.which("cloudflared") is None:
        raise RuntimeError(_INSTRUCAO_INSTALAR)

    servidor = web.criar_servidor("127.0.0.1", porta, caminho_db)
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    print(f"Servidor local em http://127.0.0.1:{porta}")
    print("Abrindo túnel público (pode levar alguns segundos)...\n")

    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{porta}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    ja_mostrada = False
    try:
        assert proc.stdout is not None
        for linha in proc.stdout:
            if not ja_mostrada:
                achada = URL_PUBLICA_RE.search(linha)
                if achada:
                    ja_mostrada = True
                    url = achada.group(0)
                    print("=" * 60)
                    print("URL pública (abra no celular, em qualquer rede):")
                    print(f"  {url}")
                    print("=" * 60)
                    _mostrar_qr_terminal(url)
                    print("\nCtrl+C para encerrar o compartilhamento.")
        proc.wait()
    except KeyboardInterrupt:
        print("\nEncerrando...")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        servidor.shutdown()
        servidor.server_close()
