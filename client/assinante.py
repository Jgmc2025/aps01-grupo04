# Cliente assinante recebe noticias em tempo real

import argparse
from NewsClient import NewsClient

HELP = ("Comandos: INSCREVER <cat,...> | REMOVER <cat,...> | CATEGORIAS | "
        "MINHAS | SAIR")

def on_news(category, title, summary):
    print(f"\n>>> [{category.upper()}] {title}\n    {summary}\n> ", end="", flush=True)

def on_info(text):
    print(f"[servidor] {text}")

def on_closed():
    print("\n[conexao encerrada]")

def main():
    parser = argparse.ArgumentParser(description="Cliente assinante do feed de noticias")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--categorias", default="",
                        help="categorias para assinar ao conectar, separadas por virgula")
    args = parser.parse_args()

    client = NewsClient(args.host, args.port)
    client.set_news_handler(on_news)
    client.set_info_handler(on_info)
    client.set_closed_handler(on_closed)
    client.start()

    initial = [c.strip() for c in args.categorias.split(",") if c.strip()]
    if initial:
        print(client.subscribe(initial))

    print(HELP)
    try:
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
            print(client.send_command(command))
    except KeyboardInterrupt:
        pass
    finally:
        client.stop()


if __name__ == "__main__":
    main()
