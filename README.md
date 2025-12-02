# Bot de Templates com Links - Telegram

Bot do Telegram em Python que permite salvar mensagens com templates contendo links e enviá-las formatadas em HTML.

## Funcionalidades

- ✅ Salvar templates de mensagens com variáveis de link no formato `{link = texto}`
- ✅ Suporte a múltiplos links na mesma mensagem
- ✅ Armazenar templates em banco de dados SQLite
- ✅ Enviar mensagens formatadas em HTML com links embutidos
- ✅ Listar todos os templates salvos
- ✅ Deletar templates

## Instalação

1. Clone ou baixe este repositório

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Configure o token do bot:
   - Copie o arquivo `.env.example` para `.env`
   - Edite o arquivo `.env` e adicione seu token do bot:
   ```
   BOT_TOKEN=seu_token_do_telegram
   ```
   - Para obter um token, converse com [@BotFather](https://t.me/BotFather) no Telegram

## Como Usar

1. Inicie o bot:
```bash
python bot.py
```

2. No Telegram, encontre seu bot e envie `/start`

3. Para salvar um template:
   - Envie uma mensagem com o formato: `{link = palavra ou frase}`
   - Exemplo com um link: `Olá {link = clique aqui} para mais informações`
   - Exemplo com múltiplos links: `Olá {link = clique aqui} tudo certo {link = me responde}`
   - O bot irá detectar e pedir os URLs dos links na ordem
   - Envie os URLs um por vez (ex: `https://example.com`)

4. Para listar templates: `/listar`

5. Para enviar um template formatado: `/enviar <id>`
   - Exemplo: `/enviar 1`

6. Para deletar um template: `/deletar <id>`

## Exemplos

### Salvar um template com um link:
```
Você: Olá {link = boa tarde} como vai?

Bot: ✅ Template detectado com 1 link(s)!
     📝 Template: Olá boa tarde como vai?
     🔗 Link 1: segmento "boa tarde"
     Envie o URL do primeiro link (1/1)...

Você: https://example.com

Bot: ✅ Template salvo com sucesso!
     ID: 1
```

### Salvar um template com múltiplos links:
```
Você: Olá {link = clique aqui} tudo certo {link = me responde}

Bot: ✅ Template detectado com 2 link(s)!
     📝 Template: Olá clique aqui tudo certo me responde
     🔗 Link 1: segmento "clique aqui"
     🔗 Link 2: segmento "me responde"
     Envie o URL do primeiro link (1/2)...

Você: https://example.com

Bot: ✅ Link 1/2 recebido!
     Agora envie o URL para o segmento "me responde" (2/2)...

Você: https://telegram.org

Bot: ✅ Template salvo com sucesso!
     ID: 2
     Total de links: 2
```

### Enviar template formatado:
```
Você: /enviar 1

Bot: [Mensagem formatada com link HTML]
     ✅ Mensagem enviada com link formatado!
```

## Estrutura do Banco de Dados

O banco SQLite (`bot_database.db`) contém duas tabelas:

**Tabela `templates`:**
- `id`: ID único do template
- `template_mensagem`: Mensagem completa do template
- `created_at`: Data de criação

**Tabela `template_links`:**
- `id`: ID único do link
- `template_id`: ID do template (chave estrangeira)
- `segmento_com_link`: Texto que contém o link
- `link_da_mensagem`: URL do link
- `ordem`: Ordem do link no template (1, 2, 3...)

## Comandos Disponíveis

- `/start` - Inicia o bot e mostra informações
- `/help` - Mostra ajuda
- `/listar` - Lista todos os templates salvos
- `/enviar <id>` - Envia um template formatado
- `/deletar <id>` - Deleta um template

## Estrutura do Projeto

```
bot-post/
├── bot.py           # Código principal do bot
├── database.py      # Gerenciamento do banco SQLite
├── parser.py        # Parser para variáveis de link
├── requirements.txt # Dependências Python
├── .env.example     # Exemplo de configuração
├── README.md        # Este arquivo
└── bot_database.db  # Banco de dados (criado automaticamente)
```

## Notas

- O bot suporta múltiplas variáveis `{link = ...}` na mesma mensagem
- As mensagens são formatadas em HTML para o Telegram
- O banco de dados é criado automaticamente na primeira execução
- Quando há múltiplos links, você deve fornecer os URLs na ordem em que aparecem na mensagem

