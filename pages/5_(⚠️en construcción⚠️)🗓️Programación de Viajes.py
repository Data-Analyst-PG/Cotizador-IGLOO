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

def guardar_programacion(df_nueva):
    if os.path.exists(RUTA_PROG):
        df_prog = pd.read_csv(RUTA_PROG)
        df_total = pd.concat([df_prog, df_nueva], ignore_index=True)
    else:
        df_total = df_nueva
    df_total.to_csv(RUTA_PROG, index=False)

# =====================================
# 1. REGISTRO
# =====================================
st.header("🚛 Carga de Tráfico Desde Reporte")

archivo_excel = st.file_uploader("📤 Sube el archivo de despacho (Excel)", type=["xlsx"])

if archivo_excel is not None:
    st.success("✅ Archivo de despacho cargado correctamente.")
    mostrar_registro = True
else:
    mostrar_registro = False
    st.info("ℹ️ No se ha cargado un archivo. Solo se mostrará la gestión de tráficos existentes, puedes seguir gestionando los tráficos ya cargados, aunque no subas un nuevo archivo.")

if mostrar_registro:
    # ✅ Cargar y limpiar datos
    df_despacho = pd.read_excel(archivo_excel)

    df_despacho = df_despacho.rename(columns={
        "Fecha Guía": "Fecha",
        "Pago al operador": "Sueldo_Operador",
        "Viaje": "Numero_Trafico",
        "Operación": "Tipo",
        "Tarifa": "Ingreso_Original",
        "Moneda": "Moneda",
        "Clasificación": "Ruta_Tipo",
        "Unidad": "Unidad",
        "Operador": "Operador"
    })

    df_despacho["Ruta_Tipo"] = df_despacho["Ruta_Tipo"].apply(lambda x: "Ruta Larga" if str(x).upper() == "PROPIA" else "Tramo")
    df_despacho["Tipo"] = df_despacho["Tipo"].str.upper()
    df_despacho["Fecha"] = pd.to_datetime(df_despacho["Fecha"]).dt.date
    df_despacho["KM"] = pd.to_numeric(df_despacho["KM"], errors='coerce')
    df_despacho["Ingreso_Original"] = pd.to_numeric(df_despacho["Ingreso_Original"], errors='coerce')
    df_despacho["Sueldo_Operador"] = pd.to_numeric(df_despacho["Sueldo_Operador"], errors='coerce')

    # ✅ Selección del tráfico
    rutas_df = cargar_rutas()
    st.header("📝 Registro de tráfico desde despacho")

    viajes_disponibles = df_despacho["Numero_Trafico"].dropna().unique()
    viaje_sel = st.selectbox("Selecciona un número de tráfico del despacho", viajes_disponibles)

    datos = df_despacho[df_despacho["Numero_Trafico"] == viaje_sel].iloc[0]

    with st.form("registro_trafico"):
        st.subheader("📝 Validar y completar datos")
        col1, col2 = st.columns(2)

        # Validación segura y conversión a string
        cliente_valor = str(datos["Cliente"]) if pd.notna(datos["Cliente"]) else ""
        origen_valor = str(datos["Origen"]) if pd.notna(datos["Origen"]) else ""
        destino_valor = str(datos["Destino"]) if pd.notna(datos["Destino"]) else ""
        operador_valor = str(datos["Operador"]) if pd.notna(datos["Operador"]) else ""
        unidad_valor = str(datos["Unidad"]) if pd.notna(datos["Unidad"]) else ""
        tipo_valor = str(datos["Tipo"]).strip().upper() if pd.notna(datos["Tipo"]) else "IMPORTACION"
        moneda_valor = str(datos["Moneda"]).strip().upper() if pd.notna(datos["Moneda"]) else "MXP"

        with col1:
            fecha = st.date_input("Fecha", value=datos["Fecha"], key="fecha_input")
            cliente = st.text_input("Cliente", value=cliente_valor, key="cliente_input")
            origen = st.text_input("Origen", value=origen_valor, key="origen_input")
            destino = st.text_input("Destino", value=destino_valor, key="destino_input")
            tipo = st.selectbox("Tipo", ["IMPORTACION", "EXPORTACION", "VACIO"],
                                index=["IMPORTACION", "EXPORTACION", "VACIO"].index(tipo_valor)
                                if tipo_valor in ["IMPORTACION", "EXPORTACION", "VACIO"] else 0,
                                key="tipo_select")
            moneda = st.selectbox("Moneda", ["MXP", "USD"],
                                    index=["MXP", "USD"].index(moneda_valor)
                                    if moneda_valor in ["MXP", "USD"] else 0,
                                    key="moneda_select")
            ingreso_original = st.number_input("Ingreso Original",
                                                value=float(safe(datos["Ingreso_Original"])),
                                                min_value=0.0,
                                                key="ingreso_original_input")

        with col2:
            unidad = st.text_input("Unidad", value=unidad_valor, key="unidad_input")
            operador = st.text_input("Operador", value=operador_valor, key="operador_input")
            km = st.number_input("KM", value=float(safe(datos["KM"])), min_value=0.0, key="km_input")
            rendimiento = st.number_input("Rendimiento Camión", value=2.5, key="rendimiento_input")
            costo_diesel = st.number_input("Costo Diesel", value=24.0, key="diesel_input")
            tipo_cambio = st.number_input("Tipo de cambio USD", value=17.5, key="tc_input")

        ingreso_total = ingreso_original * (tipo_cambio if moneda == "USD" else 1)
        diesel = (km / rendimiento) * costo_diesel
        sueldo = st.number_input("Sueldo Operador",
                                value=float(safe(datos["Sueldo_Operador"])),
                                min_value=0.0,
                                key="sueldo_input")

        st.markdown(f"💰 **Ingreso Total Convertido:** ${ingreso_total:,.2f}")
        st.markdown(f"⛽ **Costo Diesel Calculado:** ${diesel:,.2f}")

        submit = st.form_submit_button("📅 Registrar tráfico desde despacho")

        if submit:
            if not operador or not unidad:
                st.error("❌ Operador y Unidad son obligatorios.")
            else:
                fecha_str = fecha.strftime("%Y-%m-%d")
                df_nuevo = pd.DataFrame([{
                    "ID_Programacion": f"{viaje_sel}_{fecha_str}",
                    "Fecha": fecha_str,
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
                    "Unidad": unidad,
                    "Operador": operador,
                    "Modo_Viaje": "Operador",
                    "Ruta_Tipo": datos["Ruta_Tipo"],
                    "Tramo": "IDA",
                    "Número_Trafico": viaje_sel,
                    "Costo_Total_Ruta": diesel + sueldo,
                    "Costo_Extras": 0.0
                }])
                guardar_programacion(df_nuevo)
                st.success("✅ Tráfico registrado exitosamente desde despacho.")

# =====================================
# 2. VER, EDITAR Y ELIMINAR PROGRAMACIONES
# =====================================
st.markdown("---")
st.header("🛠️ Gestión de Tráficos Programados")

# Función segura forzada a float
def safe(x):
    try:
        return float(0.0 if pd.isna(x) or x is None else x)
    except:
        return 0.0

if os.path.exists(RUTA_PROG):
    df_prog = pd.read_csv(RUTA_PROG)

    # Asegurar columnas numéricas como float para evitar errores de tipo
    columnas_numericas = [
        "Movimiento_Local", "Puntualidad", "Pension", "Estancia",
        "Pistas Extra", "Stop", "Falso", "Gatas", "Accesorios", "Guías",
        "Costo_Extras", "Costo_Total_Ruta"
    ]
    for col in columnas_numericas:
        if col not in df_prog.columns:
            df_prog[col] = 0.0  # aseguramos que exista
        df_prog[col] = pd.to_numeric(df_prog[col], errors="coerce").fillna(0.0)

    if "ID_Programacion" in df_prog.columns and not df_prog.empty:
        ids = df_prog["ID_Programacion"].dropna().unique()
        id_edit = st.selectbox("Selecciona un tráfico para editar o eliminar", ids)
        df_filtrado = df_prog[df_prog["ID_Programacion"] == id_edit].reset_index(drop=True)

        st.write("**Vista previa del tráfico seleccionado:**")
        st.dataframe(df_filtrado)

        if st.button("🗑️ Eliminar tráfico completo"):
            df_prog = df_prog[df_prog["ID_Programacion"] != id_edit]
            df_prog.to_csv(RUTA_PROG, index=False)
            st.success("✅ Tráfico eliminado exitosamente.")
            st.experimental_rerun()

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

                    for col, val in columnas.items():
                        df_prog.loc[(df_prog["ID_Programacion"] == id_edit) & (df_prog["Tramo"] == "IDA"), col] = val

                    # Recalcular costo total
                    extras = sum([safe(v) for k, v in columnas.items() if isinstance(v, (int, float, float)) and k not in ["Unidad", "Operador"]])
                    base = safe(tramo_ida.get("Costo_Total_Ruta")) - safe(tramo_ida.get("Costo_Extras"))
                    total = base + extras

                    df_prog.loc[(df_prog["ID_Programacion"] == id_edit) & (df_prog["Tramo"] == "IDA"), "Costo_Extras"] = extras
                    df_prog.loc[(df_prog["ID_Programacion"] == id_edit) & (df_prog["Tramo"] == "IDA"), "Costo_Total_Ruta"] = total

                    df_prog.to_csv(RUTA_PROG, index=False)
                    st.success("✅ Cambios guardados correctamente.")
    else:
        st.warning("⚠️ No hay programaciones válidas disponibles para editar.")
else:
    st.info("ℹ️ Aún no hay archivo de programación generado.")

# =====================================
# 3. COMPLETAR Y SIMULAR TRÁFICO DETALLADO
# =====================================
st.markdown("---")
st.title("🔁 Completar y Simular Tráfico Detallado")

if not os.path.exists(RUTA_PROG):
    st.error("❌ Faltan archivos necesarios para continuar.")
    st.stop()

df_prog = pd.read_csv(RUTA_PROG)
df_rutas = cargar_rutas()

# Validación de columnas numéricas por seguridad
for col in ["Ingreso Total", "Costo_Total_Ruta"]:
    if col not in df_prog.columns:
        df_prog[col] = 0.0
    df_prog[col] = pd.to_numeric(df_prog[col], errors="coerce").fillna(0.0)

for col in ["Ingreso Total", "Costo_Total_Ruta", "% Utilidad"]:
    if col not in df_rutas.columns:
        df_rutas[col] = 0.0
    df_rutas[col] = pd.to_numeric(df_rutas[col], errors="coerce").fillna(0.0)

incompletos = df_prog.groupby("ID_Programacion").size().reset_index(name="count")
incompletos = incompletos[incompletos["count"] == 1]["ID_Programacion"]

if not incompletos.empty:
    id_sel = st.selectbox("Selecciona un tráfico pendiente", incompletos)
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
            origen_exportacion = vacio["Destino"]
            exportacion = df_rutas[(df_rutas["Tipo"] == tipo_regreso) & (df_rutas["Origen"] == origen_exportacion)]
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
            st.warning("No se encontraron rutas de regreso disponibles.")
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
            datos["ID_Programacion"] = ida["ID_Programacion"]
            datos["Tramo"] = "VUELTA"
            nuevos_tramos.append(datos)
        guardar_programacion(pd.DataFrame(nuevos_tramos))
        st.success("✅ Tráfico cerrado exitosamente.")
else:
    st.info("No hay tráficos pendientes.")

# =====================================
# 4. FILTRO Y RESUMEN DE VIAJES CONCLUIDOS
# =====================================
st.title("✅ Tráficos Concluidos con Filtro de Fechas")

if not os.path.exists(RUTA_PROG):
    st.error("❌ No se encontró el archivo de viajes programados.")
    st.stop()

df = pd.read_csv(RUTA_PROG)
df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")

programaciones = df.groupby("ID_Programacion").size().reset_index(name="Tramos")
concluidos = programaciones[programaciones["Tramos"] >= 2]["ID_Programacion"]

if concluidos.empty:
    st.info("Aún no hay tráficos concluidos.")
else:
    df_concluidos = df[df["ID_Programacion"].isin(concluidos)].copy()

    st.subheader("📅 Filtro por Fecha")
    fecha_inicio = st.date_input("Fecha inicio", value=df_concluidos["Fecha"].min().date())
    fecha_fin = st.date_input("Fecha fin", value=df_concluidos["Fecha"].max().date())

    filtro = (df_concluidos["Fecha"] >= pd.to_datetime(fecha_inicio)) & (df_concluidos["Fecha"] <= pd.to_datetime(fecha_fin))
    df_filtrado = df_concluidos[filtro]

    if df_filtrado.empty:
        st.warning("No hay tráficos concluidos en ese rango de fechas.")
    else:
        resumen = df_filtrado.groupby(["ID_Programacion", "Número_Trafico", "Fecha"]).agg({
            "Ingreso Total": "sum",
            "Costo_Total_Ruta": "sum"
        }).reset_index()

        resumen["Utilidad Bruta"] = resumen["Ingreso Total"] - resumen["Costo_Total_Ruta"]
        resumen["% Utilidad Bruta"] = (resumen["Utilidad Bruta"] / resumen["Ingreso Total"] * 100).round(2)
        resumen["Costos Indirectos (35%)"] = (resumen["Ingreso Total"] * 0.35).round(2)
        resumen["Utilidad Neta"] = resumen["Utilidad Bruta"] - resumen["Costos Indirectos (35%)"]
        resumen["% Utilidad Neta"] = (resumen["Utilidad Neta"] / resumen["Ingreso Total"] * 100).round(2)

        st.subheader("📋 Resumen de Viajes Concluidos")
        st.dataframe(resumen, use_container_width=True)

        csv = resumen.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Descargar Resumen en CSV",
            data=csv,
            file_name="resumen_traficos_concluidos.csv",
            mime="text/csv"
        )
