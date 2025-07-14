import streamlit as st
import pandas as pd
import os
from datetime import datetime
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
        elif isinstance(v, (pd.Timestamp, datetime, np.datetime64)):
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
                limpio[k] = str(v)  # Convertir a string si no se puede serializar
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
        "Pistas extra": "Pistas Extra",
        "Stop": "Stop",
        "Falso": "Falso",
        "Gatas": "Gatas",
        "Accesorios": "Accesorios",
        "Guias": "Guias",
        "Horas termo": "Horas_Termo"
    })

    columnas_num = [
        "KM", "Ingreso_Original", "Sueldo_Operador", "Movimiento_Local", "Puntualidad",
        "Pension", "Estancia", "Pistas Extra", "Stop", "Falso", "Gatas",
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
    tipo_cambio_usd = float(datos_dict.get("Tipo de cambio USD", 17.5))
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
            ingreso_cruce_incluido = st.checkbox("✅ ¿El ingreso de cruce ya está incluido en la tarifa?", value=False)

        with col2:
            km = st.number_input("KM", value=float(safe(datos["KM"])), min_value=0.0)
            moneda = st.selectbox("Moneda", ["MXP", "USD"],
                                  index=["MXP", "USD"].index(moneda_valor)
                                  if moneda_valor in ["MXP", "USD"] else 0)
            ingreso_original = st.number_input("Ingreso Original", value=float(safe(datos["Ingreso_Original"])))
            horas_termo = st.number_input("Horas Termo", value=float(safe(datos.get("Horas_Termo", 0))))
            tipo_cambio = st.number_input("Tipo de cambio USD", value=tipo_cambio_usd)
            extras_cobrados = st.checkbox("✅ ¿Costos extras cobrados al cliente?", value=bool(datos.get("Extras_Cobrados", False)))
        
        with col3:
            unidad = st.text_input("Unidad", value=unidad_valor)
            modo_viaje = st.selectbox("Modo de Viaje", ["Operador", "Team"], index=0)
            operador = st.text_input("Operador", value=operador_valor)
            rendimiento = st.number_input("Rendimiento Camión", value=rendimiento_dg_tracto, min_value=0.1)
            costo_diesel = st.number_input("Costo Diesel", value=float(precio_diesel_datos_generales), min_value=0.1)

        # Extras
        extras = sum([
            safe(datos.get("Movimiento_Local", 0)),
            safe(datos.get("Pension", 0)),
            safe(datos.get("Estancia", 0)),
            safe(datos.get("Pistas Extra", 0)),
            safe(datos.get("Stop", 0)),
            safe(datos.get("Falso", 0)),
            safe(datos.get("Gatas", 0)),
            safe(datos.get("Accesorios", 0)),
            safe(datos.get("Guias", 0))
        ])

        # Cálculos antes de guardar
        ingreso_total = ingreso_original * (tipo_cambio if moneda == "USD" else 1)
        if extras_cobrados:
            ingreso_total += extras
        if ingreso_cruce_incluido:
            st.info("ℹ️ El ingreso de cruce ya está incluido en la tarifa original.")
        diesel_camion = (km / rendimiento) * costo_diesel
        diesel_termo = horas_termo * rendimiento_dg_termo * costo_diesel

        # Puntualidad como costo (aunque no se cobra al cliente)
        puntualidad = safe(datos.get("Puntualidad", 0))

        # Sueldo
        if tipo == "VACIO":
            sueldo = valores["Pago fijo VACIO"]
        elif tipo == "IMPORTACION":
            sueldo = km * valores["Pago x km IMPORTACION"]
        elif tipo == "EXPORTACION":
            sueldo = km * valores["Pago x km EXPORTACION"]
        else:
            sueldo = 0

        sueldo = round(sueldo, 2)

        # Bono ISR/IMSS
        bono_isr = valores["Bono ISR IMSS"] if tipo in ["IMPORTACION", "EXPORTACION"] else 0
        if modo_viaje == "Team" and bono_isr:
            bono_isr *= 2

        costo_total = sueldo + bono_isr + diesel_camion + diesel_termo + extras + puntualidad
        costos_indirectos = ingreso_total * 0.35
        utilidad_bruta = ingreso_total - costo_total
        utilidad_neta = utilidad_bruta - costos_indirectos
        
        st.markdown(f"💰 **Ingreso Total Convertido:** ${ingreso_total:,.2f}")
        st.markdown(f"⛽ **Diésel Camión:** ${diesel_camion:,.2f}")
        st.markdown(f"⛽ **Diésel Termo:** ${diesel_termo:,.2f}")
        st.markdown(f"🧮 **Costo Total Ruta:** ${costo_total:,.2f}")
        st.markdown(f"📈 **Utilidad Neta:** ${utilidad_neta:,.2f} ({(utilidad_neta / ingreso_total * 100):.2f}%)")

        if st.form_submit_button("📅 Registrar tráfico desde despacho"):
            id_programacion = f"{viaje_sel}_IDA"
            if id_programacion in traficos_registrados:
                st.warning("⚠️ Este tráfico ya fue registrado previamente.")
            else:
                fila = {
                    "ID_Programacion": id_programacion,
                    "Número_Trafico": viaje_sel,
                    "Fecha": fecha,
                    "Cliente": cliente,
                    "Origen": origen,
                    "Destino": destino,
                    "Tipo": tipo,
                    "Unidad": unidad,
                    "Operador": operador,
                    "Moneda": moneda,
                    "Ingreso_Original": ingreso_original,
                    "Ingreso Total": ingreso_total,
                    "Ingreso_Flete": ingreso_original * (tipo_cambio if moneda == "USD" else 1),
                    "Pago por KM": sueldo if tipo in ["IMPORTACION", "EXPORTACION"] else 0,
                    "% Utilidad": (utilidad_bruta / ingreso_total * 100) if ingreso_total else 0,
                    "KM": km,
                    "Costo Diesel": costo_diesel,
                    "Costo_Diesel_Camion": diesel_camion,
                    "Horas_Termo": horas_termo,
                    "Costo_Diesel_Termo": diesel_termo,
                    "Movimiento_Local": safe(datos.get("Movimiento_Local", 0)),
                    "Puntualidad": safe(datos.get("Puntualidad", 0)),
                    "Pension": safe(datos.get("Pension", 0)),
                    "Estancia": safe(datos.get("Estancia", 0)),
                    "Pistas Extra": safe(datos.get("Pistas Extra", 0)),
                    "Stop": safe(datos.get("Stop", 0)),
                    "Falso": safe(datos.get("Falso", 0)),
                    "Gatas": safe(datos.get("Gatas", 0)),
                    "Accesorios": safe(datos.get("Accesorios", 0)),
                    "Guias": safe(datos.get("Guias", 0)),
                    "Costo_Extras": extras,
                    "Sueldo_Operador": sueldo,
                    "Bono_ISR_IMSS": bono_isr,
                    "Costo_Total_Ruta": costo_total,
                    "Costos_Indirectos": costos_indirectos,
                    "Utilidad_Bruta": utilidad_bruta,
                    "Utilidad_Neta": utilidad_neta,
                    "Rendimiento_Camion": rendimiento,
                    "Rendimiento_Termo": rendimiento_dg_termo,
                    "Costo_Diesel": costo_diesel,
                    "Tipo_Cambio_USD": tipo_cambio,
                    "Tramo": "IDA",
                    "Modo de Viaje": "Operador",
                    "Extras_Cobrados": extras_cobrados,
                    "Ingreso_Cruce_Incluido": ingreso_cruce_incluido,
                }

                supabase.table("Traficos").insert(limpiar_fila_json(fila)).execute()
                st.success("✅ Tráfico registrado exitosamente.")
        
# =====================================
# 2. CONSULTA, EDICIÓN Y ELIMINACIÓN DE TRÁFICOS ABIERTOS
# =====================================
st.title("🔍 Consulta, Edición y Eliminación de Tráficos")

# Cargar todos los tráficos (abiertos y cerrados)
traficos = supabase.table("Traficos").select("*").is_("Fecha_Cierre", None).order("Fecha", desc=True).limit(100).execute()
df_traficos = pd.DataFrame(traficos.data)

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
                ingreso_cruce_incluido = st.checkbox("✅ ¿El ingreso de cruce ya está incluido en la tarifa?", value=False)

            with col2:
                moneda = st.selectbox("Moneda", ["MXP", "USD"],
                                      index=["MXP", "USD"].index(seleccionado["Moneda"]))
                ingreso_original = st.number_input("Ingreso Original", value=round(float(seleccionado["Ingreso_Original"]), 2))
                tipo_cambio = 1 if moneda == "MXP" else float(st.session_state.get("tipo_cambio_usd", 17.0))
                ingreso_total = round(ingreso_original * tipo_cambio, 2)
                km = st.number_input("KM", value=round(float(seleccionado["KM"]), 2))
                horas_termo = st.number_input("Horas Termo", value=round(float(seleccionado.get("Horas_Termo", 0)), 2))
                mov_local = st.number_input("Movimiento Local", value=round(float(seleccionado.get("Movimiento_Local", 0)), 2))
                puntualidad = st.number_input("Puntualidad", value=round(float(seleccionado.get("Puntualidad", 0)), 2))
                pension = st.number_input("Pensión", value=round(float(seleccionado.get("Pension", 0)), 2))
                extras_cobrados = st.checkbox("✅ ¿Costos extras fueron cobrados?", value=bool(seleccionado.get("Extras_Cobrados", False)))

            with col3:
                estancia = st.number_input("Estancia", value=round(float(seleccionado.get("Estancia", 0)), 2))
                pistas_extra = st.number_input("Pistas Extra", value=round(float(seleccionado.get("Pistas Extra") or 0), 2))
                stop = st.number_input("Stop", value=round(float(seleccionado.get("Stop", 0)), 2))
                falso = st.number_input("Falso", value=round(float(seleccionado.get("Falso", 0)), 2))
                gatas = st.number_input("Gatas", value=round(float(seleccionado.get("Gatas", 0)), 2))
                accesorios = st.number_input("Accesorios", value=round(float(seleccionado.get("Accesorios", 0)), 2))
                guias = st.number_input("Guias", value=round(float(seleccionado.get("Guias") or 0), 2))

            # Recalcular (usando datos_generales)
            tarifa_impo = valores["Pago x km IMPORTACION"]
            tarifa_expo = valores["Pago x km EXPORTACION"]
            bono_isr_valor = valores["Bono ISR IMSS"]
            pago_fijo_vacio = valores["Pago fijo VACIO"]

            tarifa = 0
            if tipo == "VACIO":
                sueldo = pago_fijo_vacio
            elif tipo == "IMPORTACION":
                sueldo = km * tarifa_impo
            elif tipo == "EXPORTACION":
                sueldo = km * tarifa_expo
            else:
                sueldo = 0

            sueldo = round(sueldo, 2)

            rendimiento = float(seleccionado.get("Rendimiento Camion", valores["Rendimiento Camion"]))
            costo_diesel = float(seleccionado.get("Costo Diesel", valores["Costo Diesel"]))
            diesel_camion = round((km / rendimiento) * costo_diesel, 2)

            rendimiento_termo = float(seleccionado.get("Rendimiento Termo", valores["Rendimiento Termo"]))
            diesel_termo = horas_termo * rendimiento_termo * costo_diesel

            bono_isr = bono_isr_valor if tipo in ["IMPORTACION", "EXPORTACION"] else 0
            if modo == "Team":
                bono_isr *= 2

            # Puntualidad como costo (aunque no se cobra al cliente)
            puntualidad = safe(seleccionado.get("Puntualidad", 0))

            extras = sum([mov_local, pension, estancia, pistas_extra, stop, falso, gatas, accesorios, guias])
            extras_cobrados = bool(seleccionado.get("Extras_Cobrados", False))
            if extras_cobrados:
                ingreso_total += extras
            costo_total = sueldo + bono_isr + diesel_camion + diesel_termo + extras + puntualidad
            costos_indirectos = ingreso_total * 0.35
            utilidad_bruta = ingreso_total - costo_total
            utilidad_neta = utilidad_bruta - costos_indirectos

            if st.button("💾 Guardar cambios"):
                supabase.table("Traficos").update({
                    "Cliente": cliente,
                    "Origen": origen,
                    "Destino": destino,
                    "Tipo": tipo,
                    "Modo de Viaje": modo,
                    "Moneda": moneda,
                    "Ingreso_Original": ingreso_original,
                    "Ingreso Total": ingreso_total,
                    "KM": km,
                    "Horas_Termo": horas_termo,
                    "Movimiento_Local": mov_local,
                    "Puntualidad": puntualidad,
                    "Pension": pension,
                    "Estancia": estancia,
                    "Pistas Extra": pistas_extra,
                    "Stop": stop,
                    "Falso": falso,
                    "Gatas": gatas,
                    "Accesorios": accesorios,
                    "Guias": guias,
                    "Sueldo_Operador": sueldo,
                    "Costo_Diesel_Camion": diesel_camion,
                    "Costo_Diesel_Termo": diesel_termo,
                    "Costo_Extras": extras,
                    "Costo_Total_Ruta": costo_total,
                    "Bono_ISR_IMSS": bono_isr,
                    "Costos_Indirectos": costos_indirectos,
                    "Utilidad_Bruta": utilidad_bruta,
                    "Utilidad_Neta": utilidad_neta,
                    "Extras_Cobrados": extras_cobrados,
                }).eq("ID_Programacion", seleccionado["ID_Programacion"]).execute()
                st.success("✅ Tráfico actualizado correctamente.")
                
# =====================================
# 3. COMPLETAR Y SIMULAR TRÁFICO DETALLADO
# =====================================
st.markdown("---")
st.title("🔁 Completar y Simular Tráfico Detallado")

def cargar_programaciones_pendientes():
    data = supabase.table("Traficos").select("*").is_("Fecha_Cierre", None).execute()
    df = pd.DataFrame(data.data)
    if df.empty:
        return pd.DataFrame()
    conteo = df.groupby("ID_Programacion").size().reset_index(name="count")
    pendientes = conteo[conteo["count"] == 1]["ID_Programacion"]
    return df[df["ID_Programacion"].isin(pendientes)]

df_prog = cargar_programaciones_pendientes()
df_rutas = cargar_rutas()

if df_prog.empty:
    st.info("ℹ️ No hay tráficos pendientes por completar.")
else:
    id_sel = st.selectbox("Selecciona un tráfico pendiente", df_prog["ID_Programacion"].unique())
    ida = df_prog[df_prog["ID_Programacion"] == id_sel].iloc[0]
    destino_ida = ida["Destino"]
    tipo_ida = ida["Tipo"]

    tipo_regreso = "EXPORTACION" if tipo_ida == "IMPORTACION" else "IMPORTACION"
    directas = df_rutas[(df_rutas["Tipo"] == tipo_regreso) & (df_rutas["Origen"] == destino_ida)].copy()

    if not directas.empty:
        directas = directas.sort_values(by="% Utilidad", ascending=False)
        idx = st.selectbox(
            "Cliente sugerido (por utilidad)",
            directas.index,
            format_func=lambda x: f"{directas.loc[x, 'Cliente']} - {directas.loc[x, 'Ruta']} ({directas.loc[x, '% Utilidad']:.2f}%)"
        )
        rutas = [ida, directas.loc[idx]]
    else:
        vacios = df_rutas[(df_rutas["Tipo"] == "VACIO") & (df_rutas["Origen"] == destino_ida)].copy()
        mejor_combo = None
        mejor_utilidad = -999999

        for _, vacio in vacios.iterrows():
            origen_exp = vacio["Destino"]
            exportacion = df_rutas[(df_rutas["Tipo"] == tipo_regreso) & (df_rutas["Origen"] == origen_exp)]
            if not exportacion.empty:
                exportacion = exportacion.sort_values(by="% Utilidad", ascending=False).iloc[0]
                ingreso_total = safe(ida["Ingreso Total"]) + safe(exportacion["Ingreso Total"])
                costo_total = safe(ida["Costo_Total_Ruta"]) + safe(vacio["Costo_Total_Ruta"]) + safe(exportacion["Costo_Total_Ruta"])
                utilidad_bruta = ingreso_total - costo_total
                if utilidad_bruta > mejor_utilidad:
                    mejor_utilidad = utilidad_bruta
                    mejor_combo = (vacio, exportacion)

        if mejor_combo:
            vacio, exportacion = mejor_combo
            rutas = [ida, vacio, exportacion]
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

            if tipo == "VACIO":
                sueldo = valores["Pago fijo VACIO"]
            elif tipo == "IMPORTACION":
                sueldo = km * valores["Pago x km IMPORTACION"]
            elif tipo == "EXPORTACION":
               sueldo = km * valores["Pago x km EXPORTACION"]
            else:
                sueldo = 0
            bono = valores["Bono ISR IMSS"] if tipo in ["IMPORTACION", "EXPORTACION"] else 0
            if modo == "Team":
                bono *= 2

            rendimiento = valores["Rendimiento Camion"]
            diesel_precio = valores["Costo Diesel"]
            diesel_camion = (km / rendimiento) * diesel_precio
            diesel_termo = horas_termo * valores["Rendimiento Termo"] * valores["Costo Diesel"]

            extras = safe(datos.get("Costo_Extras", 0))
            costo_total = sueldo + bono + diesel_camion + diesel_termo + extras

            ingreso_total = safe(datos.get("Ingreso Total", 0))
            costos_indirectos = ingreso_total * 0.35
            utilidad_bruta = ingreso_total - costo_total
            utilidad_neta = utilidad_bruta - costos_indirectos

            datos.update({
                "Bono_ISR_IMSS": bono,
                "Costo_Diesel_Camion": diesel_camion,
                "Costo_Diesel_Termo": diesel_termo,
                "Costo_Total_Ruta": costo_total,
                "Costos_Indirectos": costos_indirectos,
                "Utilidad_Bruta": utilidad_bruta,
                "Utilidad_Neta": utilidad_neta,
                "Rendimiento_Camion": rendimiento,
                "Rendimiento_Termo": valores["Rendimiento Termo"],
                "Costo_Diesel": valores["Costo Diesel"],
                "Tipo_Cambio_USD": valores["Tipo de cambio USD"],
            })

            nuevos_tramos.append(datos)


        for fila in nuevos_tramos:
            fila_limpio = limpiar_fila_json(limpiar_tramo_para_insert(fila))
            st.write("DEBUG fila a insertar:", fila)
            st.write("DEBUG JSON limpio:", fila_limpio)

            try:
                supabase.table("Traficos").insert(fila_limpio).execute()
            except Exception as e:
                st.error(f"❌ Error al guardar tráfico: {e}")
                st.stop()

        st.success("✅ Tráfico cerrado correctamente.")
        st.rerun()

# =====================================
# 4. FILTRO Y RESUMEN DE VIAJES CONCLUIDOS
# =====================================
st.title("✅ Tráficos Concluidos con Filtro de Fechas")

def cargar_programaciones():
    data = supabase.table("Traficos").select("*").execute()
    df = pd.DataFrame(data.data)
    if df.empty:
        return pd.DataFrame()
    df["Fecha_Cierre"] = pd.to_datetime(df["Fecha_Cierre"], errors="coerce")
    return df

df = cargar_programaciones()

if df.empty:
    st.info("ℹ️ Aún no hay programaciones registradas.")
else:
    st.subheader("📅 Filtro por Fecha (Fecha de Cierre de la VUELTA)")
    fecha_min = df["Fecha_Cierre"].min()
    fecha_max = df["Fecha_Cierre"].max()
    hoy = datetime.today().date()

    fecha_inicio = st.date_input("Fecha inicio", value=fecha_min.date() if pd.notna(fecha_min) else hoy)
    fecha_fin = st.date_input("Fecha fin", value=fecha_max.date() if pd.notna(fecha_max) else hoy)

    # Paso 1: detectar viajes con vuelta cerrada
    cerrados = df[df["Fecha_Cierre"].notna()]
    traficos_cerrados = cerrados["Número_Trafico"].unique()

    # Paso 2: recuperar todos los tramos (IDA y vuelta) de esos tráficos
    df_filtrado = df[df["Número_Trafico"].isin(traficos_cerrados)].copy()

    # Paso 3: aplicar filtro de fechas sobre Fecha_Cierre de la vuelta
    fechas_vuelta = df_filtrado[df_filtrado["Fecha_Cierre"].notna()].groupby("Número_Trafico")["Fecha_Cierre"].max()
    fechas_vuelta = fechas_vuelta[(fechas_vuelta >= pd.to_datetime(fecha_inicio)) & (fechas_vuelta <= pd.to_datetime(fecha_fin))]

    # Paso 4: quedarnos con todos los tramos de esos tráficos en rango
    df_filtrado = df_filtrado[df_filtrado["Número_Trafico"].isin(fechas_vuelta.index)]

    if df_filtrado.empty:
        st.warning("No hay tráficos concluidos en ese rango de fechas.")
    else:
        resumen = []
        for trafico in df_filtrado["Número_Trafico"].unique():
            tramos = df_filtrado[df_filtrado["Número_Trafico"] == trafico]
            ida = tramos[tramos["ID_Programacion"].str.contains("_IDA")].iloc[0] if not tramos[tramos["ID_Programacion"].str.contains("_IDA")].empty else None
            vuelta = tramos[~tramos["ID_Programacion"].str.contains("_IDA")]

            ingreso_total = tramos["Ingreso Total"].sum()
            costo_total = tramos["Costo_Total_Ruta"].sum()
            utilidad_bruta = ingreso_total - costo_total
            utilidad_pct = round(utilidad_bruta / ingreso_total * 100, 2) if ingreso_total else 0

            cliente_ida = ida["Cliente"] if ida is not None else ""
            ruta_ida = f"{ida['Origen']} → {ida['Destino']}" if ida is not None else ""

            clientes_vuelta = " | ".join(vuelta["Cliente"].dropna().astype(str))
            rutas_vuelta = " | ".join(f"{row['Origen']} → {row['Destino']}" for _, row in vuelta.iterrows())
            fecha_cierre = vuelta["Fecha_Cierre"].max().date() if not vuelta.empty else ""

            resumen.append({
                "Número_Trafico": trafico,
                "Fecha": fecha_cierre,
                "Cliente IDA": cliente_ida,
                "Ruta IDA": ruta_ida,
                "Clientes VUELTA": clientes_vuelta,
                "Rutas VUELTA": rutas_vuelta,
                "Ingreso Total VR": ingreso_total,
                "Costo Total VR": costo_total,
                "Utilidad Total VR": utilidad_bruta,
                "% Utilidad Total VR": utilidad_pct
            })

        resumen_df = pd.DataFrame(resumen)
        st.subheader("📋 Resumen de Viajes Redondos")
        st.dataframe(resumen_df, use_container_width=True)

        csv = resumen_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Descargar Resumen en CSV",
            data=csv,
            file_name="resumen_viajes_redondos.csv",
            mime="text/csv"
        )
