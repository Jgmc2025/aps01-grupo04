

import argparse
import itertools
import time
from NewsClient import NewsClient


SAMPLE_NEWS = [
    ("tecnologia", "Nova versao do kernel Linux lancada", "Release traz melhorias de desempenho e drivers."),
    ("esportes", "Sport vence o classico pernambucano", "Partida terminou 2x1 na Ilha do Retiro."),
    ("cultura", "Festival de cinema abre inscricoes", "Mostra recebe filmes ate o fim do mes."),
    ("tecnologia", "Pesquisadores apresentam novo protocolo de rede", "Proposta reduz latencia em redes moveis."),
    ("esportes", "Selecao feminina convoca nova lista", "Treinos comecam na proxima semana."),
    ("cultura", "Recife recebe exposicao de arte popular", "Entrada gratuita durante todo o mes."),
]


def main():
    parser = argparse.ArgumentParser(description="Publicador de notícias no feed PUB/SUB")
    parser.add_argument("--host", default="127.0.0.1", help="IP do servidor TCP")
    parser.add_argument("--port", type=int, default=5000, help="Porta TCP do servidor")
    parser.add_argument("--auto", action="store_true", help="Ativa modo de envio automático")
    parser.add_argument("--intervalo", type=float, default=5.0, help="Intervalo em segundos para envio automático")
    args = parser.parse_args()

    client = NewsClient(args.host, args.port)
    client.set_info_handler(lambda text: print(f"[servidor] {text}"))
    client.start()

    try:
        if args.auto:
            print(f"[publicador] Modo automático ativado (intervalo: {args.intervalo}s). Pressione Ctrl+C para encerrar.\n")
            for category, title, summary in itertools.cycle(SAMPLE_NEWS):
                response = client.publish(category, title, summary)
                print(f"[envio] [{category.upper()}] {title} -> {response}")
                time.sleep(args.intervalo)
        else:
            print("[publicador] Modo interativo ativado. Pressione Ctrl+C para encerrar.\n")
            while True:
                category = input("categoria: ").strip()
                if not category:
                    continue
                title = input("título: ").strip()
                summary = input("resumo: ").strip()

                response = client.publish(category, title, summary)
                print(f"-> {response}\n")
    except (KeyboardInterrupt, EOFError):
        print("\n[publicador] Encerramento solicitado.")
    finally:
        client.stop()


if __name__ == "__main__":
    main()
