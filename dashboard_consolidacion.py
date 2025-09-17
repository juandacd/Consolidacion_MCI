import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

# --------------------------
# 1. Configuración inicial
# --------------------------
st.set_page_config(
    page_title="Consolidación Iglesia", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⛪ Dashboard de Consolidación - Personas Nuevas")
st.markdown("---")

# --------------------------
# 2. Carga de datos
# --------------------------
@st.cache_data(ttl=300)  # Cache por 5 minutos
def load_data(url):
    """Carga y preprocesa los datos del Google Sheets"""
    try:
        df = pd.read_csv(url)
        return df, None
    except Exception as e:
        return None, str(e)

# Input para la URL del Google Sheets
with st.sidebar:
    st.header("⚙️ Configuración")
    sheet_url = st.text_input(
        "URL del Google Sheets (formato CSV)",
        value="https://docs.google.com/spreadsheets/d/e/TU_ID_AQUI/pub?gid=0&single=true&output=csv",
        help="Ve a Google Sheets → Archivo → Compartir → Publicar en la web → CSV"
    )
    
    if st.button("🔄 Actualizar datos"):
        st.cache_data.clear()

# Cargar datos
df, error = load_data(sheet_url)

if error:
    st.error(f"❌ Error al cargar datos: {error}")
    st.info("Por favor, verifica que la URL sea correcta y que el Google Sheets esté publicado como CSV.")
    st.stop()

if df is None or df.empty:
    st.warning("⚠️ No se pudieron cargar los datos o están vacíos.")
    st.stop()

# --------------------------
# 3. Preprocesamiento de datos
# --------------------------
@st.cache_data
def preprocess_data(df):
    """Preprocesa y limpia los datos"""
    df = df.copy()
    
    # Limpiar nombres de columnas
    df.columns = df.columns.str.strip()
    
    # Procesar fecha con formato día/mes/año
    if "Marca temporal" in df.columns:
        # Intentar primero con formato día/mes/año
        df["Marca temporal"] = pd.to_datetime(df["Marca temporal"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
        
        # Si hay valores nulos, intentar con otros formatos comunes
        if df["Marca temporal"].isna().any():
            mask_nulos = df["Marca temporal"].isna()
            # Intentar formato día/mes/año sin hora
            df.loc[mask_nulos, "Marca temporal"] = pd.to_datetime(
                df.loc[mask_nulos, "Marca temporal"], format="%d/%m/%Y", errors="coerce"
            )
            # Si aún hay nulos, usar dayfirst=True (día primero)
            if df["Marca temporal"].isna().any():
                mask_nulos = df["Marca temporal"].isna()
                df.loc[mask_nulos, "Marca temporal"] = pd.to_datetime(
                    df.loc[mask_nulos, "Marca temporal"], dayfirst=True, errors="coerce"
                )
        
        # Contar registros con fechas válidas vs inválidas
        fechas_validas = df["Marca temporal"].notna().sum()
        fechas_invalidas = df["Marca temporal"].isna().sum()
        
        st.info(f"📅 **Procesamiento de fechas:** {fechas_validas} válidas, {fechas_invalidas} inválidas")
        
        # NO eliminar filas sin fecha, mejor mantenerlas para análisis
        # df = df.dropna(subset=["Marca temporal"])
        
        # Extraer información temporal solo para fechas válidas
        mask_fechas_validas = df["Marca temporal"].notna()
        
        df["Año"] = df["Marca temporal"].dt.year
        df["Mes"] = df["Marca temporal"].dt.month
        df["Mes_Nombre"] = df["Marca temporal"].dt.strftime("%B")
        df["Semana"] = df["Marca temporal"].dt.isocalendar().week
        df["Dia_Semana"] = df["Marca temporal"].dt.day_name()
        df["Fecha"] = df["Marca temporal"].dt.date
        
        # Identificar fines de semana (solo para fechas válidas)
        if mask_fechas_validas.any():
            dias_semana_unicos = df.loc[mask_fechas_validas, "Marca temporal"].dt.dayofweek.unique()
            tiene_entre_semana = any(dia < 5 for dia in dias_semana_unicos)
            
            if tiene_entre_semana:
                df["Es_Fin_Semana"] = df["Marca temporal"].dt.dayofweek >= 5
            else:
                df["Es_Fin_Semana"] = True
    
    # Normalizar columnas de SI/NO
    columnas_sino = [
        "Llamada realizada y contestada (SI/NO)",
        "Ubicado en célula o Grupo Go! (SI/NO)", 
        "Visita realizada (SI/NO)"
    ]
    
    for col in columnas_sino:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.upper()
            df[col] = df[col].replace({"SÍ": "SI", "YES": "SI", "Y": "SI"})
    
    # Normalizar grupos de edad
    if "Tú eres:" in df.columns:
        df["Grupo_Edad"] = df["Tú eres:"].str.strip()
    
    # Normalizar barrios
    if "¿En qué barrio vives?" in df.columns:
        df["Barrio"] = df["¿En qué barrio vives?"].str.strip().str.title()
        df["Barrio"] = df["Barrio"].fillna("No especificado")
    
    return df

df = preprocess_data(df)

# --------------------------
# 4. Información de datos y filtros
# --------------------------
# Mostrar información de los datos cargados
st.info(f"📊 **Datos cargados:** {len(df)} registros totales")

# Mostrar rango de fechas (solo para fechas válidas)
if not df.empty and "Marca temporal" in df.columns:
    fechas_validas = df["Marca temporal"].dropna()
    if not fechas_validas.empty:
        fecha_min = fechas_validas.min().strftime("%d/%m/%Y")
        fecha_max = fechas_validas.max().strftime("%d/%m/%Y")
        st.info(f"📅 **Rango de fechas:** {fecha_min} a {fecha_max}")
    else:
        st.warning("⚠️ No hay fechas válidas en los datos")

# Mostrar años disponibles (solo para fechas válidas)
if "Año" in df.columns:
    años_válidos = df["Año"].dropna()
    if not años_válidos.empty:
        años_únicos = sorted(años_válidos.unique())
        st.info(f"📆 **Años disponibles:** {', '.join(map(str, años_únicos))}")
    else:
        st.warning("⚠️ No se pudieron extraer años de las fechas")

with st.sidebar:
    st.header("🔍 Filtros")
    
    # Filtro por año (permitir múltiples años)
    if "Año" in df.columns:
        años_válidos = df["Año"].dropna()
        if not años_válidos.empty:
            # Convertir a enteros y filtrar valores válidos
            años_disponibles = [int(a) for a in años_válidos.unique() if not pd.isna(a)]
            años_disponibles = sorted(años_disponibles)
            
            if años_disponibles:
                años_seleccionados = st.multiselect(
                    "📅 Años:", 
                    años_disponibles, 
                    default=años_disponibles,  # Por defecto todos los años
                    help="Selecciona uno o varios años para analizar"
                )
            else:
                años_seleccionados = []
                st.warning("No hay años válidos para filtrar")
        else:
            años_seleccionados = []
            st.warning("No hay años válidos para filtrar")
    else:
        años_seleccionados = []
    
    # Filtro por rango de meses
    if "Mes" in df.columns:
        meses_válidos = df["Mes"].dropna()
        if not meses_válidos.empty:
            meses_nombres = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            
            # Convertir a enteros y filtrar valores válidos (1-12)
            meses_disponibles = [int(m) for m in meses_válidos.unique() if 1 <= m <= 12]
            meses_disponibles = sorted(meses_disponibles)
            
            if meses_disponibles:
                # Checkbox para habilitar/deshabilitar filtro por meses
                usar_filtro_meses = st.checkbox("🗓️ Filtrar por rango de meses", value=False)
                
                if usar_filtro_meses:
                    mes_inicio = st.selectbox("🗓️ Mes inicio:", 
                                             [meses_nombres[m-1] for m in meses_disponibles],
                                             index=0)
                    mes_fin = st.selectbox("🗓️ Mes fin:", 
                                          [meses_nombres[m-1] for m in meses_disponibles],
                                          index=len(meses_disponibles)-1)
                    
                    # Convertir nombres a números
                    mes_inicio_num = meses_nombres.index(mes_inicio) + 1
                    mes_fin_num = meses_nombres.index(mes_fin) + 1
                else:
                    # Sin filtro de meses - mostrar todos
                    mes_inicio = "Enero"
                    mes_fin = "Diciembre"
                    mes_inicio_num = 1
                    mes_fin_num = 12
                    filtrar_por_meses = False
            else:
                st.warning("No hay meses válidos para filtrar")
                mes_inicio = "Enero"
                mes_fin = "Diciembre"
                mes_inicio_num = 1
                mes_fin_num = 12
                usar_filtro_meses = False
        else:
            mes_inicio = "Enero"
            mes_fin = "Diciembre"
            mes_inicio_num = 1
            mes_fin_num = 12
            usar_filtro_meses = False
    else:
        mes_inicio = "Enero"
        mes_fin = "Diciembre"
        mes_inicio_num = 1
        mes_fin_num = 12
        usar_filtro_meses = False
    
    # Filtro por grupo de edad
    if "Grupo_Edad" in df.columns:
        grupos = ["Todos"] + list(df["Grupo_Edad"].dropna().unique())
        grupo_seleccionado = st.selectbox("👥 Grupo de edad:", grupos)
    else:
        grupo_seleccionado = "Todos"
    
    # Filtro por líder
    if "Líder Principal" in df.columns:
        lideres = ["Todos"] + list(df["Líder Principal"].dropna().unique())
        lider_seleccionado = st.selectbox("👨‍💼 Líder Principal:", lideres)
    else:
        lider_seleccionado = "Todos"

# Aplicar filtros (solo a registros con fechas válidas para filtros temporales)
df_filtrado = df.copy()

# Filtro por años (solo aplicar si hay años válidos)
if años_seleccionados and "Año" in df.columns:
    # Mantener registros sin fecha + registros con años seleccionados
    mask_sin_fecha = df["Año"].isna()
    mask_años_seleccionados = df["Año"].isin(años_seleccionados)
    df_filtrado = df_filtrado[mask_sin_fecha | mask_años_seleccionados]

# Filtro por meses (solo aplicar si está habilitado y hay fechas válidas)
if usar_filtro_meses and "Mes" in df.columns and not df["Mes"].isna().all():
    mask_sin_fecha = df["Mes"].isna()
    
    if mes_inicio_num <= mes_fin_num:
        mask_meses = (df["Mes"] >= mes_inicio_num) & (df["Mes"] <= mes_fin_num)
    else:  # Caso donde el rango cruza el año
        mask_meses = (df["Mes"] >= mes_inicio_num) | (df["Mes"] <= mes_fin_num)
    
    df_filtrado = df_filtrado[mask_sin_fecha | mask_meses]

# Filtro por grupo de edad
if grupo_seleccionado != "Todos" and "Grupo_Edad" in df.columns:
    df_filtrado = df_filtrado[df_filtrado["Grupo_Edad"] == grupo_seleccionado]

# Filtro por líder
if lider_seleccionado != "Todos" and "Líder Principal" in df.columns:
    df_filtrado = df_filtrado[df_filtrado["Líder Principal"] == lider_seleccionado]

# --------------------------
# 5. Métricas principales
# --------------------------
rango_texto = f"Mostrando: {len(df_filtrado)} de {len(df)} registros"
if años_seleccionados:
    años_texto = ", ".join(map(str, años_seleccionados))
    rango_texto += f" | Años: {años_texto}"
if usar_filtro_meses:
    rango_texto += f" | Meses: {mes_inicio} - {mes_fin}"
else:
    rango_texto += " | Todos los meses"

st.header(f"📊 Resumen General")
st.caption(rango_texto)

col1, col2, col3, col4 = st.columns(4)

total_personas = len(df_filtrado)
total_llamadas = (df_filtrado.get("Llamada realizada y contestada (SI/NO)", pd.Series()) == "SI").sum()
total_celula = (df_filtrado.get("Ubicado en célula o Grupo Go! (SI/NO)", pd.Series()) == "SI").sum()
total_visita = (df_filtrado.get("Visita realizada (SI/NO)", pd.Series()) == "SI").sum()

# Calcular porcentajes
pct_llamadas = (total_llamadas / total_personas * 100) if total_personas > 0 else 0
pct_celula = (total_celula / total_personas * 100) if total_personas > 0 else 0
pct_visita = (total_visita / total_personas * 100) if total_personas > 0 else 0

col1.metric("👥 Personas Nuevas", total_personas)
col2.metric("📞 Llamadas", f"{total_llamadas} ({pct_llamadas:.1f}%)")
col3.metric("🏠 En Célula", f"{total_celula} ({pct_celula:.1f}%)")
col4.metric("🚪 Visitadas", f"{total_visita} ({pct_visita:.1f}%)")

# --------------------------
# 6. Gráficos de evolución temporal
# --------------------------
st.header("📈 Evolución Temporal")

tab1, tab2, tab3 = st.tabs(["📅 Por Mes", "📊 Por Semana", "🎯 Consolidación"])

with tab1:
    # Gráfico mensual
    mensual = df_filtrado.groupby(["Mes", "Mes_Nombre"]).size().reset_index(name="Nuevos")
    mensual = mensual.sort_values("Mes")
    
    fig_mes = px.line(
        mensual, 
        x="Mes_Nombre", 
        y="Nuevos",
        title="Personas Nuevas por Mes",
        markers=True,
        color_discrete_sequence=["#1f77b4"]
    )
    fig_mes.update_layout(xaxis_title="Mes", yaxis_title="Cantidad")
    st.plotly_chart(fig_mes, use_container_width=True)

with tab2:
    # Gráfico semanal
    semanal = df_filtrado.groupby(["Año", "Semana"]).size().reset_index(name="Nuevos")
    semanal["Periodo"] = semanal["Año"].astype(str) + "-S" + semanal["Semana"].astype(str).str.zfill(2)
    
    fig_sem = px.bar(
        semanal,
        x="Periodo",
        y="Nuevos", 
        title="Personas Nuevas por Semana",
        color_discrete_sequence=["#2ca02c"]
    )
    fig_sem.update_layout(
        xaxis_title="Semana", 
        yaxis_title="Cantidad",
        xaxis_tickangle=45
    )
    st.plotly_chart(fig_sem, use_container_width=True)
    
    # Mostrar estadísticas adicionales si solo hay sábados
    if not df_filtrado.empty and "Dia_Semana" in df_filtrado.columns:
        dias_unicos = df_filtrado["Dia_Semana"].dropna().unique()
        if len(dias_unicos) > 0:
            # Convertir a strings y filtrar valores válidos
            dias_validos = [str(dia) for dia in dias_unicos if pd.notna(dia)]
            if dias_validos:
                st.info(f"📅 **Días de la semana en los datos:** {', '.join(dias_validos)}")
            else:
                st.info("📅 **No hay días de la semana válidos en los datos**")
        else:
            st.info("📅 **No hay información de días de la semana**")

with tab3:
    # Embudo de consolidación
    etapas = ["Personas Nuevas", "Llamadas", "En Célula", "Visitadas"]
    valores = [total_personas, total_llamadas, total_celula, total_visita]
    
    fig_embudo = go.Figure(go.Funnel(
        y=etapas,
        x=valores,
        textinfo="value+percent initial",
        marker_color=["#3498db", "#e74c3c", "#f39c12", "#27ae60"]
    ))
    
    fig_embudo.update_layout(title="Embudo de Consolidación")
    st.plotly_chart(fig_embudo, use_container_width=True)

# --------------------------
# 7. Análisis por líder
# --------------------------
if "Líder Principal" in df_filtrado.columns:
    st.header("👨‍💼 Análisis por Líder Principal")
    
    # Crear métricas por líder
    lideres_stats = df_filtrado.groupby("Líder Principal").agg({
        "Nombres y apellidos completos": "count",
        "Llamada realizada y contestada (SI/NO)": lambda x: (x == "SI").sum(),
        "Ubicado en célula o Grupo Go! (SI/NO)": lambda x: (x == "SI").sum(),
        "Visita realizada (SI/NO)": lambda x: (x == "SI").sum()
    }).reset_index()
    
    lideres_stats.columns = ["Líder", "Nuevos", "Llamadas", "Célula", "Visitas"]
    
    # Calcular porcentajes
    lideres_stats["% Llamadas"] = (lideres_stats["Llamadas"] / lideres_stats["Nuevos"] * 100).round(1)
    lideres_stats["% Célula"] = (lideres_stats["Célula"] / lideres_stats["Nuevos"] * 100).round(1)
    lideres_stats["% Visitas"] = (lideres_stats["Visitas"] / lideres_stats["Nuevos"] * 100).round(1)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Gráfico de barras comparativo
        fig_lideres = px.bar(
            lideres_stats,
            x="Líder",
            y=["Nuevos", "Llamadas", "Célula", "Visitas"],
            title="Gestión por Líder Principal",
            barmode="group"
        )
        fig_lideres.update_layout(xaxis_title="Líder", yaxis_title="Cantidad")
        st.plotly_chart(fig_lideres, use_container_width=True)
    
    with col2:
        st.subheader("📊 Tabla Resumen")
        st.dataframe(lideres_stats, use_container_width=True)

# --------------------------
# 8. Análisis adicional
# --------------------------
st.header("🔍 Análisis Adicional")

col1, col2 = st.columns(2)

with col1:
    # Distribución por grupo de edad
    if "Grupo_Edad" in df_filtrado.columns:
        grupos_dist = df_filtrado["Grupo_Edad"].value_counts()
        fig_grupos = px.pie(
            values=grupos_dist.values,
            names=grupos_dist.index,
            title="Distribución por Grupo de Edad"
        )
        st.plotly_chart(fig_grupos, use_container_width=True)

with col2:
    # Top 10 barrios
    if "Barrio" in df_filtrado.columns:
        barrios_top = df_filtrado["Barrio"].value_counts().head(10)
        fig_barrios = px.bar(
            x=barrios_top.values,
            y=barrios_top.index,
            orientation="h",
            title="Top 10 Barrios",
            labels={"x": "Cantidad", "y": "Barrio"}
        )
        st.plotly_chart(fig_barrios, use_container_width=True)

# --------------------------
# 9. Datos detallados
# --------------------------
with st.expander("📋 Ver Datos Detallados"):
    st.subheader(f"Datos Filtrados ({len(df_filtrado)} registros)")
    
    # Seleccionar columnas relevantes para mostrar
    columnas_mostrar = [
        "Marca temporal", "Nombres y apellidos completos", 
        "No. de Celular", "Tú eres:", "Quién te Invito?", 
        "Líder Principal", "¿En qué barrio vives?",
        "Llamada realizada y contestada (SI/NO)",
        "Ubicado en célula o Grupo Go! (SI/NO)",
        "Visita realizada (SI/NO)"
    ]
    
    columnas_disponibles = [col for col in columnas_mostrar if col in df_filtrado.columns]
    st.dataframe(df_filtrado[columnas_disponibles], use_container_width=True)
    
    # Botón para descargar
    csv = df_filtrado.to_csv(index=False)
    
    # Crear nombre de archivo basado en los filtros aplicados
    años_texto = "_".join(map(str, años_seleccionados)) if años_seleccionados else "todos"
    nombre_archivo = f"consolidacion_filtrada_{años_texto}_{mes_inicio}_{mes_fin}.csv"
    
    st.download_button(
        label="💾 Descargar datos filtrados (CSV)",
        data=csv,
        file_name=nombre_archivo,
        mime="text/csv"
    )

# --------------------------
# 10. Footer con información
# --------------------------
st.markdown("---")
st.markdown("""
**📝 Nota:** Este dashboard se actualiza automáticamente desde Google Sheets. 
Los datos se almacenan en caché por 5 minutos para mejorar el rendimiento.
""")

# Mostrar última actualización
st.caption(f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Debug: mostrar información de procesamiento de fechas
with st.expander("🔍 Debug - Información de fechas"):
    if not df.empty:
        # Mostrar ejemplos de fechas originales vs procesadas
        muestra_fechas = df[["Marca temporal"]].head(10).copy()
        if "Marca temporal" in df.columns:
            # Obtener datos originales para comparar
            df_original = pd.read_csv(sheet_url)
            if "Marca temporal" in df_original.columns:
                muestra_fechas["Fecha_Original"] = df_original["Marca temporal"].head(10)
        
        debug_info = {
            "Total registros originales": len(df),
            "Fechas válidas procesadas": df["Marca temporal"].notna().sum(),
            "Fechas inválidas": df["Marca temporal"].isna().sum(),
            "Rango de años procesados": f"{df['Año'].min()} - {df['Año'].max()}" if "Año" in df.columns and df["Año"].notna().any() else "N/A",
            "Años seleccionados en filtros": años_seleccionados if años_seleccionados else "Ninguno",
            "Filtro de meses": f"{mes_inicio} ({mes_inicio_num}) - {mes_fin} ({mes_fin_num})" if usar_filtro_meses else "Todos los meses",
            "Registros después de filtros": len(df_filtrado),
        }
        
        st.json(debug_info)
        
        if not muestra_fechas.empty:
            st.write("**Muestra de fechas procesadas:**")
            st.dataframe(muestra_fechas)
    else:
        st.write("No hay datos para mostrar")