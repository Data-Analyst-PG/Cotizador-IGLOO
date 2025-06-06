import streamlit as st
import pandas as pd
import os
from datetime import datetime
from supabase import create_client

# ✅ Verificación de sesión y rol
if "usuario" not in st.session_state:
    st.error("⚠️ No has iniciado sesión.")
    st.stop()

rol = st.session_state.usuario.get("Rol", "").lower()
if rol not in ["admin", "gerente", "ejecutivo"]:
    st.error("🚫 No tienes permiso para acceder a este módulo.")
    st.stop()

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# Inicializa estado si no existe
if "revisar_ruta" not in st.session_state:
    st.session_state.revisar_ruta = False

# Valores por defecto
RUTA_DATOS = "datos_generales.csv"
valores_por_defecto = {
    "Rendimiento Camion": 2.5,
    "Costo Diesel": 24.0,
    "Rendimiento Termo": 3.0,
    "Bono ISR IMSS": 462.66,
    "Pago x km IMPO": 2.10,
    "Pago x km EXPO": 2.50,
    "Pago fijo VACIO": 200.00,
    "Tipo de cambio USD": 19.5,
    "Tipo de cambio MXN": 1.0
}

def cargar_datos_generales():
    if os.path.exists(RUTA_DATOS):
        return pd.read_csv(RUTA_DATOS).set_index("Parametro").to_dict()["Valor"]
    else:
        return valores_por_defecto.copy()

def guardar_datos_generales(valores):
    df = pd.DataFrame(valores.items(), columns=["Parametro", "Valor"])
    df.to_csv(RUTA_DATOS, index=False)

def safe_number(x):
    return 0 if (x is None or (isinstance(x, float) and pd.isna(x))) else x

# Generador de ID tipo IG000001

def generar_nuevo_id():
    respuesta = supabase.table("Rutas").select("ID_Ruta").order("ID_Ruta", desc=True).limit(1).execute()
    if respuesta.data:
        ultimo = respuesta.data[0]["ID_Ruta"]
        numero = int(ultimo[2:]) + 1
    else:
        numero = 1
    return f"IG{numero:06d}"

valores = cargar_datos_generales()

st.title("🚛 Captura de Rutas + Datos Generales")

with st.expander("⚙️ Configurar Datos Generales"):
    for key in valores_por_defecto:
        valores[key] = st.number_input(key, value=float(valores.get(key, valores_por_defecto[key])), step=0.1)
    if st.button("Guardar Datos Generales"):
        guardar_datos_generales(valores)
        st.success("✅ Datos Generales guardados correctamente.")

st.markdown("---")

st.subheader("🛣️ Nueva Ruta")

# Formulario principal
with st.form("captura_ruta"):
    col1, col2 = st.columns(2)

    with col1:
        fecha = st.date_input("Fecha", value=datetime.today())
        tipo = st.selectbox("Tipo de Ruta", ["IMPO", "EXPO", "VACIO"])
        cliente = st.text_input("Nombre Cliente")
        origen = st.text_input("Origen")
        destino = st.text_input("Destino")
        Modo_de_Viaje = st.selectbox("Modo de Viaje", ["Operador", "Team"])
        km = st.number_input("Kilómetros", min_value=0.0)
        moneda_ingreso = st.selectbox("Moneda Ingreso Flete", ["MXN", "USD"])
        ingreso_flete = st.number_input("Ingreso Flete", min_value=0.0)
        moneda_cruce = st.selectbox("Moneda Ingreso Cruce", ["MXN", "USD"])
        ingreso_cruce = st.number_input("Ingreso Cruce", min_value=0.0)
    with col2:
        moneda_costo_cruce = st.selectbox("Moneda Costo Cruce", ["MXN", "USD"])
        costo_cruce = st.number_input("Costo Cruce", min_value=0.0)        
        horas_termo = st.number_input("Horas Termo", min_value=0.0)
        lavado_termo = st.number_input("Lavado Termo", min_value=0.0)
        movimiento_local = st.number_input("Movimiento Local", min_value=0.0)
        puntualidad = st.number_input("Puntualidad", min_value=0.0)
        pension = st.number_input("Pensión", min_value=0.0)
        estancia = st.number_input("Estancia", min_value=0.0)
        fianza_termo = st.number_input("Fianza Termo", min_value=0.0)
        renta_termo = st.number_input("Renta Termo", min_value=0.0)
        casetas = st.number_input("Casetas", min_value=0.0)

    st.markdown("---")
    st.subheader("🧾 Costos Extras Adicionales")
    col3, col4 = st.columns(2)
    with col3:
        pistas_extra = st.number_input("Pistas Extra", min_value=0.0)
        stop = st.number_input("Stop", min_value=0.0)
        falso = st.number_input("Falso", min_value=0.0)
    with col4:
        gatas = st.number_input("Gatas", min_value=0.0)
        accesorios = st.number_input("Accesorios", min_value=0.0)
        guias = st.number_input("Guías", min_value=0.0)

    revisar = st.form_submit_button("🔍 Revisar Ruta")

    if revisar:
        st.session_state.revisar_ruta = True
        st.session_state.datos_captura = {
            "fecha": fecha, "tipo": tipo, "cliente": cliente, "origen": origen, "destino": destino, "Modo de Viaje": Modo_de_Viaje,
            "km": km, "moneda_ingreso": moneda_ingreso, "ingreso_flete": ingreso_flete,
            "moneda_cruce": moneda_cruce, "ingreso_cruce": ingreso_cruce,
            "moneda_costo_cruce": moneda_costo_cruce, "costo_cruce": costo_cruce,
            "horas_termo": horas_termo, "lavado_termo": lavado_termo, "movimiento_local": movimiento_local,
            "puntualidad": puntualidad, "pension": pension, "estancia": estancia,
            "fianza_termo": fianza_termo, "renta_termo": renta_termo, "casetas": casetas,
            "pistas_extra": pistas_extra, "stop": stop, "falso": falso,
            "gatas": gatas, "accesorios": accesorios, "guias": guias
        }
        ingreso_total = (ingreso_flete * valores["Tipo de cambio USD"] if moneda_ingreso == "USD" else ingreso_flete)
        ingreso_total += (ingreso_cruce * valores["Tipo de cambio USD"] if moneda_cruce == "USD" else ingreso_cruce)
        costo_cruce_convertido = costo_cruce * (valores["Tipo de cambio USD"] if moneda_costo_cruce == "USD" else 1)

        costo_diesel_camion = (km / valores["Rendimiento Camion"]) * valores["Costo Diesel"]
        costo_diesel_termo = horas_termo * valores["Rendimiento Termo"] * valores["Costo Diesel"]

        factor = 2 if Modo_de_Viaje == "Team" else 1

        if tipo == "IMPO":
            pago_km = valores["Pago x km IMPO"]
            sueldo = km * pago_km * factor
            bono = valores["Bono ISR IMSS"] * factor
        elif tipo == "EXPO":
            pago_km = valores["Pago x km EXPO"]
            sueldo = km * pago_km * factor
            bono = valores["Bono ISR IMSS"] * factor
        else:
            pago_km = 0.0
            sueldo = valores["Pago fijo VACIO"] * factor
            bono = 0.0

        puntualidad_val = puntualidad * factor
        extras = sum(map(safe_number, [lavado_termo, movimiento_local, puntualidad_val, pension, estancia, fianza_termo, renta_termo, pistas_extra, stop, falso, gatas, accesorios, guias]))

        costo_total = costo_diesel_camion + costo_diesel_termo + sueldo + bono + casetas + extras + costo_cruce_convertido

        utilidad_bruta = ingreso_total - costo_total
        costos_indirectos = ingreso_total * 0.35
        utilidad_neta = utilidad_bruta - costos_indirectos
        porcentaje_bruta = (utilidad_bruta / ingreso_total * 100) if ingreso_total > 0 else 0
        porcentaje_neta = (utilidad_neta / ingreso_total * 100) if ingreso_total > 0 else 0

        def colored_bold(label, value, condition):
            color = "green" if condition else "red"
            return f"<strong>{label}:</strong> <span style='color:{color}; font-weight:bold'>{value}</span>"

        st.markdown("---")
        st.subheader("📊 Ingresos y Utilidades")

        st.write(f"**Ingreso Total:** ${ingreso_total:,.2f}")
        st.write(f"**Costo Total:** ${costo_total:,.2f}")
        st.markdown(colored_bold("Utilidad Bruta", f"${utilidad_bruta:,.2f}", utilidad_bruta >= 0), unsafe_allow_html=True)
        st.markdown(colored_bold("% Utilidad Bruta", f"{porcentaje_bruta:.2f}%", porcentaje_bruta >= 50), unsafe_allow_html=True)
        st.write(f"**Costos Indirectos (35%):** ${costos_indirectos:,.2f}")
        st.markdown(colored_bold("Utilidad Neta", f"${utilidad_neta:,.2f}", utilidad_neta >= 0), unsafe_allow_html=True)
        st.markdown(colored_bold("% Utilidad Neta", f"{porcentaje_neta:.2f}%", porcentaje_neta >= 15), unsafe_allow_html=True)

if st.session_state.revisar_ruta and st.button("💾 Guardar Ruta"):
    d = st.session_state.datos_captura

    tipo_cambio_flete = valores["Tipo de cambio USD"] if d["moneda_ingreso"] == "USD" else valores["Tipo de cambio MXN"]
    tipo_cambio_cruce = valores["Tipo de cambio USD"] if d["moneda_cruce"] == "USD" else valores["Tipo de cambio MXN"]
    tipo_cambio_costo_cruce = valores["Tipo de cambio USD"] if d["moneda_costo_cruce"] == "USD" else valores["Tipo de cambio MXN"]

    ingreso_flete_convertido = d["ingreso_flete"] * tipo_cambio_flete
    ingreso_cruce_convertido = d["ingreso_cruce"] * tipo_cambio_cruce
    costo_cruce_convertido = d["costo_cruce"] * tipo_cambio_costo_cruce
    ingreso_total = ingreso_flete_convertido + ingreso_cruce_convertido

    costo_diesel_camion = (d["km"] / valores["Rendimiento Camion"]) * valores["Costo Diesel"]
    costo_diesel_termo = d["horas_termo"] * valores["Rendimiento Termo"] * valores["Costo Diesel"]

    factor = 2 if d["Modo de Viaje"] == "Team" else 1

    if d["tipo"] == "IMPO":
        pago_km = valores["Pago x km IMPO"]
        sueldo = d["km"] * pago_km * factor
        bono = valores["Bono ISR IMSS"] * factor
    elif d["tipo"] == "EXPO":
        pago_km = valores["Pago x km EXPO"]
        sueldo = d["km"] * pago_km * factor
        bono = valores["Bono ISR IMSS"] * factor
    else:
        pago_km = 0.0
        sueldo = valores["Pago fijo VACIO"] * factor
        bono = 0.0

    puntualidad = d["puntualidad"] * factor
    extras = sum([
        safe_number(d["lavado_termo"]), safe_number(d["movimiento_local"]), safe_number(puntualidad),
        safe_number(d["pension"]), safe_number(d["estancia"]),
        safe_number(d["fianza_termo"]), safe_number(d["renta_termo"]),
        safe_number(d["pistas_extra"]), safe_number(d["stop"]), safe_number(d["falso"]),
        safe_number(d["gatas"]), safe_number(d["accesorios"]), safe_number(d["guias"])
    ])

    costo_total = costo_diesel_camion + costo_diesel_termo + sueldo + bono + d["casetas"] + extras + costo_cruce_convertido

    nueva_ruta = {
        "ID_Ruta": generar_nuevo_id(),
        "Fecha": str(d["fecha"]), "Tipo": d["tipo"], "Cliente": d["cliente"], "Origen": d["origen"], "Destino": d["destino"], "Modo de Viaje": d["Modo de Viaje"], "KM": d["km"],
        "Moneda": d["moneda_ingreso"], "Ingreso_Original": d["ingreso_flete"], "Tipo de cambio": tipo_cambio_flete,
        "Ingreso Flete": ingreso_flete_convertido, "Moneda_Cruce": d["moneda_cruce"], "Cruce_Original": d["ingreso_cruce"],
        "Tipo cambio Cruce": tipo_cambio_cruce, "Ingreso Cruce": ingreso_cruce_convertido,
        "Moneda Costo Cruce": d["moneda_costo_cruce"], "Costo Cruce": d["costo_cruce"],
        "Costo Cruce Convertido": costo_cruce_convertido,
        "Ingreso Total": ingreso_total,
        "Pago por KM": pago_km, "Sueldo_Operador": sueldo, "Bono": bono,
        "Casetas": d["casetas"], "Horas_Termo": d["horas_termo"], "Lavado_Termo": d["lavado_termo"],
        "Movimiento_Local": d["movimiento_local"], "Puntualidad": puntualidad, "Pension": d["pension"],
        "Estancia": d["estancia"], "Fianza_Termo": d["fianza_termo"], "Renta_Termo": d["renta_termo"],
        "Pistas_Extra": d["pistas_extra"], "Stop": d["stop"], "Falso": d["falso"],
        "Gatas": d["gatas"], "Accesorios": d["accesorios"], "Guias": d["guias"],
        "Costo_Diesel_Camion": costo_diesel_camion, "Costo_Diesel_Termo": costo_diesel_termo,
        "Costo_Extras": extras, "Costo_Total_Ruta": costo_total, "Costo Diesel": valores["Costo Diesel"], "Rendimiento Camion": valores["Rendimiento Camion"], "Rendimiento Termo": valores["Rendimiento Termo"]
    }

    # Generar nuevo ID y verificar duplicado
    nuevo_id = generar_nuevo_id()
    existe = supabase.table("Rutas").select("ID_Ruta").eq("ID_Ruta", nuevo_id).execute()

    if existe.data:
        st.error("⚠️ Conflicto al generar ID. Intenta de nuevo.")
    else:
        nueva_ruta["ID_Ruta"] = nuevo_id
        try:
            supabase.table("Rutas").insert(nueva_ruta).execute()
            st.success("✅ Ruta guardada exitosamente.")
            st.session_state.revisar_ruta = False
            del st.session_state["datos_captura"]
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al guardar ruta: {e}")
            st.json(nueva_ruta) 
