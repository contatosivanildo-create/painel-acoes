"""
deploy_check.py
---------------
Verificacao rapida que roda UMA vez, no servidor, logo antes de a nova versao
entrar no ar (Railway "preDeployCommand"). So imprime informacoes nos logs para
conferencia — NUNCA derruba o deploy (sempre termina com sucesso).

Confere duas coisas:
  1. o banco de dados no disco permanente (/data);
  2. se o Yahoo Finance responde a partir do servidor.

Pode ser removido depois da conferencia inicial.
"""

import os
import sqlite3

print("[deploy_check] inicio", flush=True)

db = os.environ.get("STOCKS_APP_DB", "")
print("[deploy_check] STOCKS_APP_DB =", db, flush=True)
try:
    existe = os.path.exists(db)
    print("[deploy_check] arquivo do banco existe:", existe, flush=True)
    if existe:
        con = sqlite3.connect(db)
        try:
            usuarios = con.execute(
                "SELECT username, role FROM users ORDER BY id"
            ).fetchall()
            carteira = con.execute(
                "SELECT COUNT(*) FROM portfolio_items"
            ).fetchone()[0]
            print("[deploy_check] usuarios no banco:", usuarios, flush=True)
            print("[deploy_check] itens de carteira:", carteira, flush=True)
        finally:
            con.close()
except Exception as e:  # nunca deixar estourar
    print("[deploy_check] aviso ao ler o banco:", repr(e), flush=True)

try:
    import market_data

    r = market_data._buscar_historico_sem_cache(("PETR4.SA", "VALE3.SA"), "1mo")
    print(
        "[deploy_check] Yahoo -> tem_dados:", r.tem_dados,
        "| erro_de_conexao:", r.erro_de_conexao,
        "| nao_encontrados:", r.nao_encontrados,
        flush=True,
    )
    if r.tem_dados:
        ultimos = {k: round(float(v), 2) for k, v in r.precos.iloc[-1].items()}
        print(
            "[deploy_check] Yahoo -> ultima data:", str(r.precos.index[-1])[:10],
            "| ultimos precos:", ultimos,
            flush=True,
        )
except Exception as e:
    print("[deploy_check] aviso no Yahoo:", repr(e), flush=True)

print("[deploy_check] fim (deploy segue normalmente)", flush=True)
