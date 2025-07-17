import streamlit as st
import pandas as pd
import os
from datetime import date, datetime
from supabase import create_client
import numpy as np
import json

# ✅ Verificación de sesión y rol
if "usuario" not in st.session_state:
    st.error("⚠️ No has iniciado sesión.")
    st.stop()

rol = st.session_state.usuario.get("Rol", "").lower()
if rol not in ["admin", "gerente", "ejecutivo"]:
    st.error("🚫 No tienes permiso para acceder a este módulo.")
    st.stop()

# Conexión a Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

RUTA_PROG = "viajes_programados.csv"

st.title("🛣️ Programación de Viajes Detallada")

def safe(x): return 0 if pd.isna(x) or x is None else x

def cargar_rutas():
    respuesta = supabase.table("Rutas").select("*").execute()
    if not respuesta.data:
        st.error("❌ No se encontraron rutas en Supabase.")
        st.stop()
    df = pd.DataFrame(respuesta.data)
    df["Ingreso Total"] = pd.to_numeric(df["Ingreso Total"], errors="coerce").fillna(0)
    df["Costo_Total_Ruta"] = pd.to_numeric(df["Costo_Total_Ruta"], errors="coerce").fillna(0)
    df["Utilidad"] = df["Ingreso Total"] - df["Costo_Total_Ruta"]
    df["% Utilidad"] = (df["Utilidad"] / df["Ingreso Total"] * 100).round(2)
    df["Ruta"] = df["Origen"] + " → " + df["Destino"]
    return df

def limpiar_tramo_para_insert(tramo: dict) -> dict:
    """
    Limpia campos no válidos para inserción en Supabase desde un tramo.
    Elimina campos auxiliares como % Utilidad, Ruta y Bono (no definidos en la tabla).
    """
    if tramo is None:
        return {}
    campos_no_validos = ["% Utilidad", "Ruta", "Bono", "Utilidad"]
    limpio = tramo.copy()
    for campo in campos_no_validos:
        limpio.pop(campo, None)
    return limpio

def limpiar_fila_json(fila: dict) -> dict:
    limpio = {}
    for k, v in fila.items():
        if v is None or (isinstance(v, float) and np.isnan(v)):
            limpio[k] = None
        elif isinstance(v, (pd.Timestamp, datetime, date, np.datetime64)):
            limpio[k] = str(v)[:10]
        elif isinstance(v, (np.integer, np.int64, np.int32)):
            limpio[k] = int(v)
        elif isinstance(v, (np.floating, np.float64, np.float32)):
            limpio[k] = float(v)
        elif isinstance(v, pd.Timedelta):
            limpio[k] = str(v)
        else:
            try:
                json.dumps(v)  # Probar si es serializable
                limpio[k] = v
            except TypeError:
                limpio[k] = str(v)
    return limpio

def guardar_programacion(nuevo_registro):
    columnas_base_data = supabase.table("Traficos").select("*").limit(1).execute().data
    columnas_base = columnas_base_data[0].keys() if columnas_base_data else nuevo_registro.columns

    # Asegura que sea DataFrame
    if isinstance(nuevo_registro, dict):
        nuevo_registro = pd.DataFrame([nuevo_registro])
    elif isinstance(nuevo_registro, pd.Series):
        nuevo_registro = pd.DataFrame([nuevo_registro.to_dict()])

    nuevo_registro = nuevo_registro.reindex(columns=columnas_base, fill_value=None)


    registros = nuevo_registro.to_dict(orient="records")
    for fila in registros:
        id_programacion = fila.get("ID_Programacion")
        existe = supabase.table("Traficos").select("ID_Programacion").eq("ID_Programacion", id_programacion).execute()
        if not existe.data:
            supabase.table("Traficos").insert(limpiar_fila_json(fila)).execute()
        else:
            st.warning(f"⚠️ El tráfico con ID {id_programacion} ya fue registrado previamente.")

RUTA_DATOS = "datos_generales.csv"

# Valores por defecto si no existe el archivo
valores_por_defecto = {
    "Rendimiento Camion": 2.5,
    "Costo Diesel": 24.0,
    "Rendimiento Termo": 3.0,
    "Bono ISR IMSS": 462.66,
    "Pago x km IMPORTACION": 2.10,
    "Pago x km EXPORTACION": 2.50,
    "Pago fijo VACIO": 200.00,
    "Tipo de cambio USD": 17.5,
    "Tipo de cambio MXP": 1.0
}

def cargar_datos_generales():
    if os.path.exists(RUTA_DATOS):
        df = pd.read_csv(RUTA_DATOS)
        return df.set_index("Parametro")["Valor"].to_dict()
    else:
        return valores_por_defecto.copy()

def guardar_datos_generales(valores):
    df = pd.DataFrame(list(valores.items()), columns=["Parametro", "Valor"])
    df.to_csv(RUTA_DATOS, index=False)

# Cargar valores actuales
valores = cargar_datos_generales()

with st.expander("⚙️ Configurar Datos Generales"):
    st.markdown("Estos valores se usan para calcular el sueldo, bono, costos y utilidades de los tráficos.")

    nuevos_valores = {}
    columnas = st.columns(3)
    for i, (clave, valor) in enumerate(valores.items()):
        with columnas[i % 3]:
            nuevos_valores[clave] = st.number_input(clave, value=float(valor), key=clave)

    if st.button("💾 Guardar configuración"):
        guardar_datos_generales(nuevos_valores)
        st.success("✅ Configuración guardada correctamente.")
        st.rerun()

# Asignar los valores actualizados para usar en cálculos
valores = nuevos_valores if nuevos_valores else valores

# =====================================
# 1. REGISTRO DE TRÁFICO DESDE EXCEL
# =====================================
st.header("🚛 Carga de Tráfico Desde Reporte")

archivo_excel = st.file_uploader("📤 Sube el archivo de despacho (Excel)", type=["xlsx"])

if archivo_excel is not None:
    st.success("✅ Archivo de despacho cargado correctamente.")
    mostrar_registro = True
else:
    mostrar_registro = False
    st.info("ℹ️ No se ha cargado un archivo. Puedes gestionar los tráficos ya registrados.")

if mostrar_registro:
    df_despacho = pd.read_excel(archivo_excel)

    # Renombrar columnas automáticamente
    df_despacho = df_despacho.rename(columns={
        "Fecha Guía": "Fecha",
        "Pago al operador": "Sueldo_Operador",
        "Viaje": "Número_Trafico",
        "Operación": "Tipo",
        "Tarifa": "Ingreso_Original",
        "Moneda": "Moneda",
        "Clasificación": "Ruta_Tipo",
        "Unidad": "Unidad",
        "Operador": "Operador",
        "Cliente": "Cliente",
        "Origen": "Origen",
        "Destino": "Destino",
        "Movimiento local": "Movimiento_Local",
        "Puntualidad": "Puntualidad",
        "Pensión": "Pension",
        "Estancia": "Estancia",
        "Pistas_Extra": "Pistas_Extra",
        "Stop": "Stop",
        "Falso": "Falso",
        "Gatas": "Gatas",
        "Accesorios": "Accesorios",
        "Guias": "Guias",
        "Horas termo": "Horas_Termo"
    })

    columnas_num = [
        "KM", "Ingreso_Original", "Sueldo_Operador", "Movimiento_Local", "Puntualidad",
        "Pension", "Estancia", "Pistas_Extra", "Stop", "Falso", "Gatas",
        "Accesorios", "Guias", "Horas_Termo"
    ]
    for col in columnas_num:
        if col not in df_despacho.columns:
            df_despacho[col] = 0.0
        else:
            df_despacho[col] = pd.to_numeric(df_despacho[col], errors="coerce").fillna(0.0)

    df_despacho["Fecha"] = pd.to_datetime(df_despacho["Fecha"], errors="coerce").dt.date
    df_despacho["Tipo"] = df_despacho["Tipo"].str.upper()
    df_despacho["Moneda"] = df_despacho["Moneda"].str.upper()

    registros_existentes = supabase.table("Traficos").select("ID_Programacion").execute().data
    traficos_registrados = {r["ID_Programacion"] for r in registros_existentes}

    viajes_disponibles = df_despacho["Número_Trafico"].dropna().unique()
    viaje_sel = st.selectbox("Selecciona un número de tráfico del despacho", viajes_disponibles)

    datos = df_despacho[df_despacho["Número_Trafico"] == viaje_sel].iloc[0]

    # ✅ Cargar datos generales de forma segura
    datos_dict = cargar_datos_generales()

    precio_diesel_datos_generales = float(datos_dict.get("Costo Diesel", 24.0))
    moneda_valor = str(datos["Moneda"]).strip().upper() if pd.notna(datos["Moneda"]) else "MXP"
    tipo_cambio = float(datos_dict.get("Tipo de cambio MXP", 1.0)) if moneda_valor == "MXP" else float(datos_dict.get("Tipo de cambio USD", 17.5))
    rendimiento_dg_tracto = float(datos_dict.get("Rendimiento Camion", 2.5))
    rendimiento_dg_termo = float(datos_dict.get("Rendimiento Termo", 3.0))
    bono_isr_base = float(datos_dict.get("Bono ISR IMSS", 462.66))

    with st.form("registro_trafico"):
        st.subheader("📝 Validar y completar datos")
        col1, col2, col3 = st.columns(3)

        # Validación segura
        cliente_valor = str(datos["Cliente"]) if pd.notna(datos["Cliente"]) else ""
        origen_valor = str(datos["Origen"]) if pd.notna(datos["Origen"]) else ""
        destino_valor = str(datos["Destino"]) if pd.notna(datos["Destino"]) else ""
        operador_valor = str(datos["Operador"]) if pd.notna(datos["Operador"]) else ""
        unidad_valor = str(datos["Unidad"]) if pd.notna(datos["Unidad"]) else ""
        tipo_valor = str(datos["Tipo"]).strip().upper() if pd.notna(datos["Tipo"]) else "IMPORTACION"
        moneda_valor = str(datos["Moneda"]).strip().upper() if pd.notna(datos["Moneda"]) else "MXP"

        with col1:
            fecha = st.date_input("Fecha", value=datos["Fecha"], key="fecha_input")
            cliente = st.text_input("Cliente", value=cliente_valor)
            origen = st.text_input("Origen", value=origen_valor)
            destino = st.text_input("Destino", value=destino_valor)
            tipo = st.selectbox("Tipo", ["IMPORTACION", "EXPORTACION", "VACIO"],
                                index=["IMPORTACION", "EXPORTACION", "VACIO"].index(tipo_valor)
                                if tipo_valor in ["IMPORTACION", "EXPORTACION", "VACIO"] else 0)
            km = st.number_input("KM", value=float(safe(datos["KM"])), min_value=0.0)
            modo_viaje = st.selectbox("Modo de Viaje", ["Operador", "Team"], index=0)
            operador = st.text_input("Operador", value=operador_valor)
            unidad = st.text_input("Unidad", value=unidad_valor)
            rendimiento = st.number_input("Rendimiento Camión", value=rendimiento_dg_tracto, min_value=0.1)
            
        with col2:
            moneda = st.selectbox("Moneda", ["MXP", "USD"],
                                  index=["MXP", "USD"].index(moneda_valor)
                                  if moneda_valor in ["MXP", "USD"] else 0)
            ingreso_original = st.number_input("Ingreso Original", value=float(safe(datos["Ingreso_Original"])))
            moneda_cruce = st.selectbox("Moneda Cruce", ["MXP", "USD"], index=0)
            cruce_original = st.number_input("Cruce Original", value=0.0)
            moneda_costo_cruce = st.selectbox("Moneda Costo Cruce", ["MXP", "USD"], index=0)
            costo_cruce = st.number_input("Costo Cruce", value=0.0)
            casetas = st.number_input("Casetas", value=0.0)     
            horas_termo = st.number_input("Horas Termo", value=float(safe(datos.get("Horas_Termo", 0))))
            costo_diesel = st.number_input("Costo Diesel", value=float(precio_diesel_datos_generales), min_value=0.1)
            mov_local = st.number_input("Movimiento Local", value=float(safe(datos.get("Movimiento_Local", 0))), min_value=0.0)
            
        with col3:
            puntualidad = st.number_input("Puntualidad", value=float(safe(datos.get("Puntualidad", 0))), min_value=0.0)
            pension = st.number_input("Pensión", value=float(safe(datos.get("Pension", 0))), min_value=0.0)
            estancia = st.number_input("Estancia", value=float(safe(datos.get("Estancia", 0))), min_value=0.0)
            pistas_extra = st.number_input("Pistas Extra", value=float(safe(datos.get("Pistas_Extra", 0))), min_value=0.0)
            stop = st.number_input("Stop", value=float(safe(datos.get("Stop", 0))), min_value=0.0)
            falso = st.number_input("Falso", value=float(safe(datos.get("Falso", 0))), min_value=0.0)
            gatas = st.number_input("Gatas", value=float(safe(datos.get("Gatas", 0))), min_value=0.0)
            accesorios = st.number_input("Accesorios", value=float(safe(datos.get("Accesorios", 0))), min_value=0.0)
            guias = st.number_input("Guías", value=float(safe(datos.get("Guias", 0))), min_value=0.0)
            ingreso_cruce_incluido = st.checkbox("✅ ¿El ingreso de cruce ya está incluido en la tarifa?", value=False)
            extras_cobrados = st.checkbox("✅ ¿Costos extras se incluiran al ingreso?", value=bool(datos.get("Extras_Cobrados", False)))

        # Extras
        extras = sum([
            safe(datos.get("Movimiento_Local", 0)),
            safe(datos.get("Pension", 0)),
            safe(datos.get("Estancia", 0)),
            safe(datos.get("Pistas_Extra", 0)),
            safe(datos.get("Stop", 0)),
            safe(datos.get("Falso", 0)),
            safe(datos.get("Gatas", 0)),
            safe(datos.get("Accesorios", 0)),
            safe(datos.get("Guias", 0))
        ])

        # Cálculos antes de guardar
        diesel_camion = (km / rendimiento) * costo_diesel
        diesel_termo = horas_termo * rendimiento_dg_termo * costo_diesel

        # Como costo (aunque no se cobra al cliente)
        puntualidad = safe(datos.get("Puntualidad", 0))
        casetas = safe(datos.get("Casetas", 0))

        # Tipo de cambio correcto
        tipo_cambio = float(datos_dict.get("Tipo de cambio MXP", 1.0)) if moneda == "MXP" else float(datos_dict.get("Tipo de cambio USD", 17.5))

        # Calcula ingreso cruce y costo cruce convertido
        ingreso_cruce = cruce_original * (tipo_cambio if moneda_cruce == "USD" else 1)
        costo_cruce_convertido = costo_cruce * (tipo_cambio if moneda_costo_cruce == "USD" else 1)

        # Sueldo y tarifa por KM según tipo de ruta
        if tipo == "VACIO":
            tarifa_por_km = 0
            sueldo = valores["Pago fijo VACIO"]
        elif tipo == "IMPORTACION":
            tarifa_por_km = valores["Pago x km IMPORTACION"]
            sueldo = km * tarifa_por_km
        elif tipo == "EXPORTACION":
            tarifa_por_km = valores["Pago x km EXPORTACION"]
            sueldo = km * tarifa_por_km
        else:
            tarifa_por_km = 0
            sueldo = 0

        # Si es modo Team, sueldo doble
        if modo_viaje == "Team":
            sueldo *= 2

        # Bono ISR (solo IMPO o EXPO)
        bono_isr = valores["Bono ISR IMSS"] if tipo in ["IMPORTACION", "EXPORTACION"] else 0
        if modo_viaje == "Team":
            bono_isr *= 2

        # Ingreso total = flete + cruce (+ extras si aplica)
        ingreso_flete = ingreso_original * tipo_cambio
        ingreso_total = ingreso_flete + ingreso_cruce
        if extras_cobrados:
            ingreso_total += extras


        # Costos
        costo_total = sueldo + bono_isr + diesel_camion + diesel_termo + extras + puntualidad + casetas + costo_cruce_convertido
        costos_indirectos = ingreso_total * 0.35
        utilidad_bruta = ingreso_total - costo_total
        utilidad_neta = utilidad_bruta - costos_indirectos
        
        if st.form_submit_button("🔍 Revisar cálculos del tráfico"):
                st.markdown(f"💰 **Ingreso Total:** ${ingreso_total:,.2f}")
                st.markdown(f"⛽ **Diésel Camión:** ${diesel_camion:,.2f}")
                st.markdown(f"⛽ **Diésel Termo:** ${diesel_termo:,.2f}")
                st.markdown(f"👷🏽‍♂️ **Sueldo:** ${sueldo:,.2f}")
                st.markdown(f"🧮 **Costo Total Ruta:** ${costo_total:,.2f}")
                st.markdown(f"📈 **Utilidad Bruta:** ${utilidad_bruta:,.2f} ({(utilidad_bruta / ingreso_total * 100):.2f}%)")

        if st.form_submit_button("📅 Registrar tráfico desde despacho"):
            id_programacion = f"{viaje_sel}_IDA"
            if id_programacion in traficos_registrados:
                st.warning("⚠️ Este tráfico ya fue registrado previamente.")
            else:
                fila = {
                    "ID_Programacion": id_programacion,
                    "Número_Trafico": viaje_sel,
                    "Fecha": fecha.strftime("%Y-%m-%d"),
                    "Cliente": cliente,
                    "Origen": origen,
                    "Destino": destino,
                    "Tipo": tipo,
                    "Unidad": unidad,
                    "Operador": operador,
                    "Moneda": moneda,
                    "Ingreso_Original": ingreso_original,
                    "Ingreso Total": ingreso_total,
                    "Ingreso Flete": ingreso_original * tipo_cambio,
                    "Pago por KM": tarifa_por_km,
                    "% Utilidad": float(utilidad_bruta / ingreso_total * 100) if ingreso_total else 0,
                    "KM": km,
                    "Costo Diesel": costo_diesel,
                    "Costo_Diesel_Camion": diesel_camion,
                    "Horas_Termo": horas_termo,
                    "Costo_Diesel_Termo": diesel_termo,
                    "Movimiento_Local": safe(datos.get("Movimiento_Local", 0)),
                    "Puntualidad": safe(datos.get("Puntualidad", 0)),
                    "Pension": safe(datos.get("Pension", 0)),
                    "Estancia": safe(datos.get("Estancia", 0)),
                    "Pistas_Extra": safe(datos.get("Pistas_Extra", 0)),
                    "Stop": safe(datos.get("Stop", 0)),
                    "Falso": safe(datos.get("Falso", 0)),
                    "Gatas": safe(datos.get("Gatas", 0)),
                    "Accesorios": safe(datos.get("Accesorios", 0)),
                    "Guias": safe(datos.get("Guias", 0)),
                    "Costo_Extras": extras,
                    "Casetas": casetas,
                    "Sueldo_Operador": sueldo,
                    "Bono_ISR_IMSS": bono_isr,
                    "Costo_Total_Ruta": costo_total,
                    "Costos_Indirectos": costos_indirectos,
                    "Utilidad_Bruta": utilidad_bruta,
                    "Utilidad_Neta": utilidad_neta,
                    "Rendimiento Camion": rendimiento,
                    "Rendimiento Termo": rendimiento_dg_termo,
                    "Tipo de cambio": tipo_cambio,
                    "Tramo": "IDA",
                    "Modo de Viaje": "Operador",
                    "Extras_Cobrados": extras_cobrados,
                    "Ingreso_Cruce_Incluido": ingreso_cruce_incluido,
                    "Moneda_Cruce": moneda_cruce,
                    "Cruce_Original": cruce_original,
                    "Ingreso Cruce": ingreso_cruce,
                    "Moneda Costo Cruce": moneda_costo_cruce,
                    "Costo Cruce": costo_cruce,
                    "Costo Cruce Convertido": costo_cruce_convertido,
                    "Casetas": casetas,
                }
                
                debug_fila = limpiar_fila_json(fila)

                import traceback
                try:
                    supabase.table("Traficos").insert([debug_fila]).execute()
                    st.success("✅ Tráfico registrado exitosamente.")
                except Exception as e:
                    st.error(f"❌ Error al guardar tráfico: {e}")
                    st.code(traceback.format_exc())
                    st.stop()

# =====================================
# 2. CONSULTA, EDICIÓN Y ELIMINACIÓN DE TRÁFICOS ABIERTOS
# =====================================
st.title("🔍 Consulta, Edición y Eliminación de Tráficos")

traficos = supabase.table("Traficos").select("*").execute()
df_traficos = pd.DataFrame(traficos.data)

if not df_traficos.empty:
    # Excluir tráficos que ya tienen VUELTA o VACIO cerrados
    cerrados = df_traficos[df_traficos["Fecha_Cierre"].notna() & df_traficos["ID_Programacion"].str.contains("_VUELTA|_VACIO")]
    traficos_cerrados = cerrados["Número_Trafico"].unique()

    # Mantener solo los IDA que no tengan VUELTA o VACIO cerrados
    df_traficos = df_traficos[~df_traficos["Número_Trafico"].isin(traficos_cerrados)]
    df_traficos = df_traficos[df_traficos["ID_Programacion"].str.contains("_IDA")]

if df_traficos.empty:
    st.warning("No hay programaciones registradas.")
else:
    seleccion = st.selectbox("Selecciona un tráfico para ver o editar", df_traficos["ID_Programacion"])
    seleccionado = df_traficos[df_traficos["ID_Programacion"] == seleccion].iloc[0].to_dict()
    cerrado = pd.notna(seleccionado.get("Fecha_Cierre"))

    st.write("**Vista previa del tráfico seleccionado:**")
    st.dataframe(pd.DataFrame([seleccionado]))

    if st.button("🗑️ Eliminar tráfico completo"):
        supabase.table("Traficos").delete().eq("ID_Programacion", seleccion).execute()
        st.success("✅ Tráfico eliminado exitosamente.")
        st.rerun()

    if cerrado:
        st.warning("⚠️ Este tráfico ya está cerrado. No se puede editar.")
    else:
        with st.expander("✏️ Editar tráfico seleccionado", expanded=True):
            col1, col2, col3 = st.columns(3)

            with col1:
                cliente = st.text_input("Cliente", seleccionado["Cliente"])
                origen = st.text_input("Origen", seleccionado["Origen"])
                destino = st.text_input("Destino", seleccionado["Destino"])
                tipo = st.selectbox("Tipo", ["IMPORTACION", "EXPORTACION", "VACIO"],
                                    index=["IMPORTACION", "EXPORTACION", "VACIO"].index(seleccionado["Tipo"]))
                modo = st.selectbox("Modo de Viaje", ["Operador", "Team"],
                                    index=["Operador", "Team"].index(seleccionado["Modo de Viaje"]))
                unidad = st.text_input("Unidad", seleccionado.get("Unidad", ""))
                operador = st.text_input("Operador", seleccionado.get("Operador", ""))
                km = st.number_input("KM", value=round(float(seleccionado["KM"]), 2))
                moneda = st.selectbox("Moneda", ["MXP", "USD"],
                                      index=["MXP", "USD"].index(seleccionado["Moneda"]))
            with col2:
                ingreso_original = st.number_input("Ingreso Original", value=round(float(seleccionado["Ingreso_Original"]), 2))
                moneda_cruce_valor = seleccionado.get("Moneda_Cruce") or "MXP"
                moneda_cruce = st.selectbox("Moneda Cruce", ["MXP", "USD"], index=["MXP", "USD"].index(moneda_cruce_valor))
                cruce_original = st.number_input("Cruce Original", value=round(float(seleccionado.get("Cruce_Original", 0)), 2))
                moneda_costo_cruce_valor = seleccionado.get("Moneda_Cruce") or "MXP"
                moneda_costo_cruce = st.selectbox("Moneda Costo Cruce", ["MXP", "USD"], index=["MXP", "USD"].index(moneda_costo_cruce_valor))
                costo_cruce = st.number_input("Costo Cruce", value=round(float(seleccionado.get("Costo Cruce", 0)), 2))
                casetas = st.number_input("Casetas", value=round(float(seleccionado.get("Casetas", 0)), 2))
                horas_termo = st.number_input("Horas Termo", value=round(float(seleccionado.get("Horas_Termo", 0)), 2))
                mov_local = st.number_input("Movimiento Local", value=round(float(seleccionado.get("Movimiento_Local", 0)), 2)) 
                puntualidad = st.number_input("Puntualidad", value=round(float(seleccionado.get("Puntualidad", 0)), 2))

            with col3:
                pension = st.number_input("Pensión", value=round(float(seleccionado.get("Pension", 0)), 2)) 
                estancia = st.number_input("Estancia", value=round(float(seleccionado.get("Estancia", 0)), 2))
                pistas_extra = st.number_input("Pistas Extra", value=round(float(seleccionado.get("Pistas Extra") or 0), 2))
                stop = st.number_input("Stop", value=round(float(seleccionado.get("Stop", 0)), 2))
                falso = st.number_input("Falso", value=round(float(seleccionado.get("Falso", 0)), 2))
                gatas = st.number_input("Gatas", value=round(float(seleccionado.get("Gatas", 0)), 2))
                accesorios = st.number_input("Accesorios", value=round(float(seleccionado.get("Accesorios", 0)), 2))
                guias = st.number_input("Guias", value=round(float(seleccionado.get("Guias") or 0), 2))
                ingreso_cruce_incluido = st.checkbox("✅ ¿El ingreso de cruce ya está incluido en la tarifa?", value=False)
                extras_cobrados = st.checkbox("✅ ¿Costos extras se incluiran al ingreso?", value=bool(seleccionado.get("Extras_Cobrados", False)))

            # Recalcular (usando datos_generales)
            tarifa_impo = valores["Pago x km IMPORTACION"]
            tarifa_expo = valores["Pago x km EXPORTACION"]
            bono_isr_valor = valores["Bono ISR IMSS"]
            pago_fijo_vacio = valores["Pago fijo VACIO"]
            tipo_cambio = 1 if moneda == "MXP" else float(st.session_state.get("tipo_cambio_usd", 17.0))

            if tipo == "VACIO":
                tarifa_por_km = 0
                sueldo = pago_fijo_vacio
            elif tipo == "IMPORTACION":
                tarifa_por_km = tarifa_impo
                sueldo = km * tarifa_por_km
            elif tipo == "EXPORTACION":
                tarifa_por_km = tarifa_expo
                sueldo = km * tarifa_por_km
            else:
                tarifa_por_km = 0
                sueldo = 0

            if modo == "Team":
                sueldo *= 2

            ingreso_flete = ingreso_original * tipo_cambio
            ingreso_cruce = cruce_original * tipo_cambio
            costo_cruce_convertido = costo_cruce * tipo_cambio
            rendimiento = float(seleccionado.get("Rendimiento Camion", valores["Rendimiento Camion"]))
            costo_diesel = float(seleccionado.get("Costo Diesel", valores["Costo Diesel"]))
            diesel_camion = round((km / rendimiento) * costo_diesel, 2)
            rendimiento_termo = float(seleccionado.get("Rendimiento Termo", valores["Rendimiento Termo"]))
            diesel_termo = round(horas_termo * rendimiento_termo * costo_diesel, 2)

            bono_isr = bono_isr_valor if tipo in ["IMPORTACION", "EXPORTACION"] else 0
            if modo == "Team":
                bono_isr *= 2

            extras = sum([mov_local, pension, estancia, pistas_extra, stop, falso, gatas, accesorios, guias])

            ingreso_total = ingreso_flete + ingreso_cruce
            if extras_cobrados:
                ingreso_total += extras
            costo_total = sueldo + bono_isr + diesel_camion + diesel_termo + extras + puntualidad + casetas + costo_cruce_convertido
            costos_indirectos = ingreso_total * 0.35
            utilidad_bruta = ingreso_total - costo_total
            utilidad_neta = utilidad_bruta - costos_indirectos

            if st.button("🔍 Revisar cálculos del tráfico"):
                st.markdown(f"💰 **Ingreso Total:** ${ingreso_total:,.2f}")
                st.markdown(f"⛽ **Diésel Camión:** ${diesel_camion:,.2f}")
                st.markdown(f"⛽ **Diésel Termo:** ${diesel_termo:,.2f}")
                st.markdown(f"👷🏽‍♂️ **Sueldo:** ${sueldo:,.2f}")
                st.markdown(f"🧮 **Costo Total Ruta:** ${costo_total:,.2f}")
                st.markdown(f"📈 **Utilidad Bruta:** ${utilidad_bruta:,.2f} ({(utilidad_bruta / ingreso_total * 100):.2f}%)")


            if st.button("💾 Guardar cambios"):
                try:
                    supabase.table("Traficos").update({
                        "Cliente": cliente,
                        "Origen": origen,
                        "Destino": destino,
                        "Tipo": tipo,
                        "Modo de Viaje": modo,
                        "Moneda": moneda,
                        "Ingreso_Original": ingreso_original,
                        "Ingreso Total": ingreso_total,
                        "Ingreso Flete": ingreso_flete,
                        "Pago por KM": tarifa_impo if tipo == "IMPORTACION" else tarifa_expo if tipo == "EXPORTACION" else 0,
                        "% Utilidad": round((utilidad_bruta / ingreso_total * 100), 2) if ingreso_total else 0,
                        "KM": km,
                        "Horas_Termo": horas_termo,
                        "Movimiento_Local": mov_local,
                        "Puntualidad": puntualidad,
                        "Pension": pension,
                        "Estancia": estancia,
                        "Pistas_Extra": pistas_extra,
                        "Stop": stop,
                        "Falso": falso,
                        "Gatas": gatas,
                        "Accesorios": accesorios,
                        "Guias": guias,
                        "Sueldo_Operador": sueldo,
                        "Costo_Diesel_Camion": diesel_camion,
                        "Costo_Diesel_Termo": diesel_termo,
                        "Costo_Extras": extras,
                        "Casetas": casetas,
                        "Costo_Total_Ruta": costo_total,
                        "Bono_ISR_IMSS": bono_isr,
                        "Costos_Indirectos": costos_indirectos,
                        "Utilidad_Bruta": utilidad_bruta,
                        "Utilidad_Neta": utilidad_neta,
                        "Rendimiento Camion": rendimiento,
                        "Rendimiento Termo": rendimiento_termo,
                        "Costo Diesel": costo_diesel,
                        "Tipo de cambio": tipo_cambio,
                        "Extras_Cobrados": extras_cobrados,
                        "Ingreso_Cruce_Incluido": ingreso_cruce_incluido,
                        "Moneda_Cruce": moneda_cruce,
                        "Cruce_Original": cruce_original,
                        "Tipo cambio Cruce": tipo_cambio,
                        "Ingreso Cruce": ingreso_cruce,
                        "Moneda Costo Cruce": moneda_costo_cruce,
                        "Costo Cruce": costo_cruce,
                        "Costo Cruce Convertido": costo_cruce_convertido,
                    }).eq("ID_Programacion", seleccionado["ID_Programacion"]).execute()

                    st.success("✅ Tráfico actualizado correctamente.")
                except Exception as e:
                    import traceback
                    st.error(f"❌ Error al guardar cambios: {e}")
                    st.code(traceback.format_exc())
                    st.stop()
                
# =====================================
# 3. COMPLETAR Y SIMULAR TRÁFICO DETALLADO
# =====================================
st.markdown("---")
st.title("🔁 Completar y Simular Tráfico Detallado")

def cargar_programaciones_pendientes():
    data = supabase.table("Traficos").select("*").execute()
    df = pd.DataFrame(data.data)
    if df.empty:
        return pd.DataFrame()

    # Detectar tráficos que ya tienen VUELTA o VACIO cerrados
    cerrados = df[df["Fecha_Cierre"].notna() & df["ID_Programacion"].str.contains("_VUELTA|_VACIO")]
    traficos_cerrados = cerrados["Número_Trafico"].unique()

    # Mostrar solo los IDA que no tienen tráfico cerrado asociado
    pendientes = df[~df["Número_Trafico"].isin(traficos_cerrados)]
    pendientes = pendientes[pendientes["ID_Programacion"].str.contains("_IDA")]

    return pendientes

df_prog = cargar_programaciones_pendientes()
df_rutas = cargar_rutas()

if df_prog.empty:
    st.info("ℹ️ No hay tráficos pendientes por completar.")
else:
    id_sel = st.selectbox("Selecciona un tráfico pendiente", df_prog["ID_Programacion"].unique())
    ida = df_prog[df_prog["ID_Programacion"] == id_sel].iloc[0]
    destino_ida = ida["Destino"]
    tipo_ida = ida["Tipo"]
    tipo_cambio = ida["Tipo de cambio"]
    extras_cobrados = ida.get("Extras_Cobrados", False)
    ingreso_cruce_incluido = ida.get("Ingreso_Cruce_Incluido", False)

    tipo_regreso = "EXPORTACION" if tipo_ida == "IMPORTACION" else "IMPORTACION"

    sugerencias = []

    directas = df_rutas[(df_rutas["Tipo"] == tipo_regreso) & (df_rutas["Origen"] == destino_ida)].copy()
    for _, row in directas.iterrows():
        ingreso_total = safe(ida["Ingreso Total"]) + safe(row["Ingreso Total"])
        costo_total = safe(ida["Costo_Total_Ruta"]) + safe(row["Costo_Total_Ruta"])
        utilidad = ingreso_total - costo_total
        porcentaje = (utilidad / ingreso_total * 100) if ingreso_total else 0
        sugerencias.append({
            "descripcion": f"{row['Cliente']} {row['Origen']}→{row['Destino']} ({porcentaje:.2f}%)",
            "tramos": [row],
            "utilidad": utilidad,
            "porcentaje": porcentaje
        })

    vacios = df_rutas[(df_rutas["Tipo"] == "VACIO") & (df_rutas["Origen"] == destino_ida)].copy()
    for _, vacio in vacios.iterrows():
        origen_post = vacio["Destino"]
        candidatos = df_rutas[(df_rutas["Tipo"] == tipo_regreso) & (df_rutas["Origen"] == origen_post)].copy()
        for _, final in candidatos.iterrows():
            ingreso_total = safe(ida["Ingreso Total"]) + safe(final["Ingreso Total"])
            costo_total = safe(ida["Costo_Total_Ruta"]) + safe(vacio["Costo_Total_Ruta"]) + safe(final["Costo_Total_Ruta"])
            utilidad = ingreso_total - costo_total
            porcentaje = (utilidad / ingreso_total * 100) if ingreso_total else 0
            descripcion = f"{final['Cliente']} (Vacío→{vacio['Origen']}→{vacio['Destino']})→{final['Destino']} ({porcentaje:.2f}%)"
            sugerencias.append({
                "descripcion": descripcion,
                "tramos": [vacio, final],
                "utilidad": utilidad,
                "porcentaje": porcentaje
            })

    # Ahora ordenamos por % utilidad, no por pesos
    sugerencias = sorted(sugerencias, key=lambda x: x["porcentaje"], reverse=True)

    if sugerencias:
        descripciones = [s["descripcion"] for s in sugerencias]
        descripcion_sel = st.selectbox(
            "Cliente sugerido (por utilidad)",
            descripciones,
            index=0
        )
        seleccion = next(s for s in sugerencias if s["descripcion"] == descripcion_sel)
        rutas = [ida] + seleccion["tramos"]
    else:
        st.warning("❌ No se encontraron rutas de regreso disponibles.")
        st.stop()

    st.header("🛤️ Resumen de Tramos Utilizados")
    for tramo in rutas:
        st.markdown(f"**{tramo['Tipo']}** | {tramo['Origen']} → {tramo['Destino']} | Cliente: {tramo.get('Cliente', 'Sin cliente')}")

    ingreso = sum(safe(r["Ingreso Total"]) for r in rutas)
    costo = sum(safe(r["Costo_Total_Ruta"]) for r in rutas)
    utilidad_bruta = ingreso - costo
    indirectos = ingreso * 0.35
    utilidad_neta = utilidad_bruta - indirectos

    st.header("📊 Ingresos y Utilidades")
    st.metric("Ingreso Total", f"${ingreso:,.2f}")
    st.metric("Costo Total", f"${costo:,.2f}")
    st.metric("Utilidad Bruta", f"${utilidad_bruta:,.2f} ({(utilidad_bruta/ingreso*100):.2f}%)")
    st.metric("Costos Indirectos (35%)", f"${indirectos:,.2f}")
    st.metric("Utilidad Neta", f"${utilidad_neta:,.2f} ({(utilidad_neta/ingreso*100):.2f}%)")

    if st.button("💾 Guardar y cerrar tráfico"):
        nuevos_tramos = []
        for tramo in rutas[1:]:
            if isinstance(tramo, pd.Series):
                tramo = tramo.to_dict()
            datos = limpiar_tramo_para_insert(tramo)
            datos["Fecha"] = ida["Fecha"]
            datos["Número_Trafico"] = ida["Número_Trafico"]
            datos["Unidad"] = ida["Unidad"]
            datos["Operador"] = ida["Operador"]
            sufijo = "_VACIO" if tramo["Tipo"] == "VACIO" else "_VUELTA"
            datos["ID_Programacion"] = f"{ida['Número_Trafico']}{sufijo}"
            datos["Tramo"] = "VUELTA"
            datos["Fecha_Cierre"] = datetime.today().strftime("%Y-%m-%d")

            tipo = datos.get("Tipo", "").upper()
            modo = datos.get("Modo de Viaje", "Operador")
            km = safe(datos.get("KM", 0))
            horas_termo = safe(datos.get("Horas_Termo", 0))
            casetas = safe(datos.get("Casetas", 0))
            mov_local = safe(datos.get("Movimiento_Local", 0))
            puntualidad = safe(datos.get("Puntualidad", 0))
            pension = safe(datos.get("Pension", 0))
            estancia = safe(datos.get("Estancia", 0))
            pistas_extra = safe(datos.get("Pistas_Extra", 0))
            stop = safe(datos.get("Stop", 0))
            falso = safe(datos.get("Falso", 0))
            gatas = safe(datos.get("Gatas", 0))
            accesorios = safe(datos.get("Accesorios", 0))
            guias = safe(datos.get("Guias", 0))

            tarifa_por_km = 0
            sueldo = 0
            if tipo == "VACIO":
                tarifa_por_km = 0
                sueldo = valores["Pago fijo VACIO"]
            elif tipo == "IMPORTACION":
                tarifa_por_km = valores["Pago x km IMPORTACION"]
                sueldo = km * tarifa_por_km
            elif tipo == "EXPORTACION":
                tarifa_por_km = valores["Pago x km EXPORTACION"]
                sueldo = km * tarifa_por_km

            if modo == "Team":
                sueldo *= 2

            bono = valores["Bono ISR IMSS"] if tipo in ["IMPORTACION", "EXPORTACION"] else 0
            if modo == "Team":
                bono *= 2

            rendimiento = valores["Rendimiento Camion"]
            diesel_precio = valores["Costo Diesel"]
            diesel_camion = round((km / rendimiento) * diesel_precio, 2)
            diesel_termo = round(horas_termo * valores["Rendimiento Termo"] * diesel_precio, 2)

            ingreso_original = safe(datos.get("Ingreso_Original", 0))
            cruce_original = safe(datos.get("Cruce_Original", 0))
            costo_cruce = safe(datos.get("Costo Cruce", 0))

            ingreso_flete = ingreso_original * tipo_cambio
            ingreso_cruce = cruce_original * tipo_cambio
            costo_cruce_convertido = costo_cruce * tipo_cambio

            extras = sum([mov_local, pension, estancia, pistas_extra, stop, falso, gatas, accesorios, guias])

            ingreso_total = ingreso_flete + ingreso_cruce
            if extras_cobrados:
                ingreso_total += extras

            costo_total = sueldo + bono + diesel_camion + diesel_termo + extras + puntualidad + casetas + costo_cruce_convertido
            costos_indirectos = ingreso_total * 0.35
            utilidad_bruta = ingreso_total - costo_total
            utilidad_neta = utilidad_bruta - costos_indirectos

            datos.update({
                "Pago por KM": tarifa_por_km,
                "Bono_ISR_IMSS": bono,
                "Costo_Diesel_Camion": diesel_camion,
                "Costo_Diesel_Termo": diesel_termo,
                "Costo_Total_Ruta": costo_total,
                "Costos_Indirectos": costos_indirectos,
                "Utilidad_Bruta": utilidad_bruta,
                "Utilidad_Neta": utilidad_neta,
                "Rendimiento Camion": rendimiento,
                "Rendimiento Termo": valores["Rendimiento Termo"],
                "Costo Diesel": valores["Costo Diesel"],
                "Tipo de cambio": tipo_cambio,
                "Ingreso_Original": ingreso_original,
                "Ingreso Flete": ingreso_flete,
                "Ingreso Cruce": ingreso_cruce,
                "Moneda_Cruce": "USD",
                "Cruce_Original": cruce_original,
                "Costo Cruce Convertido": costo_cruce_convertido,
                "Ingreso Total": ingreso_total,
                "Costo_Extras": extras,
                "Casetas": casetas,
                "Extras_Cobrados": extras_cobrados,
                "Ingreso_Cruce_Incluido": ingreso_cruce_incluido
            })

            nuevos_tramos.append(datos)

        for fila in nuevos_tramos:
            fila_limpio = limpiar_fila_json(limpiar_tramo_para_insert(fila))
            try:
                supabase.table("Traficos").insert([fila_limpio]).execute()
            except Exception as e:
                import traceback
                st.error(f"❌ Error al guardar tráfico: {e}")
                st.code(traceback.format_exc())
                st.stop()

        st.success("✅ Tráfico cerrado correctamente.")
        st.rerun()
