"""
app.py
------
Porta de entrada do app (é este arquivo que você roda com o Streamlit).

O que ele faz, em ordem:
  1. prepara o banco de dados (cria as tabelas se for a primeira vez);
  2. cria o primeiro administrador, se ainda não existe nenhum usuário;
  3. mostra a tela de login para quem não está logado;
  4. obriga a troca de senha de quem entrou com senha temporária;
  5. já logado: mostra o menu lateral e a página escolhida.

Para rodar:  streamlit run app.py
"""

import streamlit as st

import auth
import database
import views

st.set_page_config(page_title="Painel de Ações", page_icon="📈", layout="wide")

# 1) Banco de dados pronto.
database.init_db()
database.purge_expired_sessions()

# 2) Primeiro administrador (lê o login de .streamlit/secrets.toml).
try:
    auth.bootstrap_first_admin()
except auth.ConfigError as erro:
    st.markdown("## 📈 Painel de Ações")
    st.error(str(erro))
    st.stop()

# 3) Quem está logado?
usuario = auth.get_logged_in_user()
if usuario is None:
    auth.render_login_page()
    st.stop()

# 4) Entrou com senha temporária? Precisa trocar antes de qualquer outra coisa.
if usuario["must_change_password"]:
    views.render_change_password_gate(usuario)
    st.stop()

# 5) Menu lateral + página escolhida.
paginas = ["Ações", "Minha carteira", "Minha conta"]
if usuario["role"] == "admin":
    paginas.append("Administração")

with st.sidebar:
    st.markdown("### 📈 Painel de Ações")
    escolha = st.radio("Navegação", paginas, label_visibility="collapsed")
    st.divider()
    st.markdown(f"**{usuario['full_name']}**")
    st.caption("Administrador" if usuario["role"] == "admin" else "Usuário comum")
    if st.button("Sair", use_container_width=True):
        auth.logout_user()
        st.rerun()

if escolha == "Ações":
    views.render_stocks_page(usuario)
elif escolha == "Minha carteira":
    views.render_portfolio_page(usuario)
elif escolha == "Minha conta":
    views.render_account_page(usuario)
elif escolha == "Administração":
    views.render_admin_page(usuario)
