# app/services/document_processor.py
import io
import os
from typing import Tuple
from PyPDF2 import PdfReader
from docx import Document as DocxDocument
from bs4 import BeautifulSoup
import markdown


class DocumentProcessor:
    """Procesa diferentes formatos de documento y extrae texto"""

    @staticmethod
    async def process_pdf(content: bytes) -> Tuple[str, dict]:
        """Extrae texto de un PDF"""
        try:
            pdf_file = io.BytesIO(content)
            reader = PdfReader(pdf_file)

            text = ""
            metadata = {
                "pages": len(reader.pages),
                "author": reader.metadata.author if reader.metadata else None,
                "title": reader.metadata.title if reader.metadata else None
            }

            for page_num, page in enumerate(reader.pages, 1):
                page_text = page.extract_text()
                text += f"\n--- Página {page_num} ---\n{page_text}"

            return text, metadata
        except Exception as e:
            raise ValueError(f"Error procesando PDF: {str(e)}")

    @staticmethod
    async def process_docx(content: bytes) -> Tuple[str, dict]:
        """Extrae texto de un archivo Word (.docx)"""
        try:
            doc_file = io.BytesIO(content)
            doc = DocxDocument(doc_file)

            text = ""
            metadata = {
                "paragraphs": len(doc.paragraphs),
                "sections": len(doc.sections)
            }

            for para in doc.paragraphs:
                if para.text.strip():
                    text += para.text + "\n"

            # También extraer texto de tablas
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            text += cell.text + "\n"

            return text, metadata
        except Exception as e:
            raise ValueError(f"Error procesando Word: {str(e)}")

    @staticmethod
    async def process_html(content: bytes) -> Tuple[str, dict]:
        """Extrae texto de un archivo HTML"""
        try:
            html_content = content.decode('utf-8')
            soup = BeautifulSoup(html_content, 'html.parser')

            # Eliminar scripts y estilos
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()

            metadata = {
                "title": soup.title.string if soup.title else None,
                "links_count": len(soup.find_all('a')),
                "images_count": len(soup.find_all('img'))
            }

            # Extraer texto de body o del documento completo
            body = soup.body if soup.body else soup
            text = body.get_text(separator='\n', strip=True)

            # Limpiar líneas vacías múltiples
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            text = '\n'.join(lines)

            return text, metadata
        except Exception as e:
            raise ValueError(f"Error procesando HTML: {str(e)}")

    @staticmethod
    async def process_markdown(content: bytes) -> Tuple[str, dict]:
        """Convierte Markdown a texto plano"""
        try:
            md_content = content.decode('utf-8')

            # Convertir markdown a HTML y luego a texto
            html = markdown.markdown(md_content)
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text(separator='\n', strip=True)

            metadata = {
                "original_length": len(md_content),
                "words": len(md_content.split())
            }

            return text, metadata
        except Exception as e:
            raise ValueError(f"Error procesando Markdown: {str(e)}")

    @staticmethod
    async def process_text(content: bytes) -> Tuple[str, dict]:
        """Procesa texto plano"""
        try:
            text = content.decode('utf-8')
            metadata = {
                "lines": len(text.split('\n')),
                "words": len(text.split())
            }
            return text, metadata
        except UnicodeDecodeError:
            # Intentar con latin-1 si UTF-8 falla
            text = content.decode('latin-1')
            metadata = {"encoding": "latin-1"}
            return text, metadata

    @staticmethod
    async def process_document(content: bytes, content_type: str) -> Tuple[str, dict]:
        """Ruta principal que distribuye según el tipo de archivo"""

        processors = {
            "application/pdf": DocumentProcessor.process_pdf,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocumentProcessor.process_docx,
            "text/html": DocumentProcessor.process_html,
            "text/markdown": DocumentProcessor.process_markdown,
            "text/plain": DocumentProcessor.process_text,
            "application/msword": DocumentProcessor.process_docx,  # .doc (antiguo) - puede tener limitaciones
        }

        # Normalizar content_type (algunos navegadores envían cosas diferentes)
        if "pdf" in content_type:
            content_type = "application/pdf"
        elif "word" in content_type or "document" in content_type:
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif "html" in content_type:
            content_type = "text/html"
        elif "markdown" in content_type or "md" in content_type:
            content_type = "text/markdown"

        processor = processors.get(content_type)

        if not processor:
            raise ValueError(f"Tipo de archivo no soportado: {content_type}")

        return await processor(content)