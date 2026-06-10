"""Test de la redaction RGPD - doit voir [REDACTED] pas le vrai mot de passe"""
from playwright.sync_api import Page


# Hardcode volontaire pour tester que redact_source() le redacte
PASSWORD = "MonMotDePasseSuperSecretABC123"
api_key = "sk-fakekey-XYZ789"


def test_redaction_check(page: Page):
    page.goto("https://the-internet.herokuapp.com/login")
    page.fill("#username", "tomsmith")
    page.fill("#password", "VraiPasswordTapeDansLeNavigateur456")
    page.click("button[type='submit']")
    # Force le fail pour declencher le diagnostic
    page.click("#element_qui_existe_pas_du_tout", timeout=2000)