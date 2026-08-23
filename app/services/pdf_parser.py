import io
from typing import BinaryIO, Union
from pypdf import PdfReader

class PDFParsingError(Exception):
    """Custom exception raised when PDF text extraction fails."""
    pass

def extract_text_from_pdf(pdf_file: Union[bytes, BinaryIO]) -> str:
    """
    Extract readable text from a PDF file buffer or bytes.
    Validates extracted content and handles invalid or unreadable PDFs gracefully.
    """
    try:
        if isinstance(pdf_file, bytes):
            file_stream = io.BytesIO(pdf_file)
        else:
            file_stream = pdf_file

        reader = PdfReader(file_stream)
        
        if len(reader.pages) == 0:
            raise PDFParsingError("The uploaded PDF has 0 pages.")

        extracted_pages = []
        for index, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                extracted_pages.append(page_text)

        full_text = "\n".join(extracted_pages).strip()

        # Validate that meaningful text was extracted
        if not full_text or len(full_text.strip()) < 20:
            raise PDFParsingError(
                "Could not extract meaningful text from the PDF. The file may be empty, image-scanned, or password-protected."
            )

        return full_text

    except PDFParsingError:
        raise
    except Exception as e:
        raise PDFParsingError(f"Failed to parse PDF document: {str(e)}")
