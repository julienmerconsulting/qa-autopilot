"""
Exemple d'utilisation standalone de QA Autopilot
=================================================

Sans pytest, en mode script direct.

Usage :
  python examples/standalone.py
"""
from playwright.sync_api import sync_playwright
from qa_autopilot import QAInterceptor


def run_test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Brancher l'intercepteur
        interceptor = QAInterceptor(page)
        interceptor.start()

        try:
            # Ton test ici
            page.goto("https://www.lemonde.fr")
            page.click("a[href='/international/']", timeout=5000)
            print("✅ Test passé !")

        except Exception as e:
            # Diagnostic automatique
            diagnosis = interceptor.diagnose(
                error_message=str(e),
                test_file=__file__,
            )

            print(f"\n🔍 Cause : {diagnosis.get('root_cause')}")
            print(f"📂 Catégorie : {diagnosis.get('category')}")
            print(f"🎯 Confiance : {diagnosis.get('confidence', 0):.0%}")

            fix = diagnosis.get("suggested_fix", {})
            if fix.get("code"):
                print(f"\n💡 Fix suggéré :\n{fix['code']}")

        finally:
            interceptor.stop()
            browser.close()


if __name__ == "__main__":
    run_test()
