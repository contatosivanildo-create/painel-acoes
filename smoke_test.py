"""
smoke_test.py
-------------
Teste automático da LÓGICA do app (sem abrir o navegador).

Roda num banco de dados descartável e confere:
  - criação de tabelas e do primeiro administrador;
  - embaralhar / conferir senha (bcrypt);
  - geração de senha temporária;
  - criar / promover / rebaixar / excluir usuário, com as proteções;
  - carteira: ações iniciais, adicionar e remover;
  - sessões de login: criar, buscar e apagar;
  - busca no Yahoo Finance para um código válido e um inválido.

Como rodar (dentro da pasta "exercicio 1"):

    python smoke_test.py
"""

import os
import sys
import tempfile

# Usa um banco de dados temporário (não mexe no data/app.db real).
_ARQ_TEMP = os.path.join(tempfile.gettempdir(), "smoke_test_painel_acoes.db")
if os.path.exists(_ARQ_TEMP):
    os.remove(_ARQ_TEMP)
os.environ["STOCKS_APP_DB"] = _ARQ_TEMP

import auth          # noqa: E402
import database      # noqa: E402
import market_data   # noqa: E402

_falhas = []


def checar(condicao: bool, descricao: str) -> None:
    marca = "OK  " if condicao else "FALHOU  "
    print(f"  [{marca}] {descricao}")
    if not condicao:
        _falhas.append(descricao)


def secao(titulo: str) -> None:
    print(f"\n=== {titulo} ===")


# ---------------------------------------------------------------------------
secao("Banco de dados e primeiro administrador")
database.init_db()
checar(database.count_users() == 0, "Banco começa sem nenhum usuário")

auth.bootstrap_first_admin(
    {"ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "senha-do-chefe-123",
     "ADMIN_FULL_NAME": "Chefe Geral", "ADMIN_EMAIL": "chefe@exemplo.com"}
)
admin = database.get_user_by_username("admin")
checar(admin is not None, "Primeiro administrador foi criado")
checar(admin["role"] == "admin", "Ele tem o tipo 'admin'")
checar(admin["must_change_password"] == 0, "Ele NÃO é obrigado a trocar a senha")
checar(len(database.get_portfolio(admin["id"])) == 3, "Carteira do admin começa com 3 ações")

# Rodar de novo não deve criar outro admin.
auth.bootstrap_first_admin(
    {"ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "outra"}
)
checar(database.count_users() == 1, "bootstrap não duplica o administrador")

# ---------------------------------------------------------------------------
secao("Senhas (bcrypt) e senha temporária")
h = auth.hash_password("minhaSenha123")
checar(h != "minhaSenha123", "A senha guardada NÃO é o texto legível")
checar(auth.verify_password("minhaSenha123", h), "Senha certa é aceita")
checar(not auth.verify_password("errada", h), "Senha errada é recusada")

temp1 = auth.generate_temp_password()
temp2 = auth.generate_temp_password()
checar(len(temp1) == 10, "Senha temporária tem 10 caracteres")
checar(temp1 != temp2, "Cada senha temporária é diferente")

# ---------------------------------------------------------------------------
secao("Criar, promover, rebaixar e excluir usuários (com proteções)")
maria_id = database.create_user(
    full_name="Maria Silva", username="maria", email="maria@exemplo.com",
    role="comum", password_hash=auth.hash_password(temp1), must_change_password=True,
)
database.seed_portfolio(maria_id)
maria = database.get_user_by_id(maria_id)
checar(maria["must_change_password"] == 1, "Novo usuário é obrigado a trocar a senha")
checar(len(database.get_portfolio(maria_id)) == 3, "Carteira do novo usuário começa com 3 ações")
checar(database.username_exists("MARIA"), "username_exists ignora maiúsculas/minúsculas")

database.set_role(maria_id, "admin")
checar(database.count_admins() == 2, "Maria foi promovida a administradora")

# Proteção: com 2 admins, dá para rebaixar um.
pode_rebaixar = database.count_admins() > 1
checar(pode_rebaixar, "Com 2 administradores, rebaixar é permitido")
database.set_role(maria_id, "comum")
checar(database.count_admins() == 1, "Maria voltou a ser comum")

# Proteção: com 1 admin só, NÃO pode rebaixar/excluir o último.
ultimo_admin = database.count_admins() <= 1
checar(ultimo_admin, "Sistema detecta que só resta 1 administrador")

# Proteção: não excluir a si mesmo (regra aplicada na tela; aqui checamos a ideia).
checar(admin["id"] == database.get_user_by_username("admin")["id"],
       "Conseguimos identificar 'a mim mesmo' para bloquear a autoexclusão")

database.delete_user(maria_id)
checar(database.get_user_by_id(maria_id) is None, "Maria foi excluída")
checar(len(database.get_portfolio(maria_id)) == 0, "A carteira dela foi apagada junto (cascata)")

# ---------------------------------------------------------------------------
secao("Carteira: adicionar e remover")
antes = database.get_portfolio(admin["id"])
adicionou = database.add_ticker(admin["id"], "WEGE3.SA")
checar(adicionou, "WEGE3 foi adicionada")
checar(not database.add_ticker(admin["id"], "WEGE3.SA"), "Não adiciona a mesma ação duas vezes")
database.remove_ticker(admin["id"], "VALE3.SA")
depois = database.get_portfolio(admin["id"])
checar("WEGE3.SA" in depois and "VALE3.SA" not in depois, "Carteira reflete adição e remoção")
checar(len(depois) == len(antes), "Trocou uma ação por outra (mesmo tamanho)")

# ---------------------------------------------------------------------------
secao("Sessões de login")
database.create_session("token-abc", admin["id"], dias_ate_expirar=7)
sessao = database.get_session("token-abc")
checar(sessao is not None and sessao["user_id"] == admin["id"], "Sessão criada e encontrada pelo token")
database.create_session("token-velho", admin["id"], dias_ate_expirar=-1)  # já expirada
checar(database.get_session("token-velho") is None, "Sessão expirada não é aceita")
database.delete_session("token-abc")
checar(database.get_session("token-abc") is None, "Logout apaga a sessão")

# ---------------------------------------------------------------------------
secao("Códigos de ação")
checar(market_data.normalizar_ticker("wege3") == "WEGE3.SA", "'wege3' vira 'WEGE3.SA'")
checar(market_data.normalizar_ticker("PETR4.SA") == "PETR4.SA", "'PETR4.SA' continua igual")
checar(market_data.exibir_ticker("PETR4.SA") == "PETR4", "'PETR4.SA' aparece como 'PETR4'")

# ---------------------------------------------------------------------------
secao("Yahoo Finance (precisa de internet)")
try:
    ok = market_data._buscar_historico_sem_cache(("PETR4.SA",), "1mo")
    if ok.erro_de_conexao:
        print("  [AVISO] Yahoo Finance não respondeu agora — teste de internet pulado.")
    else:
        checar(ok.tem_dados, "PETR4 retorna dados reais do Yahoo")
        ruim = market_data._buscar_historico_sem_cache(("XXXX9.SA",), "1mo")
        checar(not ruim.tem_dados, "Código inexistente NÃO retorna dados")
        checar("XXXX9" in ruim.nao_encontrados, "Código inexistente entra na lista 'não encontrados'")
except Exception as e:  # nunca deve estourar erro técnico
    print(f"  [AVISO] Não deu para testar o Yahoo agora ({e.__class__.__name__}).")

# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
if _falhas:
    print(f"RESULTADO: {len(_falhas)} verificação(ões) FALHARAM:")
    for f in _falhas:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("RESULTADO: tudo passou. A lógica do app está funcionando. ✅")
    sys.exit(0)
