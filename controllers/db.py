# controllers/db.py
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session as SQLAlchemySession
from models import Base
import os
from typing import Optional

# 🆕 NUEVO: Importar configuración de producción
from config_production import DATABASE_URL, IS_PRODUCTION, IS_DEVELOPMENT

# Variables globales para reutilizar engine y Session
_engine = None
_Session: Optional[sessionmaker] = None

def initialize_database() -> bool:
    """
    Inicializa la base de datos adaptándose al entorno (SQLite local o PostgreSQL producción).
    
    Returns:
        bool: True si la inicialización fue exitosa, False en caso contrario
    """
    global _engine, _Session
    
    try:
        if _engine is None:
            # 🔧 ACTUALIZADO: Usar DATABASE_URL de configuración
            print(f"🔌 Connecting to database: {'PostgreSQL (Supabase)' if IS_PRODUCTION else 'SQLite (Local)'}")
            
            if IS_PRODUCTION:
                # Configuración para PostgreSQL (Supabase)
                _engine = create_engine(
                    DATABASE_URL,
                    pool_pre_ping=True,  # Verificar conexiones antes de usar
                    pool_recycle=300,    # Reciclar conexiones cada 5 minutos
                    echo=False           # No mostrar SQL queries en producción
                )
            else:
                # Configuración para SQLite (Desarrollo)
                from config import DATABASE_PATH
                if DATABASE_PATH is None:
                    raise RuntimeError("DATABASE_PATH no está configurado para desarrollo")
                
                _engine = create_engine(f"sqlite:///{DATABASE_PATH}")
                
                # Solo crear tablas si la base de datos no existe o está vacía
                if not os.path.exists(DATABASE_PATH) or os.path.getsize(DATABASE_PATH) == 0:
                    print("🔧 Creando nueva base de datos SQLite...")
                    Base.metadata.create_all(_engine)
                    print("✅ Tablas SQLite creadas exitosamente")
            
            # En producción, siempre crear/actualizar tablas (Supabase maneja esto bien)
            if IS_PRODUCTION:
                print("🔧 Sincronizando esquema de base de datos...")
                Base.metadata.create_all(_engine)
                print("✅ Esquema PostgreSQL sincronizado")
            
            _Session = sessionmaker(bind=_engine)
            print("✅ Base de datos inicializada correctamente")
            return True
            
    except Exception as e:
        print(f"❌ Error inicializando base de datos: {e}")
        _engine = None
        _Session = None
        return False
    
    return True

def get_db_session() -> SQLAlchemySession:
    """
    Devuelve una sesión SQLAlchemy lista para usar.
    
    Returns:
        SQLAlchemySession: Sesión de base de datos
        
    Raises:
        RuntimeError: Si no se puede inicializar la base de datos
    """
    global _Session
    
    # Asegurar que la base de datos esté inicializada
    if _Session is None:
        if not initialize_database():
            raise RuntimeError(
                "No se pudo inicializar la base de datos. "
                "Verifica la configuración y las credenciales."
            )
    
    # Esta verificación nunca debería fallar después de initialize_database() exitoso,
    # pero la incluimos para satisfacer a Pylance
    if _Session is None:
        raise RuntimeError("Error crítico: _Session sigue siendo None después de la inicialización")
    
    return _Session()

def close_all_connections():
    """Cierra todas las conexiones y limpia los recursos globales."""
    global _engine, _Session
    
    if _engine is not None:
        _engine.dispose()
        _engine = None
    
    _Session = None
    print("🔒 Conexiones de base de datos cerradas")

def get_database_info() -> dict:
    """
    Devuelve información sobre el estado de la base de datos.
    
    Returns:
        dict: Información sobre la base de datos
    """
    if IS_PRODUCTION:
        return {
            "database_type": "PostgreSQL (Supabase)",
            "database_url": DATABASE_URL[:50] + "..." if DATABASE_URL else "Not configured",
            "is_initialized": _Session is not None,
            "engine_active": _engine is not None,
            "environment": "PRODUCTION"
        }
    else:
        from config import DATABASE_PATH
        if DATABASE_PATH is None:
            return {
                "database_type": "SQLite (Local)",
                "database_path": "Not configured",
                "exists": False,
                "size_bytes": 0,
                "is_initialized": _Session is not None,
                "engine_active": _engine is not None,
                "environment": "DEVELOPMENT"
            }
        
        return {
            "database_type": "SQLite (Local)",
            "database_path": DATABASE_PATH,
            "exists": os.path.exists(DATABASE_PATH),
            "size_bytes": os.path.getsize(DATABASE_PATH) if os.path.exists(DATABASE_PATH) else 0,
            "is_initialized": _Session is not None,
            "engine_active": _engine is not None,
            "environment": "DEVELOPMENT"
        }

def test_database_connection() -> bool:
    """
    Prueba la conexión a la base de datos.
    
    Returns:
        bool: True si la conexión es exitosa
    """
    try:
        db = get_db_session()
        # Ejecutar una query simple para probar la conexión
        db.execute(text("SELECT 1"))
        db.close()
        print("✅ Conexión a base de datos probada exitosamente")
        return True
    except Exception as e:
        print(f"❌ Error probando conexión a base de datos: {e}")
        return False