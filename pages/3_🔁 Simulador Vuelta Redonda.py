import streamlit as st
import pandas as pd
from supabase import create_client
import os

# ✅ Verificación de sesión y rol
if "usuario" not in st.session_state:
    st.error("⚠️ No has iniciado sesión.")
    st.stop()

rol = st.session_state.usuario.get("Rol", "").lower()
if rol not in ["admin", "gerente", "ejecutivo", "visitante"]:
    st.error("🚫 No tienes permiso para acceder a este módulo.")
    st.stop()

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
df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.strftime("%Y-%m-%d")
df["Utilidad"] = df["Ingreso Total"] - df["Costo_Total_Ruta"]
df["% Utilidad"] = (df["Utilidad"] / df["Ingreso Total"] * 100).round(2)

# Paso 1: Selección ruta principal
st.subheader("📌 Ruta Principal")
tipos_disponibles = df["Tipo"].unique().tolist()
tipo_ruta_1 = st.selectbox("Selecciona tipo de ruta principal", tipos_disponibles)

rutas_tipo_1 = df[df["Tipo"] == tipo_ruta_1]
opciones_1 = rutas_tipo_1[["Origen", "Destino"]].drop_duplicates().sort_values(by=["Origen", "Destino"])

if opciones_1.empty:
    st.error("⚠️ No hay rutas disponibles para este tipo.")
    st.stop()

ruta_seleccionada_1 = st.selectbox("Selecciona ruta", opciones_1.itertuples(index=False), format_func=lambda x: f"{x.Origen} → {x.Destino}")
candidatas_1 = rutas_tipo_1[
    (rutas_tipo_1["Origen"] == ruta_seleccionada_1.Origen) &
    (rutas_tipo_1["Destino"] == ruta_seleccionada_1.Destino)
].sort_values(by="% Utilidad", ascending=False).reset_index(drop=True)

# Filtrado según tipo
if tipo_ruta_1 in ["IMPO", "EXPO"]:
    if candidatas_1["Cliente"].dropna().empty:
        st.error("⚠️ No hay clientes disponibles para esta ruta.")
        st.stop()
    candidatas_1["opcion"] = candidatas_1.apply(
        lambda row: f"{row['Fecha']} — {row['Cliente']}", axis=1
    )
    opcion_seleccionada = st.selectbox("Cliente / Fecha", candidatas_1["opcion"].tolist())
    ruta_1 = candidatas_1[candidatas_1["opcion"] == opcion_seleccionada].iloc[0]

elif tipo_ruta_1 == "VACIO":
    if candidatas_1.empty:
        st.error("⚠️ No hay rutas VACÍO disponibles para ese origen/destino.")
        st.stop()
    ruta_1 = candidatas_1.iloc[0]

else:
    st.error("⚠️ Tipo de ruta no reconocido.")
    st.stop()

# Paso 2: Sugerencia automática de combinaciones
st.markdown("---")
st.subheader("🔁 Rutas sugeridas (combinaciones con o sin vacío)")

tipo_principal = ruta_1["Tipo"]
tipo_regreso = "EXPO" if tipo_principal == "IMPO" else "IMPO"
destino_origen = ruta_1["Destino"]  # puede ser usado para directas o para buscar vacíos

sugerencias = []

# ➤ Rutas directas desde el destino actual
directas = df[(df["Tipo"] == tipo_regreso) & (df["Origen"] == destino_origen)].copy()
for _, row in directas.iterrows():
    ingreso_total = safe_number(ruta_1["Ingreso Total"]) + safe_number(row["Ingreso Total"])
    costo_total = safe_number(ruta_1["Costo_Total_Ruta"]) + safe_number(row["Costo_Total_Ruta"])
    utilidad = ingreso_total - costo_total
    porcentaje = (utilidad / ingreso_total) * 100 if ingreso_total else 0
    sugerencias.append({
        "descripcion": f"{row['Fecha']} — {row['Cliente']} → {row['Origen']} → {row['Destino']} ({porcentaje:.2f}%)",
        "tramos": [row],
        "utilidad": utilidad
    })

# ➤ Rutas con VACÍO + cliente
vacios = df[(df["Tipo"] == "VACIO") & (df["Origen"] == destino_origen)].copy()
for _, vacio in vacios.iterrows():
    origen_post = vacio["Destino"]
    candidatos = df[(df["Tipo"] == tipo_regreso) & (df["Origen"] == origen_post)].copy()
    for _, final in candidatos.iterrows():
        ingreso_total = safe_number(ruta_1["Ingreso Total"]) + safe_number(final["Ingreso Total"])
        costo_total = safe_number(ruta_1["Costo_Total_Ruta"]) + safe_number(vacio["Costo_Total_Ruta"]) + safe_number(final["Costo_Total_Ruta"])
        utilidad = ingreso_total - costo_total
        porcentaje = (utilidad / ingreso_total) * 100 if ingreso_total else 0
        descripcion = f"{final['Fecha']} — {final['Cliente']} (Vacío → {vacio['Origen']} → {vacio['Destino']}) → {final['Destino']} ({porcentaje:.2f}%)"
        sugerencias.append({
            "descripcion": descripcion,
            "tramos": [vacio, final],
            "utilidad": utilidad
        })

# Si la ruta principal es VACÍO, solo buscar desde su destino
if tipo_principal == "VACIO":
    origen_vacio = ruta_1["Destino"]
    candidatos = df[(df["Tipo"].isin(["IMPO", "EXPO"])) & (df["Origen"] == origen_vacio)].copy()
    for _, final in candidatos.iterrows():
        ingreso_total = safe_number(ruta_1["Ingreso Total"]) + safe_number(final["Ingreso Total"])
        costo_total = safe_number(ruta_1["Costo_Total_Ruta"]) + safe_number(final["Costo_Total_Ruta"])
        utilidad = ingreso_total - costo_total
        porcentaje = (utilidad / ingreso_total) * 100 if ingreso_total else 0
        descripcion = f"{final['Fecha']} — {final['Cliente']} {final['Origen']} → {final['Destino']} ({porcentaje:.2f}%)"
        sugerencias.append({
            "descripcion": descripcion,
            "tramos": [final],
            "utilidad": utilidad
        })

# Ordenar sugerencias por utilidad
sugerencias = sorted(sugerencias, key=lambda x: safe_number(x.get("utilidad", 0)), reverse=True)

# Inicializar rutas seleccionadas
rutas_seleccionadas = []

# Mostrar selectbox con todas las opciones
if sugerencias:
    # Crear un diccionario de mapeo {descripcion: objeto_sugerencia}
    opciones_sugeridas = {s["descripcion"]: s for s in sugerencias}

    # Mostrar las descripciones
    descripcion_seleccionada = st.selectbox(
        "Selecciona una opción de regreso sugerida",
        list(opciones_sugeridas.keys()),
        key="selectbox_regreso"
    )

    # Recuperar el objeto seleccionado
    seleccion = opciones_sugeridas[descripcion_seleccionada]
    if seleccion is not None and "tramos" in seleccion:
        rutas_seleccionadas = [ruta_1] + seleccion["tramos"]
    else:
        rutas_seleccionadas = [ruta_1]
else:
    st.warning("⚠️ No hay rutas de regreso disponibles.")
    rutas_seleccionadas = [ruta_1]

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
        st.markdown(f"- Fecha: {r.get('Fecha', 'N/A')}")
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
            f"Fecha: {r.get('Fecha', 'N/A')}",
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
