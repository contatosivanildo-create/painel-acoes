"""
views.py
--------
O desenho de cada página do app, depois que a pessoa já está logada:

  - render_change_password_gate  -> tela obrigatória de troca de senha temporária
  - render_stocks_page           -> "Ações" (cartões, gráficos, resumo, CSV)
  - render_portfolio_page        -> "Minha carteira" (adicionar / remover ações)
  - render_account_page          -> "Minha conta" (trocar a própria senha)
  - render_admin_page            -> "Administração" (só administradores)

Todas as mensagens são amigáveis e em português. Nenhuma tela de erro técnica.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import analise_ia
import auth
import database
import market_data


# ---------------------------------------------------------------------------
# Ajudantes de formatação e de mensagens
# ---------------------------------------------------------------------------
def _formatar_reais(valor) -> str:
    """12345.6 -> 'R$ 12.345,60' (padrão brasileiro)."""
    try:
        texto = f"{float(valor):,.2f}"
    except (TypeError, ValueError):
        return "—"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def _formatar_pct(valor) -> str:
    """0.5 -> '+0,50%'  |  -3.2 -> '-3,20%'"""
    try:
        return f"{float(valor):+.2f}%".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def _validar_nova_senha(nova: str, confirmacao: str) -> str | None:
    """Devolve uma mensagem de erro, ou None se a senha estiver ok."""
    if len(nova) < 8:
        return "A nova senha precisa ter pelo menos 8 caracteres."
    if nova != confirmacao:
        return "As duas senhas digitadas não são iguais."
    return None


def _set_flash(chave: str, tipo: str, texto: str) -> None:
    """Guarda uma mensagem para ser mostrada depois do próximo recarregamento."""
    st.session_state[chave] = (tipo, texto)


def _render_flash(chave: str) -> None:
    """Mostra (uma única vez) a mensagem guardada por _set_flash."""
    dados = st.session_state.pop(chave, None)
    if not dados:
        return
    tipo, texto = dados
    getattr(st, tipo)(texto)  # st.success / st.error / st.info / st.warning


# ---------------------------------------------------------------------------
# Troca obrigatória de senha temporária
# ---------------------------------------------------------------------------
def render_change_password_gate(user) -> None:
    st.markdown("## Crie uma nova senha")
    st.info(
        "Você entrou com uma **senha temporária**. Antes de usar o app, "
        "defina uma senha só sua."
    )
    with st.form("form_troca_obrigatoria", clear_on_submit=False):
        nova = st.text_input("Nova senha", type="password")
        confirmacao = st.text_input("Repita a nova senha", type="password")
        salvar = st.form_submit_button("Salvar nova senha", use_container_width=True)

    if salvar:
        erro = _validar_nova_senha(nova, confirmacao)
        if erro:
            st.error(erro)
        else:
            database.update_password(
                user["id"], auth.hash_password(nova), must_change_password=False
            )
            st.success("Senha atualizada! Abrindo o app...")
            st.rerun()


# ---------------------------------------------------------------------------
# Página "Ações"
# ---------------------------------------------------------------------------
def render_stocks_page(user) -> None:
    st.markdown("## Ações")

    tickers = database.get_portfolio(user["id"])
    if not tickers:
        st.info(
            "Sua carteira está vazia. Vá em **Minha carteira** e adicione ações "
            "para ver os gráficos aqui."
        )
        return

    # --- botões de período (a escolha continua ao trocar de página) ---
    rotulos = list(market_data.PERIODOS.values())
    codigos = list(market_data.PERIODOS.keys())
    atual = st.session_state.get("periodo_grafico", market_data.PERIODO_PADRAO)
    indice = codigos.index(atual) if atual in codigos else codigos.index(market_data.PERIODO_PADRAO)
    rotulo_escolhido = st.radio("Período", rotulos, index=indice, horizontal=True)
    periodo = codigos[rotulos.index(rotulo_escolhido)]
    st.session_state["periodo_grafico"] = periodo

    with st.spinner("Buscando cotações no Yahoo Finance..."):
        resultado = market_data.buscar_historico(tuple(tickers), periodo)

    if resultado.erro_de_conexao:
        st.error(
            "Não conseguimos falar com o Yahoo Finance agora. Isso costuma ser "
            "passageiro — espere alguns minutos e atualize a página (F5)."
        )
        return

    if resultado.nao_encontrados:
        nomes = ", ".join(resultado.nao_encontrados)
        st.warning(
            f"Não encontramos dados para: **{nomes}**. Confira o código em "
            "**Minha carteira** ou remova essa ação."
        )

    if not resultado.tem_dados:
        st.info("Nenhuma das ações da sua carteira retornou dados no momento.")
        return

    precos = resultado.precos.rename(
        columns={c: market_data.exibir_ticker(c) for c in resultado.precos.columns}
    )
    performance = (precos / precos.iloc[0] - 1) * 100

    # --- cartões (cards) ---
    colunas = st.columns(len(precos.columns))
    for coluna, nome in zip(colunas, precos.columns):
        preco_atual = precos[nome].dropna().iloc[-1]
        variacao = performance[nome].dropna().iloc[-1]
        coluna.metric(
            label=nome,
            value=_formatar_reais(preco_atual),
            delta=f"{_formatar_pct(variacao)} no período",
        )

    # --- gráfico de cotação ---
    st.subheader("Cotação (R$)")
    fig_preco = go.Figure()
    for nome in precos.columns:
        fig_preco.add_trace(
            go.Scatter(x=precos.index, y=precos[nome], name=nome, mode="lines")
        )
    fig_preco.update_layout(
        yaxis_title="Preço (R$)", xaxis_title="Data",
        hovermode="x unified", separators=",.", legend_title_text="",
    )
    st.plotly_chart(fig_preco, width="stretch")

    # --- gráfico de performance ---
    st.subheader("Performance no período (%)")
    fig_perf = go.Figure()
    for nome in performance.columns:
        fig_perf.add_trace(
            go.Scatter(x=performance.index, y=performance[nome], name=nome, mode="lines")
        )
    fig_perf.update_layout(
        yaxis_title="Variação no período (%)", xaxis_title="Data",
        hovermode="x unified", separators=",.", legend_title_text="",
    )
    st.plotly_chart(fig_perf, width="stretch")

    # --- tabela de resumo ---
    st.subheader("Resumo")
    resumo = pd.DataFrame(
        {
            "Preço mais recente (R$)": precos.iloc[-1].round(2),
            "Variação no período (%)": performance.iloc[-1].round(2),
        }
    )
    st.dataframe(resumo, width="stretch")

    # --- download em CSV ---
    csv = precos.to_csv().encode("utf-8-sig")
    st.download_button(
        "Baixar cotações em CSV", data=csv,
        file_name="cotacoes.csv", mime="text/csv",
    )

    try:
        ultima_data = precos.index[-1].strftime("%d/%m/%Y")
    except (AttributeError, ValueError):
        ultima_data = str(precos.index[-1])
    st.caption(
        f"Última data disponível nos dados: {ultima_data}. "
        "Dados do Yahoo Finance, atualizados a cada 15 minutos."
    )

    # --- botão flutuante "Análise do Dia" + janela com o texto da IA ---
    _render_analise_do_dia(user, precos, resultado.nao_encontrados, rotulo_escolhido)


# ---------------------------------------------------------------------------
# "Análise do Dia" (botão flutuante + janela com o texto escrito pela IA)
# ---------------------------------------------------------------------------
# O botão fica preso no canto inferior direito da tela (position: fixed), sempre
# visível mesmo rolando a página. A classe "st-key-botao_analise_dia" é criada
# pelo Streamlit por causa do  st.container(key="botao_analise_dia")  abaixo.
_CSS_BOTAO_ANALISE = """
<style>
.st-key-botao_analise_dia {
    position: fixed;
    right: 24px;
    bottom: 24px;
    z-index: 999;
    width: auto !important;
}
.st-key-botao_analise_dia button {
    border-radius: 999px !important;
    padding: 0.6rem 1.4rem !important;
    font-weight: 700 !important;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.28) !important;
}
@media (max-width: 640px) {
    .st-key-botao_analise_dia { right: 12px; bottom: 12px; }
}
</style>
"""


@st.dialog("Análise do Dia", width="large")
def _janela_analise_do_dia() -> None:
    """Janela sobre a página: mostra a análise sendo escrita, o período e a hora."""
    dados = st.session_state.get("analise_entrada")
    if not dados:
        st.info("Abra pela página Ações para gerar a análise.")
        return

    precos = dados["precos"]
    nao_encontrados = dados["nao_encontrados"]
    periodo_rotulo = dados["periodo"]
    usuario_nome = dados["usuario_nome"]

    st.caption(f"Carteira de **{usuario_nome}**  ·  período analisado: **{periodo_rotulo}**")

    chave_cache = (dados["usuario_id"], tuple(sorted(precos.columns)), periodo_rotulo)
    guardada = st.session_state.get("analise_guardada")
    agora = analise_ia.agora_brasil()
    reaproveitar = (
        isinstance(guardada, dict)
        and guardada.get("chave") == chave_cache
        and (agora - guardada["quando"]).total_seconds() < 15 * 60
    )

    if reaproveitar:
        st.markdown(guardada["texto"])
        st.info(
            f"Análise gerada às {guardada['hora']} — reaproveitada. "
            "Uma nova é feita só depois de 15 minutos."
        )
    else:
        resumo = analise_ia.montar_resumo(
            precos, nao_encontrados, periodo_rotulo, usuario_nome, agora
        )
        estado = {"ok": False}
        with st.spinner("Lendo os números da sua carteira..."):
            texto = st.write_stream(analise_ia.gerar_analise(resumo, estado))
        if estado["ok"]:
            st.session_state["analise_guardada"] = {
                "chave": chave_cache,
                "texto": texto,
                "quando": agora,
                "hora": agora.strftime("%H:%M"),
            }
            st.caption(f"Análise gerada às {agora.strftime('%H:%M')}.")

    if st.button("Fechar", key="fechar_analise_dia", use_container_width=True):
        st.session_state.pop("analise_entrada", None)
        st.rerun()


def _render_analise_do_dia(user, precos, nao_encontrados, periodo_rotulo) -> None:
    st.markdown(_CSS_BOTAO_ANALISE, unsafe_allow_html=True)
    with st.container(key="botao_analise_dia"):
        if st.button("💡 Análise do Dia", key="abrir_analise_dia", type="primary"):
            st.session_state["analise_entrada"] = {
                "usuario_id": user["id"],
                "usuario_nome": user["full_name"],
                "precos": precos,
                "nao_encontrados": list(nao_encontrados or []),
                "periodo": periodo_rotulo,
            }
            _janela_analise_do_dia()


# ---------------------------------------------------------------------------
# Página "Minha carteira"
# ---------------------------------------------------------------------------
def _tentar_adicionar(user, codigo_digitado: str, tickers_atuais: list[str]) -> None:
    ticker = market_data.normalizar_ticker(codigo_digitado)
    if not ticker:
        _set_flash("flash_carteira", "warning", "Digite o código de uma ação.")
        st.rerun()

    if ticker in tickers_atuais:
        _set_flash(
            "flash_carteira", "info",
            f"{market_data.exibir_ticker(ticker)} já está na sua carteira.",
        )
        st.rerun()

    with st.spinner("Conferindo o código no Yahoo Finance..."):
        valido = market_data.ticker_valido(ticker)

    if not valido:
        _set_flash(
            "flash_carteira", "error",
            f'Não encontrei a ação "{market_data.exibir_ticker(ticker)}". '
            "Confira o código e tente de novo.",
        )
        st.rerun()

    database.add_ticker(user["id"], ticker)
    _set_flash(
        "flash_carteira", "success",
        f"{market_data.exibir_ticker(ticker)} foi adicionada à sua carteira.",
    )
    st.rerun()


def render_portfolio_page(user) -> None:
    st.markdown("## Minha carteira")
    st.caption(
        'Estas são as ações que aparecem na página "Ações". '
        "Tudo o que você mudar aqui fica salvo."
    )
    _render_flash("flash_carteira")

    tickers = database.get_portfolio(user["id"])

    with st.form("form_add_acao", clear_on_submit=True):
        coluna_texto, coluna_botao = st.columns([3, 1])
        codigo = coluna_texto.text_input(
            "Adicionar ação", placeholder="Ex.: WEGE3", label_visibility="collapsed"
        )
        adicionar = coluna_botao.form_submit_button("Adicionar", use_container_width=True)
    if adicionar:
        _tentar_adicionar(user, codigo, tickers)

    st.divider()

    if not tickers:
        st.info("Sua carteira está vazia. Adicione uma ação no campo acima.")
        return

    st.write("**Ações na carteira:**")
    for ticker in tickers:
        coluna_nome, coluna_remover = st.columns([4, 1])
        coluna_nome.write(market_data.exibir_ticker(ticker))
        if coluna_remover.button("Remover", key=f"remover_{ticker}", use_container_width=True):
            database.remove_ticker(user["id"], ticker)
            _set_flash(
                "flash_carteira", "success",
                f"{market_data.exibir_ticker(ticker)} foi removida da carteira.",
            )
            st.rerun()


# ---------------------------------------------------------------------------
# Página "Minha conta"
# ---------------------------------------------------------------------------
def render_account_page(user) -> None:
    st.markdown("## Minha conta")
    _render_flash("flash_conta")

    st.write(f"**Nome completo:** {user['full_name']}")
    st.write(f"**Nome de usuário:** {user['username']}")
    st.write(f"**E-mail:** {user['email']}")
    tipo = "Administrador" if user["role"] == "admin" else "Usuário comum"
    st.write(f"**Tipo de conta:** {tipo}")

    st.divider()
    st.subheader("Trocar minha senha")
    with st.form("form_troca_senha", clear_on_submit=True):
        atual = st.text_input("Senha atual", type="password")
        nova = st.text_input("Nova senha", type="password")
        confirmacao = st.text_input("Repita a nova senha", type="password")
        salvar = st.form_submit_button("Salvar nova senha")

    if salvar:
        if not auth.verify_password(atual, user["password_hash"]):
            st.error("A senha atual está incorreta.")
            return
        erro = _validar_nova_senha(nova, confirmacao)
        if erro:
            st.error(erro)
            return
        database.update_password(
            user["id"], auth.hash_password(nova), must_change_password=False
        )
        _set_flash("flash_conta", "success", "Senha atualizada com sucesso.")
        st.rerun()


# ---------------------------------------------------------------------------
# Página "Administração"
# ---------------------------------------------------------------------------
def _mostrar_senha_temporaria_se_houver() -> None:
    """Caixa destacada com a senha temporária recém-gerada (mostrada uma vez)."""
    dados = st.session_state.get("senha_temp_gerada")
    if not dados:
        return
    nome, senha = dados
    st.success(
        f"Senha temporária de **{nome}** criada. **Anote agora e entregue à pessoa** "
        "— ela não será mostrada de novo."
    )
    st.code(senha, language=None)
    if st.button("Ok, já anotei", key="fechar_senha_temp"):
        st.session_state.pop("senha_temp_gerada", None)
        st.rerun()
    st.divider()


def _criar_usuario(nome: str, login: str, email: str) -> None:
    nome, login, email = nome.strip(), login.strip(), email.strip()
    if not nome or not login or not email:
        st.error("Preencha nome completo, nome de usuário e e-mail.")
        return
    if "@" not in email or "." not in email.split("@")[-1]:
        st.error("O e-mail não parece válido. Confira e tente de novo.")
        return
    if database.username_exists(login):
        st.error(f'Já existe um usuário com o nome "{login}". Escolha outro.')
        return

    senha_temp = auth.generate_temp_password()
    novo_id = database.create_user(
        full_name=nome, username=login, email=email, role="comum",
        password_hash=auth.hash_password(senha_temp), must_change_password=True,
    )
    database.seed_portfolio(novo_id)
    st.session_state["senha_temp_gerada"] = (nome, senha_temp)
    st.rerun()


def render_admin_page(user) -> None:
    st.markdown("## Administração")

    _mostrar_senha_temporaria_se_houver()

    # --- tabela de todos os usuários ---
    st.subheader("Usuários")
    usuarios = database.list_users()
    tabela = pd.DataFrame(
        [
            {
                "Nome completo": u["full_name"],
                "Nome de usuário": u["username"],
                "E-mail": u["email"],
                "Tipo": "Administrador" if u["role"] == "admin" else "Comum",
            }
            for u in usuarios
        ]
    )
    st.dataframe(tabela, width="stretch", hide_index=True)

    # --- criar usuário ---
    st.divider()
    st.subheader("Criar novo usuário")
    st.caption(
        "O app vai gerar uma senha temporária e mostrar na tela uma única vez, "
        "para você entregar à pessoa."
    )
    with st.form("form_criar_usuario", clear_on_submit=True):
        nome = st.text_input("Nome completo")
        login = st.text_input("Nome de usuário")
        email = st.text_input("E-mail")
        criar = st.form_submit_button("Criar usuário e gerar senha temporária")
    if criar:
        _criar_usuario(nome, login, email)

    # --- gerenciar um usuário ---
    st.divider()
    st.subheader("Gerenciar um usuário")
    _render_flash("flash_admin")

    opcoes = {
        f'{u["full_name"]} ({u["username"]}) — '
        f'{"Administrador" if u["role"] == "admin" else "Comum"}': u["id"]
        for u in usuarios
    }
    rotulo = st.selectbox("Escolha um usuário", list(opcoes.keys()))
    alvo_id = opcoes[rotulo]
    alvo = database.get_user_by_id(alvo_id)
    if alvo is None:
        return

    coluna1, coluna2, coluna3 = st.columns(3)

    # redefinir senha
    if coluna1.button("Redefinir senha", use_container_width=True, key="botao_redefinir"):
        senha_temp = auth.generate_temp_password()
        database.update_password(
            alvo_id, auth.hash_password(senha_temp), must_change_password=True
        )
        database.delete_sessions_for_user(alvo_id)  # desconecta os navegadores dele
        st.session_state["senha_temp_gerada"] = (alvo["full_name"], senha_temp)
        st.rerun()

    # promover / rebaixar
    if alvo["role"] == "comum":
        if coluna2.button("Promover a administrador", use_container_width=True, key="botao_promover"):
            database.set_role(alvo_id, "admin")
            _set_flash("flash_admin", "success", f'{alvo["full_name"]} agora é administrador.')
            st.rerun()
    else:
        if coluna2.button("Rebaixar para comum", use_container_width=True, key="botao_rebaixar"):
            if database.count_admins() <= 1:
                _set_flash(
                    "flash_admin", "error",
                    "Não é possível rebaixar o último administrador. "
                    "O sistema precisa ter pelo menos um.",
                )
            else:
                database.set_role(alvo_id, "comum")
                _set_flash("flash_admin", "success", f'{alvo["full_name"]} agora é usuário comum.')
            st.rerun()

    # excluir
    with coluna3:
        confirmar = st.checkbox("Confirmar exclusão", key="confirma_exclusao")
        if st.button(
            "Excluir usuário", use_container_width=True,
            key="botao_excluir", disabled=not confirmar,
        ):
            if alvo_id == user["id"]:
                _set_flash("flash_admin", "error", "Você não pode excluir a si mesmo.")
            elif alvo["role"] == "admin" and database.count_admins() <= 1:
                _set_flash(
                    "flash_admin", "error",
                    "Não é possível excluir o último administrador.",
                )
            else:
                database.delete_user(alvo_id)
                _set_flash("flash_admin", "success", f'Usuário {alvo["full_name"]} foi excluído.')
            st.rerun()

    st.caption(
        "Proteções: você não pode excluir a si mesmo, nem rebaixar/excluir o "
        "último administrador."
    )
