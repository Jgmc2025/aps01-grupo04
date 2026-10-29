class SessaoCliente:
    """Criando agora um objeto de sessão para cada cliente que se conecta ao servidor"""
    def __init__(self, socket, enderco):
        self.socket = socket
        self.enderco = enderco
        self.is_authenticated = False  # Inicialmente, o cliente não está autenticado
        self.enviarlock = threading.Lock()