# Usuario unico do feed: recebe noticias em tempo real e tambem pode publicar.

import argparse
import itertools
import time
from NewsClient import NewsClient

HELP = ("Comandos: INSCREVER <cat,...> | CANCELAR <cat,...> | CATEGORIAS | "
        "MINHAS | PUBLICAR categoria|titulo|resumo | ADICIONAR <cat,...> | REMOVER <cat,...> | "
        "RESTAURAR | SAIR")

# noticias usadas no modo automatico (--auto)
SAMPLE_NEWS = [
    ("tecnologia", "Nova versao do kernel Linux lancada", "Release traz melhorias de desempenho e drivers."),
    ("esportes", "Sport vence o classico pernambucano", "Partida terminou 2x1 na Ilha do Retiro."),
    ("cultura", "Festival de cinema abre inscricoes", "Mostra recebe filmes ate o fim do mes."),
    ("tecnologia", "Pesquisadores apresentam novo protocolo de rede", "Proposta reduz latencia em redes moveis."),
    ("esportes", "Selecao feminina convoca nova lista", "Treinos comecam na proxima semana."),
    ("cultura", "Recife recebe exposicao de arte popular", "Entrada gratuita durante todo o mes."),
]

def on_news(category, title, summary):
    print(f"\n>>> [{category.upper()}] {title}\n    {summary}\n> ", end="", flush=True)

def on_info(text):
    print(f"[servidor] {text}")

def on_closed():
    print("\n[conexao encerrada]")

def main():
    parser = argparse.ArgumentParser(description="Usuario do feed de noticias (le e publica)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--categorias", default="",
                        help="categorias para assinar ao conectar, separadas por virgula")
    parser.add_argument("--auto", action="store_true",
                        help="publica noticias de exemplo automaticamente")
    parser.add_argument("--intervalo", type=float, default=5.0,
                        help="segundos entre noticias no modo --auto")
    args = parser.parse_args()

    client = NewsClient(args.host, args.port)
    client.set_news_handler(on_news)
    client.set_info_handler(on_info)
    client.set_closed_handler(on_closed)
    client.start()

    initial = [c.strip() for c in args.categorias.split(",") if c.strip()]
    if initial:
        print(client.subscribe(initial))

    try:
        if args.auto:
            print(f"[usuario] Modo automatico (intervalo: {args.intervalo}s). Ctrl+C para encerrar.\n")
            for category, title, summary in itertools.cycle(SAMPLE_NEWS):
                if not client.running:
                    break
                print(f"[envio] [{category.upper()}] {title} -> {client.publish(category, title, summary)}")
                time.sleep(args.intervalo)
        else:
            print(HELP)
            while client.running:
                try:
                    command = input("> ").strip()
                except EOFError:
                    command = "SAIR"
                if not command:
                    continue
                if command.upper() == "SAIR":
                    print(client.quit())
                    break
                print(client.send_command(command).replace(" | ", "\n    "))
    except KeyboardInterrupt:
        pass
    finally:
        client.stop()


if __name__ == "__main__":
    main()