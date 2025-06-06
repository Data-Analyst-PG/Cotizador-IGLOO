import streamlit as st
import hashlib
from supabase import create_client

# 🔐 Función para hashear contraseñas
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# 🔗 Conexión a Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# ✅ Título
st.title("🔐 Iniciar Sesión")

# 👉 Formulario de login
correo = st.text_input("Correo (ID Usuario)")
password = st.text_input("Contraseña", type="password")

# 🔍 Verificación de credenciales
def verificar_credenciales(correo, password):
    try:
        res = supabase.table("Usuarios").select("*").eq("ID Usuario", correo).execute()
        if res.data:
            user = res.data[0]
            if user.get("Password Hash") == hash_password(password):
                return user
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
    return None

# 🟢 Botón de acceso
if st.button("Ingresar"):
    usuario = verificar_credenciales(correo, password)
    if usuario:
        st.session_state.usuario = usuario
        st.success(f"✅ Bienvenido, {usuario['Nombre']}")
        st.experimental_rerun()
    else:
        st.error("❌ Credenciales incorrectas")

import streamlit as st
from PIL import Image
import base64
from io import BytesIO

# Ruta al logo
LOGO_CLARO = "Igloo Original.png"
LOGO_OSCURO = "Igloo White.png"

# Función para convertir imagen a base64
@st.cache_data
def image_to_base64(img_path):
    with open(img_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode()

logo_claro_b64 = image_to_base64(LOGO_CLARO)
logo_oscuro_b64 = image_to_base64(LOGO_OSCURO)

# Mostrar encabezado con logo dinámico
st.markdown(f"""
    <div style='text-align: center;'>
        <img src="data:image/png;base64,{logo_claro_b64}" class="logo-light" style="height: 120px; margin-bottom: 20px;">
        <img src="data:image/png;base64,{logo_oscuro_b64}" class="logo-dark" style="height: 120px; margin-bottom: 20px;">
    </div>
    <h1 style='text-align: center; color: #003366;'>Sistema Cotizador IGLOO</h1>
    <p style='text-align: center;'>Control de rutas, costos, programación y simulación de utilidad</p>
    <hr style='margin-top: 20px; margin-bottom: 30px;'>
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

# Instrucciones de navegación
st.subheader("📂 Módulos disponibles")
st.markdown("""
- **🛣️ Captura de Rutas:** Ingreso de datos de nuevas rutas
- **🔍 Consulta Individual de Ruta:** Análisis detallado por registro
- **🔁 Simulador Vuelta Redonda:** Combinaciones IMPO + VACIO + EXPO
- **🚚 Programación de Viajes:** Registro y simulación de tráficos ida y vuelta
- **🗂️ Gestión de Rutas:** Editar y eliminar rutas existentes
- **📂 Archivos:** Descargar / cargar respaldos de datos
- **✅ Tráficos Concluidos:** Reporte de rentabilidad
""")

st.info("Selecciona una opción desde el menú lateral para comenzar 🚀")
