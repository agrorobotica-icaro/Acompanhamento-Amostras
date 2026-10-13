from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(page_title="Acompanhamento de OS", page_icon="📋", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background: #ffffff; color: #183b2c; }
    [data-testid="stSidebar"] { background: #f0f7f1; }
    .block-container { padding-top: 1.25rem; }
    div[data-testid="stMetric"] { background: #f0f7f1; padding: 14px; border-radius: 10px; border-left: 4px solid #3b9d50; }
    h1, h2, h3 { color: #26783b; }
    div.stButton > button[kind="primary"] { background: #368d45; border-color: #368d45; }
    div.stButton > button[kind="primary"]:hover { background: #26783b; border-color: #26783b; }
    </style>
    """,
    unsafe_allow_html=True,
)

logo_path = Path(__file__).parent / "logo_agrorobotica.png"
cabecalho_logo, cabecalho_titulo = st.columns([1, 3])
with cabecalho_logo:
    if logo_path.exists():
        st.image(str(logo_path), width=260)
with cabecalho_titulo:
    st.title("Acompanhamento de Ordens de Serviço")
st.caption("Localize planilhas de químico simples e acompanhe o que já foi preenchido.")

ANALISES_QUIMICAS = [
    "CHN", "K_P_Mehlich", "Macro", "Micro", "MO", "pH_CaCl2",
    "pH_H2O", "P_Resina", "S_ICP", "S_Turbidimetria", "Textura",
]


def normalizar(texto: object) -> str:
    valor = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", valor.casefold())


def nome_documento(path: Path) -> tuple[str, str] | None:
    """Retorna (tipo F/PAV, status pedido/preenchido) para nomes aceitos."""
    nome = normalizar(path.stem)
    # Exemplos aceitos: F2026001S_QUIMICO_SIMPLES[_PREENCHIDA]
    # e PAV2026001S_QUIMICO_SIMPLES[_PREENCHIDA].
    match = re.fullmatch(r"(pav|f)\d+squimicosimples(?:preenchid[ao])?", nome)
    if not match:
        return None
    status = "preenchido" if "preenchid" in nome else "pedido"
    return match.group(1).upper(), status


def coluna_por_nome(df: pd.DataFrame, procurada: str) -> object | None:
    alvo = normalizar(procurada)
    for coluna in df.columns:
        if normalizar(coluna) == alvo:
            return coluna
    return None


def ler_abas_planilha(path: Path) -> list[pd.DataFrame]:
    """Lê todas as abas uma vez para alimentar as duas visualizações."""
    try:
        return list(pd.read_excel(path, sheet_name=None, dtype=str).values())
    except Exception:
        return []


def ler_chaves_planilha(abas: list[pd.DataFrame]) -> set[tuple[str, str]]:
    """Extrai pares Unidade/Fazenda sem assumir posição das colunas."""
    pares: set[tuple[str, str]] = set()
    for df in abas:
        if df.empty:
            continue
        col_unidade = coluna_por_nome(df, "Unidade")
        col_fazenda = coluna_por_nome(df, "Fazenda")
        if col_unidade is None and col_fazenda is None:
            continue

        unidades = df[col_unidade].fillna("").astype(str).str.strip() if col_unidade is not None else pd.Series("", index=df.index)
        fazendas = df[col_fazenda].fillna("").astype(str).str.strip() if col_fazenda is not None else pd.Series("", index=df.index)
        for unidade, fazenda in zip(unidades, fazendas):
            unidade = "" if unidade.casefold() == "nan" else unidade
            fazenda = "" if fazenda.casefold() == "nan" else fazenda
            if unidade or fazenda:
                pares.add((unidade, fazenda))
    return pares


def interpretar_data(serie: pd.Series) -> pd.Series:
    """Interpreta datas como 7/7/202611:46:36, com ou sem espaço antes da hora."""
    texto = serie.fillna("").astype(str).str.strip()
    texto = texto.str.replace(
        r"^(\d{1,2}/\d{1,2}/\d{4})(\d{1,2}:\d{2}:\d{2})$",
        r"\1 \2",
        regex=True,
    )
    return pd.to_datetime(texto, errors="coerce", dayfirst=False)


def spline_cubica(dados: pd.DataFrame, eixo_x: str = "Posicao", eixo_y: str = "Percentual", pontos_por_intervalo: int = 12) -> pd.DataFrame:
    """Interpola posições consecutivas de OS com Hermite cúbica, sem Plotly spline."""
    ordenados = dados[[eixo_x, eixo_y]].dropna().sort_values(eixo_x).drop_duplicates(eixo_x)
    if len(ordenados) < 3:
        return ordenados.rename(columns={eixo_x: "Posicao", eixo_y: "Percentual"})

    x = [float(valor) for valor in ordenados[eixo_x]]
    valores = [float(valor) for valor in ordenados[eixo_y]]
    tangentes = []
    for i in range(len(x)):
        if i == 0:
            tangente = (valores[1] - valores[0]) / (x[1] - x[0])
        elif i == len(x) - 1:
            tangente = (valores[i] - valores[i - 1]) / (x[i] - x[i - 1])
        else:
            tangente = (valores[i + 1] - valores[i - 1]) / (x[i + 1] - x[i - 1])
        tangentes.append(tangente)

    curva_x: list[float] = []
    curva_y: list[float] = []
    for i in range(len(x) - 1):
        largura = x[i + 1] - x[i]
        for passo in range(pontos_por_intervalo):
            t = passo / pontos_por_intervalo
            h00 = 2 * t**3 - 3 * t**2 + 1
            h10 = t**3 - 2 * t**2 + t
            h01 = -2 * t**3 + 3 * t**2
            h11 = t**3 - t**2
            y = (
                h00 * valores[i]
                + h10 * largura * tangentes[i]
                + h01 * valores[i + 1]
                + h11 * largura * tangentes[i + 1]
            )
            curva_x.append(x[i] + t * largura)
            # A métrica é percentual; a curva não deve sair do intervalo válido.
            curva_y.append(max(0.0, min(100.0, y)))

    curva_x.append(x[-1])
    curva_y.append(valores[-1])
    return pd.DataFrame({"Posicao": curva_x, "Percentual": curva_y})


def localizar_raiz_pasta_os(path: Path, raiz: Path) -> str:
    """Usa o nome da pasta de primeiro nível dentro da raiz como Ordem de Serviço."""
    relativo = path.relative_to(raiz)
    return relativo.parts[0] if len(relativo.parts) > 1 else raiz.name


def escanear(raiz: Path) -> tuple[pd.DataFrame, pd.DataFrame, list[str], int]:
    extensoes = {".xlsx", ".xlsm", ".xls"}
    encontrados: dict[tuple[str, str, str, str], dict[str, object]] = {}
    erros: list[str] = []
    linhas_analises: list[pd.DataFrame] = []
    documentos = 0

    for path in raiz.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in extensoes:
            continue
        identificacao = nome_documento(path)
        if identificacao is None:
            continue
        documentos += 1
        tipo, status_arquivo = identificacao
        os_nome = localizar_raiz_pasta_os(path, raiz)
        abas = ler_abas_planilha(path)
        pares = ler_chaves_planilha(abas)
        if not pares:
            # Mantém o documento visível mesmo quando não há dados ou as colunas não foram localizadas.
            pares = {("", "")}

        for unidade, fazenda in pares:
            key = (os_nome, unidade, fazenda, tipo)
            registro = encontrados.setdefault(
                key,
                {"pedido": False, "preenchido": False, "arquivos": set(), "origens": set()},
            )
            registro[status_arquivo] = True
            registro["arquivos"].add(path.name)
            registro["origens"].add(str(path.relative_to(raiz)))

        for aba in abas:
            if aba.empty:
                continue
            col_data = coluna_por_nome(aba, "Data")

            colunas = {nome: coluna_por_nome(aba, nome) for nome in ANALISES_QUIMICAS}
            dados_analise = pd.DataFrame(index=aba.index)
            dados_analise["Data"] = interpretar_data(aba[col_data]) if col_data is not None else pd.NaT
            dados_analise["Ordem de Serviço"] = os_nome
            dados_analise["Tipo"] = "Fertilidade (F)" if tipo == "F" else "PAV"
            dados_analise["_arquivo_status"] = status_arquivo
            for nome in ["Unidade", "Fazenda"]:
                coluna_id = coluna_por_nome(aba, nome)
                dados_analise[nome] = (
                    aba[coluna_id].fillna("").astype(str).str.strip()
                    if coluna_id is not None
                    else "(não identificada)"
                )
            dados_analise["_sid"] = (
                aba[coluna_por_nome(aba, "SID")].fillna("").astype(str).str.strip()
                if coluna_por_nome(aba, "SID") is not None
                else ""
            )
            colunas_chave = [
                coluna_por_nome(aba, nome)
                for nome in ["SID", "Cat_Profundidade", "Profundidade", "Data", "Unidade", "Fazenda", "Obj-ID"]
            ]
            colunas_chave = [nome for nome in colunas_chave if nome is not None]
            chave_linha = aba[colunas_chave].fillna("").astype(str).agg("|".join, axis=1)
            for coluna, nome_coluna in colunas.items():
                if nome_coluna is None:
                    erros.append(f"Coluna {coluna} ausente: {path.name}")
                    dados_analise[coluna] = False
                else:
                    dados_analise[coluna] = (
                        aba[nome_coluna].fillna("").astype(str).str.strip().str.upper().eq("X")
                    )

            if not dados_analise.empty:
                # Combina identificadores e profundidade para preservar amostras em camadas distintas.
                dados_analise["_chave_linha"] = chave_linha.loc[dados_analise.index]
                linhas_analises.append(dados_analise.reset_index(drop=True))

    # Mantém F e PAV separados para o gráfico e para a tabela de resultados.
    linhas = []
    for (os_nome, unidade, fazenda, tipo), dados in encontrados.items():
        concluido = bool(dados["preenchido"])
        linhas.append(
            {
                "Ordem de Serviço": os_nome,
                "Unidade": unidade or "(não identificada)",
                "Fazenda": fazenda or "(não identificada)",
                "Tipo": "Fertilidade (F)" if tipo == "F" else "PAV",
                "Status": "Concluído" if concluido else "Não concluído",
            }
        )

    df_analises = pd.concat(linhas_analises, ignore_index=True) if linhas_analises else pd.DataFrame()
    if not df_analises.empty:
        grupos = ["Ordem de Serviço", "Tipo"]
        pares_com_pedido = set(
            map(tuple, df_analises.loc[df_analises["_arquivo_status"] == "pedido", grupos].drop_duplicates().to_numpy())
        )
        chave_tipo = list(zip(df_analises["Ordem de Serviço"], df_analises["Tipo"]))
        manter = (df_analises["_arquivo_status"] == "pedido") | ~pd.Series(chave_tipo, index=df_analises.index).isin(pares_com_pedido)
        df_analises = df_analises.loc[manter].drop_duplicates(
            subset=["Ordem de Serviço", "Tipo", "_chave_linha"], keep="first"
        )

    return pd.DataFrame(linhas), df_analises, erros, documentos


with st.sidebar:
    st.header("Pasta de origem")
    raiz_texto = st.text_input(
        "Caminho da pasta no servidor",
        placeholder=r"Ex.: \\servidor\pasta\cliente ou Z:\Ordens",
        help="Informe manualmente o caminho acessível pela máquina que executa o Streamlit.",
    )
    iniciar = st.button("Buscar documentos", type="primary", use_container_width=True)

if iniciar:
    if not raiz_texto.strip():
        st.sidebar.error("Informe o caminho da pasta.")
    else:
        raiz = Path(raiz_texto.strip().strip('"'))
        if not raiz.exists() or not raiz.is_dir():
            st.sidebar.error("A pasta não foi encontrada ou não está acessível pelo servidor do Streamlit.")
        else:
            with st.spinner("Lendo pastas e planilhas. Isso pode levar alguns instantes..."):
                dados, analises, erros, quantidade = escanear(raiz)
            st.session_state["resultado"] = dados
            st.session_state["analises"] = analises
            st.session_state["erros"] = erros
            st.session_state["quantidade"] = quantidade
            st.session_state["raiz"] = str(raiz)

if "resultado" not in st.session_state:
    st.info("Informe a pasta na lateral e clique em **Buscar documentos**.")
    st.markdown(
        """
        **Arquivos procurados**

        - `F...S_QUIMICO_SIMPLES.xlsx` e `F...S_QUIMICO_SIMPLES_PREENCHIDA.xlsx`
        - `PAV...S_QUIMICO_SIMPLES.xlsx` e `PAV...S_QUIMICO_SIMPLES_PREENCHIDA.xlsx`

        O painel percorre as subpastas. O nome da pasta mais próxima contendo números é usado como OS.
        """
    )
    st.stop()

df = st.session_state["resultado"]
df_analises = st.session_state.get("analises", pd.DataFrame())
st.caption(f"Pasta: `{st.session_state['raiz']}` · {st.session_state['quantidade']} documento(s) localizado(s)")

if df.empty and df_analises.empty:
    st.warning("Nenhum arquivo com o padrão esperado foi localizado.")
    st.stop()

aba_info, aba_analises = st.tabs(["Informações gerais", "Análises Químicas"])

with aba_info:
    if df.empty:
        st.warning("Não foram encontrados registros para a visualização geral.")
    else:
        total = len(df)
        concluidos = int((df["Status"] == "Concluído").sum())
        pendentes = total - concluidos
        c1, c2, c3 = st.columns(3)
        c1.metric("Registros OS / Unidade / Fazenda / Tipo", total)
        c2.metric("Concluídas", concluidos)
        c3.metric("Não concluídas", pendentes)

        left, right = st.columns([1, 2])
        with left:
            st.subheader("Conclusão por tipo")
            for tipo in ["Fertilidade (F)", "PAV"]:
                dados_tipo = df[df["Tipo"] == tipo]
                if dados_tipo.empty:
                    continue
                resumo = (
                    dados_tipo["Status"]
                    .value_counts()
                    .reindex(["Concluído", "Não concluído"], fill_value=0)
                    .rename_axis("Status")
                    .reset_index(name="Quantidade")
                )
                resumo = resumo[resumo["Quantidade"] > 0]
                fig = px.pie(
                    resumo,
                    values="Quantidade",
                    names="Status",
                    hole=0.42,
                    color="Status",
                    color_discrete_map={"Concluído": "#3b9d50", "Não concluído": "#c9d92c"},
                    title=tipo,
                )
                fig.update_layout(margin=dict(t=42, b=4, l=4, r=4), legend_title_text="")
                st.plotly_chart(fig, use_container_width=True)
        with right:
            st.subheader("Pesquisar e filtrar")
            f1, f2, f3 = st.columns(3)
            q_os = f1.text_input("Ordem de Serviço", placeholder="Digite para buscar")
            q_unidade = f2.text_input("Unidade", placeholder="Digite para buscar")
            q_fazenda = f3.text_input("Fazenda", placeholder="Digite para buscar")
            tipos_escolhidos = st.multiselect("Tipo", ["Fertilidade (F)", "PAV"], default=["Fertilidade (F)", "PAV"])
            status_escolhidos = st.multiselect("Status", ["Concluído", "Não concluído"], default=["Concluído", "Não concluído"])

        filtrado = df.copy()
        for coluna, termo in [("Ordem de Serviço", q_os), ("Unidade", q_unidade), ("Fazenda", q_fazenda)]:
            if termo.strip():
                filtrado = filtrado[filtrado[coluna].astype(str).str.contains(termo.strip(), case=False, na=False, regex=False)]
        filtrado = filtrado[filtrado["Status"].isin(status_escolhidos)]
        filtrado = filtrado[filtrado["Tipo"].isin(tipos_escolhidos)]

        st.subheader(f"Resultados ({len(filtrado)})")
        st.dataframe(
            filtrado[["Ordem de Serviço", "Unidade", "Fazenda", "Tipo", "Status"]],
            use_container_width=True,
            hide_index=True,
        )
        st.download_button(
            "Baixar resultado em CSV",
            data=filtrado.to_csv(index=False).encode("utf-8-sig"),
            file_name="acompanhamento_ordens_servico.csv",
            mime="text/csv",
        )

with aba_analises:
    st.subheader("Evolução das análises químicas requisitadas")
    st.caption("Percentual de linhas com “X” em cada OS, dividido pelo total de linhas daquela ordem.")
    if df_analises.empty:
        st.info("Não foram encontradas linhas para montar os gráficos.")
    else:
        filtro1, filtro2, filtro3 = st.columns(3)
        opcoes_os = sorted(df_analises["Ordem de Serviço"].dropna().unique().tolist())
        opcoes_unidade = sorted(df_analises["Unidade"].dropna().unique().tolist())
        opcoes_fazenda = sorted(df_analises["Fazenda"].dropna().unique().tolist())
        selecionadas_os = filtro1.multiselect("Ordem de Serviço", opcoes_os, default=opcoes_os, key="analises_os")
        selecionadas_unidade = filtro2.multiselect("Unidade", opcoes_unidade, default=opcoes_unidade, key="analises_unidade")
        selecionadas_fazenda = filtro3.multiselect("Fazenda", opcoes_fazenda, default=opcoes_fazenda, key="analises_fazenda")
        selecionadas_analises = st.multiselect(
            "Análises",
            ANALISES_QUIMICAS,
            default=ANALISES_QUIMICAS,
            key="analises_selecionadas",
            help="Escolha uma ou mais análises. Por exemplo, selecione apenas MO para exibir somente essa série.",
        )

        base_analises = df_analises[
            df_analises["Ordem de Serviço"].isin(selecionadas_os)
            & df_analises["Unidade"].isin(selecionadas_unidade)
            & df_analises["Fazenda"].isin(selecionadas_fazenda)
        ].copy()
        ordem_os = sorted(
            base_analises["Ordem de Serviço"].dropna().unique().tolist(),
            key=lambda nome: (
                int(re.search(r"\d+", str(nome)).group())
                if re.search(r"\d+", str(nome))
                else float("inf"),
                str(nome),
            ),
        )
        posicao_os = {os_nome: posicao for posicao, os_nome in enumerate(ordem_os)}

        for tipo in ["Fertilidade (F)", "PAV"]:
            tipo_df = base_analises[base_analises["Tipo"] == tipo]
            st.markdown(f"#### {tipo}")
            if tipo_df.empty:
                st.info("Sem registros para os filtros selecionados.")
                continue
            if not selecionadas_analises:
                st.info("Selecione pelo menos uma análise no filtro acima.")
                continue
            series = []
            for analise in selecionadas_analises:
                agregado = tipo_df.groupby("Ordem de Serviço")[analise].agg(["sum", "count"]).reset_index()
                agregado["Percentual"] = agregado["sum"] / agregado["count"] * 100
                agregado["Posicao"] = agregado["Ordem de Serviço"].map(posicao_os)
                curva = spline_cubica(agregado[["Posicao", "Percentual"]])
                curva["Análise"] = analise
                series.append(curva)
            grafico_df = pd.concat(series, ignore_index=True)
            fig = px.line(
                grafico_df,
                x="Posicao",
                y="Percentual",
                color="Análise",
                range_y=[0, 100],
                labels={"Posicao": "Ordem de Serviço", "Percentual": "Linhas selecionadas (%)"},
            )
            # O traçado já foi interpolado com spline cúbica; só desenha a linha, sem marcadores.
            fig.update_traces(mode="lines")
            fig.update_layout(
                margin=dict(t=16, b=10, l=10, r=10),
                legend_title_text="Análise",
                yaxis_ticksuffix="%",
                xaxis=dict(
                    tickmode="array",
                    tickvals=list(range(len(ordem_os))),
                    ticktext=ordem_os,
                ),
            )
            st.plotly_chart(fig, use_container_width=True)

st.caption("A busca ocorre no computador/servidor onde o Streamlit está em execução; o caminho precisa estar acessível por ele.")
