import os
import sys
import time
import socket
import argparse
import tempfile
import subprocess

# raiz do projeto, um nivel acima da pasta teste
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# deixa importar o NewsClient direto da pasta client
sys.path.insert(0, os.path.join(RAIZ, "client"))

from NewsClient import NewsClient

HOST = "127.0.0.1"

acertos = 0
erros = 0


def checar(descricao, condicao, detalhe=""):
    global acertos, erros
    if condicao:
        acertos += 1
        print(f"  [ok]    {descricao}")
    else:
        erros += 1
        print(f"  [falha] {descricao}")
        if detalhe:
            print(f"          recebido: {detalhe}")


def subir_servidor(porta, arquivo, log):
    # roda o servidor como modulo a partir da raiz, igual ao uso normal
    saida = open(log, "w", encoding="utf-8")
    processo = subprocess.Popen(
        [sys.executable, "-m", "server.NewsServer", "--host", HOST,
         "--port", str(porta), "--arquivo", arquivo],
        cwd=RAIZ, stdout=saida, stderr=subprocess.STDOUT)

    # espera a porta abrir ou o processo morrer
    limite = time.time() + 5
    while time.time() < limite:
        if processo.poll() is not None:
            print("[teste] o servidor encerrou antes de abrir a porta")
            return None
        try:
            socket.create_connection((HOST, porta), timeout=0.5).close()
            return processo
        except OSError:
            time.sleep(0.1)

    print("[teste] o servidor nao abriu a porta a tempo")
    processo.kill()
    return None


def derrubar_servidor(processo):
    processo.terminate()
    try:
        processo.wait(timeout=3)
    except subprocess.TimeoutExpired:
        processo.kill()


def mostrar_log(log):
    print("\n[teste] saida do servidor:")
    with open(log, encoding="utf-8") as f:
        print(f.read())


def main():
    parser = argparse.ArgumentParser(description="Testes do feed de noticias PUB/SUB")
    parser.add_argument("--port", type=int, default=5050, help="porta usada pelo servidor de teste")
    args = parser.parse_args()

    # arquivo de noticias e log ficam numa pasta temporaria, sem sujar o projeto
    pasta = tempfile.mkdtemp(prefix="feed_teste_")
    arquivo = os.path.join(pasta, "noticias.jsonl")
    log = os.path.join(pasta, "servidor.log")

    servidor = subir_servidor(args.port, arquivo, log)
    if servidor is None:
        mostrar_log(log)
        sys.exit(1)

    try:
        pass
    finally:
        derrubar_servidor(servidor)

    print(f"\n{acertos} ok, {erros} falha(s)")
    if erros:
        mostrar_log(log)
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
