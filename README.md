# Feed de notícias PUB/SUB com sockets TCP

APS 01 de Redes de Computadores, Equipe 04.

Sistema cliente-servidor que funciona como um feed de notícias contínuo no modelo PUB/SUB. O servidor mantém uma lista de categorias e um repositório de notícias em arquivo. Os clientes se conectam por um socket TCP persistente, escolhem as categorias de interesse e recebem cada notícia nova assim que ela é publicada, sem precisar fazer uma requisição extra. As assinaturas podem ser alteradas durante a sessão.

## Sumário

- [Estrutura do repositório](#estrutura-do-repositório)
- [Arquitetura](#arquitetura)
- [Protocolo](#protocolo)
- [Armazenamento](#armazenamento)
- [Como executar](#como-executar)
- [Testes](#testes)
- [Requisitos do enunciado](#requisitos-do-enunciado)
- [Estado atual](#estado-atual)

## Estrutura do repositório

```
aps01-grupo04/
├── client/
│   ├── NewsClient.py    # cliente base: conexão, envio de comandos e recebimento das notícias
│   ├── assinante.py     # cliente que se inscreve em categorias e recebe notícias
│   └── publicador.py    # cliente "editor" que publica notícias
├── server/
│   ├── NewsServer.py    # servidor TCP, sessões e interpretação dos comandos
│   └── NewsEngine.py    # lógica PUB/SUB: assinaturas, publicação e armazenamento
└── teste/
    └── teste.py         # testes de ponta a ponta com servidor e clientes reais
```

Foi utilizada apenas a biblioteca padrão do Python 3.

## Arquitetura

### Servidor

O servidor foi dividido em duas partes: a camada de rede (`NewsServer`) e a lógica PUB/SUB (`NewsEngine`).

- `NewsServer` abre o socket de escuta e, para cada conexão aceita, cria uma `ClienteSessao` e uma thread dedicada. Essa thread lê os comandos do cliente linha a linha e repassa para o `NewsEngine`.
- `ClienteSessao` guarda o socket, o endereço e as assinaturas de um cliente. O envio de mensagens é feito sob um lock próprio, para que uma resposta e uma notícia vinda de outra thread não se misturem no mesmo socket.
- `NewsEngine` mantém a lista de sessões conectadas, gerencia as assinaturas e faz a publicação: grava a notícia no arquivo e envia para as sessões inscritas na categoria.

Fluxo de uma publicação:

1. O publicador envia `PUBLICAR categoria|titulo|resumo`.
2. O servidor valida os campos e a categoria.
3. A notícia é gravada no arquivo de armazenamento.
4. É feita uma cópia da lista de sessões inscritas na categoria.
5. Cada sessão inscrita recebe `NOTICIA|categoria|titulo|resumo`.
6. O publicador recebe a quantidade de clientes que receberam a notícia.

Sobre a concorrência, foram usados três locks: um para a lista de sessões e as assinaturas, um para o arquivo de notícias e um por sessão para o envio. O envio das notícias acontece fora do lock das sessões, a partir de uma cópia dos destinatários. Dessa forma, um cliente lento não bloqueia as inscrições dos outros. Entretanto, o envio é sequencial na thread de quem publicou, então um cliente lento ainda atrasa a entrega para os seguintes.

### Cliente

O `NewsClient` concentra a parte de rede dos clientes. Ao conectar, ele abre uma thread que lê o socket continuamente e separa as mensagens pelo prefixo:

- `NOTICIA|...` vai para o handler de notícias, definido com `set_news_handler`;
- `INFO ...` vai para o handler de informações, definido com `set_info_handler`;
- o resto (`OK` e `ERRO`) vai para uma fila de respostas, lida por `send_command`.

Por isso uma notícia pode chegar a qualquer momento, inclusive enquanto o cliente espera a resposta de um comando, sem atrapalhar essa resposta. Os comandos do protocolo têm métodos próprios: `subscribe`, `unsubscribe`, `list_categories`, `my_subscriptions`, `publish` e `quit`.

O `publicador.py` usa o `NewsClient` em dois modos: interativo, pedindo categoria, título e resumo no terminal, ou automático (`--auto`), publicando uma lista de notícias de exemplo em ciclo, a cada `--intervalo` segundos.

## Protocolo

As mensagens são texto em UTF-8, uma por linha. Os comandos não diferenciam maiúsculas de minúsculas.

Categorias disponíveis: `tecnologia`, `esportes`, `cultura`.

### Comandos do cliente

| Comando | Exemplo | Resposta |
|---------|---------|----------|
| `INSCREVER` | `INSCREVER tecnologia, esportes` | `OK inscrito em: tecnologia, esportes` |
| `REMOVER` | `REMOVER tecnologia` | `OK removido: tecnologia` |
| `CATEGORIAS` | `CATEGORIAS` | `OK tecnologia, esportes, cultura` |
| `MINHAS` | `MINHAS` | `OK esportes` ou `OK (nenhuma assinatura)` |
| `PUBLICAR` | `PUBLICAR esportes\|Final do campeonato\|Resumo da partida` | `OK publicada para N assinante(s)` |
| `SAIR` | `SAIR` | `OK ate logo` e a conexão é encerrada |

Em `INSCREVER` e `REMOVER`, as categorias podem ser separadas por vírgula ou espaço. Categorias inexistentes em `INSCREVER` são informadas na própria resposta (`| categorias inexistentes: ...`), e as válidas são inscritas normalmente.

Erros de uso retornam uma linha começando com `ERRO`, por exemplo `ERRO uso: PUBLICAR categoria|titulo|resumo` ou `ERRO comando desconhecido`.

### Mensagens enviadas pelo servidor

| Mensagem | Quando |
|----------|--------|
| `INFO Bem-vindo! Categorias: tecnologia, esportes, cultura. Use INSCREVER <categoria>.` | ao conectar |
| `NOTICIA\|categoria\|titulo\|resumo` | a cada notícia publicada em uma categoria assinada |

### Exemplo de sessão

Assinante:

```
<- INFO Bem-vindo! Categorias: tecnologia, esportes, cultura. Use INSCREVER <categoria>.
-> INSCREVER tecnologia, esportes
<- OK inscrito em: tecnologia, esportes
-> REMOVER tecnologia
<- OK removido: tecnologia
<- NOTICIA|esportes|Final do campeonato|Resumo da partida
```

Publicador, em outra conexão:

```
<- INFO Bem-vindo! Categorias: tecnologia, esportes, cultura. Use INSCREVER <categoria>.
-> PUBLICAR esportes|Final do campeonato|Resumo da partida
<- OK publicada para 1 assinante(s)
```

O servidor não diferencia assinantes de publicadores. Qualquer conexão pode publicar e se inscrever.

## Armazenamento

As notícias são gravadas em um arquivo JSON Lines (`noticias.jsonl` por padrão, no diretório onde o servidor é executado), uma por linha:

```json
{"ts": "2026-10-30 14:00:00", "categoria": "esportes", "titulo": "Final do campeonato", "resumo": "Resumo da partida"}
```

Ao iniciar, o servidor conta as notícias já existentes no arquivo e mostra o total no log. O histórico não é reenviado para clientes novos, eles recebem apenas as notícias publicadas depois da inscrição.

## Como executar

Requisito: Python 3.

### Servidor

O servidor usa imports a partir do pacote `server`, por isso deve ser executado da raiz do repositório como módulo:

```bash
python -m server.NewsServer
```

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `--host` | `0.0.0.0` | endereço de escuta |
| `--port` | `5000` | porta TCP |
| `--arquivo` | `noticias.jsonl` | arquivo de armazenamento das notícias |

O servidor é encerrado com `Ctrl+C`.

### Publicador

Os clientes importam o `NewsClient` pelo nome, então são executados de dentro da pasta `client`:

```bash
cd client && python publicador.py --auto --intervalo 3
```

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `--host` | `127.0.0.1` | endereço do servidor |
| `--port` | `5000` | porta do servidor |
| `--auto` | desligado | publica as notícias de exemplo em ciclo |
| `--intervalo` | `5.0` | segundos entre publicações no modo automático |

Sem `--auto`, o publicador pede categoria, título e resumo no terminal.

### Assinante

Enquanto o `assinante.py` não está pronto, dá para testar com `nc` (ou `telnet`) e digitar os comandos do protocolo:

```bash
nc localhost 5000
```

## Testes

O `teste/teste.py` testa o sistema de ponta a ponta. Ele sobe o próprio servidor na porta 5050, com o arquivo de notícias numa pasta temporária, e conecta clientes reais usando o `NewsClient`. Para rodar, a partir da raiz do repositório:

```bash
python teste/teste.py
```

O parâmetro `--port` muda a porta do servidor de teste. Foram cobertos:

| Grupo | O que é conferido |
|-------|-------------------|
| Conexão | mensagem de boas-vindas, `CATEGORIAS` e `SAIR` |
| Inscrição e remoção | `INSCREVER`, `REMOVER` e `MINHAS`, categoria inexistente, categoria não assinada e maiúsculas |
| Publicação e entrega | notícia chega só para quem assinou, troca de assinatura no meio da sessão e acentos |
| Erros do protocolo | todas as respostas `ERRO` e a sessão continuando aberta depois delas |
| Clientes simultâneos | 10 assinantes recebendo a mesma notícia e 3 editores publicando em paralelo |
| Armazenamento | quantidade de registros no arquivo, campos de cada registro e acentos gravados |

Cada verificação aparece como `[ok]` ou `[falha]`, e no fim é mostrado o total. Se algo falhar, o script mostra também a saída do servidor. Uma exceção dentro de um grupo conta como falha e não impede os grupos seguintes.

## Requisitos do enunciado

| Requisito | Situação |
|-----------|----------|
| Comunicação cliente-servidor com sockets TCP | servidor e `NewsClient` implementados |
| Lista de categorias no servidor | `tecnologia`, `esportes`, `cultura` |
| Repositório de notícias em memória ou arquivo | arquivo JSON Lines |
| Envio imediato de título, resumo e categoria aos inscritos | mensagem `NOTICIA` enviada logo após a gravação |
| Socket TCP persistente com escolha de categorias | `INSCREVER` no servidor e no `NewsClient`, `assinante.py` pendente |
| Alteração das assinaturas durante a sessão | `INSCREVER` e `REMOVER` a qualquer momento |
| Várias conexões simultâneas | uma thread por cliente |
| Preferências por cliente e envio só das notícias relevantes | assinaturas guardadas por sessão e filtradas na publicação |
| Notícias enviadas por um "editor" | `publicador.py`, nos modos interativo e automático |

## Estado atual

Na versão atual, o servidor não sobe. Rodando `python teste/teste.py`, o servidor encerra antes de abrir a porta com o erro abaixo:

```
ImportError: cannot import name 'NewsEngine' from partially initialized module 'server.NewsEngine' (most likely due to a circular import)
```

Pendências:

- [ ] Import circular entre `NewsServer.py` e `NewsEngine.py`, já que os dois se importam no topo. Uma saída é mover `CATEGORIES` para um módulo próprio (por exemplo `server/config.py`).
- [ ] `socket.SOCK_TCP` não existe em `NewsServer.start`, o correto é `socket.SOCK_STREAM`.
- [ ] Nomes de métodos diferentes entre os dois arquivos: o servidor chama `register_sessao`, `subscribe`, `unsubscribe`, `subscriptions_of` e `publish`, enquanto o engine define `registrar_sessao`, `assinar`, `nao_assinar`, `assinaturas_da_sessao` e `publicar`.
- [ ] `handle_client` usa `sessao.addr`, mas o atributo de `ClienteSessao` se chama `enderco`.
- [ ] `ClienteSessao` não inicializa `subscriptions` (deveria ter `self.subscriptions = set()`).
- [ ] `NewsEngine.py` faz `from time import time` e depois chama `time.strftime`. O correto é `import time`.
- [ ] `client/assinante.py` está vazio.
- [ ] `is_authenticated` em `ClienteSessao` não é usado.

Só o primeiro item foi confirmado executando o código. Os outros foram levantados pela leitura e devem aparecer nos testes conforme os anteriores forem corrigidos.
