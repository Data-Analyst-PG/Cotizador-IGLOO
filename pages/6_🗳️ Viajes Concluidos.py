# =====================================
# 4. FILTRO Y RESUMEN DE VIAJES CONCLUIDOS
# =====================================

import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client

# ✅ Verificación de sesión y rol
if "usuario" not in st.session_state:
    st.error("⚠️ No has iniciado sesión.")
    st.stop()

rol = st.session_state.usuario.get("Rol", "").lower()
if rol not in ["admin", "gerente", "ejecutivo"]:
    st.error("🚫 No tienes permiso para acceder a este módulo.")
    st.stop()

# 🔧 Conexión a Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.title("✅ Tráficos Concluidos con Filtro de Fechas")

def cargar_programaciones():
    data = supabase.table("Traficos").select("*").execute()
    df = pd.DataFrame(data.data)
    if df.empty:
        return pd.DataFrame()
    df["Fecha_Cierre"] = pd.to_datetime(df["Fecha_Cierre"], errors="coerce")
    return df

df = cargar_programaciones()

if df.empty:
    st.info("ℹ️ Aún no hay programaciones registradas.")
else:
    st.subheader("📅 Filtro por Fecha (Fecha de Cierre de la VUELTA)")
    fecha_min = df["Fecha_Cierre"].min()
    fecha_max = df["Fecha_Cierre"].max()
    hoy = datetime.today().date()

    fecha_inicio = st.date_input("Fecha inicio", value=fecha_min.date() if pd.notna(fecha_min) else hoy)
    fecha_fin = st.date_input("Fecha fin", value=fecha_max.date() if pd.notna(fecha_max) else hoy)

    cerrados = df[df["Fecha_Cierre"].notna()]
    traficos_cerrados = cerrados["Número_Trafico"].unique()
    df_filtrado = df[df["Número_Trafico"].isin(traficos_cerrados)].copy()

    fechas_vuelta = df_filtrado[df_filtrado["Fecha_Cierre"].notna()].groupby("Número_Trafico")["Fecha_Cierre"].max()
    fechas_vuelta = fechas_vuelta[(fechas_vuelta >= pd.to_datetime(fecha_inicio)) & (fechas_vuelta <= pd.to_datetime(fecha_fin))]

    df_filtrado = df_filtrado[df_filtrado["Número_Trafico"].isin(fechas_vuelta.index)]

    if df_filtrado.empty:
        st.warning("No hay tráficos concluidos en ese rango de fechas.")
    else:
        resumen = []
        for trafico in df_filtrado["Número_Trafico"].unique():
            tramos = df_filtrado[df_filtrado["Número_Trafico"] == trafico]
            ida = tramos[tramos["ID_Programacion"].str.contains("_IDA")].iloc[0] if not tramos[tramos["ID_Programacion"].str.contains("_IDA")].empty else None
            vuelta = tramos[~tramos["ID_Programacion"].str.contains("_IDA")]

            ingreso_total = tramos["Ingreso Total"].sum()
            costo_total = tramos["Costo_Total_Ruta"].sum()
            utilidad_bruta = ingreso_total - costo_total
            utilidad_pct = round(utilidad_bruta / ingreso_total * 100, 2) if ingreso_total else 0

            cliente_ida = ida["Cliente"] if ida is not None else ""
            ruta_ida = f"{ida['Origen']} → {ida['Destino']}" if ida is not None else ""

            clientes_vuelta = " | ".join(vuelta["Cliente"].dropna().astype(str))
            rutas_vuelta = " | ".join(f"{row['Origen']} → {row['Destino']}" for _, row in vuelta.iterrows())
            fecha_cierre = vuelta["Fecha_Cierre"].max().date() if not vuelta.empty else ""

            resumen.append({
                "Número_Trafico": trafico,
                "Fecha": fecha_cierre,
                "Cliente IDA": cliente_ida,
                "Ruta IDA": ruta_ida,
                "Clientes VUELTA": clientes_vuelta,
                "Rutas VUELTA": rutas_vuelta,
                "Ingreso Total VR": ingreso_total,
                "Costo Total VR": costo_total,
                "Utilidad Total VR": utilidad_bruta,
                "% Utilidad Total VR": utilidad_pct
            })

        resumen_df = pd.DataFrame(resumen)
        st.subheader("📋 Resumen de Viajes Redondos")
        st.dataframe(resumen_df, use_container_width=True)

        # Botón para descargar resumen
        csv = resumen_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Descargar Resumen en CSV",
            data=csv,
            file_name="resumen_viajes_redondos.csv",
            mime="text/csv"
        )
        
        # Botón para descargar detalle completo filtrado
        detalle = df_filtrado.copy()
        detalle_csv = detalle.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Descargar Detalle Completo en CSV",
            data=detalle_csv,
            file_name="detalle_completo_viajes_redondos.csv",
            mime="text/csv"
        )
