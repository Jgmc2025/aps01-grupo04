import os
import sys
import time
import queue
import socket
import argparse
import tempfile
import subprocess

# raiz do projeto, um nivel acima da pasta teste
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# deixa importar o NewsClient direto da pasta client
sys.path.insert(0, os.path.join(RAIZ, "client"))

from NewsClient import NewsClient

HOST = "127.0.0.1"
# tempo maximo esperando uma noticia que deveria chegar
ESPERA_NOTICIA = 2.0
# tempo esperando uma noticia que nao deveria chegar
ESPERA_CURTA = 0.5

acertos = 0
erros = 0


def checar(descricao, condicao, detalhe=""):
    global acertos, erros
    if condicao:
        acertos += 1
        print(f"  [ok]    {descricao}")
    else:
        erros += 1
        print(f"  [falha] {descricao}")
        if detalhe:
            print(f"          recebido: {detalhe}")


def subir_servidor(porta, arquivo, log):
    # roda o servidor como modulo a partir da raiz, igual ao uso normal
    saida = open(log, "w", encoding="utf-8")
    processo = subprocess.Popen(
        [sys.executable, "-m", "server.NewsServer", "--host", HOST,
         "--port", str(porta), "--arquivo", arquivo],
        cwd=RAIZ, stdout=saida, stderr=subprocess.STDOUT)

    # espera a porta abrir ou o processo morrer
    limite = time.time() + 5
    while time.time() < limite:
        if processo.poll() is not None:
            print("[teste] o servidor encerrou antes de abrir a porta")
            return None
        try:
            socket.create_connection((HOST, porta), timeout=0.5).close()
            return processo
        except OSError:
            time.sleep(0.1)

    print("[teste] o servidor nao abriu a porta a tempo")
    processo.kill()
    return None


def derrubar_servidor(processo):
    processo.terminate()
    try:
        processo.wait(timeout=3)
    except subprocess.TimeoutExpired:
        processo.kill()


def mostrar_log(log):
    print("\n[teste] saida do servidor:")
    with open(log, encoding="utf-8") as f:
        print(f.read())


def novo_cliente(porta):
    cliente = NewsClient(HOST, porta)
    # guarda as noticias e mensagens INFO que chegarem para conferir depois
    cliente.noticias = queue.Queue()
    cliente.infos = queue.Queue()
    cliente.set_news_handler(lambda cat, tit, res: cliente.noticias.put((cat, tit, res)))
    cliente.set_info_handler(cliente.infos.put)
    cliente.start()
    return cliente


def proxima_noticia(cliente, espera=ESPERA_NOTICIA):
    try:
        return cliente.noticias.get(timeout=espera)
    except queue.Empty:
        return None


def encerrar(*clientes):
    for cliente in clientes:
        cliente.quit()
    # da tempo do servidor tirar as sessoes da lista antes do proximo teste
    time.sleep(0.2)


def teste_conexao(porta):
    print("\nconexao")
    cliente = novo_cliente(porta)

    try:
        info = cliente.infos.get(timeout=ESPERA_NOTICIA)
    except queue.Empty:
        info = ""
    checar("recebe a mensagem de boas-vindas", "Bem-vindo" in info, info)

    resposta = cliente.list_categories()
    checar("CATEGORIAS lista as tres categorias", resposta == "OK tecnologia, esportes, cultura", resposta)

    resposta = cliente.quit()
    checar("SAIR encerra a sessao", resposta == "OK ate logo", resposta)
    time.sleep(0.2)


def teste_assinaturas(porta):
    print("\ninscricao e remocao")
    cliente = novo_cliente(porta)

    resposta = cliente.subscribe(["tecnologia", "esportes"])
    checar("INSCREVER em duas categorias", resposta == "OK inscrito em: tecnologia, esportes", resposta)

    resposta = cliente.my_subscriptions()
    checar("MINHAS mostra as duas", resposta == "OK esportes, tecnologia", resposta)

    resposta = cliente.unsubscribe(["tecnologia"])
    checar("REMOVER uma categoria", resposta == "OK removido: tecnologia", resposta)

    resposta = cliente.my_subscriptions()
    checar("MINHAS depois de remover", resposta == "OK esportes", resposta)

    resposta = cliente.unsubscribe(["cultura"])
    checar("REMOVER categoria que nao estava assinada", resposta == "OK removido: (nenhuma)", resposta)

    # a valida entra e a inexistente aparece na resposta
    resposta = cliente.subscribe(["cultura", "politica"])
    checar("INSCREVER com uma categoria inexistente",
           resposta == "OK inscrito em: cultura | categorias inexistentes: politica", resposta)

    resposta = cliente.send_command("inscrever ESPORTES")
    checar("comando e categoria em maiusculas ou minusculas", resposta == "OK inscrito em: esportes", resposta)

    encerrar(cliente)


def teste_entrega(porta):
    print("\npublicacao e entrega")
    leitor_tec = novo_cliente(porta)
    leitor_esp = novo_cliente(porta)
    editor = novo_cliente(porta)
    leitor_tec.subscribe(["tecnologia"])
    leitor_esp.subscribe(["esportes"])

    noticia = ("tecnologia", "Novo processador lancado", "Chip promete gastar menos energia.")
    resposta = editor.publish(*noticia)
    checar("PUBLICAR confirma 1 assinante", resposta == "OK publicada para 1 assinante(s)", resposta)
    recebida = proxima_noticia(leitor_tec)
    checar("assinante de tecnologia recebe categoria, titulo e resumo", recebida == noticia, recebida)
    recebida = proxima_noticia(leitor_esp, ESPERA_CURTA)
    checar("assinante de esportes nao recebe", recebida is None, recebida)
    recebida = proxima_noticia(editor, ESPERA_CURTA)
    checar("editor sem assinatura nao recebe", recebida is None, recebida)

    # troca a assinatura no meio da sessao
    leitor_tec.unsubscribe(["tecnologia"])
    leitor_tec.subscribe(["cultura"])

    editor.publish("tecnologia", "Atualizacao de seguranca", "Correcao para uma falha no navegador.")
    recebida = proxima_noticia(leitor_tec, ESPERA_CURTA)
    checar("depois de REMOVER nao recebe mais a categoria", recebida is None, recebida)

    # titulo com acento para conferir o utf-8 de ponta a ponta
    noticia = ("cultura", "Exposição de arte popular no Recife", "Entrada gratuita até o fim do mês.")
    editor.publish(*noticia)
    recebida = proxima_noticia(leitor_tec)
    checar("depois de INSCREVER passa a receber a nova categoria", recebida == noticia, recebida)

    encerrar(leitor_tec, leitor_esp, editor)


def main():
    parser = argparse.ArgumentParser(description="Testes do feed de noticias PUB/SUB")
    parser.add_argument("--port", type=int, default=5050, help="porta usada pelo servidor de teste")
    args = parser.parse_args()

    # arquivo de noticias e log ficam numa pasta temporaria, sem sujar o projeto
    pasta = tempfile.mkdtemp(prefix="feed_teste_")
    arquivo = os.path.join(pasta, "noticias.jsonl")
    log = os.path.join(pasta, "servidor.log")

    servidor = subir_servidor(args.port, arquivo, log)
    if servidor is None:
        mostrar_log(log)
        sys.exit(1)

    try:
        teste_conexao(args.port)
        teste_assinaturas(args.port)
        teste_entrega(args.port)
    finally:
        derrubar_servidor(servidor)

    print(f"\n{acertos} ok, {erros} falha(s)")
    if erros:
        mostrar_log(log)
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
