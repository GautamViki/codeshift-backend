import libcst as cst
import re
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import config
from app.validators.go_validator import validate_go_code
from app.services.file_writer import save_generated_go


def extract_go_code(raw_text: str) -> str:
    """Cleans backslashes and extracts raw Go code starting from `package`."""
    text = str(raw_text).strip()

    # Safely replace literal escaped backslash sequences without using unicode_escape
    # Fixes single-line code blocks where \\n was returned instead of true newlines
    if "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n").replace("\\t", "\t")

    # Locate the start of the Go package declaration
    package_match = re.search(r'\bpackage\s+\w+', text)
    if package_match:
        text = text[package_match.start():]

    # Strip trailing markdown code block closures (e.g., ```)
    text = re.sub(r'```.*$', '', text, flags=re.DOTALL).strip()
    return text


class CodeTranspilerService:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3.6-flash",
            temperature=0.0,
            api_key=config.GOOGLE_API_KEY,
        )

    def python_to_go(self, py_code: str, base_name: str = "output") -> dict:
        # Step 1: Validate input Python syntax using CST
        try:
            cst.parse_module(py_code)
        except Exception as e:
            return {"success": False, "error": f"Invalid Python input syntax: {str(e)}"}

        # Step 2: Prompt LLM with strict formatting rules
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert compiler engineer. Convert Python code to idiomatic Go code.\n"
                       "IMPORTANT RULES:\n"
                       "1. Output MUST start immediately with 'package main'.\n"
                       "2. Do NOT wrap the output in markdown code blocks or backticks.\n"
                       "3. Do NOT add introductory or concluding text.\n"
                       "4. Use standard Go double-quoted strings or raw backticks. Do NOT use single quotes for multi-character strings.\n"
                       "5. Include explicit error handling (if err != nil) and necessary imports."),
            ("user", "{code}")
        ])

        chain = prompt | self.llm

        response = chain.invoke({"code": py_code})
        content = self.extract_text_from_response(response)
        raw_output = content.strip()
        generated_go = extract_go_code(raw_output)

        is_valid, message = validate_go_code(generated_go)

        saved_path = None
        if is_valid:
            saved_path = str(save_generated_go(generated_go, base_name))

        return {
            "success": is_valid,
            "transpiled_code": generated_go,
            "validation_message": message,
            "saved_path": saved_path,
        }

    def extract_text_from_response(self, response) -> str:
        content = response.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    parts.append(block)
            return "".join(parts)
        return str(content)