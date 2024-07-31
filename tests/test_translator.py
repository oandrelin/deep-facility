import locale
import pytest

from deepfacility.lang import translator_default as tr


@pytest.fixture
def translator():
    return tr.DefaultTranslator()


@pytest.mark.unit
def test_translator_instantiate(translator):
    lang = translator.language
    assert lang == locale.getlocale()[0].split('_')[0].lower()[:len(lang)]


@pytest.mark.unit
def test_translator_set_language(translator):
    translator.set_language("en")
    assert translator.language == "en"
    assert translator.translate("hello") == "hello"


@pytest.mark.unit
def test_translator_factory_fr():
    translator2 = tr.DefaultTranslator.create(language="fr")
    assert translator2.language == "fr"
    assert translator2.translate("hello") == "hello"
    assert translator2.translate("Yes") == "Oui"
    assert translator2.translate("Stop") == "Arrêter"


@pytest.mark.unit
def test_translator_unsupported_lang():
    translator2 = tr.DefaultTranslator.create(language="aa")
    assert translator2.language == "aa"
    assert translator2.translate("hello") == "hello"
    assert translator2.translate("Yes") == "Yes"
    assert translator2.translate("Stop") == "Stop"
