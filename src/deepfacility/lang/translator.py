from __future__ import annotations

import logging

from requests import Request

from deepfacility.lang import helpers


class BaseTranslator:
    """Base class for a translator."""
    _language: str = helpers.locale_language()
    _all_languages: list[tuple] = None

    @property
    def language(self) -> str:
        """Get the current language."""
        return self._language
        
    @classmethod
    def create(cls, language: str = None, request: Request = None):
        """Create a translator instance."""
        language = language or helpers.get_language(request)
        translator = cls()
        translator.set_language(language)
        return translator

    @property
    def supported_languages(self) -> list[tuple]:
        """Get the list of supported languages."""
        if self._all_languages is None:
            self._all_languages = helpers.get_supported_languages()

        return self._all_languages

    ######################################################
    # API to be implemented by a subclass
    
    def set_language(self, language: str) -> BaseTranslator:
        """Initialize the translator and related objects."""
        raise NotImplementedError()

    def translate(self, msg: str) -> None:
        """Translate a message to the current language."""
        raise NotImplementedError()
    
    #
    ######################################################
    