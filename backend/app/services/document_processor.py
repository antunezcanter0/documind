# app/services/document_processor.py
from PyPDF2 import PdfReader
from docx import Document as DocxDocument

import re
from typing import Dict, List, Tuple


class FOPParser:
    """Parser robusto para archivos FOP"""

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
                sections["command"] = line.split(":")[-1].strip()

            # FUNCION
            elif "FUNCION" in line:
                sections["function"] = line.split(":")[-1].strip()

            # DESCRIPCIÓN (línea libre posterior)
            elif "COMANDO" in line and ":" in line:
                sections["description"] += line + " "

            # OBJETIVO
            elif re.match(r"^\d+\s+OBJETIVO", line):
                current = "objective"
                buffer = []

            # PROCEDIMIENTO
            elif re.match(r"^\d+\s+PROCEDIMIENTO", line):
                sections["objective"] = " ".join(buffer).strip()
                current = "procedure"
                buffer = []

            # EJEMPLO
            elif re.match(r"^\d+\s+EJEMPLO", line):
                sections["procedure"] = " ".join(buffer).strip()
                current = "examples"
                buffer = []

            else:
                if current:
                    buffer.append(line)

        if current == "examples":
            sections["examples"] = " ".join(buffer).strip()

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

        def clean(x):
            return re.sub(r'\s+', ' ', x).strip().lower()

        # 🔥 CHUNK SEMÁNTICO
        semantic = f"""
            COMANDO: {sections['command']}
            FUNCIÓN: {sections['function']}
            DESCRIPCIÓN: {sections['description']}
            OBJETIVO: {sections['objective']}
        """

        # 🔥 CHUNK TÉCNICO
        technical = f"""
            PROCEDIMIENTO:
            {sections['procedure']}
        """

        # 🔥 CHUNK EJEMPLOS
        examples = f"""
            EJEMPLOS:
            {sections['examples']}
        """

        full_text = "\n\n".join([semantic, technical, examples])

        metadata = {
            "type": "fop",
            "command": sections["command"],
            "function": sections["function"]
        }

        return full_text, metadata