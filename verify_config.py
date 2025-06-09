#!/usr/bin/env python3
"""
Script de verificación post-migración para Ballers App.
Verifica que la nueva configuración unificada funcione correctamente.
"""

import sys
import os

def main():
    print("🔍 Verificando configuración unificada de Ballers App...")
    print("=" * 60)
    
    # Test 1: Importar configuración
    try:
        from config import (
            IS_PRODUCTION, IS_DEVELOPMENT, CALENDAR_ID, 
            ACCOUNTING_SHEET_ID, DATABASE_URL, log_config_info
        )
        print("✅ Config importado correctamente")
        
        # Mostrar información del entorno
        log_config_info()
        
    except ImportError as e:
        print(f"❌ Error importando config: {e}")
        return False
    except Exception as e:
        print(f"❌ Error en configuración: {e}")
        return False
    
    # Test 2: Verificar variables esenciales
    print("\n🔧 Verificando variables esenciales:")
    
    checks = [
        ("IS_PRODUCTION", IS_PRODUCTION is not None),
        ("IS_DEVELOPMENT", IS_DEVELOPMENT is not None),
        ("CALENDAR_ID", CALENDAR_ID is not None and CALENDAR_ID != ""),
        ("ACCOUNTING_SHEET_ID", ACCOUNTING_SHEET_ID is not None and ACCOUNTING_SHEET_ID != ""),
        ("DATABASE_URL", DATABASE_URL is not None and DATABASE_URL != ""),
    ]
    
    for name, check in checks:
        status = "✅" if check else "❌"
        print(f"  {status} {name}: {check}")
    
    # Test 3: Verificar Google Client
    print("\n🔑 Verificando Google Client:")
    try:
        from controllers.google_client import _get_credentials
        creds = _get_credentials()
        print("✅ Credenciales de Google obtenidas correctamente")
        print(f"   Tipo: {type(creds).__name__}")
        print(f"   Service Account: {getattr(creds, 'service_account_email', 'N/A')}")
    except Exception as e:
        print(f"❌ Error con credenciales de Google: {e}")
        return False
    
    # Test 4: Verificar Calendar ID
    print("\n📅 Verificando Calendar ID:")
    expected_prod = "info@ballersbangkok.com"
    expected_dev = "josangl08@usal.es"
    
    if IS_PRODUCTION:
        if CALENDAR_ID == expected_prod:
            print(f"✅ Calendar ID correcto para producción: {CALENDAR_ID}")
        else:
            print(f"⚠️ Calendar ID inesperado en producción: {CALENDAR_ID}")
            print(f"   Esperado: {expected_prod}")
    else:
        if CALENDAR_ID == expected_dev:
            print(f"✅ Calendar ID correcto para desarrollo: {CALENDAR_ID}")
        else:
            print(f"⚠️ Calendar ID inesperado en desarrollo: {CALENDAR_ID}")
            print(f"   Esperado: {expected_dev}")
    
    # Test 5: Verificar que config_production.py no existe
    print("\n🗑️ Verificando limpieza:")
    if os.path.exists("config_production.py"):
        print("⚠️ config_production.py todavía existe - considera eliminarlo")
    else:
        print("✅ config_production.py eliminado correctamente")
    
    # Test 6: Test opcional de conectividad
    print("\n🌐 Test opcional de conectividad:")
    try:
        # Solo intentar si no es un test automático
        if "--skip-connectivity" not in sys.argv:
            from controllers.google_client import calendar
            cal_service = calendar()
            print("✅ Conexión a Google Calendar establecida")
        else:
            print("⏭️ Test de conectividad omitido")
    except Exception as e:
        print(f"⚠️ No se pudo conectar a Google Calendar: {e}")
        print("   (Esto es normal si no hay conexión a internet)")
    
    print("\n" + "=" * 60)
    print("🎉 Verificación completada!")
    print("\n💡 Próximos pasos:")
    print("1. Ejecuta la aplicación: streamlit run main.py")
    print("2. Verifica que la sincronización funcione")
    print("3. Prueba crear/editar sesiones")
    print("4. Elimina los archivos de backup si todo funciona bien")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)