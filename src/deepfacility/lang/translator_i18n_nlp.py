from deepfacility.lang.translator_default import DefaultTranslator
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline


class TranslatorI18N_NLP(DefaultTranslator):
    """i18n NLP translator implementation."""
    tokenizer = None
    model = None
    model_name = None
    
    _supported_lang = {
        "fr": "fra_Latn"
    }

    def set_language(self, language: str):
        """Set the current language."""
        super().set_language(language=language)
        self.model_name = f"Helsinki-NLP/opus-mt-en-fr"
        self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
    
    def translate(self, msg: str):
        """Translate a message to the current language."""
        if self.language not in self._supported_lang.keys():
            return msg

        default_translated_msg = super().translate(msg)
        if msg == default_translated_msg and self.language != "en":
            batch = self.tokenizer([msg], return_tensors="pt")

            generated_ids = self.model.generate(**batch)
            translated_msg = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
            return translated_msg
        else:
            return default_translated_msg