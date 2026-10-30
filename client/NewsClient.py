
import queue
import socket
import threading


class NewsClient:

    def __init__(self, host="127.0.0.1", port=5000):
        self.host = host
        self.port = port
        self.sock = None
        self.running = False
        self._responses = queue.Queue()
        self._send_lock = threading.Lock()
        self.news_handler = None
        self.info_handler = None
        self.closed_handler = None

    # handlers
    def set_news_handler(self, fn):

        self.news_handler = fn

    def set_info_handler(self, fn):

        self.info_handler = fn

    def set_closed_handler(self, fn):

        self.closed_handler = fn


    def start(self):
        """inicia a conexão e inicia a thread """
        self.sock = socket.create_connection((self.host, self.port))
        self.running = True
        threading.Thread(target=self._receive_loop, daemon=True).start()

    def stop(self):
        """encerra a conexão com o servidor """
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass

    def _receive_loop(self):
        """le continuamente o fluxo de dados enviados pelo servidor"""
        try:
            with self.sock.makefile("r", encoding="utf-8", newline="\n") as f:
                for line in f:
                    self._dispatch(line.rstrip("\n"))
        except (OSError, ValueError):
            pass
        finally:
            self.running = False
            if self.closed_handler:
                self.closed_handler()

    def _dispatch(self, line):
        """classifica as mensagens do servidor"""
        if line.startswith("NOTICIA|"):
            parts = line.split("|", 3)
            if len(parts) == 4 and self.news_handler:
                self.news_handler(parts[1], parts[2], parts[3])
        elif line.startswith("INFO"):
            if self.info_handler:
                self.info_handler(line[5:])
        else:
            self._responses.put(line)

    # comandos do protocolo
    def send_command(self, command, timeout=5):
        """envia um comando via socket"""
        with self._send_lock:
            self.sock.sendall((command + "\n").encode("utf-8"))
        try:
            return self._responses.get(timeout=timeout)
        except queue.Empty:
            return "ERRO sem resposta do servidor"

    def subscribe(self, categories):
        return self.send_command("INSCREVER " + ", ".join(categories))

    def unsubscribe(self, categories):
        return self.send_command("REMOVER " + ", ".join(categories))

    def list_categories(self):
        return self.send_command("CATEGORIAS")

    def my_subscriptions(self):

        return self.send_command("MINHAS")

    def publish(self, category, title, summary):
        return self.send_command(f"PUBLICAR {category}|{title}|{summary}")

    def quit(self):
        try:
            return self.send_command("SAIR", timeout=2)
        finally:
            self.stop()