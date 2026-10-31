import os
import sys
import json
import time
import queue
import socket
import argparse
import threading
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
# tempo para o servidor remover a sessao depois do SAIR
ESPERA_SAIDA = 0.2

acertos = 0
falhas = 0


def checar(descricao, condicao, detalhe=""):
    global acertos, falhas
    if condicao:
        acertos += 1
        print(f"  [ok]    {descricao}")
    else:
        falhas += 1
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
    time.sleep(ESPERA_SAIDA)


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
    time.sleep(ESPERA_SAIDA)


def teste_assinaturas(porta):
    print("\ninscricao e cancelamento")
    cliente = novo_cliente(porta)

    resposta = cliente.subscribe(["tecnologia", "esportes"])
    checar("INSCREVER em duas categorias", resposta == "OK inscrito em: tecnologia, esportes", resposta)

    resposta = cliente.my_subscriptions()
    checar("MINHAS mostra as duas", resposta == "OK esportes, tecnologia", resposta)

    resposta = cliente.unsubscribe(["tecnologia"])
    checar("CANCELAR uma categoria", resposta == "OK cancelado: tecnologia", resposta)

    resposta = cliente.my_subscriptions()
    checar("MINHAS depois de cancelar", resposta == "OK esportes", resposta)

    resposta = cliente.unsubscribe(["cultura"])
    checar("CANCELAR categoria que nao estava assinada", resposta == "OK cancelado: (nenhuma)", resposta)

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
    checar("depois de CANCELAR nao recebe mais a categoria", recebida is None, recebida)

    # titulo com acento para conferir o utf-8 de ponta a ponta
    noticia = ("cultura", "Exposição de arte popular no Recife", "Entrada gratuita até o fim do mês.")
    editor.publish(*noticia)
    recebida = proxima_noticia(leitor_tec)
    checar("depois de INSCREVER passa a receber a nova categoria", recebida == noticia, recebida)

    encerrar(leitor_tec, leitor_esp, editor)
    # quantidade de noticias publicadas com sucesso neste teste
    return 3


def teste_erros(porta):
    print("\nerros do protocolo")
    cliente = novo_cliente(porta)

    # comando enviado e resposta esperada do servidor
    casos = [
        ("INSCREVER", "ERRO uso: INSCREVER <categoria>[, <categoria>...]"),
        ("CANCELAR", "ERRO uso: CANCELAR <categoria>[, <categoria>...]"),
        ("PUBLICAR esportes|so o titulo", "ERRO uso: PUBLICAR categoria|titulo|resumo"),
        ("PUBLICAR esportes||resumo sem titulo", "ERRO uso: PUBLICAR categoria|titulo|resumo"),
        ("PUBLICAR politica|Titulo|Resumo", "ERRO categoria inexistente. Disponiveis: tecnologia, esportes, cultura"),
        ("LISTAR", "ERRO comando desconhecido"),
    ]
    for comando, esperado in casos:
        resposta = cliente.send_command(comando)
        checar(f"'{comando}' retorna erro", resposta == esperado, resposta)

    # depois dos erros a sessao continua funcionando
    resposta = cliente.list_categories()
    checar("sessao continua aberta depois dos erros", resposta.startswith("OK"), resposta)

    encerrar(cliente)


def teste_simultaneos(porta, quantidade=10):
    print(f"\n{quantidade} clientes ao mesmo tempo")
    leitores = [novo_cliente(porta) for _ in range(quantidade)]
    for leitor in leitores:
        leitor.subscribe(["esportes"])
    editor = novo_cliente(porta)

    resposta = editor.publish("esportes", "Final do campeonato", "Jogo decidido nos penaltis.")
    checar(f"PUBLICAR confirma {quantidade} assinantes",
           resposta == f"OK publicada para {quantidade} assinante(s)", resposta)
    recebidas = sum(1 for leitor in leitores if proxima_noticia(leitor) is not None)
    checar("todos os clientes recebem a noticia", recebidas == quantidade, f"{recebidas} de {quantidade}")

    # tres editores publicando juntos, cada um em uma thread
    editores = [novo_cliente(porta) for _ in range(3)]
    threads = [
        threading.Thread(target=e.publish, args=("esportes", f"Rodada {i}", f"Resumo da rodada {i}."))
        for i, e in enumerate(editores)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # cada leitor deve receber as tres, em qualquer ordem
    completos = 0
    for leitor in leitores:
        titulos = set()
        for _ in range(3):
            noticia = proxima_noticia(leitor)
            if noticia is None:
                break
            titulos.add(noticia[1])
        if titulos == {"Rodada 0", "Rodada 1", "Rodada 2"}:
            completos += 1
    checar("publicacoes simultaneas chegam inteiras para todos",
           completos == quantidade, f"{completos} de {quantidade}")

    encerrar(*leitores, editor, *editores)
    return 1 + len(editores)


def teste_armazenamento(arquivo, esperadas):
    print("\narmazenamento")
    try:
        with open(arquivo, encoding="utf-8") as f:
            registros = [json.loads(linha) for linha in f if linha.strip()]
    except (OSError, json.JSONDecodeError) as erro:
        checar("arquivo de noticias pode ser lido", False, erro)
        return

    checar(f"arquivo tem as {esperadas} noticias publicadas", len(registros) == esperadas,
           f"{len(registros)} registros")
    campos = {"ts", "categoria", "titulo", "resumo"}
    checar("todo registro tem ts, categoria, titulo e resumo",
           all(set(r) == campos for r in registros))
    # o acento precisa ficar legivel no arquivo, sem virar ç
    titulos = [r.get("titulo") for r in registros]
    checar("acentos gravados corretamente", "Exposição de arte popular no Recife" in titulos)


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

    testes = [teste_conexao, teste_assinaturas, teste_entrega, teste_erros, teste_simultaneos]
    publicadas = 0
    try:
        for teste in testes:
            # uma excecao conta como falha e nao impede os proximos testes
            try:
                publicadas += teste(args.port) or 0
            except Exception as erro:
                checar(f"{teste.__name__} rodou ate o fim", False, repr(erro))
    finally:
        derrubar_servidor(servidor)

    teste_armazenamento(arquivo, publicadas)

    print(f"\n{acertos} ok, {falhas} falha(s)")
    if falhas:
        mostrar_log(log)
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
