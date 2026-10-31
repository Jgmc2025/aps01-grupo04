import threading
import socket
import argparse

from server.NewsEngine import NewsEngine

class ClienteSessao:
    """Criando agora um objeto de sessão para cada cliente que se conecta ao servidor"""
    def __init__(self, socket, enderco):
        self.socket = socket
        self.addr = enderco
        self.subscriptions = set()  # categorias assinadas por este cliente
        self.enviarlock = threading.Lock()

    def send(self, message): # Função de envio de mensagens para o cliente
        try:
            with self.enviarlock:
                self.socket.sendall((message + "\n").encode("utf-8"))
            return True
        except OSError:
            return False

    def close(self): # Função para fechar a conexão com o cliente
        try:
            self.socket.close()
        except OSError:
            pass

class NewsServer:
    def __init__(self, host="0.0.0.0", port=5000,
                 armazenamento="noticias.jsonl"):
        self.host = host
        self.port = port
        self.engine = NewsEngine(armazenamento)
        self.servidor_socket = None


    def start(self):
        self.servidor_socket = socket.socket(socket.AF_INET, socket.SOCK_TCP)
        self.servidor_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.servidor_socket.bind((self.host, self.port))
        self.servidor_socket.listen()
        print(f"[NewsServer] Ouvindo em {self.host}:{self.port} "
              f"({self.engine.total_news} noticias no historico)", flush=True)

        try:
            while True:
                sock, addr = self.servidor_socket.accept()
                sessao = ClienteSessao(sock, addr)
                self.engine.registrar_sessao(sessao)
                threading.Thread(target=self.handle_client,
                                 args=(sessao,), daemon=True).start()
        except KeyboardInterrupt:
            print("\n[NewsServer] Encerrando...")
        finally:
            self.stop()

    def stop(self):
        if self.servidor_socket:
            self.servidor_socket.close()
            self.servidor_socket = None
        print("[NewsServer] Servidor parado.")

    def handle_client(self, sessao):
        print(f"[NewsServer] Cliente conectado: {sessao.addr}", flush=True)
        try:
            sessao.send("INFO Bem-vindo! Categorias: " + ", ".join(self.engine.listar_categorias())
                         + ". Use INSCREVER <categoria>.")
            with sessao.socket.makefile("r", encoding="utf-8", newline="\n") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if not self.process_command(sessao, line):
                        break
        except (OSError, UnicodeDecodeError):
            pass
        finally:
            self.engine.nao_registrar_sessao(sessao)
            sessao.close()
            print(f"[NewsServer] Cliente desconectado: {sessao.addr}", flush=True)
    
    @staticmethod
    def _parse_categories(text):
        return [c.strip().lower() for c in text.replace(",", " ").split() if c.strip()]

    @staticmethod
    def _clean(text):
        return text.replace("|", "/").replace("\n", " ").replace("\r", " ").strip()

    def process_command(self, session, line):
        """Retorna False quando a sessao deve ser encerrada."""
        command, _, rest = line.partition(" ")
        command = command.upper()

        if command == "INSCREVER":
            cats = self._parse_categories(rest)
            if not cats:
                session.send("ERRO uso: INSCREVER <categoria>[, <categoria>...]")
                return True
            valid, invalid = self.engine.assinar(session, cats)
            msg = "OK inscrito em: " + (", ".join(valid) or "(nenhuma)")
            if invalid:
                msg += " | categorias inexistentes: " + ", ".join(invalid)
            session.send(msg)

        elif command == "CANCELAR":
            cats = self._parse_categories(rest)
            if not cats:
                session.send("ERRO uso: CANCELAR <categoria>[, <categoria>...]")
                return True
            removed = self.engine.nao_assinar(session, cats)
            session.send("OK cancelado: " + (", ".join(removed) or "(nenhuma)"))

        elif command == "REMOVER":
            cats = self._parse_categories(rest)
            if not cats:
                session.send("ERRO uso: REMOVER <categoria>[, <categoria>...]")
                return True
            removidas, inexistentes = self.engine.remover_categorias(cats)
            msg = "OK categoria removida do sistema: " + (", ".join(removidas) or "(nenhuma)")
            if inexistentes:
                msg += " | categorias inexistentes: " + ", ".join(inexistentes)
            session.send(msg)

        elif command == "CATEGORIAS":
            session.send("OK " + ", ".join(self.engine.listar_categorias()))

        elif command == "MINHAS":
            current = self.engine.assinaturas_da_sessao(session)
            session.send("OK " + (", ".join(current) or "(nenhuma assinatura)"))

        elif command == "PUBLICAR":
            parts = [self._clean(p) for p in rest.split("|")]
            if len(parts) != 3 or not all(parts):
                session.send("ERRO uso: PUBLICAR categoria|titulo|resumo")
                return True
            category, title, summary = parts
            category = category.lower()
            categorias = self.engine.listar_categorias()
            if category not in categorias:
                session.send("ERRO categoria inexistente. Disponiveis: " + ", ".join(categorias))
                return True
            delivered = self.engine.publicar(category, title, summary)
            session.send(f"OK publicada para {delivered} assinante(s)")

        elif command == "RESTAURAR":
            apagadas = self.engine.restaurar()
            session.send(f"OK banco restaurado: {apagadas} noticia(s) apagada(s) | "
                         "categorias: " + ", ".join(self.engine.listar_categorias()))

        elif command == "SAIR":
            session.send("OK ate logo")
            return False

        else:
            session.send("ERRO comando desconhecido")
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor de feed de noticias PUB/SUB (TCP)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--arquivo", default="noticias.jsonl")
    args = parser.parse_args()

    NewsServer(args.host, args.port, args.arquivo).start()