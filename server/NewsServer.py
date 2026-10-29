import threading

class SessaoCliente:
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