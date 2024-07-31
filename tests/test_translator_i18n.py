import importlib
import pytest

has_i18n = importlib.util.find_spec('torchvision')
if has_i18n:
    from deepfacility.lang import translator_i18n as tr


@pytest.fixture
def translator():
    return tr.TranslatorI18N() if has_i18n else None


@pytest.mark.unit
@pytest.mark.skipif(not has_i18n, reason="TranslatorI18N is not available")
def test_translate_supported_language(translator):
    msg = "Life"
    translator.set_language(language="fr")
    translated_msg = translator.translate(msg)
    assert translated_msg != msg
    assert translated_msg == "La vie"


@pytest.mark.unit
@pytest.mark.skipif(not has_i18n, reason="TranslatorI18N is not available")
def test_translate_unsupported_language(translator):
    msg = "Hola"
    translator.set_language(language="es")
    translated_msg = translator.translate(msg)
    assert translated_msg == msg
