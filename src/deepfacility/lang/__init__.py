import importlib
import os

from deepfacility.lang.helpers import locale_language, request_language

# Load the translation model
translation_model = os.environ.get('DEEPFACILITY_LANG_MODEL', "NLP")
if importlib.util.find_spec('torchvision'):
    # If PyTorch is installed use the ML model
    if translation_model == "NLLB":
        from deepfacility.lang.translator_i18n import TranslatorI18N as Translator
    elif translation_model == "NLP":
        from deepfacility.lang.translator_i18n_nlp import TranslatorI18N_NLP as Translator
else:  
    # Otherwise use the default model
    from deepfacility.lang.translator_default import DefaultTranslator as Translator


