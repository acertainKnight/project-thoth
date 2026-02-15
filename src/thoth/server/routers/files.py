"""
File upload and extraction endpoints for chat attachments.

This module provides endpoints for extracting text from PDFs to enable
inline file context in chat messages.
"""

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from loguru import logger
from pydantic import BaseModel
from pypdf import PdfReader

router = APIRouter()


class PdfExtractionResponse(BaseModel):
    """Response model for PDF text extraction."""

    filename: str
    text: str
    pages: int
    size_bytes: int


@router.post('/extract', response_model=PdfExtractionResponse)
async def extract_pdf_text(file: UploadFile) -> PdfExtractionResponse:
    """
    Extract text content from a PDF file.

    Args:
        file: Uploaded PDF file (multipart form data)

    Returns:
        Extracted text with metadata

    Raises:
        HTTPException: If file is too large, not a PDF, or extraction fails
    """
    max_size = 20 * 1024 * 1024  # 20MB

    if not file.filename:
        raise HTTPException(status_code=400, detail='No filename provided')

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400, detail='Only PDF files are supported for extraction'
        )

    try:
        contents = await file.read()
        file_size = len(contents)

        if file_size > max_size:
            raise HTTPException(
                status_code=413,
                detail=f'File too large: {file_size / 1024 / 1024:.1f}MB (max 20MB)',
            )

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(contents)
            tmp_path = Path(tmp.name)

        try:
            reader = PdfReader(str(tmp_path))
            text_pages = []

            for i, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ''
                if text.strip():
                    text_pages.append(f'## Page {i}\n\n{text.strip()}')

            extracted_text = '\n\n'.join(text_pages).strip()

            if not extracted_text:
                raise HTTPException(
                    status_code=422,
                    detail='No text could be extracted from the PDF',
                )

            logger.info(
                f'Extracted text from PDF: {file.filename} '
                f'({len(reader.pages)} pages, {len(extracted_text)} chars)'
            )

            return PdfExtractionResponse(
                filename=file.filename,
                text=extracted_text,
                pages=len(reader.pages),
                size_bytes=file_size,
            )

        finally:
            tmp_path.unlink(missing_ok=True)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Failed to extract text from PDF {file.filename}: {e}')
        raise HTTPException(
            status_code=500, detail=f'PDF extraction failed: {e}'
        ) from e
