import pandas as pd
import streamlit as st
from .google_client import sheets

# 🆕 NUEVO: Importar configuración de producción
from config_production import ProductionConfig

@st.cache_data(ttl=300)  # se actualiza cada 5 min
def get_accounting_df():
    """
    Obtiene datos de contabilidad desde Google Sheets.
    Usa configuración automática según el entorno.
    """
    # Usar SHEET_ID de configuración según el entorno
    SHEET_ID = ProductionConfig.get_accounting_sheet_id()
    
    rng = "Hoja 1!A:G"  # cambia si tu pestaña se llama distinto
    data = sheets().spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=rng
    ).execute().get("values", [])
    
    df = pd.DataFrame(data[1:], columns=data[0])
    for col in ("Ingresos", "Gastos"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df