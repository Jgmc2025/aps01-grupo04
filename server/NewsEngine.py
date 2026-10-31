import os
import threading
import time
import json

# categorias do estado original do sistema (usadas tambem pelo RESTAURAR)
CATEGORIAS_PADRAO = ["tecnologia", "esportes", "cultura"]

class NewsEngine:
    def __init__(self, armazenamento="noticias.jsonl"):
        self.armazenamento = armazenamento
        # o arquivo de categorias fica na mesma pasta do arquivo de noticias
        pasta = os.path.dirname(os.path.abspath(armazenamento))
        self.arquivo_categorias = os.path.join(pasta, "categorias.json")
        self.sessions = []                 # sessoes conectadas
        self.lock = threading.Lock()       # protege sessions, subscriptions e categorias
        self.lock_armazenamento = threading.Lock()  # protege o arquivo de noticias
        self.categorias = self._carregar_categorias()
        self.total_news = self._count_existing()

    def registrar_sessao(self, session):
        with self.lock:
            self.sessions.append(session)

    def nao_registrar_sessao(self, session):
        with self.lock:
            if session in self.sessions:
                self.sessions.remove(session)

    def listar_categorias(self):
        with self.lock:
            return list(self.categorias)

    def assinar(self, session, categories):
        with self.lock:
            valid = [c for c in categories if c in self.categorias]
            invalid = [c for c in categories if c not in self.categorias]
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

    def publicar(self, categoria, title, summary):
        """Grava a noticia e envia para quem assinou a categoria.

        Retorna a quantidade de clientes que receberam.
        """
        record = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "categoria": categoria,
            "titulo": title,
            "resumo": summary,
        }
        with self.lock_armazenamento:
            with open(self.armazenamento, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            self.total_news += 1

        # copia dos destinatarios sob lock, o envio acontece fora dele
        with self.lock:
            targets = [s for s in self.sessions if categoria in s.subscriptions]

        message = f"NOTICIA|{categoria}|{title}|{summary}"
        delivered = 0
        for s in targets:
            if s.send(message):
                delivered += 1
        print(f"[NewsEngine] [{categoria}] {title} -> {delivered} cliente(s)", flush=True)
        return delivered

    def remover_categorias(self, nomes):
        """Apaga as categorias do sistema de vez (tambem do arquivo de categorias).

        Retorna (removidas, inexistentes). Quem assinava perde a assinatura."""
        nomes = list(dict.fromkeys(nomes))  # tira repetidos mantendo a ordem
        with self.lock:
            removidas = [c for c in nomes if c in self.categorias]
            inexistentes = [c for c in nomes if c not in self.categorias]
            if removidas:
                self.categorias = [c for c in self.categorias if c not in removidas]
                self._salvar_categorias()
                for s in self.sessions:
                    s.subscriptions.difference_update(removidas)
            todas = list(self.sessions)

        if removidas:
            self._avisar(todas, "INFO categoria removida do sistema: " + ", ".join(removidas))
            print(f"[NewsEngine] Categoria(s) removida(s): {', '.join(removidas)}", flush=True)
        return removidas, inexistentes

    def restaurar(self):
        """Volta o banco ao estado original: apaga todas as noticias e
        restaura as categorias padrao. Retorna quantas noticias foram apagadas."""
        with self.lock_armazenamento:
            apagadas = self.total_news
            open(self.armazenamento, "w", encoding="utf-8").close()
            self.total_news = 0

        with self.lock:
            self.categorias = list(CATEGORIAS_PADRAO)
            self._salvar_categorias()
            # ninguem continua assinando categoria que deixou de existir
            for s in self.sessions:
                s.subscriptions.intersection_update(self.categorias)
            todas = list(self.sessions)

        self._avisar(todas, "INFO banco de dados restaurado ao estado original")
        print(f"[NewsEngine] Banco restaurado ({apagadas} noticia(s) apagada(s))", flush=True)
        return apagadas

    def _avisar(self, sessoes, texto):
        """Envia uma mensagem INFO para as sessoes (sempre fora do lock)."""
        for s in sessoes:
            s.send(texto)

    def _carregar_categorias(self):
        try:
            with open(self.arquivo_categorias, "r", encoding="utf-8") as f:
                categorias = json.load(f)
            if isinstance(categorias, list):
                return categorias
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        categorias = list(CATEGORIAS_PADRAO)
        self.categorias = categorias
        self._salvar_categorias()
        return categorias

    def _salvar_categorias(self):
        with open(self.arquivo_categorias, "w", encoding="utf-8") as f:
            json.dump(self.categorias, f, ensure_ascii=False)

    def _count_existing(self): # Conta quantas noticias existem no arquivo de armazenamento
        try:
            with open(self.armazenamento, "r", encoding="utf-8") as f:
                return sum(1 for _ in f)
        except FileNotFoundError:
            return 0