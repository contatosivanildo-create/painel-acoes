# CLAUDE.md — Guia do projeto para o Claude Code

Este arquivo orienta o Claude Code (e qualquer pessoa desenvolvedora) a trabalhar
neste repositório. Escrito em português do Brasil, como todo o restante do projeto.

---

## 1. Visão geral

**Painel de Ações** é um app web feito com **Streamlit** (Python) que mostra
cotações e performance de ações da B3 usando dados gratuitos do **Yahoo Finance**
(biblioteca `yfinance`).

O app tem **login obrigatório**, **dois perfis** (administrador e usuário comum),
**área de administração** e **carteira de ações por usuário**. Roda **localmente**
e também é **publicado na internet** via Railway + GitHub (ver seção 8).

Público-alvo do dono do projeto: **pessoa iniciante**. Prefira sempre a solução
mais simples e explique mudanças em linguagem acessível.

---

## 2. Como rodar

Todos os comandos são executados **dentro da pasta `exercicio 1`**.

```bash
# instalar dependências (primeira vez ou quando requirements.txt mudar)
python -m pip install -r requirements.txt

# rodar o app (abre em http://localhost:8501)
python -m streamlit run app.py

# rodar o teste automático da lógica (não abre navegador)
python smoke_test.py
```

> No Windows, use `python -m pip` e `python -m streamlit` — os comandos `pip` e
> `streamlit` podem não estar no PATH.

---

## 3. Configuração obrigatória

O login do **primeiro administrador** fica em `.streamlit/secrets.toml`
(fora do código, **não versionado**). Chaves:

| Chave             | Obrigatória | Uso                                             |
|-------------------|-------------|-------------------------------------------------|
| `ADMIN_USERNAME`  | sim         | usuário do primeiro admin                       |
| `ADMIN_PASSWORD`  | sim         | senha do primeiro admin (em texto, só aqui)     |
| `ADMIN_FULL_NAME` | não         | nome exibido (padrão: "Administrador")          |
| `ADMIN_EMAIL`     | não         | e-mail (padrão: "admin@exemplo.com")            |

Essas chaves são lidas **uma única vez**: quando o banco `data/app.db` ainda não
tem nenhum usuário (função `auth.bootstrap_first_admin`). Depois disso, o arquivo
fica praticamente inerte. Modelo em `.streamlit/secrets.toml.example`.

`auth._ler_secrets()` procura essas chaves em **duas fontes**, nesta ordem:
`.streamlit/secrets.toml` (uso local) e, para o que faltar, **variáveis de
ambiente** (uso no servidor, onde o arquivo não existe). Ver seção 8.

---

## 4. Arquitetura

Fluxo de uma requisição (arquivo `app.py`, de cima para baixo):

1. `database.init_db()` — cria as tabelas SQLite se não existirem.
2. `database.purge_expired_sessions()` — limpa sessões vencidas.
3. `auth.bootstrap_first_admin()` — cria o primeiro admin (ou levanta `ConfigError`).
4. `auth.get_logged_in_user()` — identifica o usuário pela sessão da aba ou pelo cookie.
   - Sem usuário → `auth.render_login_page()` + `st.stop()`.
5. Se `must_change_password` → `views.render_change_password_gate()` + `st.stop()`.
6. Menu lateral + `views.render_*_page()` conforme a escolha.

### Mapa de arquivos

| Arquivo            | Responsabilidade                                                        |
|--------------------|------------------------------------------------------------------------|
| `app.py`           | Ponto de entrada. Roteamento entre login, troca de senha e páginas.   |
| `auth.py`          | Hash de senha (bcrypt), senha temporária, bootstrap do 1º admin, cookie/sessão, tela de login. |
| `database.py`      | Acesso ao SQLite (`data/app.db`): tabelas `users`, `sessions`, `portfolio_items`. Uma conexão por operação. |
| `market_data.py`   | Busca no Yahoo Finance com cache de 15 min. Devolve `ResultadoMercado` (preços + não encontrados + erro de conexão). |
| `views.py`         | Desenho das páginas: Ações, Minha carteira, Minha conta, Administração. Toda a UI pós-login. |
| `smoke_test.py`    | Teste da lógica sem navegador. Usa um banco temporário via `STOCKS_APP_DB`. |
| `analise_ia.py`    | "Análise do Dia": monta o resumo numérico da carteira e chama a API da Anthropic (Claude Haiku 4.5) com streaming. Toda falha vira `AnaliseIndisponivel` → aviso amigável. |
| `agente_analise_instrucoes.md` | Instruções de sistema do agente (texto puro, editável sem tocar no código). |
| `.streamlit/config.toml`  | Tema visual e opções do Streamlit.                             |
| `.streamlit/secrets.toml` | Segredos locais (não versionado).                              |

### Banco de dados (SQLite, `data/app.db`)

```
users            (id, full_name, username UNIQUE NOCASE, email, role['admin'|'comum'],
                  password_hash, must_change_password, created_at)
sessions         (token PK, user_id -> users.id ON DELETE CASCADE, created_at, expires_at)
portfolio_items  (user_id -> users.id ON DELETE CASCADE, ticker, position, PK(user_id,ticker))
```

`PRAGMA foreign_keys = ON` é ativado em toda conexão (`database.get_connection`),
então apagar um usuário apaga em cascata as sessões e a carteira dele.

---

## 5. Decisões e convenções

- **Idioma**: tudo em pt-BR — UI, mensagens, nomes de funções/variáveis novas,
  comentários, docstrings, documentação.
- **Sem segredos no código**: nenhuma senha literal em arquivos `.py`. Senhas de
  usuários só existem como hash bcrypt no banco. A senha do 1º admin só em
  `secrets.toml`.
- **Persistência de login**: cookie de sessão (`extra-streamlit-components`
  `CookieManager`) guardando um token opaco (`secrets.token_urlsafe(32)`) que
  aponta para uma linha em `sessions` (validade de 7 dias). O `CookieManager` é
  criado uma vez por aba e guardado em `st.session_state["cookie_manager"]`.
- **Tickers B3**: entrada do usuário é normalizada para o formato Yahoo com
  sufixo `.SA` (`market_data.normalizar_ticker`). Exibição remove o sufixo
  (`market_data.exibir_ticker`).
- **Carteira nova**: começa com `PETR4.SA`, `ITUB4.SA`, `VALE3.SA`
  (`database.TICKERS_PADRAO`), aplicada em `seed_portfolio` na criação do usuário.
- **Erros do Yahoo**: nunca deixar estourar. `market_data` captura tudo e sinaliza
  `erro_de_conexao` (Yahoo mudo) ou `nao_encontrados` (código inválido); `views`
  transforma isso em `st.error` / `st.warning` amigável.
- **Mensagens entre recarregamentos**: padrão "flash" em `views._set_flash` /
  `views._render_flash` (guarda no `session_state`, mostra uma vez após `st.rerun`).
- **Senha temporária exibida uma vez**: guardada em
  `st.session_state["senha_temp_gerada"]` e apagada quando o admin clica
  "Ok, já anotei".
- **Proteções de admin** (em `views.render_admin_page`):
  - não excluir a si mesmo;
  - não rebaixar nem excluir o último administrador (`database.count_admins() <= 1`).

---

## 6. Testes

- **`python smoke_test.py`** cobre a lógica: bootstrap, hash/verify, senha
  temporária, CRUD de usuários + proteções, carteira, sessões (incl. expiração),
  normalização de ticker e uma chamada real ao Yahoo (pulada com aviso se estiver
  offline). Sai com código 1 se algo falhar.
- **Fluxo de UI** (login, cookie/F5, formulários) precisa de navegador — ver o
  roteiro no `README.md`.
- Ao mexer em `database.py` / `auth.py` / `market_data.py`, rode o smoke test
  antes de considerar pronto.

---

## 7. Ao evoluir o projeto

- Mantenha `app.py` fino: só roteamento. Lógica nova vai para o módulo do assunto.
- Funções de acesso a dados ficam em `database.py` e recebem/retornam tipos
  simples (`str`, `int`, `sqlite3.Row`, listas).
- Se adicionar uma coluna/tabela, faça `init_db` criar de forma idempotente
  (`CREATE TABLE IF NOT EXISTS` / `ALTER TABLE` protegido) — o banco do usuário
  já existe e não pode ser recriado do zero.
- Novas telas: uma função `render_*_page(user)` em `views.py` + uma entrada na
  lista `paginas` em `app.py`.
- Atualize `README.md` (linguagem para leigo) e este `claude.md` (técnico) a cada
  mudança relevante de comportamento ou de configuração.
- Nunca commite `data/` nem `.streamlit/secrets.toml` (já no `.gitignore`).

---

## 8. Publicação (Railway + GitHub)

O código vive no GitHub (repo público `painel-acoes`, raiz = conteúdo de
`exercicio 1`). O Railway está ligado a esse repo e **redeploya a cada push**
na branch `main`.

### Arquivos de publicação

| Arquivo | Papel |
|---|---|
| `requirements.txt` | Dependências com versão fixada (`==`). |
| `.python-version`  | Versão do Python no servidor (Nixpacks lê este arquivo). |
| `railway.json`     | `startCommand` do Streamlit (porta `$PORT`, `--server.address 0.0.0.0`, headless), `healthcheckPath = /_stcore/health`, restart `ON_FAILURE`. |
| `.env.example`     | Referência das variáveis do painel (sem valores reais). |

### Estado que precisa sobreviver a redeploy

O filesystem do Railway é efêmero. Um **Volume** montado em `/data` guarda o
SQLite; a variável `STOCKS_APP_DB=/data/app.db` aponta o `database.DB_PATH` para
lá. Sem o Volume, `users` / `sessions` / `portfolio_items` seriam recriados
vazios a cada deploy.

### Variáveis no painel do Railway (Service → Variables)

`STOCKS_APP_DB=/data/app.db`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` (obrigatórias),
`ADMIN_FULL_NAME`, `ADMIN_EMAIL` (opcionais). Lidas por `auth._ler_secrets()`
via `os.environ` quando não há `secrets.toml`. Nenhum segredo em arquivo
versionado.

### Yahoo Finance no servidor

`yfinance` a partir de IP de datacenter pode tomar `429`/bloqueio do Yahoo.
`market_data` já degrada com mensagem amigável (`erro_de_conexao`). Se acontecer
de forma persistente no servidor, avaliar: sessão HTTP com `User-Agent` de
navegador, retry/backoff, ou trocar de fonte de dados.

---

## 9. Análise do Dia (IA — API da Anthropic)

Botão flutuante (`position: fixed`, canto inferior direito) na página Ações →
`@st.dialog` que roda `analise_ia.gerar_analise` e mostra o texto via
`st.write_stream` (efeito de digitação).

### Fluxo

1. `views._render_analise_do_dia` injeta o CSS (classe `st-key-botao_analise_dia`,
   criada pelo `st.container(key=...)`), desenha o botão e, ao clicar, guarda o
   necessário em `st.session_state["analise_entrada"]` e abre a janela.
2. `views._janela_analise_do_dia` (dialog): reaproveita `st.session_state
   ["analise_guardada"]` se for a **mesma** `(user_id, tickers, período)` e tiver
   < 15 min; senão chama `analise_ia.montar_resumo` + `analise_ia.gerar_analise`.
3. `montar_resumo` recebe o `precos` já renomeado (colunas = código sem `.SA`) e a
   lista `nao_encontrados`. Calcula por ação: preço/data, variação no período,
   mín/máx com datas, distância da máxima, variação 5 pregões, tendência
   (MM20 × MM50, exige ≥ 50 pregões), volatilidade (desvio-padrão dos retornos
   diários). **A IA recebe só esse texto — nunca DataFrames nem gráficos.**
4. `gerar_analise(resumo, estado)` — gerador. `estado["ok"]` vira `True` só no
   sucesso; a tela só guarda no cache de 15 min quando `estado["ok"]`.

### Modelo e chave

- Modelo: `MODELO_IA = "claude-haiku-4-5"` (o mais barato: US$ 1/US$ 5 por Mtok).
  Sem `thinking`/`effort` (Haiku 4.5 não usa adaptive thinking).
- Chave: `analise_ia._ler_chave()` → `st.secrets["ANTHROPIC_API_KEY"]` e depois
  `os.environ["ANTHROPIC_API_KEY"]` (mesmo padrão do `auth._ler_secrets`).
  Local: `.streamlit/secrets.toml`. Servidor: variável no Railway. Nunca no código.

### Erros → mensagem amigável (constantes `_MSG_*` em `analise_ia.py`)

`AuthenticationError`/`PermissionDeniedError` → chave inválida;
`BadRequestError` com "credit"/"balance"/"quota" → sem crédito;
`RateLimitError` → ocupado; `APIConnectionError` → sem internet;
demais `APIStatusError`/exceções → indisponível. Nada estoura para a tela.

### Dependências novas

`anthropic` (SDK) e `tzdata` (fuso `America/Sao_Paulo` para carimbar a hora no
container Linux). Em `requirements.txt` com versão fixada.
