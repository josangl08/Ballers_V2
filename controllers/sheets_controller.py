# controllers/sheets_controller.py
"""
Controlador para Google Sheets simplificado.
Usa configuración unificada de config.py.
"""
import pandas as pd
import streamlit as st
from .google_client import sheets
from config import ACCOUNTING_SHEET_ID

@st.cache_data(ttl=300)  # se actualiza cada 5 min
def get_accounting_df():
    """Obtiene datos de contabilidad desde Google Sheets."""
    if not ACCOUNTING_SHEET_ID:
        raise ValueError(
            "ACCOUNTING_SHEET_ID no configurado. "
            "Verifica la configuración en secrets o .env"
        )
    
    print(f"📊 Obteniendo datos de Google Sheets (ID: {ACCOUNTING_SHEET_ID})")
    
    rng = "Hoja 1!A:G"  # cambia si tu pestaña se llama distinto
    data = sheets().spreadsheets().values().get(
        spreadsheetId=ACCOUNTING_SHEET_ID, range=rng
    ).execute().get("values", [])
    
    if not data or len(data) < 2:
        raise ValueError("No se encontraron datos en la hoja de cálculo")
    
    df = pd.DataFrame(data[1:], columns=data[0])
    
    # Convertir columnas numéricas
    for col in ("Ingresos", "Gastos"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    
    print(f"✅ Datos de contabilidad obtenidos: {len(df)} filas")
    return df