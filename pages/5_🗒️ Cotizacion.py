import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import date
from supabase import create_client
import re

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
    fecha = st.date_input("Fecha de cotización", value=date.today(), format="DD/MM/YYYY")

    # ---------------------------
    # DATOS DE CLIENTE Y EMPRESA
    # ---------------------------
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Datos del Cliente")
        cliente_nombre = st.text_input("Nombre del Cliente")
        cliente_direccion = st.text_input("Dirección del Cliente")
        cliente_mail = st.text_input("Email del Cliente")
        cliente_telefono = st.text_input("Teléfono del Cliente")
        cliente_ext = st.text_input("Ext Cliente")

    with col2:
        st.subheader("Datos de la Empresa")
        empresa_nombre = st.text_input("Nombre de tu Empresa", "IGLOO TRANSPORT")
        empresa_direccion = st.text_input("Dirección de la Empresa")
        empresa_mail = st.text_input("Email de la Empresa")
        empresa_telefono = st.text_input("Teléfono de la Empresa")
        empresa_ext = st.text_input("Ext Empresa")

    # ---------------------------
    # SELECCIÓN DE RUTAS SIN FILTRO
    # ---------------------------
    ids_seleccionados = st.multiselect(
        "Elige las rutas que deseas incluir:",
        df["ID_Ruta"] + " | " + df["Tipo"] + " | " + df["Origen"] + " → " + df["Destino"]
    )

    # ---------------------------
    # MONEDA Y TIPO DE CAMBIO
    # ---------------------------
    moneda_default = None
    if ids_seleccionados:
        id_ruta = ids_seleccionados[0].split(" | ")[0]
        ruta_data = df[df["ID_Ruta"] == id_ruta].iloc[0]
        moneda_default = ruta_data["Moneda"]

    st.subheader("Moneda y Tipo de Cambio para la Cotización")
    moneda_cotizacion = st.selectbox("Moneda Principal de la Cotización", ["MXP", "USD"], index=0 if moneda_default == "MXP" else 1)
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
    # ETIQUETAS VISIBLES (renombrar en PDF)
    # ---------------------------
    DISPLAY_LABELS = {
        "Ingreso_Original": "Flete",
        "Cruce_Original": "Cruce",
        # el resto usa formateo automático
    }
    def label_de(campo: str) -> str:
        return DISPLAY_LABELS.get(campo, campo.replace("_", " ").title())
    
    # ---------------------------
    # SELECCIÓN DE CONCEPTOS POR RUTA (Sumar vs Mostrar)
    # ---------------------------
    rutas_config = {}

    # Nombres de columnas disponibles en la base
    CONCEPTOS = [
        "Ingreso_Original", "Cruce_Original", "Movimiento_Local", "Puntualidad", "Pension", "Estancia",
        "Pistas_Extra", "Stop", "Falso", "Gatas", "Accesorios", "Casetas", "Fianza_Termo", "Guias",
        "Lavado_Termo", "Renta_Termo", "Costo_Diesel_Camion", "Costo_Diesel_Termo"
    ]

    for ruta in ids_seleccionados:
        st.markdown(f"**Configura la ruta {ruta}**")

        # Defaults sugeridos:
        default_sumar = ["Ingreso_Original", "Cruce_Original"]
        default_visual = ["Casetas", "Pension", "Estancia"]

        colS, colV = st.columns(2)
        with colS:
            sumar = st.multiselect(
                f"➡️ Sumar al total ({ruta})",
                options=CONCEPTOS,
                default=[c for c in default_sumar if c in CONCEPTOS],
                key=f"sumar_{ruta}"
            )
        with colV:
            solo_visual = st.multiselect(
                f"👁️ Mostrar sin sumar ({ruta})",
                options=[c for c in CONCEPTOS if c not in sumar],
                default=[c for c in default_visual if c not in sumar],
                key=f"visual_{ruta}"
            )

        # Exclusión mutua
        sumar = [c for c in sumar if c not in solo_visual]
        solo_visual = [c for c in solo_visual if c not in sumar]

        rutas_config[ruta] = {"sumar": sumar, "visual": solo_visual}

# ---------------------------
# BOTÓN PARA GENERAR PDF
# ---------------------------
def safe_text(text):
    return str(text).encode('latin-1', 'ignore').decode('latin-1')

if st.button("Generar Cotización PDF"):

    class PDF(FPDF):
        def __init__(self, orientation='P', unit='in', format='Letter'):
            super().__init__(orientation=orientation, unit=unit, format=format)
            # Fuentes
            self.add_font('Montserrat', '', 'Montserrat-Regular.ttf', uni=True)
            self.add_font('Montserrat', 'B', 'Montserrat-Bold.ttf', uni=True)
            # Intentar cargar itálica; si no existe, usaremos Helvetica itálica como respaldo
            try:
                self.add_font('Montserrat', 'I', 'Montserrat-Italic.ttf', uni=True)
                self.has_montserrat_italic = True
            except Exception:
                self.has_montserrat_italic = False

        def header(self):
            # Fondo/plantilla
            self.image('ADT PGL GRAL NO TXT.png', x=0, y=0, w=8.5, h=11)

        # helper para poner cursiva con fallback
        def set_italic(self, size=7):
            if self.has_montserrat_italic:
                self.set_font("Montserrat", "I", size)
            else:
                self.set_font("Helvetica", "I", size)

    pdf = PDF(orientation='P', unit='in', format='Letter')
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    # ---------------------------
    # DATOS EN PLANTILLA ALINEADOS
    # ---------------------------
    # Cliente
    pdf.set_font("Montserrat", "", 10)
    pdf.set_xy(0.8, 2.29); pdf.multi_cell(2.89, 0.22, safe_text(cliente_nombre), align="L")
    pdf.set_xy(0.8, 2.93); pdf.multi_cell(2.89, 0.22, safe_text(cliente_direccion), align="L")
    pdf.set_xy(0.8, 3.48); pdf.multi_cell(2.89, 0.22, safe_text(cliente_mail), align="L")
    pdf.set_xy(0.8, 3.9);  pdf.cell(1.35, 0.22, safe_text(cliente_telefono), align="L")
    pdf.set_xy(2.63, 3.9); pdf.cell(0.76, 0.22, safe_text(cliente_ext), align="L")

    # Empresa
    pdf.set_xy(4.78, 2.29); pdf.multi_cell(2.89, 0.22, safe_text(empresa_nombre), align="R")
    pdf.set_xy(4.78, 2.93); pdf.multi_cell(2.89, 0.22, safe_text(empresa_direccion), align="R")
    pdf.set_xy(4.78, 3.48); pdf.multi_cell(2.89, 0.22, safe_text(empresa_mail), align="R")
    pdf.set_xy(5.23, 3.9);  pdf.cell(1.35, 0.22, safe_text(empresa_telefono), align="L")
    pdf.set_xy(6.98, 3.9);  pdf.cell(0.76, 0.22, safe_text(empresa_ext), align="L")

    # Fecha
    pdf.set_xy(0.85, 4.66)
    pdf.multi_cell(1.78, 0.22, safe_text(f"{fecha.strftime('%d/%m/%Y')}"))

    # ---------------------------
    # DETALLE DE CONCEPTOS
    # ---------------------------
    pdf.set_font("Montserrat", "", 7)
    pdf.set_text_color(128, 128, 128)
    y = 5.84
    total_global = 0.0

    for ruta in ids_seleccionados:
        id_ruta = ruta.split(" | ")[0]
        ruta_data = df[df["ID_Ruta"] == id_ruta].iloc[0]
        tipo_ruta = ruta_data['Tipo']
        origen = ruta_data['Origen']
        destino = ruta_data['Destino']
        descripcion = f"{origen} - {destino}"

        # Título de sección por ruta
        pdf.set_font("Montserrat", "B", 7)
        pdf.set_text_color(128, 128, 128)
        pdf.set_xy(0.85, y)
        pdf.multi_cell(7, 0.15, safe_text(tipo_ruta), align="L")

        y_ruta = pdf.get_y()
        pdf.set_xy(0.85, y_ruta)
        pdf.multi_cell(7, 0.15, safe_text(descripcion), align="L")

        y = pdf.get_y() + 0.05  # pequeño espacio

        # Conceptos ordenados: primero los que suman, luego los visuales
        cfg = rutas_config.get(ruta, {"sumar": [], "visual": []})
        conceptos_orden = cfg["sumar"] + cfg["visual"]

        for campo in conceptos_orden:
            if campo not in ruta_data or pd.isna(ruta_data[campo]) or ruta_data[campo] == 0:
                continue

            valor = float(ruta_data[campo])

            # Moneda original del concepto
            if campo == "Ingreso_Original":
                moneda_original = ruta_data.get("Moneda", "MXP")
            elif campo == "Cruce_Original":
                moneda_original = ruta_data.get("Moneda_Cruce", "MXP")
            else:
                moneda_original = "MXP"

            valor_convertido = convertir_moneda(valor, moneda_original, moneda_cotizacion, tipo_cambio)

            if y > 9:
                pdf.add_page()
                y = 1

            # ¿Se cobra o es informativo?
            es_cobrado = campo in cfg["sumar"]

            # Estilo del texto del concepto (normal vs cursiva)
            if es_cobrado:
                pdf.set_font("Montserrat", "", 7)
            else:
                pdf.set_italic(7)  # cursiva

            # Etiqueta (renombrada) y valores
            pdf.set_xy(0.85, y); pdf.cell(3.55, 0.15, safe_text(label_de(campo)), align="L")

            # Cantidad: "1" solo si se cobra; vacío si es informativo
            cantidad_texto = "1" if es_cobrado else ""
            pdf.set_font("Montserrat", "", 7)  # aseguramos número/moneda en regular
            pdf.set_xy(4.69, y); pdf.cell(0.61, 0.15, cantidad_texto, align="C")
            pdf.set_xy(5.79, y); pdf.cell(0.61, 0.15, moneda_cotizacion, align="C")
            pdf.set_xy(6.77, y); pdf.cell(0.88, 0.15, f"${valor_convertido:,.2f}", align="C")

            # ➕ Sumar solo si corresponde
            if es_cobrado:
                total_global += valor_convertido

            # Restaurar fuente base para siguiente renglón
            pdf.set_font("Montserrat", "", 7)
            y += 0.18

    # ---------------------------
    # TOTAL
    # ---------------------------
    pdf.set_font("Montserrat", "B", 7)
    pdf.set_text_color(0, 0, 0)
    # (opcional) Etiqueta de total: descomenta si la quieres visible
    # pdf.set_xy(4.69, 9.34); pdf.cell(0.61, 0.15, "TARIFA TOTAL", align="C")
    pdf.set_xy(5.79, 9.34); pdf.cell(0.61, 0.15, moneda_cotizacion, align="C")
    pdf.set_xy(6.77, 9.34); pdf.cell(0.88, 0.15, f"${total_global:,.2f}", align="C")

    pdf.set_font("Montserrat", "", 7)
    pdf.set_text_color(128, 128, 128)
    pdf.set_xy(0.86, 9.69)
    pdf.multi_cell(
        3.55, 0.15,
        safe_text("Esta cotización es válida por 15 días, No aplica IVA y Retenciones en el caso de las importaciones y exportacione, Y las exportaciones aplica tasa 0"),
        align="L"
    )

    # ---------------------------
    # GUARDAR PDF
    # ---------------------------
    nombre_archivo_cliente = re.sub(r'[^\w\-]', '_', cliente_nombre or "Cliente")
    pdf_output = f'Cotizacion-{nombre_archivo_cliente}-{fecha.strftime("%d-%m-%Y")}.pdf'
    pdf.output(pdf_output)

    with open(pdf_output, "rb") as file:
        st.download_button(
            label="📄 Descargar Cotización en PDF",
            data=file,
            file_name=pdf_output,
            mime="application/pdf"
        )
        
else:
    st.warning("⚠️ No hay rutas registradas en Supabase.")
