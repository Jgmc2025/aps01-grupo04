import threading

from server.NewsServer import CATEGORIES

class NewsEngine:
    def __init__(self, armazenamento="noticias.jsonl"):
        self.armazenamento = armazenamento
        self.sessions = []                 # sessoes conectadas
        self.lock = threading.Lock()       # protege sessions e subscriptions
        self.lock_armazenamento = threading.Lock()  # protege o arquivo de noticias
        self.total_news = self._count_existing()

    def registrar_sessao(self, session):
        with self.lock:
            self.sessions.append(session)

    def nao_registrar_sessao(self, session):
        with self.lock:
            if session in self.sessions:
                self.sessions.remove(session)

    def assinar(self, session, categories):
        valid = [c for c in categories if c in CATEGORIES]
        invalid = [c for c in categories if c not in CATEGORIES]
        with self.lock:
            session.subscriptions.update(valid)
        return valid, invalid

    def nao_assinar(self, session, categories):
        with self.lock:
            removed = [c for c in categories if c in session.subscriptions]
            session.subscriptions.difference_update(categories)
        return removed

    def assinaturas_da_sessao(self, session):
        with self.lock:
            return sorted(session.subscriptions)