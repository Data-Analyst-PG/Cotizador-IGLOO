import streamlit as st
import hashlib
import base64
from supabase import create_client
from PIL import Image

# =========================
# 🔐 LOGIN Y AUTENTICACIÓN
# =========================

# Función para hashear contraseñas
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Conexión a Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# Formulario de login (si no hay sesión activa)
if "usuario" not in st.session_state:
    st.title("🔐 Iniciar Sesión")
    correo = st.text_input("ID Usuario")
    password = st.text_input("Contraseña", type="password")

    def verificar_credenciales(correo, password):
        try:
            res = supabase.table("Usuarios").select("*").eq("ID_Usuario", correo).execute()
            if res.data:
                user = res.data[0]
                if user.get("Password_Hash") == hash_password(password):
                    return user
        except Exception as e:
            st.error(f"❌ Error de conexión: {e}")
        return None

    if st.button("Ingresar"):
        usuario = verificar_credenciales(correo, password)
        if usuario:
            st.session_state.usuario = usuario
            st.success(f"✅ Bienvenido, {usuario['Nombre']}")
            st.rerun()
        else:
            st.error("❌ Credenciales incorrectas")
    st.stop()

# Botón de cerrar sesión en el sidebar
with st.sidebar:
    st.markdown(f"👤 **{st.session_state.usuario['Nombre']}** ({st.session_state.usuario['Rol']})")
    if st.button("Cerrar sesión"):
        del st.session_state["usuario"]
        st.experimental_rerun()

# =========================
# ✅ ENCABEZADO Y MENÚ
# =========================

# Ruta al logo
LOGO_CLARO = "Igloo Original.png"
LOGO_OSCURO = "Igloo White.png"

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

st.info("Selecciona una opción desde el menú lateral para comenzar 🚀")

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
