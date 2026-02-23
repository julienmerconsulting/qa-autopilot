"""
Tests VICIEUX — Pièges de pro
================================
Chaque test a un bug subtil et traître, le genre qui te fait
perdre 2 heures avant de comprendre. On va voir si l'IA trouve.

Lance : pytest tests/test_traps.py --qa-autopilot --headed -v
"""
from playwright.sync_api import expect, Page
import re


def test_element_cache_par_overlay(page: Page):
    """
    PIÈGE : L'élément existe dans le DOM, le sélecteur est bon,
    MAIS il est recouvert par le bandeau cookies.
    Playwright trouve l'élément, essaie de cliquer → intercept error.

    C'est le cauchemar n°1 en E2E : "mais le sélecteur est bon ?!"
    """
    page.goto("https://www.lemonde.fr")
    page.click("a[href='/international/']", timeout=5000)


def test_iframe_invisible(page: Page):
    """
    PIÈGE : Le formulaire de recherche est dans un iframe.
    Le sélecteur est correct DANS l'iframe, mais le test
    cherche dans le main frame → élément introuvable.

    Bug classique avec les widgets tiers (paiement, captcha, chat).
    """
    page.goto("https://www.w3schools.com/html/html_iframe.asp")
    page.click("text=HTML Tutorial", timeout=5000)
    iframe = page.frame_locator("iframe[src='/html/default.asp']")
    expect(page.locator(".w3-sidebar")).to_be_visible(timeout=3000)


def test_stale_element_apres_ajax(page: Page):
    """
    PIÈGE : On récupère un locator, puis une action AJAX recharge
    le DOM, et le locator pointe vers un élément qui a été remplacé.

    Race condition classique avec les SPA.
    """
    page.goto("https://fr.wikipedia.org")
    page.fill("#searchInput", "Python")

    suggestion = page.locator(".cdx-menu-item__text").first

    page.fill("#searchInput", "Java")
    page.wait_for_timeout(500)

    suggestion.click(timeout=3000)

    expect(page.locator("#firstHeading")).to_have_text("Python (langage)")


def test_navigation_redirect_silencieux(page: Page):
    """
    PIÈGE : La page fait un redirect 301/302 silencieux.
    Le test attend des éléments de la page originale,
    mais on est déjà sur une autre URL.

    Classique avec les pages de login qui redirigent.
    """
    page.goto("https://fr.wikipedia.org/wiki/Accueil")
    expect(page).to_have_url("https://fr.wikipedia.org/wiki/Accueil")


def test_element_visible_mais_disabled(page: Page):
    """
    PIÈGE : Le bouton est visible, le sélecteur est bon,
    mais il est disabled. Le click ne fait rien, et le test
    continue en pensant que l'action a réussi.
    Puis l'assertion suivante fail sans raison apparente.

    Le genre de bug où tu te dis "mais j'ai cliqué dessus ?!"
    """
    page.goto("https://www.w3schools.com/tags/tryit.asp?filename=tryhtml_button_disabled")

    result_frame = page.frame_locator("#iframeResult")

    btn = result_frame.locator("button")
    expect(btn).to_be_visible(timeout=5000)

    btn.click()

    expect(result_frame.locator("#result")).to_be_visible(timeout=3000)


def test_regex_assertion_subtile(page: Page):
    """
    PIÈGE : L'assertion utilise une regex qui semble correcte
    mais échoue à cause d'un caractère spécial Unicode
    dans le texte réel de la page.

    Cauchemar i18n / encodage.
    """
    page.goto("https://fr.wikipedia.org/wiki/Zinédine_Zidane")

    heading = page.locator("#firstHeading")
    expect(heading).to_be_visible()

    expect(heading).to_have_text(re.compile(r"^Zinedine Zidane$"))


def test_double_click_piege(page: Page):
    """
    PIÈGE : Le test fait un simple click() sur un élément
    qui nécessite un double-click pour déclencher l'action.
    Le click passe sans erreur, mais l'état attendu n'arrive jamais.

    Subtil car pas d'erreur technique.
    """
    page.goto("https://www.w3schools.com/tags/tryit.asp?filename=tryhtml5_ev_ondblclick")

    result_frame = page.frame_locator("#iframeResult")
    button = result_frame.locator("button")
    expect(button).to_be_visible(timeout=5000)

    button.click()

    expect(result_frame.locator("#demo")).to_have_text("Hello World", timeout=3000)
