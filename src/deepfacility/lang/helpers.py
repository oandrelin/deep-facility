import json
import locale

from fastapi import Request
from pathlib import Path


def code_from_locale(locale_str: str):
    """Get the language code from the locale string."""
    return locale_str[:2].lower()


def locale_language():
    """Get the language code from the locale."""
    return code_from_locale(locale.getlocale()[0])
    

def request_language(request: Request):
    """Get the language code from the http request."""
    try:
        if request:
            locale_str = request.headers.get("accept-language", "en").split(",")[0]
        else:
            locale_str = ""
    except Exception as e:
        locale_str = ""

    return code_from_locale(locale_str)


def get_language(request: Request = None):
    """Get the language code."""
    return request_language(request) or locale_language()


def get_supported_languages() -> list[tuple]:
    """Get the list of supported languages."""

    # Path to your JSON file
    filename = Path(__file__).parent / "languages.json"

    # Open the file in read mode
    with open(filename, "r", encoding="utf-8") as f:
        # Load the JSON data
        data = json.load(f)

    langs = [tuple(t) for t in data['langs']]

    return langs

