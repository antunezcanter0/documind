# app/services/embedding_service.py

import asyncio

from openai import AsyncOpenAI
from app.core.config import settings
from app.core.cache import cache_manager
from typing import List
import tiktoken


class EmbeddingService:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.OPENAI_BASE_URL,
            api_key=settings.OPENAI_API_KEY,
            timeout=120.0,  # ← Aumentar timeout a 120 segundos
            max_retries=3  # ← Reintentar automáticamente
        )
        self.model = settings.EMBEDDING_MODEL
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    async def get_embedding(self, text: str) -> List[float]:
        """Obtener embedding simplificado sin procesamiento de lotes para una sola query"""
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=[text]
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"❌ Error rápido en embedding: {e}")
            raise

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Obtener embeddings para múltiples textos en batch"""
        try:
            # Procesar en lotes para no saturar la API
            batch_size = 10
            all_embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=batch
                )
                embeddings = [data.embedding for data in response.data]
                all_embeddings.extend(embeddings)
            
            return all_embeddings
        except Exception as e:
            print(f"❌ Error en batch embeddings: {e}")
            raise

    def chunk_text(self, text: str, chunk_size: int = 1200, overlap: int = 200):
        tokens = self.tokenizer.encode(text)

        chunks = []
        step = chunk_size - overlap

        for i in range(0, len(tokens), step):
            chunk_tokens = tokens[i:i + chunk_size]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)

        return chunks

    def _extract_code_variations(self, code: str) -> List[str]:
        """Extrae variaciones de un código de comando (ABOCR-01 -> [ABOCR-01, ABOCR, ABOCR01])"""
        variations = [code]
        if '-' in code:
            base, variant = code.split('-')
            variations.extend([base, base + variant])
        variations.append(code.replace('-', ''))
        return variations

    def _extract_filename_code(self, filename: str) -> str:
        """Extrae código de comando del nombre del archivo (FABOCR01 -> ABOCR-01)"""
        if not filename.endswith('.fop'):
            return ""
        
        base_name = filename.replace('.fop', '').upper()
        if len(base_name) < 6:
            return ""
        
        letters = ''.join([c for c in base_name if c.isalpha()])
        numbers = ''.join([c for c in base_name if c.isdigit()])
        
        if not (letters and numbers):
            return ""
        
        # Quitar prefijo inicial (FABOCR01 -> ABOCR01)
        command_base = letters[1:] if letters else letters
        variant = numbers[:2] if len(numbers) >= 2 else numbers
        
        filename_code = f"{command_base}-{variant}"
        print(f"  📋 CÓDIGO de archivo: {filename_code} (comando: {command_base}, variante: {variant})")
        return filename_code

    def chunk_fop_text(self, content: str, filename: str) -> List[str]:
        """Chunking especializado para archivos FOP que preserva la estructura de comandos"""
        chunks = []
        print(f"🔧 chunk_fop_text: Procesando {filename}")
        
        try:
            # Limpiar contenido de caracteres problemáticos
            content = content.replace('\x00', '').replace('\x0b', '').replace('\x0c', '')
            lines = content.split('\n')

            # EXTRACCIÓN ÚNICA DE INFORMACIÓN (una sola pasada por líneas)
            command_name = ""
            command_code = ""
            function_name = ""
            sections = []
            current_section = ""
            current_title = ""
            
            import re
            
            for line in lines:
                line_clean = line.strip()
                
                # Extraer metadata del header
                if 'COMANDO' in line_clean:
                    parts = line_clean.split(':')
                    if len(parts) > 1:
                        command_name = parts[1].strip()
                        print(f"  📋 COMANDO encontrado: {command_name}")
                elif 'FUNCION' in line_clean:
                    parts = line_clean.split(':')
                    if len(parts) > 1:
                        function_name = parts[1].strip()
                        print(f"  📋 FUNCIÓN encontrada: {function_name}")
                elif line_clean and '-' in line_clean and any(char.isdigit() for char in line_clean):
                    # Buscar patrones de código: ABOCR-01, ACHCR-01, etc.
                    match = re.search(r'([A-Z]{3,6}-\d{2})', line_clean)
                    if match and not command_code:
                        command_code = match.group(1)
                        print(f"  📋 CÓDIGO encontrado: {command_code}")
                
                # Extraer secciones numeradas (1 OBJETIVO, 2 ADVERTENCIA, etc.)
                if line_clean and line_clean[0].isdigit() and ' ' in line_clean:
                    # Guardar sección anterior
                    if current_section.strip():
                        sections.append({
                            'title': current_title,
                            'content': current_section.strip()
                        })
                    current_title = line_clean
                    current_section = ""
                elif line_clean and not line_clean.startswith(('?', '+', '!')):
                    current_section += line_clean + "\n"
            
            # Guardar última sección
            if current_section.strip():
                sections.append({
                    'title': current_title,
                    'content': current_section.strip()
                })
            
            # Extraer código del filename
            filename_code = self._extract_filename_code(filename)
            
            # Preparar variaciones del comando (UNA SOLA VEZ)
            command_variations = set()
            
            if command_name:
                command_variations.add(command_name)
                # Sinónimos telecomunicaciones
                # telecom_synonyms = {
                #     'CREAR': ['alta', 'creación', 'nuevo', 'instalar', 'provisionar', 'agregar'],
                #     'BORRAR': ['eliminar', 'suprimir', 'baja', 'remover', 'quitar'],
                #     'MODIFICAR': ['cambiar', 'actualizar', 'editar', 'modificación', 'ajustar'],
                #     'CONSULTAR': ['ver', 'mostrar', 'listar', 'exhibir', 'consultar', 'visualizar'],
                #     'LIS.': ['listar', 'mostrar', 'visualizar', 'consultar'],
                #     'ABONADO': ['cliente', 'usuario', 'línea', 'servicio', 'suscriptor'],
                #     'LINEA': ['conexión', 'circuito', 'terminal', 'enlace'],
                #     'ENCAMINAMIENTO': ['ruta', 'dirección', 'enrutamiento', 'camino'],
                #     'MILLARES': ['grupo', 'bloque', 'conjunto', 'milla']
                # }
                
                # for key, values in telecom_synonyms.items():
                #     if key in command_name.upper():
                #         command_variations.update(values)
            
            # Agregar variaciones de códigos (ÚNICA VEZ)
            for code in [command_code, filename_code]:
                if code:
                    command_variations.update(self._extract_code_variations(code))
            
            # Agregar nombre del archivo
            if filename.endswith('.fop'):
                base_name = filename.replace('.fop', '').upper()
                command_variations.add(base_name)
                command_variations.add(base_name.replace('FA', ''))  # Quitar prefijos comunes
            
            # Definir código principal para chunks
            command_code_display = command_code or filename_code or "N/A"
            
            # Crear chunks optimizados
            def _create_fallback_chunks():
                """Fallback: chunking por párrafos cuando no hay secciones"""
                fallback = []
                paragraphs = content.split('\n\n')
                for i, para in enumerate(paragraphs):
                    para = para.strip()
                    if para and len(para) > 30:
                        chunk = f"CÓDIGO DEL COMANDO: {command_code_display}\nDESCRIPCIÓN: {command_name}\nFUNCIÓN: {function_name}\nARCHIVO: {filename}\n\nParte {i+1}\n{para}"
                        fallback.append(chunk)
                return fallback
            
            if sections:
                # Crear chunk de metadata única
                variations_str = " | ".join(sorted(command_variations)) if command_variations else ""
                metadata_chunk = f"CÓDIGO DEL COMANDO: {command_code_display}\nDESCRIPCIÓN: {command_name}\nFUNCIÓN: {function_name}\nARCHIVO: {filename}\nVARIACIONES: {variations_str}"
                chunks.append(metadata_chunk)
                
                # Un chunk por sección (sin repetir metadatos)
                for section in sections:
                    if section['content']:
                        chunk = f"CÓDIGO DEL COMANDO: {command_code_display}\nDESCRIPCIÓN: {command_name}\n\n{section['title']}\n{section['content']}"
                        chunks.append(chunk)
            else:
                # Sin secciones: usar fallback
                chunks = _create_fallback_chunks()
                        
        except Exception as e:
            print(f"❌ Error en chunk_fop_text: {e}")
            # Fallback final por párrafos
            command_code_display = command_code if 'command_code' in locals() else filename_code if 'filename_code' in locals() else "N/A"
            command_name = command_name if 'command_name' in locals() else ""
            function_name = function_name if 'function_name' in locals() else ""
            paragraphs = content.split('\n\n')
            for i, para in enumerate(paragraphs):
                para = para.strip()
                if para and len(para) > 30:
                    chunks.append(f"CÓDIGO DEL COMANDO: {command_code_display}\nDESCRIPCIÓN: {command_name}\nFUNCIÓN: {function_name}\nARCHIVO: {filename}\n\nParte {i+1}\n{para}")
        
        return chunks


embedding_service = EmbeddingService()