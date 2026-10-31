import os
import sys
import argparse

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


def main():
    parser = argparse.ArgumentParser(description="Testes do feed de noticias PUB/SUB")
    parser.add_argument("--port", type=int, default=5050, help="porta usada pelo servidor de teste")
    args = parser.parse_args()

    print(f"\n{acertos} ok, {erros} falha(s)")
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
