import streamlit as st
import pandas as pd
import os
from datetime import datetime
from supabase import create_client
import numpy as np

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

def guardar_programacion(nuevo_registro):
    def limpiar_fila_json(fila: dict) -> dict:
        limpio = {}
        for k, v in fila.items():
            # Si es float NaN o None → convierte a None (Supabase lo acepta)
            if v is None or (isinstance(v, float) and np.isnan(v)):
                limpio[k] = None
            # Si es fecha u objeto timestamp, convierte a string
            elif isinstance(v, (pd.Timestamp, datetime)):
                limpio[k] = v.strftime("%Y-%m-%d")
            else:
                limpio[k] = v
        return limpio
    
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

# =====================================
# 1. REGISTRO DESDE DESPACHO
# =====================================
st.title("🛣️ Registro de Viajes desde Despacho")

st.markdown("Carga un archivo de programación generado por despacho para registrar el tráfico inicial (IDA).")

archivo = st.file_uploader("Selecciona el archivo Excel", type=["xlsx"])
if archivo:
    df = pd.read_excel(archivo)
    columnas = df.columns

    if "Número_Trafico" in columnas:
        for i, fila in df.iterrows():
            fecha = datetime.today().strftime("%Y-%m-%d")
            viaje_sel = fila["Número_Trafico"]
            tipo = fila["Tipo"]
            modo = fila["Modo_Viaje"]
            operador = fila["Operador"]
            unidad = fila["Unidad"]
            cliente = fila["Cliente"]
            origen = fila["Origen"]
            destino = fila["Destino"]
            ingreso_original = float(safe(fila["Ingreso"]))
            moneda = fila["Moneda"]
            km = float(safe(fila["KM"]))
            casetas = float(safe(fila["Casetas"]))
            cruce = float(safe(fila["Costo_Cruce"]))
            moneda_cruce = fila.get("Moneda_Costo_Cruce", "MXN")

            puntualidad = safe(fila.get("Puntualidad", 0))
            pension = safe(fila.get("Pension", 0))
            estancia = safe(fila.get("Estancia", 0))
            pistas_extra = safe(fila.get("Pistas Extra", 0))
            stop = safe(fila.get("Stop", 0))
            falso = safe(fila.get("Falso", 0))
            gatas = safe(fila.get("Gatas", 0))
            accesorios = safe(fila.get("Accesorios", 0))
            guias = safe(fila.get("Guías", 0))
            mov_local = safe(fila.get("Movimiento_Local", 0))
            horas_termo = safe(fila.get("Horas_Termo", 0))

            # Valores base
            tarifa_operador = 2.1 if tipo == "IMPORTACION" else 2.5 if tipo == "EXPORTACION" else 0
            tipo_cambio = float(safe(fila.get("Tipo_Cambio", 1)))
            rendimiento = float(safe(fila.get("Rendimiento Camion", 2.5)))
            costo_diesel = float(safe(fila.get("Costo Diesel", 24)))

            sueldo = round(km * tarifa_operador, 2)
            diesel = round((km / rendimiento) * costo_diesel, 2)
            ingreso_total = round(ingreso_original * tipo_cambio, 2)

            # Cálculo de bono ISR/IMSS
            bono_isr = 0
            if tipo in ["IMPORTACION", "EXPORTACION"]:
                bono_isr = 280  # Valor estándar para Igloo
                if modo == "Team":
                    bono_isr *= 2

            # Horas termo y costo termo
            horas_termo = float(safe(horas_termo))
            costo_termo = horas_termo * 50  # Costo por hora termo para Igloo

            # Costo extras ya calculado por separado (pistas, stop, etc.)
            extras = (
                float(safe(puntualidad)) + float(safe(pension)) + float(safe(estancia)) +
                float(safe(pistas_extra)) + float(safe(stop)) + float(safe(falso)) +
                float(safe(gatas)) + float(safe(accesorios)) + float(safe(guias)) +
                float(safe(mov_local))
            )

            # Costo total
            costo_total = sueldo + bono_isr + diesel + costo_termo + extras

            # Ingreso y utilidades
            costos_indirectos = ingreso_total * 0.35
            utilidad_bruta = ingreso_total - costo_total
            utilidad_neta = utilidad_bruta - costos_indirectos

            id_programacion = f"{viaje_sel}_IDA"

            df_nuevo = pd.DataFrame([{
                "ID_Programacion": id_programacion,
                "Fecha": fecha,
                "Número_Trafico": viaje_sel,
                "Tramo": "IDA",
                "Modo_Viaje": modo,
                "Operador": operador,
                "Unidad": unidad,
                "Cliente": cliente,
                "Origen": origen,
                "Destino": destino,
                "Tipo": tipo,
                "Moneda": moneda,
                "Ingreso_Original": ingreso_original,
                "Ingreso Total": ingreso_total,
                "KM": km,
                "Costo Diesel": costo_diesel,
                "Rendimiento Camion": rendimiento,
                "Costo_Diesel_Camion": diesel,
                "Sueldo_Operador": sueldo,
                "Costo_Total_Ruta": costo_total,
                "Costo_Extras": extras,
                "Movimiento_Local": mov_local,
                "Puntualidad": puntualidad,
                "Pension": pension,
                "Estancia": estancia,
                "Pistas Extra": pistas_extra,
                "Stop": stop,
                "Falso": falso,
                "Gatas": gatas,
                "Accesorios": accesorios,
                "Guías": guias,
                "Bono_ISR_IMSS": bono_isr,
                "Costo_Termo": costo_termo,
                "Horas_Termo": horas_termo,
                "Costos_Indirectos": costos_indirectos,
                "Utilidad_Bruta": utilidad_bruta,
                "Utilidad_Neta": utilidad_neta
            }])

            # Insertar a Supabase
            for fila in df_nuevo.to_dict(orient="records"):
                supabase.table("Traficos").insert(fila).execute()

        st.success("✅ Los viajes se registraron correctamente.")
    else:
        st.error("❌ El archivo no contiene la columna 'Número_Trafico'.")

# =====================================
# 2. VER, EDITAR Y ELIMINAR PROGRAMACIONES
# =====================================
st.markdown("---")
st.header("🛠️ Gestión de Tráficos Programados")

# Función para cargar tráficos abiertos (sin Fecha_Cierre)
def cargar_programaciones_abiertas():
    data = supabase.table("Traficos").select("*").is_("Fecha_Cierre", None).execute()
    df = pd.DataFrame(data.data)
    if not df.empty:
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    return df

df_prog = cargar_programaciones_abiertas()

if df_prog.empty:
    st.info("ℹ️ No hay tráficos abiertos para editar.")
else:
    columnas_numericas = [
        "Movimiento_Local", "Puntualidad", "Pension", "Estancia",
        "Pistas Extra", "Stop", "Falso", "Gatas", "Accesorios", "Guías",
        "Costo_Extras", "Costo_Total_Ruta"
    ]
    for col in columnas_numericas:
        if col not in df_prog.columns:
            df_prog[col] = 0.0
        df_prog[col] = pd.to_numeric(df_prog[col], errors="coerce").fillna(0.0)

    ids = df_prog["ID_Programacion"].dropna().unique()
    id_edit = st.selectbox("Selecciona un tráfico para editar o eliminar", ids)

    df_filtrado = df_prog[df_prog["ID_Programacion"] == id_edit].reset_index(drop=True)
    st.write("**Vista previa del tráfico seleccionado:**")
    st.dataframe(df_filtrado)

    if st.button("🗑️ Eliminar tráfico completo"):
        supabase.table("Traficos").delete().eq("ID_Programacion", id_edit).execute()
        st.success("✅ Tráfico eliminado exitosamente.")
        st.rerun()

    df_ida = df_filtrado[df_filtrado["Tramo"] == "IDA"]

    if not df_ida.empty:
        tramo_ida = df_ida.iloc[0]
        with st.form("editar_trafico"):
            nueva_unidad = st.text_input("Editar Unidad", value=str(tramo_ida.get("Unidad", "")))
            nuevo_operador = st.text_input("Editar Operador", value=str(tramo_ida.get("Operador", "")))

            col1, col2 = st.columns(2)
            with col1:
                movimiento_local = st.number_input("Movimiento Local", min_value=0.0, value=safe(tramo_ida.get("Movimiento_Local")), key="mov_local_edit")
                puntualidad = st.number_input("Puntualidad", min_value=0.0, value=safe(tramo_ida.get("Puntualidad")), key="puntualidad_edit")
                pension = st.number_input("Pensión", min_value=0.0, value=safe(tramo_ida.get("Pension")), key="pension_edit")
                estancia = st.number_input("Estancia", min_value=0.0, value=safe(tramo_ida.get("Estancia")), key="estancia_edit")
                pistas_extra = st.number_input("Pistas Extra", min_value=0.0, value=safe(tramo_ida.get("Pistas Extra")), key="pistas_extra_edit")
            with col2:
                stop = st.number_input("Stop", min_value=0.0, value=safe(tramo_ida.get("Stop")), key="stop_edit")
                falso = st.number_input("Falso", min_value=0.0, value=safe(tramo_ida.get("Falso")), key="falso_edit")
                gatas = st.number_input("Gatas", min_value=0.0, value=safe(tramo_ida.get("Gatas")), key="gatas_edit")
                accesorios = st.number_input("Accesorios", min_value=0.0, value=safe(tramo_ida.get("Accesorios")), key="accesorios_edit")
                guias = st.number_input("Guías", min_value=0.0, value=safe(tramo_ida.get("Guías")), key="guias_edit")

            actualizar = st.form_submit_button("💾 Guardar cambios")

            if actualizar:
                columnas = {
                    "Unidad": nueva_unidad,
                    "Operador": nuevo_operador,
                    "Movimiento_Local": movimiento_local,
                    "Puntualidad": puntualidad,
                    "Pension": pension,
                    "Estancia": estancia,
                    "Pistas Extra": pistas_extra,
                    "Stop": stop,
                    "Falso": falso,
                    "Gatas": gatas,
                    "Accesorios": accesorios,
                    "Guías": guias
                }

                extras = sum([safe(v) for k, v in columnas.items() if isinstance(v, (int, float)) and k not in ["Unidad", "Operador"]])
                base = safe(tramo_ida.get("Costo_Total_Ruta")) - safe(tramo_ida.get("Costo_Extras"))
                total = base + extras

                columnas.update({
                    "Costo_Extras": extras,
                    "Costo_Total_Ruta": total
                })

                supabase.table("Traficos").update(columnas).eq("ID_Programacion", id_edit).eq("Tramo", "IDA").execute()
                st.success("✅ Cambios guardados correctamente.")
    else:
        st.warning("⚠️ No hay tramo IDA para editar.")

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
                utilidad = ingreso_total - costo_total
                if utilidad > mejor_utilidad:
                    mejor_utilidad = utilidad
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
    utilidad = ingreso - costo
    indirectos = ingreso * 0.35
    utilidad_neta = utilidad - indirectos

    st.header("📊 Ingresos y Utilidades")
    st.metric("Ingreso Total", f"${ingreso:,.2f}")
    st.metric("Costo Total", f"${costo:,.2f}")
    st.metric("Utilidad Bruta", f"${utilidad:,.2f} ({(utilidad/ingreso*100):.2f}%)")
    st.metric("Costos Indirectos (35%)", f"${indirectos:,.2f}")
    st.metric("Utilidad Neta", f"${utilidad_neta:,.2f} ({(utilidad_neta/ingreso*100):.2f}%)")

    if st.button("💾 Guardar y cerrar tráfico"):
        nuevos_tramos = []
        for tramo in rutas[1:]:
            datos = tramo.copy()
            datos["Fecha"] = ida["Fecha"]
            datos["Número_Trafico"] = ida["Número_Trafico"]
            datos["Unidad"] = ida["Unidad"]
            datos["Operador"] = ida["Operador"]
            sufijo = "_VACIO" if tramo["Tipo"] == "VACIO" else "_VUELTA"
            datos["ID_Programacion"] = f"{ida['Número_Trafico']}{sufijo}"
            datos["Tramo"] = "VUELTA"
            datos["Fecha_Cierre"] = datetime.today().strftime("%Y-%m-%d")

            # === CÁLCULOS ADICIONALES PARA IGLOO ===
            tipo = datos.get("Tipo", "").upper()
            modo = datos.get("Modo_Viaje", "Operado")
            km = safe(datos.get("KM", 0))
            sueldo = safe(datos.get("Sueldo_Operador", 0))

            # Bono ISR/IMSS
            bono_isr = 0
            if tipo in ["IMPO", "EXPO"]:
                bono_isr = safe(bonos.get("Bono_ISR_IMSS", 0))
                if modo == "Team":
                    bono_isr *= 2

            # Termo
            horas_termo = safe(datos.get("Horas_Termo", 0))
            costo_termo = horas_termo * safe(termo.get("Costo_Hora_Termo", 0))

            # Extras y diesel
            extras = safe(datos.get("Costo_Extras", 0))
            diesel_camion = safe(datos.get("Costo_Diesel_Camion", 0))

            # Costos y utilidad
            costo_total = sueldo + bono_isr + diesel_camion + costo_termo + extras
            ingreso = safe(datos.get("Ingreso Total", 0))
            costos_indirectos = ingreso * 0.35
            utilidad_bruta = ingreso - costo_total
            utilidad_neta = utilidad_bruta - costos_indirectos

            # Asignar campos
            datos["Bono_ISR_IMSS"] = bono_isr
            datos["Costo_Termo"] = costo_termo
            datos["Horas_Termo"] = horas_termo
            datos["Costo_Total_Ruta"] = costo_total
            datos["Costos_Indirectos"] = costos_indirectos
            datos["Utilidad_Bruta"] = utilidad_bruta
            datos["Utilidad_Neta"] = utilidad_neta

            nuevos_tramos.append(datos)

        for fila in nuevos_tramos:
            supabase.table("Traficos").insert(limpiar_fila_json(fila)).execute()

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
            utilidad = ingreso_total - costo_total
            utilidad_pct = round(utilidad / ingreso_total * 100, 2) if ingreso_total else 0

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
                "Utilidad Total VR": utilidad,
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
