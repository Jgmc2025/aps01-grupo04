import threading
import socket

class ClienteSessao:
    """Criando agora um objeto de sessão para cada cliente que se conecta ao servidor"""
    def __init__(self, socket, enderco):
        self.socket = socket
        self.enderco = enderco
        self.is_authenticated = False  # Inicialmente, o cliente não está autenticado
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
                session = ClienteSessao(sock, addr)
                self.engine.register_session(session)
                threading.Thread(target=self.handle_client,
                                 args=(session,), daemon=True).start()
        except KeyboardInterrupt:
            print("\n[NewsServer] Encerrando...")
        finally:
            self.stop()

    def stop(self):
        if self.servidor_socket:
            self.servidor_socket.close()
            self.servidor_socket = None
        print("[NewsServer] Servidor parado.")
    
        