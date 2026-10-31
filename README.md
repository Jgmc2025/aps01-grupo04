# Feed de Noticias PUB/SUB com Sockets TCP

## Sumario

- [Sobre](#sobre)
- [Como funciona](#como-funciona)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Primeiros passos](#primeiros-passos)
- [Uso](#uso)
- [Comandos do protocolo](#comandos-do-protocolo)
- [Armazenamento](#armazenamento)
- [Testes](#testes)
- [Limitacoes conhecidas](#limitacoes-conhecidas)
- [Tecnologias utilizadas](#tecnologias-utilizadas)

## Sobre

Este projeto e um sistema distribuido cliente-servidor que funciona como um feed de noticias continuo, no modelo publicador/assinante (PUB/SUB). A comunicacao e feita com sockets TCP puros, sem broker nem biblioteca externa.

O servidor mantem uma lista de categorias (por padrao: tecnologia, esportes e cultura) e guarda em arquivo todas as noticias que recebe. Os clientes se conectam, escolhem as categorias que lhes interessam e ficam com a conexao aberta. Quando alguem publica uma noticia, o servidor envia o titulo, o resumo e a categoria na hora, e somente para quem assinou aquele tema. O cliente nao precisa pedir nada para receber.

Existe um unico tipo de usuario. Qualquer cliente pode receber noticias, publicar noticias e mexer nas categorias do sistema.

O projeto foi desenvolvido para a atividade APS 01 (Grupo 04). A separacao em servidor, engine e cliente foi inspirada no projeto de exemplo do professor (Midd4VC), que organiza o codigo da mesma forma, mas la a comunicacao passa por um broker MQTT e aqui ela e feita direto sobre TCP.

## Como funciona

- O servidor aceita conexoes em loop e cria **uma thread para cada cliente conectado**. Assim, varios clientes sao atendidos ao mesmo tempo sem que um bloqueie o outro.
- Cada cliente tem uma sessao no servidor, que guarda o socket, o endereco, a thread que o atende e o conjunto de categorias assinadas.
- Quando uma noticia e publicada, o servidor grava no arquivo, separa os clientes que assinaram a categoria e envia a mensagem para cada um pelo socket que ja esta aberto.
- No lado do cliente, uma thread fica lendo o socket o tempo todo. Mensagens de noticia e de aviso chegam a qualquer momento e sao entregues a funcoes de tratamento. Respostas a comandos vao para uma fila, que o metodo que enviou o comando espera.
- Os dados compartilhados (lista de sessoes, assinaturas, categorias e arquivo de noticias) sao protegidos por locks. O envio das mensagens e feito fora do lock principal para que um cliente lento nao trave os demais.

Mensagens que o servidor envia sem ninguem pedir:

```
NOTICIA|categoria|titulo|resumo
INFO texto de aviso
```

Respostas a comandos sempre comecam com `OK` ou `ERRO`.

## Estrutura do projeto

```
aps01-grupo04/
|-- server/
|   |-- NewsServer.py     # socket de escuta, thread por cliente e interpretacao dos comandos
|   `-- NewsEngine.py     # regras de negocio: sessoes, assinaturas, categorias e armazenamento
|-- client/
|   |-- NewsClient.py     # biblioteca do cliente (conexao, thread de leitura e comandos)
|   `-- usuario.py        # programa de linha de comando do usuario
|-- teste/
|   `-- teste.py          # testes automatizados de ponta a ponta
`-- README.md
```

Dois arquivos sao criados pelo servidor quando ele roda: `noticias.jsonl` e `categorias.json` (veja [Armazenamento](#armazenamento)).

## Primeiros passos

Estas instrucoes mostram como colocar o projeto para rodar na sua maquina.

Clone o repositorio e entre na pasta do projeto:

```bash
git clone <url-do-repositorio>
cd aps01-grupo04
```

### Pre-requisitos

Basta ter o Python 3 instalado. O projeto usa apenas a biblioteca padrao, entao nao ha nada para instalar com o pip. Foi testado com Python 3.13 em Linux.

```bash
# Debian/Ubuntu
sudo apt install python3
```

No Windows, instale pelo site oficial (https://www.python.org/) e use `python` no lugar de `python3` nos comandos abaixo.

## Uso

### Rodando o servidor

Na raiz do projeto:

```bash
python3 -m server.NewsServer
```

O servidor fica ouvindo em `0.0.0.0:5000`. Os parametros opcionais sao:

| Parametro   | Padrao            | Descricao                          |
|-------------|-------------------|------------------------------------|
| `--host`    | `0.0.0.0`         | Endereco em que o servidor escuta  |
| `--port`    | `5000`            | Porta TCP                          |
| `--arquivo` | `noticias.jsonl`  | Arquivo onde as noticias sao salvas |

Exemplo:

```bash
python3 -m server.NewsServer --port 6000 --arquivo meu_feed.jsonl
```

### Rodando o cliente

Em outro terminal, entre na pasta `client` e abra o usuario:

```bash
cd client
python3 usuario.py
```

Parametros opcionais:

| Parametro      | Padrao      | Descricao                                                       |
|----------------|-------------|-----------------------------------------------------------------|
| `--host`       | `127.0.0.1` | Endereco do servidor                                            |
| `--port`       | `5000`      | Porta do servidor                                               |
| `--categorias` | vazio       | Categorias para assinar ao conectar, separadas por virgula      |
| `--auto`       | desligado   | Publica noticias de exemplo automaticamente, sem prompt         |
| `--intervalo`  | `5.0`       | Segundos entre as noticias no modo `--auto`                     |

### Exemplo de uso com varios clientes

Abra tres terminais alem do servidor.

Terminal 2, um usuario que quer so tecnologia:

```bash
cd client
python3 usuario.py --categorias tecnologia
```

Terminal 3, um usuario que quer esportes e cultura:

```bash
cd client
python3 usuario.py --categorias esportes,cultura
```

Terminal 4, um usuario que publica noticias de exemplo a cada 2 segundos:

```bash
cd client
python3 usuario.py --auto --intervalo 2
```

Cada usuario recebe na hora apenas as noticias das categorias que assinou. Dentro de um deles, voce tambem pode digitar comandos a qualquer momento, por exemplo:

```
> INSCREVER cultura
OK inscrito em: cultura
> CANCELAR tecnologia
OK cancelado: tecnologia
> PUBLICAR cultura|Festival de cinema abre inscricoes|Mostra recebe filmes ate o fim do mes.
OK publicada para 2 assinante(s)
```

Uma noticia chegando aparece assim:

```
>>> [ESPORTES] Sport vence o classico pernambucano
    Partida terminou 2x1 na Ilha do Retiro.
```

### Ver as conexoes simultaneas

Com varios usuarios conectados, digite `CONEXOES` em qualquer um deles:

```
> CONEXOES
OK 3 conexao(oes) simultanea(s), 3 thread(s) de cliente distinta(s), 4 thread(s) no processo (1 principal + 3 de cliente)
    127.0.0.1:39158 (voce) -> thread cliente-127.0.0.1:39158 id=139792801068736 viva=True
    127.0.0.1:39170 -> thread cliente-127.0.0.1:39170 id=139792792676032 viva=True
    127.0.0.1:39184 -> thread cliente-127.0.0.1:39184 id=139792784283328 viva=True
```

O numero de conexoes e igual ao numero de threads de cliente, e cada thread tem um id diferente. O total de threads do processo e sempre uma a mais, que e a thread principal esperando novas conexoes. O log do servidor tambem mostra a thread criada a cada conexao:

```
[NewsServer] Cliente conectado: ('127.0.0.1', 39158) | thread: cliente-127.0.0.1:39158 (id=139792801068736)
```

## Comandos do protocolo

Os comandos podem ser escritos em maiusculas ou minusculas, e os nomes de categoria tambem. Varias categorias podem ser separadas por virgula ou espaco.

| Comando | O que faz |
|---|---|
| `INSCREVER <cat>[, <cat>...]` | Passa a receber as noticias das categorias informadas. Categorias que nao existem sao listadas na resposta. |
| `CANCELAR <cat>[, <cat>...]` | Cancela a assinatura das categorias informadas. A categoria continua existindo no sistema. |
| `CATEGORIAS` | Lista as categorias que existem no sistema. |
| `MINHAS` | Lista as categorias que voce assina. |
| `PUBLICAR categoria\|titulo\|resumo` | Cadastra uma noticia e a envia na hora para todos os assinantes da categoria. |
| `ADICIONAR <cat>[, <cat>...]` | Cria categorias no sistema de forma permanente. |
| `REMOVER <cat>[, <cat>...]` | Apaga categorias do sistema de forma permanente. |
| `CONEXOES` | Mostra as conexoes simultaneas e a thread que atende cada cliente. |
| `RESTAURAR` | Restaura o banco de dados ao estado original. |
| `SAIR` | Encerra a sessao. |

Detalhes que vale saber:

- `CANCELAR` e `REMOVER` sao coisas diferentes. `CANCELAR` mexe so na sua assinatura. `REMOVER` apaga a categoria para todo mundo.
- `ADICIONAR` e `REMOVER` sao permanentes. A mudanca e gravada em `categorias.json` e continua valendo depois de reiniciar o servidor.
- Ao remover uma categoria, todos que a assinavam perdem a assinatura. Nao e possivel publicar em uma categoria que nao existe.
- Quando uma categoria e adicionada ou removida, todos os clientes conectados recebem uma mensagem `INFO` avisando.
- Nomes de categoria podem ter letras, numeros, hifen e underline. O caractere `|` nao e aceito.
- `RESTAURAR` apaga todas as noticias salvas e volta as categorias para tecnologia, esportes e cultura. Como existe um unico tipo de usuario, qualquer cliente pode usar esse comando, entao use com cuidado.
- No `PUBLICAR`, o titulo e o resumo nao podem conter o caractere `|`, porque ele e o separador do comando. Usar `|` a mais faz o servidor responder com o erro de uso.

## Armazenamento

O servidor cria dois arquivos na pasta em que e executado (ou na pasta do arquivo informado em `--arquivo`):

- `noticias.jsonl`: uma noticia por linha, em JSON, no formato abaixo. O texto e gravado em UTF-8, entao os acentos ficam legiveis.

  ```json
  {"ts": "2026-10-30 22:45:10", "categoria": "tecnologia", "titulo": "Nova versao do kernel Linux lancada", "resumo": "Release traz melhorias de desempenho e drivers."}
  ```

- `categorias.json`: a lista de categorias do sistema, por exemplo `["tecnologia", "esportes", "cultura"]`. Se o arquivo nao existir, ele e criado com as tres categorias padrao.

As noticias de uma categoria removida continuam no `noticias.jsonl` como historico. Para zerar tudo, use o comando `RESTAURAR` ou apague os dois arquivos com o servidor parado.

## Testes

Os testes sobem um servidor proprio em uma pasta temporaria, entao nao mexem nos seus arquivos de noticias e categorias. Na raiz do projeto:

```bash
python3 teste/teste.py
```

O parametro `--port` muda a porta usada (padrao 5050; alguns testes usam a porta seguinte). A saida esperada termina com:

```
57 ok, 0 falha(s)
```

O que e verificado:

- conexao, mensagem de boas-vindas e encerramento da sessao;
- `INSCREVER` e `CANCELAR`, inclusive com categoria inexistente e troca de assinatura no meio da sessao;
- entrega da noticia apenas para quem assinou a categoria, com acentos preservados;
- mensagens de erro do protocolo e continuidade da sessao depois de um erro;
- 10 clientes ao mesmo tempo recebendo a mesma noticia e 3 publicadores enviando em paralelo;
- `CONEXOES`: uma thread distinta para cada cliente, e as threads somem da lista quando os clientes saem;
- gravacao correta no arquivo de noticias;
- `RESTAURAR`, `ADICIONAR` e `REMOVER`, incluindo a conferencia de que as categorias continuam como estavam depois de reiniciar o servidor.

## Limitacoes conhecidas

- Nao ha autenticacao. Qualquer pessoa que alcance a porta do servidor pode publicar, mudar categorias e restaurar o banco.
- Quem se inscreve em uma categoria recebe apenas as noticias publicadas dali em diante. O historico salvo no arquivo nao e reenviado.
- O servidor usa uma thread por cliente, o que funciona bem para dezenas de conexoes, mas nao foi pensado para milhares.
- Um cliente que desconecta perde as assinaturas. Ao voltar, precisa assinar de novo (ou usar `--categorias`).

## Tecnologias utilizadas

- [Python 3](https://www.python.org/) - linguagem de programacao
- `socket` - comunicacao TCP
- `threading` - uma thread por cliente e locks para os dados compartilhados
- JSON Lines - formato de armazenamento das noticias