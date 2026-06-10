"""Tests de la redaction RGPD - verifie que les credentials hardcodes
sont remplaces par [REDACTED] avant envoi au LLM.

Couverture :
- nominal: .fill("#password", ...) + variable PASSWORD = "..."
- locator chains: get_by_label / get_by_placeholder + .fill(...)
- TODO (xfail): nested quotes from Playwright codegen
- TODO (xfail): Page Object Model (locator declared as class attr, .fill elsewhere)
"""
import pytest
from playwright.sync_api import Page

from qa_autopilot import redact_source


# Hardcode volontaire pour tester que redact_source() le redacte
PASSWORD = "MonMotDePasseSuperSecretABC123"
api_key = "sk-fakekey-XYZ789"


def test_redaction_check(page: Page):
    """Integration test : valeur tapee dans le navigateur ET hardcoded
    dans le code source doivent etre redactes."""
    page.goto("https://the-internet.herokuapp.com/login")
    page.fill("#username", "tomsmith")
    page.fill("#password", "VraiPasswordTapeDansLeNavigateur456")
    page.click("button[type='submit']")
    # Force le fail pour declencher le diagnostic
    page.click("#element_qui_existe_pas_du_tout", timeout=2000)


# --- Unit tests sur redact_source() ---

def test_fill_password_selector_redacted():
    """Pattern #1 : page.fill('#password', 'xxx') -> [REDACTED]"""
    src = 'page.fill("#password", "MyP@ss123")'
    out = redact_source(src)
    assert "MyP@ss123" not in out
    assert "[REDACTED]" in out


def test_python_variable_password_redacted():
    """Pattern #2 : PASSWORD = "xxx" -> [REDACTED]"""
    src = 'PASSWORD = "SuperSecret456"'
    out = redact_source(src)
    assert "SuperSecret456" not in out
    assert "[REDACTED]" in out


def test_get_by_label_chain_redacted():
    """Pattern #4 : get_by_label('Password').fill('xxx') -> [REDACTED]

    Style locator moderne recommande par la doc Playwright officielle.
    Tres frequent dans les tests ecrits apres 2023.
    """
    src = 'page.get_by_label("Password").fill("MyP@ss123")'
    out = redact_source(src)
    assert "MyP@ss123" not in out, f"Expected redaction, got: {out}"
    assert "[REDACTED]" in out


def test_get_by_placeholder_chain_redacted():
    """Pattern #4 : get_by_placeholder('IBAN').fill('xxx') -> [REDACTED]"""
    src = 'page.get_by_placeholder("IBAN").fill("FR761234567890")'
    out = redact_source(src)
    assert "FR761234567890" not in out, f"Expected redaction, got: {out}"
    assert "[REDACTED]" in out


# --- Cas residuel documente : TODOs trackes en xfail ---

@pytest.mark.xfail(
    reason="TODO: nested quotes from Playwright codegen — page.fill(\"[name='cvv']\", ...) "
           "currently not caught by regex (rare in human-written code, common in codegen output)"
)
def test_nested_quotes_in_selector_redacted():
    """Cas residuel : selecteur CSS avec quotes imbriquees.

    Rare en ecriture humaine, mais existe dans :
    - Output de codegen Playwright (npx playwright codegen)
    - Code copie-colle depuis du JavaScript
    """
    src = "page.fill(\"[name='cvv']\", \"123\")"
    out = redact_source(src)
    assert "123" not in out or out.count('"123"') == 0
    assert "[REDACTED]" in out


@pytest.mark.xfail(
    reason="TODO: Page Object Model — locator declared as class attribute, "
           ".fill() called elsewhere. Dominant pattern in enterprise Selenium->Playwright migrations."
)
def test_pom_locator_redacted():
    """Cas residuel : Page Object Model.

    Le selecteur est declare separement de l'appel .fill(). Pattern dominant
    dans les equipes en migration Selenium -> Playwright.
    """
    src = '''
PASSWORD_INPUT = "#password"
page.fill(PASSWORD_INPUT, "secret123")
'''
    out = redact_source(src)
    assert "secret123" not in out, f"Expected redaction, got: {out}"
    assert "[REDACTED]" in out
