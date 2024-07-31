from deepfacility.lang.translator_default import DefaultTranslator
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline


class TranslatorI18N(DefaultTranslator):
    """i18n NLLB translator implementation."""
    tokenizer = None
    model = None
    model_name = None
    
    _supported_lang = {
        "en": "eng_Latn",
        "fr": "fra_Latn"
    }

    def set_language(self, language: str):
        """Set the current language."""
        super().set_language(language=language)
        self.model_name = f"facebook/nllb-200-distilled-600M"
        self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
    
    def translate(self, msg: str):
        """Translate a message to the current language."""
        if self.language not in self._supported_lang.keys():
            return msg

        default_translated_msg = super().translate(msg)
        if msg == default_translated_msg and self.language != "en":
            translator = pipeline('translation',
                                  model=self.model,
                                  tokenizer=self.tokenizer,
                                  src_lang=self._supported_lang["en"],
                                  tgt_lang=self._supported_lang[self.language],
                                  max_length=400)
            output = translator(msg)
            translated_msg = output[0]['translation_text']
            return translated_msg
        else:
            return default_translated_msg
