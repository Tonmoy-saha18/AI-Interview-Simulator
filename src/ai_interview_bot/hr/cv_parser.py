"""CV parsing service for extracting text and structured data from CV files."""

from __future__ import annotations

from typing import Any, Dict, Optional

try:
    import PyPDF2
    PDF2_AVAILABLE = True
except ImportError:
    PDF2_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser


class CVParser:
    """Service for parsing CV files and extracting structured information."""

    def __init__(self, llm: Optional[Any] = None) -> None:
        self.llm = llm or ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.json_parser = JsonOutputParser()

    def extract_text_from_pdf(self, file_path: str) -> str:
        text = ""

        if PDFPLUMBER_AVAILABLE:
            try:
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        text += page.extract_text() or ""
                return text.strip()
            except Exception:
                pass

        if PDF2_AVAILABLE:
            try:
                with open(file_path, "rb") as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page in pdf_reader.pages:
                        text += page.extract_text() or ""
                return text.strip()
            except Exception:
                pass

        raise ValueError(
            "Unable to extract text from PDF. Ensure pdfplumber or PyPDF2 is installed."
        )

    def extract_text_from_docx(self, file_path: str) -> str:
        if not DOCX_AVAILABLE:
            raise ValueError("python-docx is not installed. Install it to support DOCX files.")

        try:
            doc = Document(file_path)
            text_parts = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(text_parts).strip()
        except Exception as e:
            raise ValueError(f"Error extracting text from DOCX: {e!s}")

    def extract_text(self, file_path: str, file_extension: str) -> str:
        ext = file_extension.lower()

        if ext == ".pdf":
            return self.extract_text_from_pdf(file_path)
        elif ext in [".docx", ".doc"]:
            return self.extract_text_from_docx(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}. Supported formats: PDF, DOCX")

    def extract_structured_data(self, cv_text: str) -> Dict[str, Any]:
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                (
                    "You are an expert at extracting structured information from resumes/CVs. "
                    "Extract the following information from the CV text and return it as JSON:\n"
                    "- name: Candidate's full name (if available)\n"
                    "- email: Email address (if available)\n"
                    "- phone: Phone number (if available)\n"
                    "- skills: List of technical skills, programming languages, tools\n"
                    "- experience: List of work experience entries with company, role, duration, and key responsibilities\n"
                    "- education: List of educational qualifications with degree, institution, and year\n"
                    "- summary: Brief professional summary or objective (if available)\n"
                    "- years_of_experience: Estimated total years of professional experience\n"
                    "\n"
                    "Return valid JSON only. If information is not available, use null or empty arrays/lists."
                ),
            ),
            ("human", "Extract structured information from this CV:\n\n{cv_text}"),
        ])

        chain = prompt | self.llm | self.json_parser

        try:
            return chain.invoke({"cv_text": cv_text[:8000]})
        except Exception as e:
            return {
                "name": None,
                "email": None,
                "phone": None,
                "skills": [],
                "experience": [],
                "education": [],
                "summary": None,
                "years_of_experience": None,
                "raw_text": cv_text[:1000],
                "extraction_error": str(e),
            }

    def parse_cv(self, file_path: str, file_extension: str) -> Dict[str, Any]:
        cv_text = self.extract_text(file_path, file_extension)
        structured_data = self.extract_structured_data(cv_text)
        profile_summary = self._create_profile_summary(structured_data, cv_text)

        return {
            "raw_text": cv_text,
            "structured_data": structured_data,
            "profile_summary": profile_summary,
        }

    def _create_profile_summary(self, structured_data: Dict[str, Any], raw_text: str) -> str:
        parts = []

        name = structured_data.get("name")
        if name:
            parts.append(f"Name: {name}")

        years_exp = structured_data.get("years_of_experience")
        if years_exp:
            parts.append(f"Experience: {years_exp} years")

        skills = structured_data.get("skills", [])
        if skills:
            parts.append(f"Skills: {', '.join(skills[:10])}")

        experience = structured_data.get("experience", [])
        if experience:
            exp_summary = []
            for exp in experience[:3]:
                role = exp.get("role", "")
                company = exp.get("company", "")
                if role or company:
                    exp_summary.append(
                        f"{role} at {company}" if role and company else role or company
                    )
            if exp_summary:
                parts.append(f"Recent roles: {', '.join(exp_summary)}")

        summary = structured_data.get("summary")
        if summary:
            parts.append(f"Summary: {summary[:200]}")

        if not parts and raw_text:
            parts.append(raw_text[:500])

        return "\n".join(parts) if parts else "No profile information available."
