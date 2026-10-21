# compat_macos.py
# Contorno para o Python nativo do macOS, cujo LibreSSL 2.8.3 não fala TLS 1.3.
#
# Quando o Overpass ou o Nominatim recusam o handshake antigo, a requisição é
# refeita com o /usr/bin/curl do sistema. O contorno só é instalado nesse
# ambiente específico: em Linux, Windows ou Python com OpenSSL nada muda.
import shutil
import ssl
import subprocess
import sys

import requests

_instalado = False


def precisa_do_contorno():
    """True apenas no macOS com Python linkado ao LibreSSL."""
    return sys.platform == "darwin" and "LibreSSL" in ssl.OPENSSL_VERSION


def instalar_fallback_curl(forcar=False):
    """Instala o fallback em requests.Session.send. Retorna True se instalou."""
    global _instalado
    if _instalado or not (forcar or precisa_do_contorno()):
        return False

    envio_original = requests.Session.send

    def envio_com_fallback(self, request, **kwargs):
        try:
            return envio_original(self, request, **kwargs)
        except requests.exceptions.SSLError:
            return _enviar_com_curl(request, kwargs.get("timeout"))

    requests.Session.send = envio_com_fallback
    _instalado = True
    return True


def _enviar_com_curl(request, timeout):
    if isinstance(timeout, tuple):
        timeout = max(timeout)
    timeout = int(timeout or 180)

    curl_bin = shutil.which("curl") or "/usr/bin/curl"
    cmd = [curl_bin, "-sS", "-L", "-m", str(timeout), "-w", "\n%{http_code}", "-X", request.method]
    for chave, valor in (request.headers or {}).items():
        if chave.lower() == "accept-encoding":
            continue
        cmd.extend(["-H", f"{chave}: {valor}"])
    if request.body:
        corpo = request.body.decode("utf-8") if isinstance(request.body, bytes) else str(request.body)
        cmd.extend(["--data-raw", corpo])
    cmd.append(request.url)

    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise requests.exceptions.SSLError(
            f"curl falhou (código {proc.returncode}): {proc.stderr.decode('utf-8', 'replace').strip()}"
        )

    partes = proc.stdout.rsplit(b"\n", 1)
    corpo = partes[0] if len(partes) == 2 else proc.stdout
    status = partes[1].strip() if len(partes) == 2 else b"200"

    resposta = requests.Response()
    resposta.status_code = int(status) if status.isdigit() else 200
    resposta.reason = "OK" if 200 <= resposta.status_code < 400 else "Error"
    resposta._content = corpo
    resposta.encoding = "utf-8"
    resposta.url = request.url
    resposta.request = request
    return resposta
