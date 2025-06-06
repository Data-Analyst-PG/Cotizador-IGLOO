
import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ✅ Verificación de sesión y rol
if "usuario" not in st.session_state:
    st.error("⚠️ No has iniciado sesión.")
    st.stop()

rol = st.session_state.usuario.get("Rol", "").lower()
if rol not in ["admin", "gerente", "ejecutivo"]:
    st.error("🚫 No tienes permiso para acceder a este módulo.")
    st.stop()

RUTA_RUTAS = "rutas_guardadas.csv"
RUTA_PROG = "viajes_programados.csv"

st.title("🛣️ Programación de Viajes Detallada")

def safe(x): return 0 if pd.isna(x) or x is None else x

def cargar_rutas():
    if not os.path.exists(RUTA_RUTAS):
        st.error("No se encontró rutas_guardadas.csv")
        st.stop()
    df = pd.read_csv(RUTA_RUTAS)
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
st.header("🚛 Registro de Tráfico - Persona 1")

rutas_df = cargar_rutas()
tipo = st.selectbox("Tipo de ruta (ida)", ["IMPO", "EXPO"])
rutas_tipo = rutas_df[rutas_df["Tipo"] == tipo].copy()

if rutas_tipo.empty:
    st.info("No hay rutas registradas de este tipo.")
    st.stop()

ruta_sel = st.selectbox("Selecciona una ruta (Origen → Destino)", rutas_tipo["Ruta"].unique())
rutas_filtradas = rutas_tipo[rutas_tipo["Ruta"] == ruta_sel].copy()
rutas_filtradas = rutas_filtradas.sort_values(by="% Utilidad", ascending=False)

st.markdown("### Selecciona Cliente (ordenado por % utilidad)")
cliente_idx = st.selectbox("Cliente", rutas_filtradas.index,
    format_func=lambda x: f"{rutas_filtradas.loc[x, 'Cliente']} ({rutas_filtradas.loc[x, '% Utilidad']:.2f}%)")
ruta_ida = rutas_filtradas.loc[cliente_idx]

with st.form("registro_trafico"):
    st.subheader("📝 Datos del tráfico")
    fecha = st.date_input("Fecha de tráfico", value=datetime.today())
    trafico = st.text_input("Número de Tráfico")
    unidad = st.text_input("Unidad")
    operador = st.text_input("Operador")
    submit = st.form_submit_button("📅 Registrar Tráfico")

    if submit:
        if not trafico or not unidad or not operador:
            st.error("❌ Todos los campos son obligatorios para registrar un tráfico.")
        else:
            fecha_str = fecha.strftime("%Y-%m-%d")
            datos = ruta_ida.copy()
            datos["Fecha"] = fecha_str
            datos["Número_Trafico"] = trafico
            datos["Unidad"] = unidad
            datos["Operador"] = operador
            datos["Tramo"] = "IDA"
            datos["ID_Programacion"] = f"{trafico}_{fecha_str}"
            guardar_programacion(pd.DataFrame([datos]))
            st.success("✅ Tráfico registrado exitosamente.")


# =====================================
# 2. VER, EDITAR Y ELIMINAR PROGRAMACIONES
# =====================================
st.markdown("---")
st.header("🛠️ Gestión de Tráficos Programados")

if os.path.exists(RUTA_PROG):
    df_prog = pd.read_csv(RUTA_PROG)

    if "ID_Programacion" in df_prog.columns:
        ids = df_prog["ID_Programacion"].dropna().unique()
        id_edit = st.selectbox("Selecciona un tráfico para editar o eliminar", ids)
        df_filtrado = df_prog[df_prog["ID_Programacion"] == id_edit].reset_index()
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
                nueva_unidad = st.text_input("Editar Unidad", value=tramo_ida["Unidad"])
                nuevo_operador = st.text_input("Editar Operador", value=tramo_ida["Operador"])
                editar_btn = st.form_submit_button("💾 Guardar cambios")

                if editar_btn:
                    df_prog.loc[(df_prog["ID_Programacion"] == id_edit) & (df_prog["Tramo"] == "IDA"), "Unidad"] = nueva_unidad
                    df_prog.loc[(df_prog["ID_Programacion"] == id_edit) & (df_prog["Tramo"] == "IDA"), "Operador"] = nuevo_operador
                    df_prog.to_csv(RUTA_PROG, index=False)
                    st.success("✅ Cambios guardados exitosamente.")
        else:
            st.warning("⚠️ No se encontró tramo IDA en este tráfico. No es posible editar Unidad u Operador.")


# =====================================
# 3. COMPLETAR Y SIMULAR TRÁFICO DETALLADO
# =====================================
st.markdown("---")
st.title("🔁 Completar y Simular Tráfico Detallado")

if not os.path.exists(RUTA_PROG) or not os.path.exists(RUTA_RUTAS):
    st.error("❌ Faltan archivos necesarios para continuar.")
    st.stop()

df_prog = pd.read_csv(RUTA_PROG)
df_rutas = cargar_rutas()

incompletos = df_prog.groupby("ID_Programacion").size().reset_index(name="count")
incompletos = incompletos[incompletos["count"] == 1]["ID_Programacion"]

if not incompletos.empty:
    id_sel = st.selectbox("Selecciona un tráfico pendiente", incompletos)
    ida = df_prog[df_prog["ID_Programacion"] == id_sel].iloc[0]
    destino_ida = ida["Destino"]
    tipo_ida = ida["Tipo"]

    tipo_regreso = "EXPO" if tipo_ida == "IMPO" else "IMPO"
    directas = df_rutas[(df_rutas["Tipo"] == tipo_regreso) & (df_rutas["Origen"] == destino_ida)].copy()

    if not directas.empty:
        directas = directas.sort_values(by="% Utilidad", ascending=False)
        idx = st.selectbox("Cliente sugerido (por utilidad)", directas.index,
            format_func=lambda x: f"{directas.loc[x, 'Cliente']} - {directas.loc[x, 'Ruta']} ({directas.loc[x, '% Utilidad']:.2f}%)")
        rutas = [ida, directas.loc[idx]]
    else:
        vacios = df_rutas[(df_rutas["Tipo"] == "VACIO") & (df_rutas["Origen"] == destino_ida)].copy()
        mejor_combo = None
        mejor_utilidad = -999999

        for _, vacio in vacios.iterrows():
            origen_expo = vacio["Destino"]
            expo = df_rutas[(df_rutas["Tipo"] == tipo_regreso) & (df_rutas["Origen"] == origen_expo)]
            if not expo.empty:
                expo = expo.sort_values(by="% Utilidad", ascending=False).iloc[0]
                ingreso_total = safe(ida["Ingreso Total"]) + safe(expo["Ingreso Total"])
                costo_total = safe(ida["Costo_Total_Ruta"]) + safe(vacio["Costo_Total_Ruta"]) + safe(expo["Costo_Total_Ruta"])
                utilidad = ingreso_total - costo_total
                if utilidad > mejor_utilidad:
                    mejor_utilidad = utilidad
                    mejor_combo = (vacio, expo)

        if mejor_combo:
            vacio, expo = mejor_combo
            rutas = [ida, vacio, expo]
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

st.title("✅ Tráficos Concluidos con Filtro de Fechas")

if not os.path.exists(RUTA_PROG):
    st.error("❌ No se encontró el archivo de viajes programados.")
    st.stop()

df = pd.read_csv(RUTA_PROG)

# Verificamos que haya tráfico cerrado (IDA + VUELTA o más)
programaciones = df.groupby("ID_Programacion").size().reset_index(name="Tramos")
concluidos = programaciones[programaciones["Tramos"] >= 2]["ID_Programacion"]

if concluidos.empty:
    st.info("Aún no hay tráficos concluidos.")
else:
    df_concluidos = df[df["ID_Programacion"].isin(concluidos)].copy()
    df_concluidos["Fecha"] = pd.to_datetime(df_concluidos["Fecha"])

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
