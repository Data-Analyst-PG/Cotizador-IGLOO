import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import date
from supabase import create_client

# ---------------------------
# CONEXIÓN A SUPABASE
# ---------------------------
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# ---------------------------
# VERIFICACIÓN DE SESIÓN Y ROL
# ---------------------------
if "usuario" not in st.session_state:
    st.error("⚠️ No has iniciado sesión.")
    st.stop()

rol = st.session_state.usuario.get("Rol", "").lower()
if rol not in ["admin", "gerente"]:
    st.error("🚫 No tienes permiso para acceder a este módulo.")
    st.stop()

# ---------------------------
# TITULO
# ---------------------------
st.title("📝 Generador de Cotización para Clientes")

# ---------------------------
# CARGAR RUTAS DE SUPABASE
# ---------------------------
respuesta = supabase.table("Rutas").select("*").execute()

if respuesta.data:
    df = pd.DataFrame(respuesta.data)
    df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.date
    
    # Clientes únicos de Supabase
    clientes_disponibles = df["Cliente"].dropna().unique().tolist()
    clientes_disponibles.sort()

    # ---------------------------
    # DATOS DE CLIENTE Y EMPRESA
    # ---------------------------
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Datos del Cliente")
        cliente_nombre = st.selectbox("Selecciona el Cliente", clientes_disponibles)
        cliente_direccion = st.text_input("Dirección del Cliente")
        cliente_mail = st.text_input("Email del Cliente")
        cliente_telefono = st.text_input("Teléfono del Cliente")

    with col2:
        st.subheader("Datos de la Empresa")
        empresa_nombre = st.text_input("Nombre de tu Empresa", "IGLOO TRANSPORT")
        empresa_direccion = st.text_input("Dirección de la Empresa")
        empresa_mail = st.text_input("Email de la Empresa")
        empresa_telefono = st.text_input("Teléfono de la Empresa")
        fecha = st.date_input("Fecha de cotización", value=date.today(), format="DD/MM/YYYY")

    
    # ---------------------------
    # MONEDA Y TIPO DE CAMBIO
    # ---------------------------
    st.subheader("Moneda y Tipo de Cambio para la Cotización")
    moneda_cotizacion = st.selectbox("Moneda Principal de la Cotización", ["MXP", "USD"])
    tipo_cambio = st.number_input("Tipo de Cambio USD/MXP", min_value=0.0, value=18.0)

    def convertir_moneda(valor, origen, destino, tipo_cambio):
        if origen == destino:
            return valor
        if origen == "MXP" and destino == "USD":
            return valor / tipo_cambio
        if origen == "USD" and destino == "MXP":
            return valor * tipo_cambio
        return valor
    # ---------------------------
    # FILTRAR RUTAS DEL CLIENTE + VACÍOS y GUARDAR SELECCIÓN DE CONCEPTOS POR RUTA
    # ---------------------------
    rutas_filtradas = df[
        ((df["Cliente"] == cliente_nombre) & (df["Tipo"].isin(["IMPORTACION", "EXPORTACION"]))) |
        (df["Tipo"] == "VACIO")
    ]

    ids_seleccionados = st.multiselect(
        "Elige las rutas que deseas incluir:",
        rutas_filtradas["ID_Ruta"] + " | " + rutas_filtradas["Tipo"] + " | " + rutas_filtradas["Origen"] + " → " + rutas_filtradas["Destino"]
    )
    rutas_conceptos = {}

    for ruta in ids_seleccionados:
        st.markdown(f"**Selecciona los conceptos para la ruta {ruta}**")
        conceptos = st.multiselect(
            f"Conceptos para {ruta}",
            options=["Ingreso_Original", "Cruce_Original", "Movimiento_Local", "Puntualidad", "Pension", "Estancia",
                     "Pistas_Extra", "Stop", "Falso", "Gatas", "Accesorios", "Casetas", "Fianza_Termo", "Guias",
                     "Lavado_Termo", "Renta_Termo"],
            default=["Ingreso_Original", "Casetas"]
        )
        rutas_conceptos[ruta] = conceptos

    # ---------------------------
    # BOTÓN PARA GENERAR PDF
    # ---------------------------
    if st.button("Generar Cotización PDF"):

        class PDF(FPDF):
            def header(self):
                self.image('Cotización Igloo.png', x=0, y=0, w=210, h=297)

        pdf = PDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        pdf.set_font("Arial", "", 10)

        # DATOS EN PLANTILLA
        pdf.set_xy(25, 50)
        pdf.multi_cell(80, 5, f"Nombre: {cliente_nombre}\nDirección: {cliente_direccion}\nMail: {cliente_mail}\nTeléfono: {cliente_telefono}", align='L')

        pdf.set_xy(120, 50)
        pdf.multi_cell(80, 5, f"Nombre: {empresa_nombre}\nDirección: {empresa_direccion}\nMail: {empresa_mail}\nTeléfono: {empresa_telefono}", align='L')

        pdf.set_xy(25, 80)
        pdf.cell(0, 10, f"Fecha: {fecha.strftime('%d/%m/%Y')}", ln=True)

        # DETALLE DE CONCEPTOS
        pdf.set_font("Arial", "", 10)
        y = 100
        total_global = 0

        for ruta in ids_seleccionados:
            id_ruta = ruta.split(" | ")[0]
            ruta_data = df[df["ID_Ruta"] == id_ruta].iloc[0]

            descripcion_ruta = f"{ruta_data['Tipo']} | {ruta_data['Origen']} → {ruta_data['Destino']}"
            pdf.set_xy(25, y)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(0, 10, descripcion_ruta, ln=True)
            y += 8
            pdf.set_font("Arial", "", 10)

            conceptos = rutas_conceptos[ruta]

            for campo in conceptos:
                valor = ruta_data[campo]
                if pd.notnull(valor) and valor != 0:
                    if campo == "Ingreso_Original":
                        moneda = ruta_data["Moneda"]
                    elif campo == "Cruce_Original":
                        moneda = ruta_data["Moneda_Cruce"]
                    else:
                        moneda = "MXP"

                    valor_convertido = convertir_moneda(valor, moneda, moneda_cotizacion, tipo_cambio)

                    pdf.set_xy(25, y)
                    pdf.cell(90, 8, campo.replace("_", " ").title())
                    pdf.cell(20, 8, "1")
                    pdf.cell(30, 8, moneda)
                    pdf.cell(30, 8, f"${valor_convertido:,.2f}", ln=True)
                    total_global += valor_convertido
                    y += 8

        # TOTAL GENERAL
        pdf.set_xy(130, y + 10)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(40, 10, "Total", 0, 0, "L")
        pdf.cell(30, 10, f"${total_global:,.2f} {moneda_cotizacion}", 0, 1, "L")

        # LEYENDA FINAL
        pdf.set_xy(25, 250)
        pdf.set_font("Arial", "I", 9)
        pdf.cell(0, 10, "Esta cotización es válida por 15 días.", ln=True)

        # DESCARGAR PDF
        pdf_output = f'Cotizacion-{cliente_nombre}-{fecha.strftime("%d-%m-%Y")}.pdf'
        pdf.output(pdf_output)

        with open(pdf_output, "rb") as file:
            btn = st.download_button(
                label="📄 Descargar Cotización en PDF",
                data=file,
                file_name=pdf_output,
                mime="application/pdf"
            )
else:
    st.warning("⚠️ No hay rutas registradas en Supabase.")
