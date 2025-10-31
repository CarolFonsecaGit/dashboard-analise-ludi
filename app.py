import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Matriculados UFC - Análise por Área", layout="wide")
st.title("Dashboard simples - Matriculados UFC")
st.write("Cada linha do arquivo representa um discente. O app conta registros e mostra proporções de mulheres e mulheres pretas por área de conhecimento.")

CSV = "estudantes-matriculados-graduacao - Discentes Matriculados 20251.csv"

# 1) Carrega os dados
df = pd.read_csv(CSV)

# 2) Padroniza nomes de colunas (pequeno tratamento)
df.columns = [c.strip().lower().replace(" ", "_").replace("é", "e").replace("ç", "c") for c in df.columns]

# 3) Mostrar colunas detectadas na sidebar para debug
st.sidebar.header("Info do arquivo")
st.sidebar.write(list(df.columns))

# 4) Renomeia automaticamente colunas comuns para nomes simples
candidates = {
    "curso": ["curso", "habilitacao", "nome", "nome_do_curso"],
    "sexo": ["sexo", "genero"],
    "raca": ["raca", "raca_etinia", "raca_etnia"],
    "ano": ["ano", "ano_matricula", "ano_ingresso"],
    "campus": ["campus", "unidade", "unidade_academica"]
}

for nice_name, options in candidates.items():
    for opt in options:
        if opt in df.columns:
            df = df.rename(columns={opt: nice_name})
            break

# 5) Checagem mínima: precisamos de 'curso' ao menos
if "curso" not in df.columns:
    st.error("O arquivo não contém uma coluna de curso reconhecida. Verifique as colunas na barra lateral.")
    st.stop()

# 6) Cria coluna de contagem (cada linha = 1 discente)
df["count"] = 1

# 7) Mapear cursos para áreas de conhecimento (mesmo mapeamento do notebook)
areaDeConhecimento = {
    'CIENCIAS AGRARIAS': ['AGRONOMIA','ENGENHARIA DE ALIMENTOS','ENGENHARIA DE PESCA','ZOOTECNIA'],
    'CIENCIAS BIOLOGICAS': ['CIENCIAS BIOLOGICAS','BIOTECNOLOGIA','BIOLOGIA'],
    'CIENCIAS DA SAUDE': ['ENFERMAGEM','EDUCACAO FISICA','MEDICINA','FISIOTERAPIA',
                           'ODONTOLOGIA','FARMACIA','PSICOLOGIA','NUTRICAO','BIOMEDICINA'],
    'CIENCIAS EXATAS E DA TERRA': ['CIENCIA DA COMPUTACAO','COMPUTACAO','INFORMATICA','FISICA',
                                   'MATEMATICA','QUIMICA','ESTATISTICA','ENGENHARIA DE SOFTWARE',
                                   'ENGENHARIA DA COMPUTACAO','SISTEMAS DE INFORMACAO','CIENCIA DE DADOS'],
    'CIENCIAS HUMANAS': ['FILOSOFIA','HISTORIA','SOCIOLOGIA','LETRAS','PEDAGOGIA','GEOGRAFIA'],
    'CIENCIAS SOCIAIS APLICADAS': ['ADMINISTRACAO','CIENCIAS ECONOMICAS','DIREITO','PUBLICIDADE',
                                   'JORNALISMO','TURISMO','LOGISTICA','CONTABILIDADE','GESTAO'],
    'ENGENHARIAS': ['ENGENHARIA CIVIL','ENGENHARIA ELETRICA','ENGENHARIA MECANICA',
                    'ENGENHARIA METALURGICA','ENGENHARIA QUIMICA','ENGENHARIA DE PRODUCAO',
                    'ENGENHARIA AMBIENTAL'],
    'LINGUISTICA E ARTES': ['ARTES','MUSICA','DANCA','TEATRO','CINEMA','DESIGN','CINEMA E AUDIOVISUAL'],
    'OUTROS': ['OUTROS']
}

# criar mapa curso->area
curso_para_area = {}
for area, cursos in areaDeConhecimento.items():
    for curso in cursos:
        curso_para_area[curso] = area

# coluna auxiliar com nome do curso em maiúsculas para mapear
df['curso_upper'] = df['curso'].astype(str).str.strip().str.upper()
df['area_de_conhecimento'] = df['curso_upper'].map(curso_para_area).fillna('OUTROS')

# 8) Filtros simples na sidebar
st.sidebar.header("Filtros")
# filtro ano
if "ano" in df.columns:
    anos = sorted(df["ano"].dropna().unique())
    anos_selecionados = st.sidebar.multiselect("Ano", anos, default=anos)
else:
    anos_selecionados = None

# filtro campus
if "campus" in df.columns:
    campi = sorted(df["campus"].dropna().unique())
    campi_selecionados = st.sidebar.multiselect("Campus", campi, default=campi)
else:
    campi_selecionados = None

# filtro area de conhecimento
areas = sorted(df["area_de_conhecimento"].dropna().unique())
areas_selecionadas = st.sidebar.multiselect("Área de Conhecimento", areas, default=areas)

# filtro curso (opcional)
cursos = sorted(df["curso"].dropna().unique())
cursos_selecionados = st.sidebar.multiselect("Curso (opcional)", cursos, default=cursos)

# 9) Aplicar filtros de forma segura
df_filtered = df.copy()
if anos_selecionados is not None:
    df_filtered = df_filtered[df_filtered["ano"].isin(anos_selecionados)]
if campi_selecionados is not None:
    df_filtered = df_filtered[df_filtered["campus"].isin(campi_selecionados)]
if areas_selecionadas:
    df_filtered = df_filtered[df_filtered["area_de_conhecimento"].isin(areas_selecionadas)]
if cursos_selecionados:
    df_filtered = df_filtered[df_filtered["curso"].isin(cursos_selecionados)]

st.write(f"Registros após filtros: {len(df_filtered)}")

# 10) Agregados básicos por área
agg_area = df_filtered.groupby("area_de_conhecimento").agg(
    total_discentes = ("count", "sum")
).reset_index()

# 11) Calcular mulheres por área (se houver coluna 'sexo')
if "sexo" in df_filtered.columns:
    # considera feminino quem começa com 'F' (tolerante a maiúsc/minúsc)
    df_filtered["sexo_norm"] = df_filtered["sexo"].astype(str).str.strip().str.upper()
    mulheres_area = df_filtered[df_filtered["sexo_norm"].str.startswith("F")].groupby("area_de_conhecimento").agg(
        mulheres = ("count", "sum")
    ).reset_index()
    # juntar com agg_area
    agg_area = agg_area.merge(mulheres_area, on="area_de_conhecimento", how="left")
    agg_area["mulheres"] = agg_area["mulheres"].fillna(0).astype(int)
else:
    agg_area["mulheres"] = 0
    st.info("Coluna 'sexo' não encontrada — gráficos de mulheres estarão indisponíveis.")

# 12) Proporção de mulheres por área
agg_area["pct_mulheres_total"] = (agg_area["mulheres"] / agg_area["total_discentes"] * 100).fillna(0)

# 13) Recorte por raça: mulheres pretas por área
# Definimos valores considerados 'pretos/pardos/negros' comuns e normalizamos
black_values = {"PRETA","PRETO","NEGRA","NEGRO","PARDA","PARDAS","PARD0","PARD0?","PARD"}  # inclui variantes; o importante é estar em maiúsculas após normalizar
if "raca" in df_filtered.columns and "sexo" in df_filtered.columns:
    df_filtered["raca_norm"] = df_filtered["raca"].astype(str).str.strip().str.upper()
    # mulheres pretas: sexo feminino e raca em black_values (ajuste conforme os valores do seu CSV)
    cond_mulher_preta = df_filtered["sexo_norm"].str.startswith("F") & df_filtered["raca_norm"].isin(black_values)
    mulheres_pretas_area = df_filtered[cond_mulher_preta].groupby("area_de_conhecimento").agg(
        mulheres_pretas = ("count", "sum")
    ).reset_index()
    agg_area = agg_area.merge(mulheres_pretas_area, on="area_de_conhecimento", how="left")
    agg_area["mulheres_pretas"] = agg_area["mulheres_pretas"].fillna(0).astype(int)
    # proporção de mulheres pretas sobre total da área e sobre mulheres da área
    agg_area["pct_mulheres_pretas_total"] = (agg_area["mulheres_pretas"] / agg_area["total_discentes"] * 100).fillna(0)
    agg_area["pct_mulheres_pretas_sobre_mulheres"] = (agg_area["mulheres_pretas"] / agg_area["mulheres"].replace(0, pd.NA) * 100).fillna(0)
else:
    agg_area["mulheres_pretas"] = 0
    agg_area["pct_mulheres_pretas_total"] = 0
    agg_area["pct_mulheres_pretas_sobre_mulheres"] = 0
    st.info("Coluna 'raca' não encontrada — recorte por raça indisponível.")

# 14) Mostrar tabela resumo por área
st.subheader("Resumo por Área de Conhecimento")
st.dataframe(
    agg_area[[
        "area_de_conhecimento", "total_discentes", "mulheres", "pct_mulheres_total",
        "mulheres_pretas", "pct_mulheres_pretas_total", "pct_mulheres_pretas_sobre_mulheres"
    ]].sort_values("total_discentes", ascending=False).reset_index(drop=True)
)

st.markdown("---")

# 15) Gráfico: Proporção de mulheres por área (percentual)
st.subheader("Proporção de mulheres por área (mulheres / total da área)")
fig_pct_mulheres = px.bar(
    agg_area.sort_values("pct_mulheres_total", ascending=False),
    x="area_de_conhecimento",
    y="pct_mulheres_total",
    labels={"area_de_conhecimento":"Área","pct_mulheres_total":"% Mulheres"},
    title="Percentual de mulheres sobre total de discentes por área"
)
fig_pct_mulheres.update_layout(yaxis_tickformat=",.1f")
st.plotly_chart(fig_pct_mulheres, use_container_width=True)

st.markdown("---")

# 16) Gráfico: Proporção de mulheres pretas por área
st.subheader("Proporção de mulheres pretas por área")
if "raca" in df_filtered.columns and "sexo" in df_filtered.columns:
    # Gráfico 1: mulheres pretas sobre total da área
    fig_mp_total = px.bar(
        agg_area.sort_values("pct_mulheres_pretas_total", ascending=False),
        x="area_de_conhecimento",
        y="pct_mulheres_pretas_total",
        labels={"area_de_conhecimento":"Área","pct_mulheres_pretas_total":"% Mulheres pretas (sobre total)"},
        title="Percentual de mulheres pretas sobre o total de discentes por área"
    )
    fig_mp_total.update_layout(yaxis_tickformat=",.2f")
    st.plotly_chart(fig_mp_total, use_container_width=True)

    st.markdown("**Recorte dentro do universo feminino:** percentual de mulheres pretas sobre o total de mulheres da área")
    # Gráfico 2: mulheres pretas sobre mulheres da área
    fig_mp_sobre_mulheres = px.bar(
        agg_area.sort_values("pct_mulheres_pretas_sobre_mulheres", ascending=False),
        x="area_de_conhecimento",
        y="pct_mulheres_pretas_sobre_mulheres",
        labels={"area_de_conhecimento":"Área","pct_mulheres_pretas_sobre_mulheres":"% Mulheres pretas (sobre mulheres)"},
        title="Percentual de mulheres pretas sobre todas as mulheres por área"
    )
    fig_mp_sobre_mulheres.update_layout(yaxis_tickformat=",.2f")
    st.plotly_chart(fig_mp_sobre_mulheres, use_container_width=True)
else:
    st.info("Para mostrar proporções por raça é preciso que o arquivo tenha as colunas 'raca' e 'sexo'.")

st.markdown("---")

# 17) Mostrar dados originais filtrados (opcional)
with st.expander("Ver registros filtrados (linhas)"):
    st.dataframe(df_filtered.drop(columns=["count","curso_upper","sexo_norm","raca_norm"], errors="ignore").reset_index(drop=True))

