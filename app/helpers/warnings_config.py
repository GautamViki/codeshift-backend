import warnings
import logging


def configure_warnings():
    warnings.filterwarnings(
        "ignore",
        message="Model 'gemini-3.6-flash' uses fixed sampling defaults.*",
        category=UserWarning,
        module="langchain_google_genai.chat_models",
    )
    logging.getLogger("google_genai.models").setLevel(logging.ERROR)
    logging.getLogger("google_genai").setLevel(logging.ERROR)