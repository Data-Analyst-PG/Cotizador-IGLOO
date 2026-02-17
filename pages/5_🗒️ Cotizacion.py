import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import date
from supabase import create_client
import re, os
from pathlib import Path

# --------- Opcional: optimización de plantilla con Pillow ---------
try:
    from PIL import Image
    HAS_PIL = True
except Exception:
    HAS_PIL = False

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
if not respuesta.data:
    st.warning("⚠️ No hay rutas registradas en Supabase.")
    st.stop()

df = pd.DataFrame(respuesta.data)
df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.date
# Acceso rápido por ID
if "ID_Ruta" in df.columns:
    df.set_index("ID_Ruta", inplace=True, drop=False)

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
    id_ruta_0 = ids_seleccionados[0].split(" | ")[0]
    ruta_0 = df.loc[id_ruta_0]
    moneda_default = ruta_0.get("Moneda", "MXP")

st.subheader("Moneda y Tipo de Cambio para la Cotización")
moneda_cotizacion = st.selectbox(
    "Moneda Principal de la Cotización", ["MXP", "USD"],
    index=0 if (moneda_default or "MXP") == "MXP" else 1
)
tipo_cambio = st.number_input("Tipo de Cambio USD/MXP", min_value=0.0, value=18.0)

def convertir_moneda(valor, origen, destino, tipo_cambio):
    if origen == destino:
        return float(valor)
    if origen == "MXP" and destino == "USD":
        return float(valor) / tipo_cambio
    if origen == "USD" and destino == "MXP":
        return float(valor) * tipo_cambio
    return float(valor)

# ---------------------------
# ETIQUETAS VISIBLES (renombrar en PDF)
# ---------------------------
DISPLAY_LABELS = {
    "Ingreso_Original": "Flete",
    "Cruce_Original": "Cruce",
}
def label_de(campo: str) -> str:
    return DISPLAY_LABELS.get(campo, campo.replace("_", " ").title())

# ---------------------------
# SELECCIÓN DE CONCEPTOS POR RUTA (Sumar vs Mostrar)
# ---------------------------
rutas_config = {}

CONCEPTOS = [
    "Ingreso_Original", "Cruce_Original", "Movimiento_Local", "Puntualidad", "Pension", "Estancia",
    "Pistas_Extra", "Stop", "Falso", "Gatas", "Accesorios", "Casetas", "Fianza_Termo", "Guias",
    "Lavado_Termo", "Renta_Termo", "Costo_Diesel_Camion", "Costo_Diesel_Termo"
]

for ruta_sel in ids_seleccionados:
    st.markdown(f"**Configura la ruta {ruta_sel}**")
    default_sumar = ["Ingreso_Original", "Cruce_Original"]
    default_visual = ["Casetas", "Pension", "Estancia"]

    colS, colV = st.columns(2)
    with colS:
        sumar = st.multiselect(
            f"➡️ Sumar al total ({ruta_sel})",
            options=CONCEPTOS,
            default=[c for c in default_sumar if c in CONCEPTOS],
            key=f"sumar_{ruta_sel}"
        )
    with colV:
        solo_visual = st.multiselect(
            f"👁️ Mostrar sin sumar ({ruta_sel})",
            options=[c for c in CONCEPTOS if c not in sumar],
            default=[c for c in default_visual if c not in sumar],
            key=f"visual_{ruta_sel}"
        )

    # Exclusión mutua
    sumar = [c for c in sumar if c not in solo_visual]
    solo_visual = [c for c in solo_visual if c not in sumar]
    rutas_config[ruta_sel] = {"sumar": sumar, "visual": solo_visual}

# ---------------------------
# UTILIDADES PLANTILLA (antes de clase PDF)
# ---------------------------
PLANTILLA_CANDIDATAS = [
    "ADT PGL GRAL NO TXT.jpg", "ADT PGL GRAL NO TXT.jpeg", "ADT PGL GRAL NO TXT.png",
    "assets/ADT PGL GRAL NO TXT.jpg", "assets/ADT PGL GRAL NO TXT.png",
    "/mnt/data/Igloo White.png", "/mnt/data/Igloo Original.png",
]
def _find_template():
    for p in PLANTILLA_CANDIDATAS:
        if os.path.exists(p):
            return p
    return None

def _optimize_to_jpg(path_png, max_kb=750, target_w=1275, target_h=1650, quality=85):
    """Convierte PNG pesado a JPG optimizado (150–200 DPI aprox). Devuelve ruta final."""
    if not HAS_PIL:
        return path_png
    try:
        img = Image.open(path_png).convert("RGB")
        img.thumbnail((target_w, target_h), Image.LANCZOS)
        out = Path(path_png).with_suffix("")  # sin extensión
        out = f"{out}-opt.jpg"
        img.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
        if os.path.getsize(out) > max_kb * 1024:
            img.save(out, "JPEG", quality=75, optimize=True, progressive=True)
        return out
    except Exception:
        return path_png

PLANTILLA_PATH = _find_template()
if PLANTILLA_PATH and PLANTILLA_PATH.lower().endswith(".png"):
    try:
        if os.path.getsize(PLANTILLA_PATH) > 900 * 1024:
            PLANTILLA_PATH = _optimize_to_jpg(PLANTILLA_PATH)
    except Exception:
        pass

def safe_text(text):
    return str(text).encode('latin-1', 'ignore').decode('latin-1')

# ---------------------------
# NOTAS / CONDICIONES EDITABLES
# ---------------------------
st.subheader("Notas o Condiciones de la Cotización")

texto_default = (
    "Esta cotización es válida por 15 días. "
    "No aplica IVA y Retenciones en el caso de las importaciones y exportaciones. "
    "Las exportaciones aplican tasa 0."
)

notas_cotizacion = st.text_area(
    "Puedes editar este texto si lo deseas:",
    value=texto_default,
    height=100
)

# ---------------------------
# GENERAR PDF
# ---------------------------
if st.button("Generar Cotización PDF"):

    class PDF(FPDF):
        def __init__(self, orientation='P', unit='in', format='Letter'):
            super().__init__(orientation=orientation, unit=unit, format=format)
            self.set_compression(True)
            # Fuentes Montserrat con fallback a Helvetica
            try:
                self.add_font('Montserrat', '', 'Montserrat-Regular.ttf', uni=True)
                self.add_font('Montserrat', 'B', 'Montserrat-Bold.ttf', uni=True)
                self.add_font('Montserrat', 'I', 'Montserrat-Italic.ttf', uni=True)
                self.has_montserrat = True
            except Exception:
                self.has_montserrat = False

        def header(self):
            if PLANTILLA_PATH and os.path.exists(PLANTILLA_PATH):
                self.image(PLANTILLA_PATH, x=0, y=0, w=8.5, h=11)
            else:
                self.set_fill_color(245, 245, 245)
                self.rect(0, 0, 8.5, 0.8, 'F')

        def set_body_font(self, bold=False, italic=False, size=7):
            if self.has_montserrat:
                style = ("B" if bold else "") + ("I" if italic else "")
                self.set_font("Montserrat", style, size)
            else:
                style = ("B" if bold else "") + ("I" if italic else "")
                self.set_font("Helvetica", style, size)

    pdf = PDF(orientation='P', unit='in', format='Letter')
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    # ---------------------------
    # DATOS EN PLANTILLA ALINEADOS
    # ---------------------------
    pdf.set_body_font(size=10)
    # Cliente
    pdf.set_xy(0.85, 2.29); pdf.multi_cell(2.89, 0.31, safe_text(cliente_nombre), align="L")
    pdf.set_xy(0.85, 2.89); pdf.multi_cell(2.89, 0.31, safe_text(cliente_direccion), align="L")
    pdf.set_xy(0.85, 3.48); pdf.multi_cell(2.89, 0.31, safe_text(cliente_mail), align="L")
    pdf.set_xy(0.85, 3.85);  pdf.cell(1.35, 0.31, safe_text(cliente_telefono), align="L")
    pdf.set_xy(2.39, 3.83); pdf.cell(0.76, 0.31, safe_text(cliente_ext), align="C")
    # Empresa
    pdf.set_xy(4.76, 2.29); pdf.multi_cell(2.89, 0.31, safe_text(empresa_nombre), align="R")
    pdf.set_xy(4.76, 2.89); pdf.multi_cell(2.89, 0.31, safe_text(empresa_direccion), align="R")
    pdf.set_xy(4.76, 3.48); pdf.multi_cell(2.89, 0.31, safe_text(empresa_mail), align="R")
    pdf.set_xy(5.43, 3.85);  pdf.cell(1.35, 0.31, safe_text(empresa_telefono), align="R")
    pdf.set_xy(7.03, 3.83);  pdf.cell(0.76, 0.31, safe_text(empresa_ext), align="C")
    # Fecha
    pdf.set_xy(0.85, 4.66)
    pdf.multi_cell(1.78, 0.22, safe_text(f"{fecha.strftime('%d/%m/%Y')}"))

    # ---------------------------
    # DETALLE DE CONCEPTOS
    # ---------------------------
    pdf.set_body_font(size=7)
    pdf.set_text_color(128, 128, 128)
    y = 5.84
    total_global = 0.0

    for ruta_sel in ids_seleccionados:
        id_ruta = ruta_sel.split(" | ")[0]
        ruta_data = df.loc[id_ruta]
        tipo_ruta = ruta_data['Tipo']
        origen = ruta_data['Origen']
        destino = ruta_data['Destino']
        descripcion = f"{origen} - {destino}"

        # Título de sección por ruta
        pdf.set_body_font(bold=True, size=7)
        pdf.set_text_color(128, 128, 128)
        pdf.set_xy(0.85, y); pdf.multi_cell(7, 0.15, safe_text(tipo_ruta), align="L")
        y = pdf.get_y()
        pdf.set_xy(0.85, y); pdf.multi_cell(7, 0.15, safe_text(descripcion), align="L")
        y = pdf.get_y() + 0.05

        cfg = rutas_config.get(ruta_sel, {"sumar": [], "visual": []})
        conceptos_orden = cfg["sumar"] + cfg["visual"]

        for campo in conceptos_orden:
            if campo not in ruta_data or pd.isna(ruta_data[campo]) or ruta_data[campo] == 0:
                continue

            valor = float(ruta_data[campo])
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

            es_cobrado = campo in cfg["sumar"]

            # Concepto: normal si suma, cursiva si informativo
            pdf.set_body_font(italic=not es_cobrado, size=7)
            pdf.set_xy(0.85, y); pdf.cell(3.55, 0.15, safe_text(label_de(campo)), align="L")

            # Cantidad: "1" si se cobra, vacío si informativo
            cantidad_texto = "1" if es_cobrado else ""
            pdf.set_body_font(size=7)  # números en regular
            pdf.set_xy(4.64, y); pdf.cell(0.79, 0.12, cantidad_texto, align="C")
            pdf.set_xy(5.72, y); pdf.cell(0.79, 0.12, moneda_cotizacion, align="C")
            pdf.set_xy(6.80, y); pdf.cell(0.79, 0.12, f"${valor_convertido:,.2f}", align="R")

            if es_cobrado:
                total_global += valor_convertido

            pdf.set_body_font(size=7)
            y += 0.18

    # ---------------------------
    # TOTAL
    # ---------------------------
    pdf.set_body_font(bold=True, size=7)
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(5.65, 9.15); pdf.cell(0.92, 0.15, moneda_cotizacion, align="C")
    pdf.set_xy(6.73, 9.15); pdf.cell(0.92, 0.15, f"${total_global:,.2f}", align="C")

    pdf.set_body_font(size=7)
    pdf.set_text_color(128, 128, 128)
    pdf.set_xy(0.86, 9.69)
    pdf.multi_cell(
        3.55, 0.15,
        safe_text(notas_cotizacion),
        align="L"
    )

    # ---------------------------
    # DESCARGA (sin escribir a disco)
    # ---------------------------
    nombre_archivo_cliente = re.sub(r'[^\w\-]', '_', cliente_nombre or "Cliente")
    file_name = f'Cotizacion-{nombre_archivo_cliente}-{fecha.strftime("%d-%m-%Y")}.pdf'
    pdf_bytes = pdf.output(dest="S").encode("latin-1")

    if PLANTILLA_PATH and os.path.exists(PLANTILLA_PATH):
        peso_kb = os.path.getsize(PLANTILLA_PATH) / 1024
        st.caption(f"Plantilla usada: {PLANTILLA_PATH} · {peso_kb:.0f} KB")
    else:
        st.warning("No se encontró la imagen de plantilla; usando encabezado básico.")

    st.download_button("📄 Descargar Cotización en PDF", data=pdf_bytes, file_name=file_name, mime="application/pdf")
