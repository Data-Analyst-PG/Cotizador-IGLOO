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

# ✅ Conexión a Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# ✅ Valores por defecto
valores_por_defecto = {
    "Rendimiento Camion": 2.5,
    "Costo Diesel": 24.0,
}

# ✅ Ruta para valores locales
RUTA_DATOS = "datos_generales.csv"

# ✅ Cargar valores desde CSV o usar los por defecto
if os.path.exists(RUTA_DATOS):
    df_datos = pd.read_csv(RUTA_DATOS).set_index("Parametro")["Valor"].to_dict()
    valores = {**valores_por_defecto, **df_datos}
else:
    valores = valores_por_defecto.copy()

# ✅ Cargar rutas desde Supabase
respuesta = supabase.table("Rutas").select("*").execute()
df = pd.DataFrame(respuesta.data)

# ✅ Asegurar formato correcto
if not df.empty:
    df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.strftime("%Y-%m-%d")
    df["Ingreso Total"] = pd.to_numeric(df["Ingreso Total"], errors="coerce").fillna(0)
    df["Costo_Total_Ruta"] = pd.to_numeric(df["Costo_Total_Ruta"], errors="coerce").fillna(0)

st.title("🔍 Consulta Individual de Ruta")

def safe_number(x):
    return 0 if pd.isna(x) else x

def mostrar_resultados(ingreso_total, costo_total, utilidad_bruta, costos_indirectos, utilidad_neta, porcentaje_bruta, porcentaje_neta):
    st.markdown("---")
    st.subheader("📊 Ingresos y Utilidades")

    def colored_bold(label, value, condition):
        color = "green" if condition else "red"
        return f"<strong>{label}:</strong> <span style='color:{color}; font-weight:bold'>{value}</span>"

    st.write(f"**Ingreso Total:** ${ingreso_total:,.2f}")
    st.write(f"**Costo Total:** ${costo_total:,.2f}")
    st.markdown(colored_bold("Utilidad Bruta", f"${utilidad_bruta:,.2f}", utilidad_bruta >= 0), unsafe_allow_html=True)
    st.markdown(colored_bold("% Utilidad Bruta", f"{porcentaje_bruta:.2f}%", porcentaje_bruta >= 50), unsafe_allow_html=True)
    st.write(f"**Costos Indirectos (35%):** ${costos_indirectos:,.2f}")
    st.markdown(colored_bold("Utilidad Neta", f"${utilidad_neta:,.2f}", utilidad_neta >= 0), unsafe_allow_html=True)
    st.markdown(colored_bold("% Utilidad Neta", f"{porcentaje_neta:.2f}%", porcentaje_neta >= 15), unsafe_allow_html=True)
    
if df.empty:
    st.warning("⚠️ No hay rutas guardadas todavía.")
    st.stop()

st.subheader("📌 Selecciona Tipo de Ruta")
tipo_sel = st.selectbox("Tipo", ["IMPO", "EXPO", "VACIO"])

df_tipo = df[df["Tipo"] == tipo_sel]
rutas_unicas = df_tipo[["Origen", "Destino"]].drop_duplicates()
opciones_ruta = list(rutas_unicas.itertuples(index=False, name=None))

st.subheader("📌 Selecciona Ruta (Origen → Destino)")
ruta_sel = st.selectbox("Ruta", opciones_ruta, format_func=lambda x: f"{x[0]} → {x[1]}")
origen_sel, destino_sel = ruta_sel

df_filtrada = df_tipo[(df_tipo["Origen"] == origen_sel) & (df_tipo["Destino"] == destino_sel)]

if df_filtrada.empty:
    st.warning("⚠️ No hay rutas con esa combinación.")
    st.stop()

st.subheader("📌 Selecciona Cliente")
opciones = df_filtrada.index.tolist()
index_sel = st.selectbox(
    "Cliente",
    opciones,
    format_func=lambda x: f"{df.loc[x, 'Cliente']} ({df.loc[x, 'Origen']} → {df.loc[x, 'Destino']})"
)

ruta = df.loc[index_sel]
    
# Campos simulables
st.markdown("---")
st.subheader("⚙️ Ajustes para Simulación")
costo_diesel_input = st.number_input("Costo del Diesel ($/L)", value=float(valores.get("Costo Diesel", 24.0)))
rendimiento_input = st.number_input("Rendimiento Camión (km/L)", value=float(valores.get("Rendimiento Camion", 2.65)))


if st.button("🔁 Simular"):
    st.session_state["simular"] = True

# Mostrar resultados simulados si está activo
if st.session_state.get("simular", False):
    ingreso_total = safe_number(ruta["Ingreso Total"])
    costo_diesel_camion = (safe_number(ruta["KM"]) / rendimiento_input) * costo_diesel_input
    costo_diesel_termo = safe_number(ruta["Horas_Termo"]) * float(valores.get("Rendimiento Termo", 3.0)) * costo_diesel_input

    costo_total = (
        costo_diesel_camion +
        costo_diesel_termo +
        safe_number(ruta["Sueldo_Operador"]) +
        safe_number(ruta["Bono"]) +
        safe_number(ruta["Casetas"]) +
        safe_number(ruta["Costo Cruce Convertido"]) +
        safe_number(ruta["Costo_Extras"])
    )

    utilidad_bruta = ingreso_total - costo_total
    costos_indirectos = ingreso_total * 0.35
    utilidad_neta = utilidad_bruta - costos_indirectos
    porcentaje_bruta = (utilidad_bruta / ingreso_total * 100) if ingreso_total > 0 else 0
    porcentaje_neta = (utilidad_neta / ingreso_total * 100) if ingreso_total > 0 else 0

    st.success("🔧 Estás viendo una simulación. Los valores han sido ajustados con los parámetros ingresados.")
    mostrar_resultados(ingreso_total, costo_total, utilidad_bruta, costos_indirectos, utilidad_neta, porcentaje_bruta, porcentaje_neta)

    # Botón para volver a valores reales
    if st.button("🔄 Volver a valores reales"):
        st.session_state["simular"] = False
        st.rerun()

# Mostrar resultados reales por defecto
else:
    ingreso_total = safe_number(ruta["Ingreso Total"])
    costo_total = safe_number(ruta["Costo_Total_Ruta"])
    utilidad_bruta = ingreso_total - costo_total
    costos_indirectos = ingreso_total * 0.35
    utilidad_neta = utilidad_bruta - costos_indirectos
    porcentaje_bruta = (utilidad_bruta / ingreso_total * 100) if ingreso_total > 0 else 0
    porcentaje_neta = (utilidad_neta / ingreso_total * 100) if ingreso_total > 0 else 0

    mostrar_resultados(ingreso_total, costo_total, utilidad_bruta, costos_indirectos, utilidad_neta, porcentaje_bruta, porcentaje_neta)

    
# =====================
# 📋 Detalles y Costos
# =====================
st.markdown("---")
st.subheader("📋 Detalles y Costos de la Ruta")
    
col1, col2, col3 = st.columns(3)
    
with col1:
    st.write(f"Fecha: {ruta['Fecha']}")
    st.write(f"Tipo: {ruta['Tipo']}")
    st.write(f"Modo: {ruta.get('Modo de Viaje', 'Operado')}")
    st.write(f"Cliente: {ruta['Cliente']}")
    st.write(f"Origen → Destino: {ruta['Origen']} → {ruta['Destino']}")
    st.write(f"KM: {safe_number(ruta['KM']):,.2f}")
    st.write(f"Rendimiento Camión: {rendimiento_input:.2f}")
        
with col2:
    st.write(f"Moneda Flete: {ruta['Moneda']}")
    st.write(f"Ingreso Flete Original: ${safe_number(ruta['Ingreso_Original']):,.2f}")
    st.write(f"Tipo de cambio: {safe_number(ruta['Tipo de cambio']):,.2f}")
    st.write(f"Ingreso Flete Convertido: ${safe_number(ruta['Ingreso Flete']):,.2f}")
    st.write(f"Moneda Cruce: {ruta['Moneda_Cruce']}")
    st.write(f"Ingreso Cruce Original: ${safe_number(ruta['Cruce_Original']):,.2f}")
    st.write(f"Tipo cambio Cruce: {safe_number(ruta['Tipo cambio Cruce']):,.2f}")
    st.write(f"Ingreso Cruce Convertido: ${safe_number(ruta['Ingreso Cruce']):,.2f}")
    st.write(f"Moneda Costo Cruce: {ruta['Moneda Costo Cruce']}")
    st.write(f"Costo Cruce Original: ${safe_number(ruta['Costo Cruce']):,.2f}")
    st.write(f"Costo Cruce Convertido: ${safe_number(ruta['Costo Cruce Convertido']):,.2f}")
    if st.session_state.get("simular", False):
        costo_diesel_camion = (safe_number(ruta["KM"]) / rendimiento_input) * costo_diesel_input
        st.write(f"Diesel Camión (Simulado): ${costo_diesel_camion:,.2f}")
    else:
        st.write(f"Diesel Camión: ${safe_number(ruta['Costo_Diesel_Camion']):,.2f}")
    if st.session_state.get("simular", False):
        costo_diesel_termo = safe_number(ruta["Horas_Termo"]) * safe_number(ruta["KM"]) * costo_diesel_input
        st.write(f"Diesel Termo (Simulado): ${costo_diesel_termo:,.2f}")
    else:
        st.write(f"Diesel Termo: ${safe_number(ruta['Costo_Diesel_Termo']):,.2f}")
    st.write(f"Sueldo Operador: ${safe_number(ruta['Sueldo_Operador']):,.2f}")
    st.write(f"Bono: ${safe_number(ruta['Bono']):,.2f}")
    st.write(f"Casetas: ${safe_number(ruta['Casetas']):,.2f}")
        
with col3:
    st.write("**Extras:**")
    st.write(f"- Lavado Termo: ${safe_number(ruta['Lavado_Termo']):,.2f}")
    st.write(f"- Movimiento Local: ${safe_number(ruta['Movimiento_Local']):,.2f}")
    st.write(f"- Puntualidad: ${safe_number(ruta['Puntualidad']):,.2f}")
    st.write(f"- Pensión: ${safe_number(ruta['Pension']):,.2f}")
    st.write(f"- Estancia: ${safe_number(ruta['Estancia']):,.2f}")
    st.write(f"- Fianza Termo: ${safe_number(ruta['Fianza_Termo']):,.2f}")
    st.write(f"- Renta Termo: ${safe_number(ruta['Renta_Termo']):,.2f}")
    st.write(f"- Pistas Extra: ${safe_number(ruta.get('Pistas_Extra', 0)):,.2f}")
    st.write(f"- Stop: ${safe_number(ruta.get('Stop', 0)):,.2f}")
    st.write(f"- Falso: ${safe_number(ruta.get('Falso', 0)):,.2f}")
    st.write(f"- Gatas: ${safe_number(ruta.get('Gatas', 0)):,.2f}")
    st.write(f"- Accesorios: ${safe_number(ruta.get('Accesorios', 0)):,.2f}")
    st.write(f"- Guías: ${safe_number(ruta.get('Guias', 0)):,.2f}")
