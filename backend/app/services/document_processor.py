# app/services/document_processor.py
from PyPDF2 import PdfReader
from docx import Document as DocxDocument

import re
from typing import Dict, List, Tuple


class FOPParser:
    """Parser robusto para archivos FOP"""

    @staticmethod
    def _clean_field(text: str) -> str:
        """Limpiar campos: remover espacios excesivos, caracteres especiales, acentos"""
        # Remover caracteres especiales como ! " * ? etc.
        text = re.sub(r'[!"*?\-+=\|\\]+', ' ', text)
        # Remover espacios en blanco excesivos
        text = re.sub(r'\s+', ' ', text)
        # Remover caracteres de control
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
        return text.strip()

    @staticmethod
    def parse(text: str) -> Dict[str, str]:
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        sections = {
            "command": "",
            "function": "",
            "description": "",
            "objective": "",
            "procedure": "",
            "examples": ""
        }

        buffer = []
        current = None

        for line in lines:

            # COMANDO
            if "COMANDO" in line:
                sections["command"] = FOPParser._clean_field(line.split(":")[-1])

            # FUNCION
            elif "FUNCION" in line:
                sections["function"] = FOPParser._clean_field(line.split(":")[-1])

            # DESCRIPCIÓN (línea libre posterior)
            elif "COMANDO" in line and ":" in line:
                sections["description"] += FOPParser._clean_field(line) + " "

            # OBJETIVO
            elif re.match(r"^\d+\s+OBJETIVO", line):
                current = "objective"
                buffer = []

            # PROCEDIMIENTO
            elif re.match(r"^\d+\s+PROCEDIMIENTO", line):
                sections["objective"] = FOPParser._clean_field(" ".join(buffer))
                current = "procedure"
                buffer = []

            # EJEMPLO
            elif re.match(r"^\d+\s+EJEMPLO", line):
                sections["procedure"] = FOPParser._clean_field(" ".join(buffer))
                current = "examples"
                buffer = []

            else:
                if current:
                    buffer.append(line)

        if current == "examples":
            sections["examples"] = FOPParser._clean_field(" ".join(buffer))

        return sections


class DocumentProcessor:
    """Procesador principal de documentos"""

    @staticmethod
    async def process_fop(content: bytes) -> Tuple[str, dict]:

        # 🔥 decode robusto
        text = None
        for enc in ["utf-8", "latin-1", "cp1252"]:
            try:
                text = content.decode(enc)
                break
            except:
                continue

        if not text:
            raise ValueError("No se pudo decodificar FOP")

        parser = FOPParser()
        sections = parser.parse(text)

        # 🔥 CHUNK SEMÁNTICO - Enfatizar comando y función para mejor búsqueda
        semantic = f"""COMANDO: {sections['command']}
FUNCIÓN: {sections['function']}
OBJETIVO: {sections['objective']}
DESCRIPCIÓN: {sections['description']}"""

        # 🔥 CHUNK TÉCNICO
        technical = f"""PROCEDIMIENTO:\n{sections['procedure']}"""

        # 🔥 CHUNK EJEMPLOS
        examples = f"""EJEMPLOS:\n{sections['examples']}"""

        # Crear chunks con mejor separación para mantener términos clave juntos
        full_text = "\n\n".join([semantic, technical, examples])

        metadata = {
            "type": "fop",
            "command": sections["command"],
            "function": sections["function"]
        }

        return full_text, metadata