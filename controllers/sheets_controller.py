import os
import pandas as pd
import streamlit as st
from .google_client import sheets

def get_sheet_id():
    """Obtiene Sheet ID desde secrets o variable de entorno"""
    # 1. Streamlit secrets (producción)
    try:
        if hasattr(st, 'secrets') and hasattr(st.secrets.google, 'accounting_sheet_id'):
            return st.secrets.google.accounting_sheet_id
    except:
        pass
    
    # 2. Variable de entorno (desarrollo)
    return os.getenv("ACCOUNTING_SHEET_ID")

@st.cache_data(ttl=300)  # se actualiza cada 5 min
def get_accounting_df():
    sheet_id = get_sheet_id()
    if not sheet_id:
        raise ValueError("ACCOUNTING_SHEET_ID not configured")
    
    rng = "Hoja 1!A:G"  # cambia si tu pestaña se llama distinto
    data = sheets().spreadsheets().values().get(
        spreadsheetId=sheet_id, range=rng
    ).execute().get("values", [])
    
    df = pd.DataFrame(data[1:], columns=data[0])
    for col in ("Ingresos", "Gastos"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df