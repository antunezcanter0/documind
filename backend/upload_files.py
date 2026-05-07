#!/usr/bin/env python3
"""
Script para subir archivos a DocuMind API
"""
import os
import asyncio
import aiohttp
import aiofiles
from pathlib import Path

# Configuración
API_BASE_URL = "http://localhost:8000/api/v1"
UPLOAD_ENDPOINT = f"{API_BASE_URL}/documents/upload"

# Directorios con archivos
DIRECTORIOS = [
    # "/home/ariel/Programacion/IA/documind/backend/files/prmtros",
    "/home/ariel/Programacion/IA/documind/backend/files/guiaComandos"
    # "/home/ariel/Programacion/IA/documind/backend/files/prmtros1"
]

# Tipos de archivo permitidos (basados en los archivos encontrados)
ALLOWED_EXTENSIONS = ['.prt', '.fop', '']  # .prt, .fop y archivos sin extensión

async def upload_file(session, file_path):
    """Subir un archivo individual"""
    try:
        filename = os.path.basename(file_path)
        
        async with aiofiles.open(file_path, 'rb') as f:
            file_content = await f.read()
        
        # Determinar el directorio fuente
        source_dir = os.path.basename(os.path.dirname(file_path))
        print(f"DEBUG: Enviando archivo {filename} con source='{source_dir}'")
        
        # Crear multipart form data
        data = aiohttp.FormData()
        data.add_field('file', file_content, filename=filename, content_type='application/octet-stream')
        # Añadir source como campo de formulario
        data.add_field('source', source_dir)
        
        # Subir archivo
        async with session.post(UPLOAD_ENDPOINT, data=data) as response:
            if response.status == 200:
                print(f"✅ Subido: {filename}")
                return True
            else:
                print(f"❌ Error subiendo {filename}: {response.status}")
                error_text = await response.text()
                print(f"   Detalle: {error_text}")
                return False
                
    except Exception as e:
        print(f"❌ Error procesando {file_path}: {str(e)}")
        return False

async def upload_directory(directory_path):
    """Subir todos los archivos de un directorio"""
    print(f"\n📁 Procesando directorio: {directory_path}")
    
    if not os.path.exists(directory_path):
        print(f"❌ Directorio no existe: {directory_path}")
        return
    
    # Obtener todos los archivos
    files = []
    for file_path in Path(directory_path).iterdir():
        if file_path.is_file():
            # Verificar extensión
            if file_path.suffix.lower() in ALLOWED_EXTENSIONS:
                files.append(file_path)
    
    print(f"📊 Encontrados {len(files)} archivos para subir")
    
    # Subir archivos en lotes para no sobrecargar el servidor
    async with aiohttp.ClientSession() as session:
        success_count = 0
        error_count = 0
        
        for i, file_path in enumerate(files, 1):
            print(f"[{i}/{len(files)}] Subiendo: {file_path.name}")
            
            success = await upload_file(session, str(file_path))
            if success:
                success_count += 1
            else:
                error_count += 1
            
            # Pequeña pausa entre archivos
            await asyncio.sleep(0.1)
        
        print(f"\n📈 Resumen del directorio:")
        print(f"   ✅ Exitosos: {success_count}")
        print(f"   ❌ Errores: {error_count}")
        print(f"   📊 Total: {len(files)}")

async def main():
    """Función principal"""
    print("🚀 Iniciando subida de archivos a DocuMind")
    print(f"🌐 API URL: {UPLOAD_ENDPOINT}")
    
    # Verificar que el servidor está disponible
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE_URL}/health") as response:
                if response.status != 200:
                    print("❌ El servidor DocuMind no está disponible")
                    print("   Asegúrate de que el servidor esté corriendo:")
                    print("   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
                    return
                else:
                    print("✅ Servidor DocuMind disponible")
    except Exception as e:
        print(f"❌ Error conectando al servidor: {e}")
        return
    
    # Procesar cada directorio
    total_files = 0
    for directory in DIRECTORIOS:
        if os.path.exists(directory):
            file_count = len([f for f in os.listdir(directory) 
                           if os.path.isfile(os.path.join(directory, f))])
            total_files += file_count
    
    print(f"\n📊 Total de archivos a procesar: {total_files}")
    print("=" * 60)
    
    # Subir archivos de cada directorio
    for directory in DIRECTORIOS:
        await upload_directory(directory)
    
    print("\n🎉 Proceso de subida completado!")

if __name__ == "__main__":
    asyncio.run(main())
