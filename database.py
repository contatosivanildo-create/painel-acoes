"""
database.py
-----------
Este arquivo cuida do "cofre" de dados do app: um banco de dados SQLite
guardado no arquivo  data/app.db  dentro desta pasta.

Aqui ficam guardados, de forma permanente (não somem quando o app fecha):
  - os usuários (nome completo, usuário, e-mail, tipo e senha embaralhada);
  - as sessões de login (para você continuar logado depois do F5);
  - a carteira de ações de cada usuário.

Nenhuma senha legível é guardada aqui: só uma versão embaralhada (hash),
gerada no arquivo  auth.py .
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Onde fica o arquivo do banco de dados
# ---------------------------------------------------------------------------
# Por padrão: uma pasta "data" ao lado deste arquivo.
# Dá para trocar o caminho definindo a variável de ambiente STOCKS_APP_DB
# (isso é usado pelo teste automático smoke_test.py).
_PASTA_ATUAL = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("STOCKS_APP_DB", os.path.join(_PASTA_ATUAL, "data", "app.db"))

# Ações que toda carteira nova recebe no começo.
TICKERS_PADRAO = ["PETR4.SA", "ITUB4.SA", "VALE3.SA"]


def _agora_iso() -> str:
    """Data e hora de agora, em texto, no fuso UTC (padrão para guardar)."""
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    """
    Abre uma conexão com o banco de dados.
    Cada operação abre a sua conexão e fecha em seguida — simples e seguro
    para um app que roda no seu computador.
    """
    pasta = os.path.dirname(DB_PATH)
    if pasta and not os.path.exists(pasta):
        os.makedirs(pasta, exist_ok=True)

    conexao = sqlite3.connect(DB_PATH)
    conexao.row_factory = sqlite3.Row          # deixa acessar colunas pelo nome
    conexao.execute("PRAGMA foreign_keys = ON")  # respeita os vínculos entre tabelas
    return conexao


def init_db() -> None:
    """Cria as tabelas do banco de dados, se ainda não existirem."""
    with get_connection() as conexao:
        conexao.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name            TEXT    NOT NULL,
                username             TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                email                TEXT    NOT NULL,
                role                 TEXT    NOT NULL CHECK (role IN ('admin', 'comum')),
                password_hash        TEXT    NOT NULL,
                must_change_password INTEGER NOT NULL DEFAULT 0,
                created_at           TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token      TEXT    PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT    NOT NULL,
                expires_at TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS portfolio_items (
                user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                ticker   TEXT    NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, ticker)
            );
            """
        )


# ---------------------------------------------------------------------------
# Usuários
# ---------------------------------------------------------------------------
def count_users() -> int:
    with get_connection() as conexao:
        return conexao.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def count_admins() -> int:
    with get_connection() as conexao:
        return conexao.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'admin'"
        ).fetchone()[0]


def username_exists(username: str) -> bool:
    with get_connection() as conexao:
        linha = conexao.execute(
            "SELECT 1 FROM users WHERE username = ? COLLATE NOCASE", (username,)
        ).fetchone()
        return linha is not None


def create_user(
    full_name: str,
    username: str,
    email: str,
    role: str,
    password_hash: str,
    must_change_password: bool,
) -> int:
    """Cria um usuário e devolve o id dele. Erro se o usuário já existir."""
    with get_connection() as conexao:
        cursor = conexao.execute(
            """
            INSERT INTO users
                (full_name, username, email, role, password_hash,
                 must_change_password, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                full_name.strip(),
                username.strip(),
                email.strip(),
                role,
                password_hash,
                1 if must_change_password else 0,
                _agora_iso(),
            ),
        )
        return int(cursor.lastrowid)


def get_user_by_username(username: str) -> sqlite3.Row | None:
    with get_connection() as conexao:
        return conexao.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username.strip(),)
        ).fetchone()


def get_user_by_id(user_id: int) -> sqlite3.Row | None:
    with get_connection() as conexao:
        return conexao.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()


def list_users() -> list[sqlite3.Row]:
    """Todos os usuários: administradores primeiro, depois em ordem de nome."""
    with get_connection() as conexao:
        return conexao.execute(
            """
            SELECT * FROM users
            ORDER BY CASE role WHEN 'admin' THEN 0 ELSE 1 END,
                     full_name COLLATE NOCASE
            """
        ).fetchall()


def update_password(user_id: int, password_hash: str, must_change_password: bool) -> None:
    with get_connection() as conexao:
        conexao.execute(
            """
            UPDATE users
               SET password_hash = ?, must_change_password = ?
             WHERE id = ?
            """,
            (password_hash, 1 if must_change_password else 0, user_id),
        )


def set_role(user_id: int, role: str) -> None:
    with get_connection() as conexao:
        conexao.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))


def delete_user(user_id: int) -> None:
    """Apaga o usuário. As sessões e a carteira dele somem junto (cascata)."""
    with get_connection() as conexao:
        conexao.execute("DELETE FROM users WHERE id = ?", (user_id,))


# ---------------------------------------------------------------------------
# Sessões de login (para continuar logado depois do F5)
# ---------------------------------------------------------------------------
def create_session(token: str, user_id: int, dias_ate_expirar: int = 7) -> None:
    criado = datetime.now(timezone.utc)
    expira = criado + timedelta(days=dias_ate_expirar)
    with get_connection() as conexao:
        conexao.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, criado.isoformat(), expira.isoformat()),
        )


def get_session(token: str) -> sqlite3.Row | None:
    """Devolve a sessão se o token existir e ainda não tiver expirado."""
    if not token:
        return None
    with get_connection() as conexao:
        linha = conexao.execute(
            "SELECT * FROM sessions WHERE token = ?", (token,)
        ).fetchone()
        if linha is None:
            return None
        try:
            expira = datetime.fromisoformat(linha["expires_at"])
        except ValueError:
            return None
        if expira < datetime.now(timezone.utc):
            conexao.execute("DELETE FROM sessions WHERE token = ?", (token,))
            return None
        return linha


def delete_session(token: str) -> None:
    if not token:
        return
    with get_connection() as conexao:
        conexao.execute("DELETE FROM sessions WHERE token = ?", (token,))


def delete_sessions_for_user(user_id: int) -> None:
    """Desconecta o usuário de todos os navegadores (usado ao redefinir a senha)."""
    with get_connection() as conexao:
        conexao.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def purge_expired_sessions() -> None:
    agora = datetime.now(timezone.utc).isoformat()
    with get_connection() as conexao:
        conexao.execute("DELETE FROM sessions WHERE expires_at < ?", (agora,))


# ---------------------------------------------------------------------------
# Carteira de ações (uma por usuário)
# ---------------------------------------------------------------------------
def get_portfolio(user_id: int) -> list[str]:
    """Lista de códigos (tickers) da carteira do usuário, na ordem em que ele deixou."""
    with get_connection() as conexao:
        linhas = conexao.execute(
            "SELECT ticker FROM portfolio_items WHERE user_id = ? ORDER BY position, ticker",
            (user_id,),
        ).fetchall()
        return [linha["ticker"] for linha in linhas]


def seed_portfolio(user_id: int, tickers: list[str] | None = None) -> None:
    """Coloca as ações iniciais na carteira de um usuário recém-criado."""
    tickers = tickers or TICKERS_PADRAO
    with get_connection() as conexao:
        for posicao, ticker in enumerate(tickers):
            conexao.execute(
                """
                INSERT OR IGNORE INTO portfolio_items (user_id, ticker, position)
                VALUES (?, ?, ?)
                """,
                (user_id, ticker, posicao),
            )


def add_ticker(user_id: int, ticker: str) -> bool:
    """
    Adiciona uma ação à carteira. Devolve True se adicionou,
    False se a ação já estava lá.
    """
    with get_connection() as conexao:
        ja_existe = conexao.execute(
            "SELECT 1 FROM portfolio_items WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        ).fetchone()
        if ja_existe:
            return False
        proxima_posicao = conexao.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM portfolio_items WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        conexao.execute(
            "INSERT INTO portfolio_items (user_id, ticker, position) VALUES (?, ?, ?)",
            (user_id, ticker, proxima_posicao),
        )
        return True


def remove_ticker(user_id: int, ticker: str) -> None:
    with get_connection() as conexao:
        conexao.execute(
            "DELETE FROM portfolio_items WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        )
