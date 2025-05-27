import streamlit as st
import pandas as pd
import os

RUTA_RUTAS = "rutas_guardadas.csv"

st.title("🔁 Simulador de Vuelta Redonda")

def safe_number(x):
    return 0 if (x is None or (isinstance(x, float) and pd.isna(x))) else x

if os.path.exists(RUTA_RUTAS):
    df = pd.read_csv(RUTA_RUTAS)

    impo_rutas = df[df["Tipo"] == "IMPO"].copy()
    expo_rutas = df[df["Tipo"] == "EXPO"].copy()
    vacio_rutas = df[df["Tipo"] == "VACIO"].copy()

st.subheader("📌 Paso 1: Selecciona tipo de ruta principal")
tipo_principal = st.selectbox("Tipo principal", ["IMPO", "EXPO", "VACIO"])

ruta_1 = ruta_2 = ruta_3 = None
rutas_seleccionadas = []

def elegir_ruta(df_tipo, label):
    rutas_unicas = df_tipo[["Origen", "Destino"]].drop_duplicates()
    opciones_ruta = list(rutas_unicas.itertuples(index=False, name=None))
    ruta_sel = st.selectbox(label, opciones_ruta, format_func=lambda x: f"{x[0]} → {x[1]}")
    origen, destino = ruta_sel
    candidatas = df_tipo[(df_tipo["Origen"] == origen) & (df_tipo["Destino"] == destino)].copy()
    candidatas["Utilidad"] = candidatas["Ingreso Total"] - candidatas["Costo_Total_Ruta"]
    candidatas["% Utilidad"] = (candidatas["Utilidad"] / candidatas["Ingreso Total"] * 100).round(2)
    candidatas = candidatas.sort_values(by="% Utilidad", ascending=False).reset_index()
    idx = st.selectbox("Cliente (ordenado por % utilidad)", candidatas.index,
                      format_func=lambda i: f"{candidatas.loc[i, 'Cliente']} ({candidatas.loc[i, '% Utilidad']:.2f}%)")
    return candidatas.loc[idx]

if tipo_principal == "IMPO":
    ruta_1 = elegir_ruta(impo_rutas, "Selecciona ruta IMPO")
    rutas_seleccionadas.append(ruta_1)

    st.markdown("---")
    st.subheader("📌 Paso 2: Ruta VACÍA (opcional)")
    vacios = vacio_rutas[vacio_rutas["Origen"] == ruta_1["Destino"]]
    if not vacios.empty:
        ruta_2 = elegir_ruta(vacios, "Selecciona ruta VACÍA")
        rutas_seleccionadas.append(ruta_2)

    st.markdown("---")
    st.subheader("📌 Paso 3: Ruta EXPO (opcional)")
    origen_expo = ruta_2["Destino"] if ruta_2 is not None else ruta_1["Destino"]
    candidatos = expo_rutas[expo_rutas["Origen"] == origen_expo]
    if not candidatos.empty:
        ruta_3 = elegir_ruta(candidatos, "Selecciona ruta EXPO")
        rutas_seleccionadas.append(ruta_3)

elif tipo_principal == "EXPO":
    ruta_1 = elegir_ruta(expo_rutas, "Selecciona ruta EXPO")
    rutas_seleccionadas.append(ruta_1)

    st.markdown("---")
    st.subheader("📌 Paso 2: Ruta VACÍA (opcional)")
    vacios = vacio_rutas[vacio_rutas["Origen"] == ruta_1["Destino"]]
    if not vacios.empty:
        ruta_2 = elegir_ruta(vacios, "Selecciona ruta VACÍA")
        rutas_seleccionadas.append(ruta_2)

    st.markdown("---")
    st.subheader("📌 Paso 3: Ruta IMPO (opcional)")
    origen_impo = ruta_2["Destino"] if ruta_2 is not None else ruta_1["Destino"]
    candidatos = impo_rutas[impo_rutas["Origen"] == origen_impo]
    if not candidatos.empty:
        ruta_3 = elegir_ruta(candidatos, "Selecciona ruta IMPO")
        rutas_seleccionadas.append(ruta_3)

elif tipo_principal == "VACIO":
    ruta_1 = elegir_ruta(vacio_rutas, "Selecciona ruta VACÍA")
    rutas_seleccionadas.append(ruta_1)

    st.markdown("---")
    st.subheader("📌 Paso 2: Ruta siguiente sugerida (IMPO o EXPO)")
    origen_siguiente = ruta_1["Destino"]
    candidatos = pd.concat([
        impo_rutas[impo_rutas["Origen"] == origen_siguiente],
        expo_rutas[expo_rutas["Origen"] == origen_siguiente]
    ])

    if not candidatos.empty:
        ruta_2 = elegir_ruta(candidatos, "Selecciona ruta IMPO o EXPO")
        rutas_seleccionadas.append(ruta_2)

# 🔁 Simulación y visualización
st.markdown("---")
if rutas_seleccionadas and st.button("🚛 Simular Vuelta Redonda"):
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
        st.markdown(f"- Tipo de cambio: {safe_number(r.get('Tipo_Cambio_Ingreso')):,.2f}")
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

    # 📋 Resumen final por columnas
    st.markdown("---")
    st.subheader("📋 Resumen de Rutas")

    tipos = ["IMPO", "VACIO", "EXPO"]
    cols = st.columns(3)

    def resumen_ruta(r):
        return [
            f"KM: {safe_number(r.get('KM')):,.2f}",
            f"Diesel Camión: ${safe_number(r.get('Costo_Diesel_Camion')):,.2f}",
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
