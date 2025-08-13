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

# Configuración de conexión a Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# =========================
# Datos Generales (CSV)
# =========================
RUTA_DATOS = "datos_generales.csv"

DEFAULTS_DATOS_GENERALES = {
    "Rendimiento Camion": 2.5,
    "Costo Diesel": 24.0,
    "Rendimiento Termo": 3.0,
    "Bono ISR IMSS": 462.66,
    "Pago x km IMPORTACION": 2.10,
    "Pago x km EXPORTACION": 2.50,
    "Pago fijo VACIO": 200.00,
    "Tipo de cambio USD": 19.5,
    "Tipo de cambio MXP": 1.0
}

def cargar_datos_generales() -> dict:
    """Lee Parametro/Valor desde CSV. Si no existe, devuelve defaults."""
    if os.path.exists(RUTA_DATOS):
        try:
            df = pd.read_csv(RUTA_DATOS)
            if {"Parametro", "Valor"}.issubset(df.columns):
                # Convertir a dict asegurando numéricos
                vals = {}
                for _, row in df.iterrows():
                    p = str(row["Parametro"])
                    v = row["Valor"]
                    # Intento convertir a float si aplica
                    try:
                        v = float(v)
                    except (TypeError, ValueError):
                        pass
                    vals[p] = v
                # Merge sobre defaults para completar faltantes sin perder CSV
                merged = {**DEFAULTS_DATOS_GENERALES, **vals}
                return merged
        except Exception:
            pass
    # Si no existe o hubo error, usar defaults
    return DEFAULTS_DATOS_GENERALES.copy()

def guardar_datos_generales(valores: dict) -> None:
    """Escribe Parametro/Valor al CSV (siempre se guarda en dos columnas)."""
    registros = [{"Parametro": k, "Valor": valores[k]} for k in valores]
    df = pd.DataFrame(registros, columns=["Parametro", "Valor"])
    df.to_csv(RUTA_DATOS, index=False)

def safe_number(x):
    return 0 if (x is None or (isinstance(x, float) and pd.isna(x))) else float(x)

st.title("🗂️ Gestión de Rutas Guardadas")

# Cargar rutas desde Supabase
respuesta = supabase.table("Rutas").select("*").execute()

# Cargar Datos Generales desde CSV (única fuente de verdad)
valores = cargar_datos_generales()

if respuesta.data:
    df = pd.DataFrame(respuesta.data)
    # Normaliza fecha
    if "Fecha" in df.columns:
        df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.date

    st.subheader("📋 Rutas Registradas")
    st.dataframe(df, use_container_width=True)
    st.markdown(f"**Total de rutas registradas:** {len(df)}")
    st.markdown("---")

    st.subheader("🗑️ Eliminar rutas")
    ids_disponibles = df["ID_Ruta"].tolist()
    ids_a_eliminar = st.multiselect("Selecciona los ID de ruta a eliminar", ids_disponibles)

    if st.button("Eliminar rutas seleccionadas") and ids_a_eliminar:
        for idr in ids_a_eliminar:
            supabase.table("Rutas").delete().eq("ID_Ruta", idr).execute()
        st.success("✅ Rutas eliminadas correctamente.")
        st.rerun()

    st.markdown("---")
    st.subheader("✏️ Editar Ruta Existente")

    # =========================
    # ⚙️ Configurar Datos Generales (CSV)
    # =========================
    with st.expander("⚙️ Configurar Datos Generales"):
        st.markdown("Estos valores afectan el cálculo de costos, sueldo y utilidad en todas las rutas.")
        nuevos_valores = {}
        # Para mantener orden legible: primero keys de defaults, luego adicionales del CSV
        ordered_keys = list(DEFAULTS_DATOS_GENERALES.keys()) + [
            k for k in valores.keys() if k not in DEFAULTS_DATOS_GENERALES
        ]
        columnas = st.columns(3)
        for i, clave in enumerate(ordered_keys):
            valor_actual = float(valores.get(clave, DEFAULTS_DATOS_GENERALES.get(clave, 0)))
            with columnas[i % 3]:
                nuevos_valores[clave] = st.number_input(clave, value=valor_actual, step=0.1, key=f"dg_{clave}")

        if st.button("💾 Guardar Datos Generales (Gestión de Rutas)"):
            guardar_datos_generales(nuevos_valores)  # ⬅️ ahora sí existe
            st.success("✅ Datos Generales guardados correctamente en CSV.")
            st.rerun()

    st.markdown("---")

    id_editar = st.selectbox("Selecciona el ID de Ruta a editar", ids_disponibles)
    ruta = df[df["ID_Ruta"] == id_editar].iloc[0]

    with st.form("editar_ruta"):
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha", ruta["Fecha"])
            tipo = st.selectbox("Tipo", ["IMPORTACION", "EXPORTACION", "VACIO"],
                                index=["IMPORTACION", "EXPORTACION", "VACIO"].index(ruta["Tipo"]))
            cliente = st.text_input("Cliente", value=ruta["Cliente"])
            origen = st.text_input("Origen", value=ruta["Origen"])
            destino = st.text_input("Destino", value=ruta["Destino"])
            Modo_de_Viaje = st.selectbox("Modo de Viaje", ["Operador", "Team"],
                                         index=["Operador", "Team"].index(ruta["Modo de Viaje"]))
            km = st.number_input("Kilómetros", min_value=0.0, value=float(ruta["KM"]))
            moneda_ingreso = st.selectbox("Moneda Flete", ["MXP", "USD"],
                                          index=["MXP", "USD"].index(ruta["Moneda"]))
            ingreso_original = st.number_input("Ingreso Flete Original", min_value=0.0, value=float(ruta["Ingreso_Original"]))
            moneda_cruce = st.selectbox("Moneda Cruce", ["MXP", "USD"],
                                        index=["MXP", "USD"].index(ruta["Moneda_Cruce"]))
            ingreso_cruce = st.number_input("Ingreso Cruce Original", min_value=0.0, value=float(ruta["Cruce_Original"]))
        with col2:
            moneda_costo_cruce = st.selectbox("Moneda Costo Cruce", ["MXP", "USD"],
                                              index=["MXP", "USD"].index(ruta["Moneda Costo Cruce"]))
            costo_cruce = st.number_input("Costo Cruce", min_value=0.0, value=float(ruta["Costo Cruce"]))
            horas_termo = st.number_input("Horas Termo", min_value=0.0, value=float(ruta["Horas_Termo"]))
            lavado_termo = st.number_input("Lavado Termo", min_value=0.0, value=float(ruta["Lavado_Termo"]))
            movimiento_local = st.number_input("Movimiento Local", min_value=0.0, value=float(ruta["Movimiento_Local"]))
            puntualidad = st.number_input("Puntualidad", min_value=0.0, value=float(ruta["Puntualidad"]))
            pension = st.number_input("Pensión", min_value=0.0, value=float(ruta["Pension"]))
            estancia = st.number_input("Estancia", min_value=0.0, value=float(ruta["Estancia"]))
            fianza_termo = st.number_input("Fianza Termo", min_value=0.0, value=float(ruta["Fianza_Termo"]))
            renta_termo = st.number_input("Renta Termo", min_value=0.0, value=float(ruta["Renta_Termo"]))
            casetas = st.number_input("Casetas", min_value=0.0, value=float(ruta["Casetas"]))

        st.markdown("---")
        st.subheader("🧾 Costos Extras Adicionales")
        col3, col4 = st.columns(2)
        with col3:
            pistas_extra = st.number_input("Pistas Extra", min_value=0.0, value=float(ruta["Pistas_Extra"]))
            stop = st.number_input("Stop", min_value=0.0, value=float(ruta["Stop"]))
            falso = st.number_input("Falso", min_value=0.0, value=float(ruta["Falso"]))
            extras_cobrados_val = bool(ruta["Extras_Cobrados"]) if "Extras_Cobrados" in ruta else False
            extras_cobrados = st.checkbox("✅ ¿Costos extras se incluirán al ingreso?", value=extras_cobrados_val)
        with col4:
            gatas = st.number_input("Gatas", min_value=0.0, value=float(ruta["Gatas"]))
            accesorios = st.number_input("Accesorios", min_value=0.0, value=float(ruta["Accesorios"]))
            guias = st.number_input("Guías", min_value=0.0, value=float(ruta["Guias"]))

        guardar = st.form_submit_button("💾 Guardar cambios")

        if guardar:
            # --- Tipos de cambio desde CSV ---
            tc_usd = float(valores.get("Tipo de cambio USD", 17.5))
            tc_mxp = float(valores.get("Tipo de cambio MXP", 1.0))
            tipo_cambio_flete = tc_usd if moneda_ingreso == "USD" else tc_mxp
            tipo_cambio_cruce = tc_usd if moneda_cruce == "USD" else tc_mxp
            tipo_cambio_costo_cruce = tc_usd if moneda_costo_cruce == "USD" else tc_mxp

            ingreso_flete_convertido = ingreso_original * tipo_cambio_flete
            ingreso_cruce_convertido = ingreso_cruce * tipo_cambio_cruce

            # --- Costos de combustible desde CSV ---
            rendimiento_camion = float(valores.get("Rendimiento Camion", 1))
            costo_diesel = float(valores.get("Costo Diesel", 1))
            rendimiento_termo = float(valores.get("Rendimiento Termo", 1))
            costo_diesel_camion = (km / max(rendimiento_camion, 0.0001)) * costo_diesel
            costo_diesel_termo = horas_termo * max(rendimiento_termo, 0) * costo_diesel

            # --- Sueldo/Bono desde CSV ---
            factor = 2 if Modo_de_Viaje == "Team" else 1

            if tipo == "IMPORTACION":
                pago_km = float(valores.get("Pago x km IMPORTACION", 2.1))
                sueldo = km * pago_km * factor
                bono = float(valores.get("Bono ISR IMSS", 0)) * factor
            elif tipo == "EXPORTACION":
                pago_km = float(valores.get("Pago x km EXPORTACION", 2.5))
                sueldo = km * pago_km * factor
                bono = float(valores.get("Bono ISR IMSS", 0)) * factor
            else:
                pago_km = 0.0
                sueldo = float(valores.get("Pago fijo VACIO", 200.0)) * factor
                bono = 0.0

            # Ajustes y extras
            puntualidad_adj = puntualidad * factor
            extras = sum(map(safe_number, [
                lavado_termo, movimiento_local, puntualidad_adj, pension, estancia,
                fianza_termo, renta_termo, pistas_extra, stop, falso, gatas, accesorios, guias
            ]))

            ingreso_total = ingreso_flete_convertido + ingreso_cruce_convertido
            if extras_cobrados:
                ingreso_total += extras  # <-- ahora sí, extras ya existe

            costo_cruce_convertido = costo_cruce * tipo_cambio_costo_cruce
            costo_total = (
                costo_diesel_camion + costo_diesel_termo + sueldo + bono + casetas + extras + costo_cruce_convertido
            )

            ruta_actualizada = {
                "Modo de Viaje": Modo_de_Viaje,
                "Fecha": fecha.isoformat(),
                "Tipo": tipo,
                "Cliente": cliente,
                "Origen": origen,
                "Destino": destino,
                "KM": km,
                "Moneda": moneda_ingreso,
                "Ingreso_Original": ingreso_original,
                "Tipo de cambio": tipo_cambio_flete,
                "Ingreso Flete": ingreso_flete_convertido,
                "Moneda_Cruce": moneda_cruce,
                "Cruce_Original": ingreso_cruce,
                "Tipo cambio Cruce": tipo_cambio_cruce,
                "Ingreso Cruce": ingreso_cruce_convertido,
                "Ingreso Total": ingreso_total,
                "Moneda Costo Cruce": moneda_costo_cruce,
                "Costo Cruce": costo_cruce,
                "Costo Cruce Convertido": costo_cruce_convertido,
                "Pago por KM": pago_km,
                "Sueldo_Operador": sueldo,
                "Bono": bono,
                "Casetas": casetas,
                "Horas_Termo": horas_termo,
                "Lavado_Termo": lavado_termo,
                "Movimiento_Local": movimiento_local,
                "Puntualidad": puntualidad,
                "Pension": pension,
                "Estancia": estancia,
                "Fianza_Termo": fianza_termo,
                "Renta_Termo": renta_termo,
                "Pistas_Extra": pistas_extra,
                "Stop": stop,
                "Falso": falso,
                "Gatas": gatas,
                "Accesorios": accesorios,
                "Guias": guias,
                "Costo_Diesel_Camion": costo_diesel_camion,
                "Costo_Diesel_Termo": costo_diesel_termo,
                "Costo_Extras": extras,
                "Costo_Total_Ruta": costo_total,
                "Costo Diesel": costo_diesel,
                "Rendimiento Camion": rendimiento_camion,
                "Rendimiento Termo": rendimiento_termo,
                "Extras_Cobrados": extras_cobrados,
            }

            try:
                supabase.table("Rutas").update(ruta_actualizada).eq("ID_Ruta", id_editar).execute()
                st.success("✅ Ruta actualizada exitosamente.")
                st.stop()
            except Exception as e:
                st.error(f"❌ Error al actualizar ruta: {e}")

else:
    st.warning("⚠️ No hay rutas guardadas todavía.")
