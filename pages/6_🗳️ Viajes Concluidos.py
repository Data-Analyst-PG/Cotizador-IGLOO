# 6_📂 Administración de Archivos
import streamlit as st
import pandas as pd
import os
from PIL import Image
import base64
from io import BytesIO

# ✅ Verificación de sesión y rol
if "usuario" not in st.session_state:
    st.error("⚠️ No has iniciado sesión.")
    st.stop()

rol = st.session_state.usuario.get("Rol", "").lower()
if rol not in ["admin", "gerente", "ejecutivo"]:
    st.error("🚫 No tienes permiso para acceder a este módulo.")
    st.stop()

# Función para convertir imagen en base64
def image_to_base64(img):
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

# Cargar logos
logo_claro = Image.open("PG Brand.png")
logo_oscuro = Image.open("PG Brand.png")
logo_claro_b64 = image_to_base64(logo_claro)
logo_oscuro_b64 = image_to_base64(logo_oscuro)

# Mostrar logo
st.markdown(f"""
    <div style='text-align: left; margin-bottom: 10px;'>
        <img src="data:image/png;base64,{logo_claro_b64}" class="logo-light" style="height:50px;">
        <img src="data:image/png;base64,{logo_oscuro_b64}" class="logo-dark" style="height:50px;">
    </div>
    <style>
    @media (prefers-color-scheme: dark) {{
        .logo-light {{ display: none; }}
        .logo-dark {{ display: inline; }}
    }}
    @media (prefers-color-scheme: light) {{
        .logo-light {{ display: inline; }}
        .logo-dark {{ display: none; }}
    }}
    </style>
""", unsafe_allow_html=True)

st.title("Administración de Archivos 📂")

RUTA_RUTAS = "rutas_guardadas.csv"
RUTA_DATOS = "datos_generales.csv"
RUTA_PROG = "viajes_programados.csv"

st.subheader("📥 Descargar respaldos")

# Descargar rutas_guardadas.csv
if os.path.exists(RUTA_RUTAS):
    rutas = pd.read_csv(RUTA_RUTAS)
    st.download_button(
        label="Descargar rutas_guardadas.csv",
        data=rutas.to_csv(index=False),
        file_name="rutas_guardadas.csv",
        mime="text/csv"
    )

# Descargar datos_generales.csv
if os.path.exists(RUTA_DATOS):
    datos = pd.read_csv(RUTA_DATOS)
    st.download_button(
        label="Descargar datos_generales.csv",
        data=datos.to_csv(index=False),
        file_name="datos_generales.csv",
        mime="text/csv"
    )

# Descargar viajes_programados.csv
if os.path.exists(RUTA_PROG):
    viajes = pd.read_csv(RUTA_PROG)
    st.download_button(
        label="Descargar viajes_programados.csv",
        data=viajes.to_csv(index=False),
        file_name="viajes_programados.csv",
        mime="text/csv"
    )

st.markdown("---")

st.subheader("📤 Restaurar desde archivos")

# Subir rutas_guardadas.csv
rutas_file = st.file_uploader("Subir rutas_guardadas.csv", type="csv", key="rutas_upload")
if rutas_file:
    try:
        rutas_df = pd.read_csv(rutas_file)
        rutas_df.to_csv(RUTA_RUTAS, index=False)
        st.success("✅ Rutas restauradas correctamente.")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Error al cargar rutas: {e}")

# Subir datos_generales.csv
datos_file = st.file_uploader("Subir datos_generales.csv", type="csv", key="datos_upload")
if datos_file:
    try:
        datos_df = pd.read_csv(datos_file)
        datos_df.to_csv(RUTA_DATOS, index=False)
        st.success("✅ Datos generales restaurados correctamente.")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Error al cargar datos generales: {e}")

# Subir viajes_programados.csv
prog_file = st.file_uploader("Subir viajes_programados.csv", type="csv", key="programacion_upload")
if prog_file:
    try:
        prog_df = pd.read_csv(prog_file)
        prog_df.to_csv(RUTA_PROG, index=False)
        st.success("✅ Programaciones de viaje restauradas correctamente.")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Error al cargar programaciones: {e}")
