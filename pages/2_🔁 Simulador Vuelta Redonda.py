import streamlit as st
import pandas as pd
from supabase import create_client
import os

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.title("🔁 Simulador de Vuelta Redonda")

def safe_number(x):
    return 0 if (x is None or (isinstance(x, float) and pd.isna(x))) else x

# Cargar rutas desde Supabase
respuesta = supabase.table("Rutas").select("*").execute()
if not respuesta.data:
    st.warning("⚠️ No hay rutas guardadas en Supabase.")
    st.stop()

df = pd.DataFrame(respuesta.data)
df["Utilidad"] = df["Ingreso Total"] - df["Costo_Total_Ruta"]
df["% Utilidad"] = (df["Utilidad"] / df["Ingreso Total"] * 100).round(2)

# Paso 1: Selección ruta principal
st.subheader("📌 Ruta Principal")
tipos_disponibles = df["Tipo"].unique().tolist()
tipo_ruta_1 = st.selectbox("Selecciona tipo de ruta principal", tipos_disponibles)

rutas_tipo_1 = df[df["Tipo"] == tipo_ruta_1]
opciones_1 = rutas_tipo_1[["Origen", "Destino"]].drop_duplicates().sort_values(by=["Origen", "Destino"])
ruta_seleccionada_1 = st.selectbox("Selecciona ruta", opciones_1.itertuples(index=False), format_func=lambda x: f"{x.Origen} → {x.Destino}")
candidatas_1 = rutas_tipo_1[(rutas_tipo_1["Origen"] == ruta_seleccionada_1.Origen) & (rutas_tipo_1["Destino"] == ruta_seleccionada_1.Destino)]
candidatas_1 = candidatas_1.sort_values(by="% Utilidad", ascending=False).reset_index(drop=True)
cliente_1 = None
if not candidatas_1["Cliente"].dropna().empty:
    cliente_1 = st.selectbox("Cliente", candidatas_1["Cliente"].dropna().tolist())
    ruta_1 = candidatas_1[candidatas_1["Cliente"] == cliente_1].iloc[0]
else:
    # Para rutas VACÍO sin cliente
    ruta_1 = candidatas_1.iloc[0]
cliente_1 = st.selectbox("Cliente", candidatas_1["Cliente"].tolist())
ruta_1 = candidatas_1[candidatas_1["Cliente"] == cliente_1].iloc[0]

# Inicializar lista con la ruta principal
rutas_seleccionadas = [ruta_1] + seleccion["tramos"]

# Paso 2: Sugerencia automática de combinaciones
st.markdown("---")
st.subheader("🔁 Ruta sugerida de regreso (combinaciones con o sin vacío)")

tipo_principal = ruta_1["Tipo"]
tipo_regreso = "EXPO" if tipo_principal == "IMPO" else "IMPO"
destino_origen = ruta_1["Destino"]  # puede ser usado para directas o para buscar vacíos

sugerencias = []

# ➤ Rutas directas desde el destino actual
directas = df[(df["Tipo"] == tipo_regreso) & (df["Origen"] == destino_origen)].copy()
for _, row in directas.iterrows():
    utilidad = safe_number(row["Ingreso Total"]) - safe_number(row["Costo_Total_Ruta"])
    porcentaje = (utilidad / safe_number(row["Ingreso Total"])) * 100 if row["Ingreso Total"] else 0
    sugerencias.append({
        "descripcion": f"{row['Cliente']} → {row['Origen']} → {row['Destino']} ({porcentaje:.2f}%)",
        "tramos": [row],
        "utilidad": utilidad
    })

# ➤ Rutas con VACÍO + cliente
vacios = df[(df["Tipo"] == "VACIO") & (df["Origen"] == destino_origen)].copy()
for _, vacio in vacios.iterrows():
    origen_post = vacio["Destino"]
    candidatos = df[(df["Tipo"] == tipo_regreso) & (df["Origen"] == origen_post)].copy()
    for _, final in candidatos.iterrows():
        ingreso_total = safe_number(vacio["Ingreso Total"]) + safe_number(final["Ingreso Total"])
        costo_total = safe_number(vacio["Costo_Total_Ruta"]) + safe_number(final["Costo_Total_Ruta"])
        utilidad = ingreso_total - costo_total
        porcentaje = (utilidad / ingreso_total) * 100 if ingreso_total else 0
        descripcion = f"{final['Cliente']} (Vacío → {vacio['Origen']} → {vacio['Destino']}) → {final['Destino']} ({porcentaje:.2f}%)"
        sugerencias.append({
            "descripcion": descripcion,
            "tramos": [vacio, final],
            "utilidad": utilidad
        })

# Si la ruta principal es VACÍO, sólo buscar desde el destino del VACÍO
if tipo_principal == "VACIO":
    origen_vacio = ruta_1["Destino"]
    candidatos = df[((df["Tipo"] == "IMPO") | (df["Tipo"] == "EXPO")) & (df["Origen"] == origen_vacio)].copy()
    for _, final in candidatos.iterrows():
        utilidad = safe_number(final["Ingreso Total"]) - safe_number(final["Costo_Total_Ruta"])
        porcentaje = (utilidad / safe_number(final["Ingreso Total"])) * 100 if final["Ingreso Total"] else 0
        descripcion = f"{final['Cliente']} {final['Origen']} → {final['Destino']} ({porcentaje:.2f}%)"
        sugerencias.append({
            "descripcion": descripcion,
            "tramos": [final],
            "utilidad": utilidad
        })

# Ordenar sugerencias por utilidad
sugerencias = sorted(sugerencias, key=lambda x: x["utilidad"], reverse=True)

# Mostrar selectbox con todas las opciones
seleccion = st.selectbox(
    "Selecciona una opción de regreso sugerida",
    sugerencias,
    format_func=lambda x: x["descripcion"]
)

# Inicializar rutas seleccionadas
rutas_seleccionadas = [ruta_1] + seleccion["tramos"]

rutas_seleccionadas = [r if isinstance(r, dict) else r.to_dict() for r in rutas_seleccionadas]

if len(candidatas_1) == 0:
    st.warning("⚠️ No hay rutas disponibles con esos criterios.")
    st.stop()

# 🔁 Simulación y visualización
st.markdown("---")
if st.button("🚛 Simular Vuelta Redonda"):
    ingreso_total = sum(safe_number(r.get("Ingreso Total", 0)) for r in rutas_seleccionadas)
    costo_total_general = sum(safe_number(r.get("Costo_Total_Ruta", 0)) for r in rutas_seleccionadas)
    utilidad_bruta = ingreso_total - costo_total_general
    costos_indirectos = ingreso_total * 0.35
    utilidad_neta = utilidad_bruta - costos_indirectos
    pct_bruta = (utilidad_bruta / ingreso_total * 100) if ingreso_total > 0 else 0
    pct_neta = (utilidad_neta / ingreso_total * 100) if ingreso_total > 0 else 0

    st.markdown("---")
    st.markdown("## 📄 Detalle de Rutas")
    for r in rutas_seleccionadas:
        st.markdown(f"**{r['Tipo']} — {r.get('Cliente', 'nan')}**")
        st.markdown(f"- {r['Origen']} → {r['Destino']}")
        st.markdown(f"- Ingreso Original: ${safe_number(r.get('Ingreso_Original')):,.2f}")
        st.markdown(f"- Moneda: {r.get('Moneda', 'N/A')}")
        st.markdown(f"- Tipo de cambio: {safe_number(r.get('Tipo de cambio')):,.2f}")
        st.markdown(f"- Ingreso Total: ${safe_number(r.get('Ingreso Total')):,.2f}")
        st.markdown(f"- Costo Total Ruta: ${safe_number(r.get('Costo_Total_Ruta')):,.2f}")

    st.markdown("---")
    st.subheader("📊 Resultado General")
    st.markdown(f"<strong>Ingreso Total:</strong> <span style='font-weight:bold'>${ingreso_total:,.2f}</span>", unsafe_allow_html=True)
    st.markdown(f"<strong>Costo Total:</strong> <span style='font-weight:bold'>${costo_total_general:,.2f}</span>", unsafe_allow_html=True)

    color_utilidad_bruta = "green" if utilidad_bruta >= 0 else "red"
    st.markdown(f"<strong>Utilidad Bruta:</strong> <span style='color:{color_utilidad_bruta}; font-weight:bold'>${utilidad_bruta:,.2f}</span>", unsafe_allow_html=True)

    color_porcentaje_bruta = "green" if pct_bruta >= 50 else "red"
    st.markdown(f"<strong>% Utilidad Bruta:</strong> <span style='color:{color_porcentaje_bruta}; font-weight:bold'>{pct_bruta:.2f}%</span>", unsafe_allow_html=True)

    st.markdown(f"<strong>Costos Indirectos (35%):</strong> <span style='font-weight:bold'>${costos_indirectos:,.2f}</span>", unsafe_allow_html=True)

    color_utilidad_neta = "green" if utilidad_neta >= 0 else "red"
    st.markdown(f"<strong>Utilidad Neta:</strong> <span style='color:{color_utilidad_neta}; font-weight:bold'>${utilidad_neta:,.2f}</span>", unsafe_allow_html=True)

    color_porcentaje_neta = "green" if pct_neta >= 15 else "red"
    st.markdown(f"<strong>% Utilidad Neta:</strong> <span style='color:{color_porcentaje_neta}; font-weight:bold'>{pct_neta:.2f}%</span>", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("📋 Resumen de Rutas")

    tipos = ["IMPO", "VACIO", "EXPO"]
    cols = st.columns(3)

    def resumen_ruta(r):
        return [
            f"KM: {safe_number(r.get('KM')):,.2f}",
            f"Costo Diesel: ${safe_number(r.get('Costo Diesel')):,.2f}",
            f"Rendimiento Camión: {safe_number(r.get('Rendimiento Camion')):,.2f} km/l",
            f"Diesel Camión: ${safe_number(r.get('Costo_Diesel_Camion')):,.2f}",
            f"Rendimiento Termo: {safe_number(r.get('Rendimiento Termo')):,.2f} l/hr",
            f"Diesel Termo: ${safe_number(r.get('Costo_Diesel_Termo')):,.2f}",
            f"Sueldo: ${safe_number(r.get('Sueldo_Operador')):,.2f}",
            f"Casetas: ${safe_number(r.get('Casetas')):,.2f}",
            f"Costo Cruce Convertido: ${safe_number(r.get('Costo Cruce Convertido')):,.2f}",
            f"Ingreso Original: ${safe_number(r.get('Ingreso_Original')):,.2f}",
            f"Moneda: {r.get('Moneda', 'N/A')}",
            f"Tipo de cambio: {safe_number(r.get('Tipo de cambio')):,.2f}",
            "**Extras detallados:**",
            f"Lavado Termo: ${safe_number(r.get('Lavado_Termo')):,.2f}",
            f"Movimiento Local: ${safe_number(r.get('Movimiento_Local')):,.2f}",
            f"Puntualidad: ${safe_number(r.get('Puntualidad')):,.2f}",
            f"Pensión: ${safe_number(r.get('Pension')):,.2f}",
            f"Estancia: ${safe_number(r.get('Estancia')):,.2f}",
            f"Fianza Termo: ${safe_number(r.get('Fianza_Termo')):,.2f}",
            f"Renta Termo: ${safe_number(r.get('Renta_Termo')):,.2f}",
            f"Pistas Extra: ${safe_number(r.get('Pistas_Extra')):,.2f}",
            f"Stop: ${safe_number(r.get('Stop')):,.2f}",
            f"Falso: ${safe_number(r.get('Falso')):,.2f}",
            f"Gatas: ${safe_number(r.get('Gatas')):,.2f}",
            f"Accesorios: ${safe_number(r.get('Accesorios')):,.2f}",
            f"Guías: ${safe_number(r.get('Guias')):,.2f}"
        ]

    for i, tipo in enumerate(tipos):
        with cols[i]:
            st.markdown(f"**{tipo}**")
            ruta = next((r for r in rutas_seleccionadas if r["Tipo"] == tipo), None)
            if ruta is not None:
                for line in resumen_ruta(ruta):
                    st.write(line)
            else:
                st.write("No aplica")
