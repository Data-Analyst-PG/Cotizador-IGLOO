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
cliente_1 = st.selectbox("Cliente", candidatas_1["Cliente"].tolist())
ruta_1 = candidatas_1[candidatas_1["Cliente"] == cliente_1].iloc[0]

# Paso 2: Sugerencia automática de combinaciones
st.markdown("---")
st.subheader("🔁 Ruta sugerida de regreso")

combinaciones = {
    "IMPO → VACIO → EXPO": ["VACIO", "EXPO"],
    "IMPO → EXPO": ["EXPO"],
    "EXPO → VACIO → IMPO": ["VACIO", "IMPO"],
    "EXPO → IMPO": ["IMPO"],
    "VACIO → IMPO": ["IMPO"],
    "VACIO → EXPO": ["EXPO"]
}

opcion_combo = st.selectbox("Selecciona combinación de regreso", list(combinaciones.keys()))
tipos_combo = combinaciones[opcion_combo]

rutas_seleccionadas = [ruta_1]
ultimo_destino = ruta_1["Destino"]

for tipo in tipos_combo:
    df_opciones = df[(df["Tipo"] == tipo) & (df["Origen"] == ultimo_destino)].copy()

    if df_opciones.empty:
        st.warning(f"⚠️ No hay rutas tipo {tipo} desde {ultimo_destino}")
        break

    # Crear selectbox de ruta Origen → Destino
    rutas_unicas = df_opciones[["Origen", "Destino"]].drop_duplicates()
    ruta_sel = st.selectbox(
        f"Ruta {tipo}",
        rutas_unicas.itertuples(index=False),
        key=f"rutas_{tipo}",
        format_func=lambda x: f"{x.Origen} → {x.Destino}"
    )

    # Filtrar clientes para esa ruta y ordenar por % Utilidad
    rutas_filtradas = df_opciones[(df_opciones["Origen"] == ruta_sel.Origen) & (df_opciones["Destino"] == ruta_sel.Destino)].copy()
    rutas_filtradas["Utilidad"] = rutas_filtradas["Ingreso Total"] - rutas_filtradas["Costo_Total_Ruta"]
    rutas_filtradas["% Utilidad"] = (rutas_filtradas["Utilidad"] / rutas_filtradas["Ingreso Total"] * 100).round(2)
    rutas_filtradas = rutas_filtradas.sort_values(by="% Utilidad", ascending=False).reset_index(drop=True)

    cliente_sel = st.selectbox(
        f"Cliente para ruta {tipo}",
        rutas_filtradas.index,
        key=f"cliente_{tipo}",
        format_func=lambda i: f"{rutas_filtradas.loc[i, 'Cliente']} — {rutas_filtradas.loc[i, 'Origen']} → {rutas_filtradas.loc[i, 'Destino']} ({rutas_filtradas.loc[i, '% Utilidad']:.2f}%)"
    )

    ruta = rutas_filtradas.loc[cliente_sel]
    rutas_seleccionadas.append(ruta)
    ultimo_destino = ruta["Destino"]

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
            F"Rendimiento Camió: {safe_number(r.get('Rendimiento Camion')):,.2f} km/l",
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

else:
    st.warning("⚠️ No hay rutas guardadas todavía.")
