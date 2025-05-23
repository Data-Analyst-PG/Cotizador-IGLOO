import streamlit as st
from PIL import Image
import os

# Cargar imágenes locales
logo_claro = Image.open("Igloo Original.png")
logo_oscuro = Image.open("Igloo White.png")

# Detectar si el tema es oscuro o claro usando CSS preferencia de sistema
theme = st.get_option("theme.base")

# Mostrar el logo correcto
if theme == "dark":
    st.image(logo_oscuro, width=300)
else:
    st.image(logo_claro, width=300)

# Texto de bienvenida
st.markdown("""
# Bienvenido al Cotizador de Rutas

Esta herramienta te permitirá capturar, gestionar y simular rutas de forma eficiente y precisa.  
Utiliza el menú lateral para comenzar con:

- 🛣️ **Captura de Ruta**
- 🔁 **Simulador Vuelta Redonda**
- 🗂️ **Gestión de Rutas**
- 📂 **Archivos**

---
""")
