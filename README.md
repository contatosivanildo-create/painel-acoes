# Painel de Ações

App que mostra a **cotação** e a **performance (%)** de ações da B3 (Bolsa
brasileira), com dados gratuitos do **Yahoo Finance**. Agora com **login**,
**área de administração** e **carteira de ações por usuário**.

O app **roda no seu computador** e também pode ser **publicado na internet**
(veja a seção "Publicar na internet", mais abaixo).

---

## O que o app faz

- **Login com usuário e senha.** Sem entrar, a pessoa só vê a tela de entrada.
- **Continua logado** depois de apertar F5 ou fechar e abrir o navegador (por
  alguns dias). Tem botão **"Sair"**.
- **Dois tipos de usuário:** administrador e comum.
- **Área de Administração** (só o administrador vê):
  - tabela com todos os usuários (nome completo, usuário, e-mail, tipo);
  - **criar usuário** — o app gera uma **senha temporária** e mostra na tela
    **uma única vez**, para você entregar à pessoa;
  - **redefinir senha** de alguém (gera outra senha temporária) — é assim que se
    resolve o "esqueci minha senha";
  - **promover** um usuário comum a administrador e **rebaixar** de volta;
  - **excluir** usuário;
  - **proteções:** você não pode excluir a si mesmo nem rebaixar/excluir o
    último administrador.
- **Senha temporária:** quem entra com ela é obrigado a criar uma senha nova
  antes de usar o resto do app.
- **"Minha conta":** qualquer usuário troca a própria senha quando quiser.
- **"Minha carteira":** cada usuário tem a sua lista de ações. Começa com
  **PETR4, ITUB4 e VALE3**. Dá para adicionar (digitando o código, ex.: `WEGE3`)
  e remover. Fica salva.
- **"Ações":** cartões com o preço atual e a variação, dois gráficos (cotação e
  performance), tabela de resumo e **botão para baixar os dados em CSV**.
  Botões de período: **1 mês, 3 meses, 6 meses, no ano, 1 ano e máximo**.
- **Dados atualizados a cada 15 minutos** (não recarrega tudo a cada clique).
- **Mensagens amigáveis:** se o Yahoo não responder ou o código da ação não
  existir, aparece um aviso claro — nunca uma tela de erro técnica.
- **Nada se perde:** usuários, senhas e carteiras continuam existindo depois de
  fechar e abrir o app.

As senhas são guardadas de forma segura (embaralhadas com *bcrypt*) e **nenhuma
senha fica escrita no código**.

---

## O que tem nesta pasta

| Item | Para que serve |
|---|---|
| `app.py` | O app em si (é o que você roda). |
| `auth.py`, `database.py`, `market_data.py`, `views.py` | Partes internas do app (login, banco de dados, dados do Yahoo, telas). |
| `requirements.txt` | Lista das bibliotecas necessárias. |
| `.streamlit/config.toml` | Aparência do app. |
| `.streamlit/secrets.toml` | **Onde você define o primeiro administrador** (veja abaixo). |
| `.streamlit/secrets.toml.example` | Um modelo de exemplo do arquivo acima. |
| `smoke_test.py` | Teste automático da lógica (não abre o navegador). |
| `data/` | Criada sozinha quando o app roda. Guarda o banco `app.db`. |
| `README.md` | Este guia. |
| `claude.md` | Documentação técnica (para quem for programar). |

---

## Passo a passo para rodar

Todos os comandos são digitados **no terminal**, **dentro desta pasta**
(`exercicio 1`).

### 1. Ter o Python instalado (só na primeira vez)

No terminal, digite:

```
python --version
```

Se aparecer algo como `Python 3.12` (ou maior), está ok. Se der erro, instale em
<https://www.python.org/downloads/> e **marque a opção "Add Python to PATH"**
durante a instalação.

### 2. Instalar as bibliotecas do app (primeira vez)

```
python -m pip install -r requirements.txt
```

Isso instala Streamlit, yfinance, pandas, Plotly, bcrypt e
extra-streamlit-components.

### 3. Definir o primeiro administrador

1. Abra o arquivo **`.streamlit/secrets.toml`** (clique nele no VS Code).
2. Troque o valor de **`ADMIN_PASSWORD`** (o texto entre aspas) por uma senha sua.
   Exemplo:

   ```toml
   ADMIN_USERNAME  = "admin"
   ADMIN_PASSWORD  = "COLOQUE-AQUI-UMA-SENHA-SUA"
   ADMIN_FULL_NAME = "Seu Nome"
   ADMIN_EMAIL     = "voce@exemplo.com"
   ```

3. Se quiser, troque também `ADMIN_USERNAME` (o padrão é `admin`).
4. Salve o arquivo (**Ctrl + S**).

> Esse usuário e senha são usados **uma única vez**: na primeira vez que o app
> roda, para criar o administrador. Depois disso, você pode trocar a senha dentro
> do app, em **Minha conta**.

### 4. Rodar o app

```
python -m streamlit run app.py
```

O navegador abre sozinho em `http://localhost:8501` com a **tela de login**.

Para rodar de novo em outro dia, basta repetir só este comando.

### 5. Fechar o app

Volte ao terminal onde ele está rodando e aperte **Ctrl + C**.

---

## Como entrar pela primeira vez

1. Rode o app (passo 4 acima).
2. Na tela de login, digite o **`ADMIN_USERNAME`** e o **`ADMIN_PASSWORD`** que
   você colocou no `secrets.toml`.
3. Clique em **Entrar**. Você cai na página **Ações**, com o menu lateral à
   esquerda e o seu nome embaixo dele.

---

## Como criar usuários para outras pessoas

1. Entre como administrador.
2. No menu lateral, clique em **Administração**.
3. Na seção **Criar novo usuário**, preencha **nome completo**, **nome de
   usuário** e **e-mail** e clique em **Criar usuário e gerar senha temporária**.
4. O app mostra uma **senha temporária** numa caixa verde. **Anote agora** (tem um
   botão de copiar) — ela não aparece de novo. Clique em **Ok, já anotei**.
5. Entregue à pessoa o **nome de usuário** e a **senha temporária**.
6. Quando ela entrar, o app vai **obrigá-la a criar uma senha nova**.

**Esqueci minha senha:** a pessoa te avisa; você vai em **Administração**,
escolhe o usuário em **Gerenciar um usuário** e clica em **Redefinir senha**.
Uma nova senha temporária aparece — repasse para ela.

---

## Roteiro de teste (faça você mesmo, no navegador)

Com o app rodando (`python -m streamlit run app.py`):

1. **Tela de login aparece sozinha.** Abra `http://localhost:8501`. Você só deve
   ver a tela de entrada — nada de gráficos.
2. **Login do admin.** Entre com o usuário/senha do `secrets.toml`. Deve abrir a
   página **Ações** com o menu lateral.
3. **Gráficos e período.** Na página Ações, clique nos períodos (1 mês, 3 meses,
   ..., Máximo). Os gráficos e os cartões devem mudar. Clique em **Baixar
   cotações em CSV** — um arquivo `cotacoes.csv` deve ser baixado.
4. **Criar usuário.** Vá em **Administração** → **Criar novo usuário**. Crie um
   usuário de teste (ex.: nome "Maria Teste", usuário "maria", e-mail
   "maria@teste.com"). **Anote a senha temporária** mostrada.
5. **Sair e entrar como o novo usuário.** Clique em **Sair**. Entre com "maria" e
   a senha temporária. O app deve **obrigar a criar uma nova senha**. Crie uma
   (mínimo 8 caracteres).
6. **Carteira.** Como "maria", vá em **Minha carteira**. Adicione `WEGE3` e
   remova `VALE3`. Aperte **F5**: a carteira deve continuar como você deixou e
   você deve continuar logado.
7. **Código inválido.** Ainda em Minha carteira, tente adicionar `ABCD1`. Deve
   aparecer um **aviso amigável** dizendo que a ação não foi encontrada — nunca
   um erro técnico.
8. **Trocar senha.** Vá em **Minha conta** e troque a senha (informando a senha
   atual). Deve aparecer "Senha atualizada com sucesso".
9. **Proteções do admin.** Saia e entre de novo como **admin**. Em
   **Administração** → **Gerenciar um usuário**, escolha o próprio admin, marque
   "Confirmar exclusão" e clique em **Excluir usuário**: deve aparecer "Você não
   pode excluir a si mesmo". Tente **Rebaixar para comum** o único admin: deve
   aparecer "Não é possível rebaixar o último administrador".
10. **Nada se perde.** Feche o app (Ctrl + C no terminal) e rode de novo. Entre:
    os usuários e as carteiras devem estar lá.

Para testar só a lógica (sem navegador), rode:

```
python smoke_test.py
```

Deve terminar com **"RESULTADO: tudo passou"**.

---

## Publicar na internet (Railway + GitHub)

O app pode ficar disponível num link público, com HTTPS, sem depender do seu
computador ligado. A publicação usa dois serviços gratuitos:

- **GitHub** — guarda o código.
- **Railway** — roda o app. Toda vez que você envia uma versão nova para o
  GitHub, o Railway publica sozinho.

### Arquivos que fazem a publicação funcionar

| Arquivo | Para que serve |
|---|---|
| `requirements.txt` | Versões exatas das bibliotecas (publicação previsível). |
| `.python-version` | Fixa a versão do Python usada no servidor. |
| `railway.json` | Diz ao Railway o comando para ligar o app e como checar se ele está de pé. |
| `.env.example` | **Modelo** das variáveis que você configura no painel do Railway (não tem segredo de verdade). |

### O que configurar no painel do Railway

1. **Volume (disco permanente)** montado em `/data`. É o que impede que os
   usuários e as carteiras sumam quando o app reinicia ou você publica de novo.
2. **Variables (variáveis):**

   | Variável | Valor | Para quê |
   |---|---|---|
   | `STOCKS_APP_DB` | `/data/app.db` | Guarda o banco de dados no disco permanente. |
   | `ADMIN_USERNAME` | (o usuário do 1º admin) | Login do primeiro administrador. |
   | `ADMIN_PASSWORD` | (uma senha forte) | Senha do primeiro administrador. |
   | `ADMIN_FULL_NAME` | (seu nome) | Opcional — nome exibido. |
   | `ADMIN_EMAIL` | (seu e-mail) | Opcional. |

   As variáveis `ADMIN_*` são usadas **uma única vez**, para criar o primeiro
   administrador. Depois disso, troque a senha dentro do app, em **Minha conta**.
   Nenhuma senha fica em arquivo — só no painel do Railway.

3. **Gerar o domínio público** (botão "Generate Domain"): você recebe um
   endereço `https://...up.railway.app`.

> No seu computador **nada muda**: o login do primeiro administrador continua
> vindo de `.streamlit/secrets.toml`. As variáveis do Railway só valem no
> servidor, onde esse arquivo não existe.

---

## Análise do Dia (inteligência artificial)

Na página **Ações** há um botão redondo no **canto inferior direito da tela**,
sempre visível, chamado **"Análise do Dia"**. Ao clicar, abre uma janela onde um
**analista de IA** escreve, ao vivo, um comentário didático sobre a sua carteira
**no período selecionado** (1 mês, 3 meses, ..., máximo).

- O app monta um **resumo só com números** de cada ação (preço e data, variação
  no período, mínima/máxima com datas, distância da máxima, variação nos últimos
  5 pregões, tendência de 20 x 50 dias e volatilidade) e manda **apenas isso**
  para a IA. Ela **não** recebe os gráficos e é instruída a **nunca inventar**
  notícias, balanços ou previsões.
- O texto traz um parágrafo de visão geral, **"Vale olhar com atenção"** (até 2
  ações), **"Sinal de cautela"** (até 2 ações) e um aviso de que **não é
  recomendação de investimento**.
- **Economia:** se você clicar de novo com a mesma carteira e o mesmo período
  dentro de **15 minutos**, o app **reaproveita** a análise e mostra
  "gerada às HH:MM" — sem gastar de novo.
- **Se algo faltar** (chave não configurada, chave errada, crédito acabou, IA
  fora do ar), a janela mostra um **aviso amigável** — o resto do app continua
  funcionando normalmente.

O texto das instruções do analista fica no arquivo
**`agente_analise_instrucoes.md`** — você pode ajustá-lo quando quiser, sem
mexer no código.

### Modelo e custo

Usa o modelo **mais barato da Anthropic, o Claude Haiku 4.5**
(US$ 1 por milhão de "tokens" de entrada, US$ 5 por milhão de saída).
Cada análise custa **cerca de US$ 0,004 a US$ 0,01** — menos de um centavo de
dólar, algo como **R$ 0,02 a R$ 0,05**. 200 análises no mês ≈ **US$ 1 a US$ 2**.

### Configurar a chave de acesso

A chave **nunca** fica no código nem vai para o GitHub. São dois lugares:

**a) No seu computador** (só se você for rodar localmente): abra
`.streamlit/secrets.toml` e adicione a linha:

```toml
ANTHROPIC_API_KEY = "sk-ant-...a-sua-chave..."
```

Salve (Ctrl+S) e atualize a página (F5).

**b) No Railway** (o site publicado): painel do serviço → aba **Variables** →
**+ New Variable** → nome `ANTHROPIC_API_KEY`, valor a sua chave → **Add** →
**Deploy**. É o mesmo procedimento da senha `ADMIN_PASSWORD`.

Para **criar** uma chave: entre em <https://console.anthropic.com>, adicione um
crédito pequeno (ex.: US$ 5) em **Billing**, e gere a chave em
**Settings → API keys**. Guarde a chave num lugar seguro — ela só aparece uma vez.

---

## Problemas comuns e solução

- **"python não é reconhecido" / "streamlit não é reconhecido"**
  Feche e abra o terminal depois de instalar o Python. Use sempre
  `python -m pip ...` e `python -m streamlit run app.py` (com o `python -m` na
  frente).

- **A tela mostra "O app ainda não tem nenhum usuário e eu não encontrei o
  login do primeiro administrador"**
  O arquivo `.streamlit/secrets.toml` está sem `ADMIN_USERNAME` ou
  `ADMIN_PASSWORD`. Abra o arquivo, preencha os dois, salve e atualize a página
  (F5). Confira que existe a pasta `.streamlit` e que o arquivo se chama
  exatamente `secrets.toml`.

- **Mudei a senha no `secrets.toml` e nada aconteceu**
  Esse arquivo só vale na **primeira vez**, quando ainda não há usuários. Para
  trocar sua senha depois, use **Minha conta** dentro do app. (Se quiser mesmo
  recomeçar do zero, veja o item seguinte.)

- **Quero apagar tudo e começar de novo**
  Feche o app e apague o arquivo `data/app.db`. Na próxima vez que rodar, o app
  recria o banco e o primeiro administrador a partir do `secrets.toml`.
  Atenção: isso apaga **todos** os usuários e carteiras.

- **"Não conseguimos falar com o Yahoo Finance agora"**
  Confira sua internet e tente de novo em alguns minutos. O app busca os dados a
  cada 15 minutos; enquanto isso, usa o que já tinha baixado.

- **Adicionei uma ação e apareceu "não encontrei a ação"**
  Confira o código na B3 (ex.: `PETR4`, `ITUB4`, `WEGE3`, `BBAS3`). O app
  completa sozinho com `.SA` (formato do Yahoo). Ações que não são da B3 podem
  não funcionar.

- **Continuo caindo na tela de login mesmo com usuário e senha certos**
  Verifique se o navegador está **bloqueando cookies** para `localhost`. O app
  usa um cookie para manter você logado.

- **Esqueci a senha do administrador e não consigo entrar**
  Se houver outro administrador, peça a ele para redefinir a sua senha. Se o
  admin for o único usuário, apague `data/app.db` (item acima) e comece de novo
  com o `secrets.toml`.
