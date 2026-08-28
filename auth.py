"""
auth.py
-------
Tudo o que tem a ver com "quem é você": login, senha e sessão.

  - embaralhar (hash) e conferir senhas com bcrypt;
  - gerar senhas temporárias;
  - criar o PRIMEIRO administrador na primeira vez que o app roda,
    lendo o usuário e a senha do arquivo  .streamlit/secrets.toml ;
  - manter você logado depois do F5 usando um cookie no navegador;
  - desenhar a tela de login.

Nenhuma senha aparece escrita neste arquivo.
"""

from __future__ import annotations

import os
import secrets
import string
from datetime import datetime, timedelta

import bcrypt
import extra_streamlit_components as stx
import streamlit as st

import database

# Nome do cookie que guarda o "crachá" da sessão no navegador.
COOKIE_SESSAO = "painel_acoes_sessao"
# Por quantos dias o login continua valendo sem precisar digitar a senha de novo.
DIAS_LOGADO = 7


class ConfigError(Exception):
    """Erro de configuração que deve virar uma mensagem amigável na tela."""


# ---------------------------------------------------------------------------
# Senhas
# ---------------------------------------------------------------------------
def hash_password(senha: str) -> str:
    """Transforma a senha em um texto embaralhado que NÃO dá para reverter."""
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(senha: str, hash_guardado: str) -> bool:
    """Confere se a senha digitada corresponde ao hash guardado no banco."""
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), hash_guardado.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def generate_temp_password(tamanho: int = 10) -> str:
    """
    Cria uma senha temporária fácil de digitar.
    Evita letras e números que se confundem (O, 0, I, l, 1).
    """
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alfabeto) for _ in range(tamanho))


# ---------------------------------------------------------------------------
# Primeiro administrador
# ---------------------------------------------------------------------------
def _ler_secrets() -> dict:
    """
    Lê as chaves ADMIN_* de duas fontes, nesta ordem de prioridade:

      1. o arquivo  .streamlit/secrets.toml  — usado quando você roda o app
         no seu computador;
      2. as variáveis de ambiente do sistema — usado quando o app roda em um
         servidor (ex.: Railway), onde não existe o arquivo secrets.toml e os
         segredos são configurados no painel do serviço.

    O que estiver no arquivo tem prioridade; o que faltar é procurado no
    ambiente. Se nenhuma das fontes tiver a chave, ela simplesmente não entra
    no dicionário devolvido.
    """
    chaves = ("ADMIN_USERNAME", "ADMIN_PASSWORD", "ADMIN_FULL_NAME", "ADMIN_EMAIL")
    valores: dict = {}

    try:
        for chave in chaves:
            if chave in st.secrets:
                valores[chave] = st.secrets[chave]
    except Exception:
        # Arquivo de segredos ausente ou ilegível — tudo bem, tentamos o ambiente.
        pass

    for chave in chaves:
        if chave not in valores and os.environ.get(chave):
            valores[chave] = os.environ[chave]

    return valores


def bootstrap_first_admin(secrets_source: dict | None = None) -> None:
    """
    Se o banco de dados ainda não tem NENHUM usuário, cria o primeiro
    administrador usando o que estiver em .streamlit/secrets.toml.

    Se faltar usuário ou senha nesse arquivo, levanta ConfigError com uma
    mensagem explicando o que fazer.
    """
    if database.count_users() > 0:
        return

    fonte = secrets_source if secrets_source is not None else _ler_secrets()
    usuario = (fonte.get("ADMIN_USERNAME") or "").strip()
    senha = fonte.get("ADMIN_PASSWORD") or ""

    if not usuario or not senha:
        raise ConfigError(
            "O app ainda não tem nenhum usuário e eu não encontrei o login do "
            "primeiro administrador.\n\n"
            "Abra o arquivo  .streamlit/secrets.toml  dentro da pasta  \"exercicio 1\"  "
            "e preencha pelo menos:\n\n"
            '    ADMIN_USERNAME = \"admin\"\n'
            '    ADMIN_PASSWORD = \"uma-senha-sua\"\n\n'
            "Depois salve o arquivo e atualize esta página (F5)."
        )

    database.create_user(
        full_name=(fonte.get("ADMIN_FULL_NAME") or "Administrador").strip(),
        username=usuario,
        email=(fonte.get("ADMIN_EMAIL") or "admin@exemplo.com").strip(),
        role="admin",
        password_hash=hash_password(senha),
        must_change_password=False,  # a senha foi definida por você, não é temporária
    )
    novo_admin = database.get_user_by_username(usuario)
    if novo_admin is not None:
        database.seed_portfolio(novo_admin["id"])


# ---------------------------------------------------------------------------
# Cookie / sessão (continuar logado depois do F5)
# ---------------------------------------------------------------------------
def _get_cookie_manager() -> stx.CookieManager:
    """Cria (uma vez por aba do navegador) o objeto que lê e grava cookies."""
    if "cookie_manager" not in st.session_state:
        st.session_state["cookie_manager"] = stx.CookieManager(key="gerenciador_cookies")
    return st.session_state["cookie_manager"]


def login_user(user_row) -> None:
    """Registra a sessão no banco e grava o cookie no navegador."""
    token = secrets.token_urlsafe(32)
    database.create_session(token, user_row["id"], DIAS_LOGADO)
    st.session_state["user_id"] = user_row["id"]

    gerenciador = _get_cookie_manager()
    gerenciador.set(
        COOKIE_SESSAO,
        token,
        expires_at=datetime.now() + timedelta(days=DIAS_LOGADO),
        key="grava_cookie_sessao",
    )


def logout_user() -> None:
    """Apaga a sessão do banco e remove o cookie do navegador."""
    gerenciador = _get_cookie_manager()
    token = (gerenciador.get_all() or {}).get(COOKIE_SESSAO)
    if token:
        database.delete_session(token)
    try:
        gerenciador.delete(COOKIE_SESSAO, key="apaga_cookie_sessao")
    except KeyError:
        # O cookie já não estava lá — tudo bem.
        pass
    st.session_state.pop("user_id", None)


def get_logged_in_user():
    """
    Descobre quem está logado agora. Devolve a linha do usuário ou None.

    Primeiro tenta pela memória da aba (rápido); se não achar, tenta pelo
    cookie do navegador (é isso que mantém você logado depois do F5).
    """
    # 1) Já sabemos quem é nesta aba?
    user_id = st.session_state.get("user_id")
    if user_id:
        usuario = database.get_user_by_id(user_id)
        if usuario is not None:
            return usuario
        st.session_state.pop("user_id", None)

    # 2) Tentar pelo cookie (é isso que mantém o login depois do F5).
    gerenciador = _get_cookie_manager()
    cookies = gerenciador.get_all() or {}
    token = cookies.get(COOKIE_SESSAO)
    if token:
        sessao = database.get_session(token)
        if sessao is not None:
            st.session_state["user_id"] = sessao["user_id"]
            return database.get_user_by_id(sessao["user_id"])

    return None


# ---------------------------------------------------------------------------
# Tela de login
# ---------------------------------------------------------------------------
def render_login_page() -> None:
    """Desenha a tela de entrada. É a única coisa que aparece sem login."""
    st.markdown("## 📈 Painel de Ações")
    st.caption("Entre com seu usuário e senha para continuar.")

    with st.form("formulario_login"):
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar", use_container_width=True)

    if entrar:
        registro = database.get_user_by_username(usuario)
        if registro is not None and verify_password(senha, registro["password_hash"]):
            login_user(registro)
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos. Confira e tente de novo.")

    st.caption(
        "Não tem acesso? Peça a um administrador para criar seu usuário. "
        "Ninguém se cadastra sozinho."
    )
