import streamlit as st

def vista_reportes():
    st.header("📊 Reportes")
    st.write("Contenido…")

# Páginas: pueden ser archivos .py o funciones
pages = [
    st.Page("🏠Home.py", title="Inicio", icon="🏠"),                 # archivo
    st.Page(function=vista_reportes, title="Reportes", icon="📊"),   # función
    st.Page("pages/01_Usuarios.py", title="Usuarios", icon="👤"),    # archivo en /pages
]

pg = st.navigation(pages, position="top")
pg.run()
