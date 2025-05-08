import streamlit as st
import pandas as pd
import os
from datetime import datetime

RUTA_RUTAS = "rutas_guardadas.csv"
RUTA_DATOS = "datos_generales.csv"

def cargar_datos_generales():
    if os.path.exists(RUTA_DATOS):
        return pd.read_csv(RUTA_DATOS).set_index("Parametro").to_dict()["Valor"]
    else:
        return {}

def safe_number(x):
    return 0 if (x is None or (isinstance(x, float) and pd.isna(x))) else x

st.title("🗂️ Gestión de Rutas Guardadas")

if os.path.exists(RUTA_RUTAS):
    df = pd.read_csv(RUTA_RUTAS)
    valores = cargar_datos_generales()

    st.subheader("📋 Rutas Registradas")
    st.dataframe(df, use_container_width=True)
    st.markdown(f"**Total de rutas registradas:** {len(df)}")
    st.markdown("---")

    st.subheader("🗑️ Eliminar rutas")
    indices = st.multiselect("Selecciona los índices a eliminar", df.index.tolist())
    if st.button("Eliminar rutas seleccionadas") and indices:
        df.drop(index=indices, inplace=True)
        df.reset_index(drop=True, inplace=True)
        df.to_csv(RUTA_RUTAS, index=False)
        st.success("✅ Rutas eliminadas correctamente.")
        st.experimental_rerun()

    st.markdown("---")
    st.subheader("✏️ Editar Ruta Existente")
    indice_editar = st.selectbox("Selecciona el índice a editar", df.index.tolist())
    if indice_editar is not None:
        ruta = df.loc[indice_editar]
        st.markdown("### Modifica los valores de la ruta:")
        with st.form("editar_ruta"):
            col1, col2 = st.columns(2)
            with col1:
                fecha = st.date_input("Fecha", pd.to_datetime(ruta.get("Fecha", pd.Timestamp.now())))
                tipo = st.selectbox("Tipo", ["IMPO", "EXPO", "VACIO"], index=["IMPO", "EXPO", "VACIO"].index(ruta.get("Tipo", "IMPO")))
                cliente = st.text_input("Cliente", value=ruta.get("Cliente", ""))
                origen = st.text_input("Origen", value=ruta.get("Origen", ""))
                destino = st.text_input("Destino", value=ruta.get("Destino", ""))
                km = st.number_input("Kilómetros", min_value=0.0, value=float(ruta.get("KM", 0.0)))
                moneda_ingreso = st.selectbox("Moneda Flete", ["MXN", "USD"], index=["MXN", "USD"].index(ruta.get("Moneda", "MXN")))
                ingreso_original = st.number_input("Ingreso Flete Original", min_value=0.0, value=float(ruta.get("Ingreso_Original", 0.0)))
                moneda_cruce = st.selectbox("Moneda Cruce", ["MXN", "USD"], index=["MXN", "USD"].index(ruta.get("Moneda_Cruce", "MXN")))
                ingreso_cruce = st.number_input("Ingreso Cruce Original", min_value=0.0, value=float(ruta.get("Cruce_Original", 0.0)))
                moneda_costo_cruce = st.selectbox("Moneda Costo Cruce", ["MXN", "USD"], index=["MXN", "USD"].index(ruta.get("Moneda Costo Cruce", "MXN")))
                costo_cruce = st.number_input("Costo Cruce", min_value=0.0, value=float(ruta.get("Costo Cruce", 0.0)))
            with col2:
                horas_termo = st.number_input("Horas Termo", min_value=0.0, value=float(ruta.get("Horas_Termo", 0.0)))
                lavado_termo = st.number_input("Lavado Termo", min_value=0.0, value=float(ruta.get("Lavado_Termo", 0.0)))
                movimiento_local = st.number_input("Movimiento Local", min_value=0.0, value=float(ruta.get("Movimiento_Local", 0.0)))
                puntualidad = st.number_input("Puntualidad", min_value=0.0, value=float(ruta.get("Puntualidad", 0.0)))
                pension = st.number_input("Pensión", min_value=0.0, value=float(ruta.get("Pension", 0.0)))
                estancia = st.number_input("Estancia", min_value=0.0, value=float(ruta.get("Estancia", 0.0)))
                fianza_termo = st.number_input("Fianza Termo", min_value=0.0, value=float(ruta.get("Fianza_Termo", 0.0)))
                renta_termo = st.number_input("Renta Termo", min_value=0.0, value=float(ruta.get("Renta_Termo", 0.0)))
                casetas = st.number_input("Casetas", min_value=0.0, value=float(ruta.get("Casetas", 0.0)))

            guardar = st.form_submit_button("💾 Guardar cambios")

            if guardar:
                tc_usd = valores.get("Tipo de cambio USD", 17.5)
                tc_mxn = valores.get("Tipo de cambio MXN", 1.0)

                tipo_cambio_flete = tc_usd if moneda_ingreso == "USD" else tc_mxn
                tipo_cambio_cruce = tc_usd if moneda_cruce == "USD" else tc_mxn
                tipo_cambio_costo_cruce = tc_usd if moneda_costo_cruce == "USD" else tc_mxn

                ingreso_flete_convertido = ingreso_original * tipo_cambio_flete
                ingreso_cruce_convertido = ingreso_cruce * tipo_cambio_cruce
                ingreso_total = ingreso_flete_convertido + ingreso_cruce_convertido
                costo_cruce_convertido = costo_cruce * tipo_cambio_costo_cruce

                rendimiento_camion = valores.get("Rendimiento Camion", 1)
                costo_diesel = valores.get("Costo Diesel", 1)
                rendimiento_termo = valores.get("Rendimiento Termo", 1)

                costo_diesel_camion = (km / rendimiento_camion) * costo_diesel
                costo_diesel_termo = horas_termo * rendimiento_termo * costo_diesel

                if tipo == "IMPO":
                    pago_km = valores.get("Pago x km IMPO", 2.1)
                    sueldo = km * pago_km
                    bono = valores.get("Bono ISR IMSS", 0)
                elif tipo == "EXPO":
                    pago_km = valores.get("Pago x km EXPO", 2.5)
                    sueldo = km * pago_km
                    bono = valores.get("Bono ISR IMSS", 0)
                else:
                    pago_km = 0.0
                    sueldo = valores.get("Pago fijo VACIO", 200.0)
                    bono = 0.0

                extras = sum([
                    safe_number(lavado_termo), safe_number(movimiento_local), safe_number(puntualidad),
                    safe_number(pension), safe_number(estancia), safe_number(fianza_termo), safe_number(renta_termo)
                ])

                costo_total = costo_diesel_camion + costo_diesel_termo + sueldo + bono + casetas + extras + costo_cruce_convertido

                df.at[indice_editar, "Fecha"] = fecha
                df.at[indice_editar, "Tipo"] = tipo
                df.at[indice_editar, "Cliente"] = cliente
                df.at[indice_editar, "Origen"] = origen
                df.at[indice_editar, "Destino"] = destino
                df.at[indice_editar, "KM"] = km
                df.at[indice_editar, "Moneda"] = moneda_ingreso
                df.at[indice_editar, "Ingreso_Original"] = ingreso_original
                df.at[indice_editar, "Tipo de cambio"] = tipo_cambio_flete
                df.at[indice_editar, "Ingreso Flete"] = ingreso_flete_convertido
                df.at[indice_editar, "Moneda_Cruce"] = moneda_cruce
                df.at[indice_editar, "Cruce_Original"] = ingreso_cruce
                df.at[indice_editar, "Tipo cambio Cruce"] = tipo_cambio_cruce
                df.at[indice_editar, "Ingreso Cruce"] = ingreso_cruce_convertido
                df.at[indice_editar, "Ingreso Total"] = ingreso_total
                df.at[indice_editar, "Moneda Costo Cruce"] = moneda_costo_cruce
                df.at[indice_editar, "Costo Cruce"] = costo_cruce
                df.at[indice_editar, "Costo Cruce Convertido"] = costo_cruce_convertido
                df.at[indice_editar, "Pago por KM"] = pago_km
                df.at[indice_editar, "Sueldo_Operador"] = sueldo
                df.at[indice_editar, "Bono"] = bono
                df.at[indice_editar, "Casetas"] = casetas
                df.at[indice_editar, "Horas_Termo"] = horas_termo
                df.at[indice_editar, "Lavado_Termo"] = lavado_termo
                df.at[indice_editar, "Movimiento_Local"] = movimiento_local
                df.at[indice_editar, "Puntualidad"] = puntualidad
                df.at[indice_editar, "Pension"] = pension
                df.at[indice_editar, "Estancia"] = estancia
                df.at[indice_editar, "Fianza_Termo"] = fianza_termo
                df.at[indice_editar, "Renta_Termo"] = renta_termo
                df.at[indice_editar, "Costo_Diesel_Camion"] = costo_diesel_camion
                df.at[indice_editar, "Costo_Diesel_Termo"] = costo_diesel_termo
                df.at[indice_editar, "Costo_Extras"] = extras
                df.at[indice_editar, "Costo_Total_Ruta"] = costo_total

                df.to_csv(RUTA_RUTAS, index=False)
                st.success("✅ Ruta actualizada exitosamente.")
                st.stop()

else:
    st.warning("⚠️ No hay rutas guardadas todavía.")
