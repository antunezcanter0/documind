# test_raw_connection.py
import asyncio
import asyncpg


async def test_direct():
    print("🔍 Probando conexión directa a PostgreSQL...")

    # Usa los mismos valores que en tu Settings
    config = {
        "host": "127.0.0.1",
        "port": 5434,
        "user": "postgres",
        "password": "password",
        "database": "documind",
        "timeout": 30,
        "command_timeout": 30
    }

    print(f"📡 Conectando a {config['host']}:{config['port']}...")

    try:
        conn = await asyncpg.connect(**config)
        print("✅ ¡Conexión exitosa!")

        # Probar consulta simple
        result = await conn.fetchval("SELECT 1")
        print(f"📊 Consulta de prueba: {result}")

        # Verificar extensión vector
        has_vector = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')")
        print(f"🔢 Extensión vector instalada: {has_vector}")

        await conn.close()
        return True

    except asyncpg.exceptions.InvalidCatalogNameError:
        print("❌ La base de datos 'documind' no existe")
        print("   Crea la base de datos con: CREATE DATABASE documind;")
    except asyncpg.exceptions.InvalidPasswordError:
        print("❌ Contraseña incorrecta")
    except asyncpg.exceptions.CannotConnectNowError:
        print("❌ PostgreSQL no está aceptando conexiones")
    except asyncio.TimeoutError:
        print("❌ Timeout - PostgreSQL no responde")
        print("   Verifica que el contenedor está corriendo: docker ps")
    except ConnectionRefusedError:
        print("❌ Conexión rechazada - El puerto no está abierto")
        print(f"   Verifica: docker ps | grep documind-postgres")
    except Exception as e:
        print(f"❌ Error inesperado: {type(e).__name__}: {e}")

    return False


if __name__ == "__main__":
    asyncio.run(test_direct())