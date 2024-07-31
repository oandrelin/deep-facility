from __future__ import annotations

import json

from pathlib import Path

from deepfacility.lang.translator import BaseTranslator


class DefaultTranslator(BaseTranslator):
    """Default translator implementation."""
    
    _messages: dict = None

    def _load_messages(self):
        """Load messages from the language file."""
        self._messages = self._messages or {}
        # TODO: Make messages dir configurable to be any directory
        msg_file = Path(__file__).parent / "messages" / f"{self.language}.json"
        if msg_file.is_file():
            with open(msg_file, 'r', encoding='utf-8') as fp:
                msg_dict = json.load(fp)

            self._messages[self.language] = msg_dict
        else:
            self._messages = {}

    # API

    def set_language(self, language: str):
        """Set the current language."""
        assert language is not None, "Language must be set."
        self._language = language
        self._load_messages()

    def translate(self, msg):
        """Translate a message to the current language."""
        try:
            # If language supported and message is present set default translation
            if self.language in self._messages:
                if msg in self._messages[self.language]:
                    res = self._messages[self.language][msg]
                else:
                    res = msg  # if no translation keep the original text

                # consider status format [message][sep][status] and translate the text before the separator
                for sep in [": ", " ("]:
                    if sep in msg:
                        key, data = msg.split(sep, maxsplit=1) 
                        if key in self._messages[self.language]:
                            res = f"{self._messages[self.language][key]}{sep}{data}"  # put it back together
                    
                return res
            
            else:
                return msg

        except KeyError:
            return msg
