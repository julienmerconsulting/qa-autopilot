<div align="center">

# 🚀 QA Autopilot

### Plugin pytest — Diagnostic IA des échecs Playwright en temps réel

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Playwright](https://img.shields.io/badge/Playwright-Compatible-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)](https://playwright.dev)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4.1-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com)
[![pytest](https://img.shields.io/badge/pytest-Plugin-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)](https://pytest.org)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![Lines](https://img.shields.io/badge/Lines_of_Code-~600-brightgreen?style=for-the-badge)]()

<br/>

[Installation](#-installation) •
[Quick Start](#-quick-start) •
[Scorecard](#-scorecard) •
[Comment ça marche](#-comment-ça-marche) •
[Configuration](#-configuration)

</div>

---

## 🎯 Le problème

Un test Playwright échoue. Le message d'erreur dit :

```
TimeoutError: Page.click: Timeout 5000ms exceeded.
waiting for locator("a[href='/international/']")
```

Le sélecteur est bon. L'élément existe. **Alors pourquoi ça marche pas ?**

Parce que le bandeau cookies recouvre tout. Ou parce que l'élément est dans un iframe. Ou parce que le DOM a été rechargé en AJAX. Ou parce que le bouton est `disabled`. Ou parce que tu fais un `click()` au lieu d'un `dblclick()`.

**QA Autopilot diagnostique la vraie cause en une seule commande.**

---

## 📊 Scorecard

Résultats sur une suite de **7 tests pièges** conçus pour piéger les outils de diagnostic :

| Test | Piège | Diagnostic IA | Catégorie | Confiance |
|:-----|:------|:-------------|:----------|:---------:|
| 🫣 Overlay cookies | Élément recouvert par bandeau | ✅ Bandeau cookies bloque le click | `element_obscured` | 🟢 95% |
| 🖼️ Iframe invisible | Élément dans iframe, cherché dans main frame | ✅ Contexte iframe manquant | `iframe_context` | 🟢 95% |
| 👻 Stale AJAX | Locator capturé avant rechargement DOM | ✅ Référence obsolète après AJAX | `stale_reference` | 🟢 95% |
| ↪️ Redirect silencieux | URL redirigée 301/302 | ✅ Test PASSED (piège détecté) | — | ✅ |
| 🚫 Bouton disabled | Élément visible mais disabled | ✅ Attribut disabled détecté | `element_disabled` | 🟢 95% |
| 🔤 Regex Unicode | `Zinedine` vs `Zinédine` | ✅ Mismatch accent dans regex | `encoding_mismatch` | 🟢 95% |
| 🫣 Double-click | Consent manager intercepte le click | ✅ Overlay détecté | `element_obscured` | 🟢 95% |

> **6/6 diagnostics corrects à 95% de confiance** — le 7ème test PASSED (pas de diagnostic nécessaire).

---

## ⚠️ Limitations

> [!CAUTION]
> **Tests de +200 lignes :** le contexte envoyé à l'IA est volontairement tronqué.
> Un test E2E doit rester court — un scénario, une responsabilité, moins de 50 lignes.
> Au-delà, c'est un problème de conception, pas de diagnostic.
> Refactorisez vos tests avant de chercher la cause d'un échec.

## 📦 Installation

```bash
pip install qa-autopilot
```

Ou depuis les sources :

```bash
git clone https://github.com/jmer-consulting/qa-autopilot.git
cd qa-autopilot
pip install -e .
```

### Prérequis

```bash
pip install playwright openai
playwright install chromium
```

### Variable d'environnement

```bash
export OPENAI_API_KEY=sk-...
```

---

## ⚡ Quick Start

### Mode pytest (recommandé)

Ajoute un seul flag à ta commande pytest :

```bash
pytest tests/ --qa-autopilot -v
```

C'est tout. Chaque test en échec reçoit un diagnostic IA automatique.

### Avec rapport HTML

```bash
pytest tests/ --qa-autopilot --html=qa-reports/rapport.html --self-contained-html -v
```

### Mode standalone

```bash
python -m qa_autopilot tests/test_checkout.py
python -m qa_autopilot tests/test_login.py::test_auth
python -m qa_autopilot tests/ -k "checkout" --headed
```

### Mode import direct

```python
from qa_autopilot import QAInterceptor

# Dans ton test
interceptor = QAInterceptor(page)
interceptor.start()

# ... ton test ...

# En cas d'échec
diagnosis = interceptor.diagnose(error_message, "test_file.py")
print(diagnosis["root_cause"])
print(diagnosis["category"])
```

---

## 🔍 Comment ça marche

```
┌─────────────────────────────────────────────────────┐
│                    TON TEST PLAYWRIGHT               │
│                                                      │
│   page.goto("https://example.com")                  │
│   page.click("#submit")           ← FAIL            │
│   expect(page).to_have_url(...)                     │
└──────────────────────┬──────────────────────────────┘
                       │
         ┌─────────────▼─────────────┐
         │    QA AUTOPILOT HOOK      │
         │   (écoute en parallèle)   │
         └─────────────┬─────────────┘
                       │
    ┌──────────────────┼──────────────────┐
    ▼                  ▼                  ▼
┌────────┐      ┌──────────┐      ┌───────────┐
│  DOM   │      │ RÉSEAU   │      │ CONSOLE   │
│Listener│      │ Capture  │      │ Capture   │
│  (JS)  │      │ req/res  │      │ err/warn  │
└───┬────┘      └────┬─────┘      └─────┬─────┘
    │                │                   │
    └────────────────┼───────────────────┘
                     │
         ┌───────────▼───────────┐
         │   BUNDLE CONTEXTE     │
         │  code + erreur + DOM  │
         │  + réseau + console   │
         │  + screenshot (opt)   │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │    UN PROMPT → IA     │
         │   (12 catégories)     │
         │   diagnostic + fix    │
         └───────────┬───────────┘
                     │
    ┌────────────────┼────────────────┐
    ▼                ▼                ▼
┌────────┐    ┌───────────┐    ┌──────────┐
│Terminal│    │   JSON    │    │  Jira    │
│ Output │    │  Report   │    │ (si bug) │
└────────┘    └───────────┘    └──────────┘
```

### Pipeline en 5 étapes

1. **Hook transparent** — Se branche sur la page Playwright via les events natifs
2. **Capture en parallèle** — DOM (listener JS injecté), réseau, console, screenshots
3. **Détection d'échec** — Le hook pytest intercepte le `FAILED`
4. **Bundle + Prompt** — Tout le contexte part en UN appel IA
5. **Diagnostic** — Cause racine + catégorie + fix concret + rapport JSON

---

## 🏷️ Les 12 catégories de diagnostic

| Icône | Catégorie | Description |
|:-----:|:----------|:------------|
| 🎯 | `wrong_selector` | Sélecteur cassé, inexistant ou trop large |
| ⏭️ | `missing_step` | Étape manquante (cookies, goto, dropdown) |
| ⏱️ | `timing` | Race condition, élément pas encore prêt |
| 🫣 | `element_obscured` | Élément recouvert par overlay/modal/bannière |
| 🚫 | `element_disabled` | Élément trouvé mais désactivé |
| 🔀 | `wrong_action` | Mauvaise méthode (click vs dblclick, fill vs type) |
| 🖼️ | `iframe_context` | Élément cherché dans le mauvais frame |
| 🔤 | `encoding_mismatch` | Problème Unicode/accents/regex |
| 👻 | `stale_reference` | Locator obsolète après changement DOM |
| 📊 | `test_data` | Assertion avec mauvaise valeur attendue |
| 🐛 | `app_bug` | Bug applicatif (pas le test) → génère un ticket Jira |
| 🌐 | `network` | Requêtes réseau en échec (4xx/5xx) |

---

## ⚙️ Configuration

### Variables d'environnement

| Variable | Défaut | Description |
|:---------|:-------|:------------|
| `OPENAI_API_KEY` | *(obligatoire)* | Clé API OpenAI |
| `QA_MODEL` | `gpt-4.1-mini` | Modèle IA à utiliser |
| `QA_SCREENSHOT` | `0` | `1` pour inclure les screenshots dans le prompt |
| `QA_REPORT_DIR` | `qa-reports/` | Dossier des rapports |

### Arguments pytest

```bash
pytest tests/ --qa-autopilot          # Active le diagnostic IA
pytest tests/ --qa-autopilot --headed # Avec navigateur visible
pytest tests/ --qa-autopilot -k "login" # Filtrer par keyword
```

---

## 📁 Structure des rapports

```
qa-reports/
├── summary_20260223_014751.json       # Rapport consolidé du run
├── diag_test_casse_20260223_014713.json  # Diagnostic individuel
├── diag_test_casse_20260223_014659.json
├── jira_test_casse_20260223_014659.md    # Ticket Jira (si app_bug)
└── rapport.html                          # Rapport HTML pytest
```

### Exemple de rapport consolidé

```json
[
  {
    "test": "test_element_cache_par_overlay[chromium]",
    "category": "element_obscured",
    "confidence": 0.95,
    "root_cause": "L'élément ciblé est recouvert par le bandeau cookies",
    "suggested_fix": "Fermer le bandeau cookies avant de cliquer"
  }
]
```

---

## 🏗️ Architecture

```
qa-autopilot/
├── qa_autopilot/
│   ├── __init__.py          # Exports publics
│   ├── core.py              # QAInterceptor + capture
│   ├── prompt.py            # Prompt v2 (12 catégories)
│   ├── diagnose.py          # Appel IA + retry + JSON mode
│   ├── reporter.py          # Rapports JSON + Jira markdown
│   ├── listener.js          # DOM listener (injection navigateur)
│   └── plugin.py            # Hooks pytest
├── tests/
│   ├── test_casse.py        # Suite de tests pièges
│   └── conftest.py
├── examples/
│   └── standalone.py        # Exemple d'utilisation directe
├── pyproject.toml
├── LICENSE
└── README.md
```

> **Note :** La version actuelle est un fichier monolithique `qa_autopilot.py` (~600 lignes).
> Le découpage ci-dessus est la cible pour la v2.

---

## 🆚 Pourquoi pas les alternatives ?

| | QA Autopilot | Playwright MCP (23K lignes) | SaaS (Testim, Mabl...) |
|:--|:--|:--|:--|
| **Lignes de code** | ~600 | 23 000+ | Fermé |
| **Installation** | `pip install` | MCP server + config | Compte + licence |
| **Config** | 1 flag | 32 outils MCP | Dashboard + intégration |
| **Prix** | Gratuit + clé OpenAI | Gratuit | 200-500€/mois/user |
| **Diagnostic** | 12 catégories, 95% | Basique | Variable |
| **Vendor lock-in** | Zéro | MCP protocol | Total |

---

## 🛠️ DOM Listener — Cascade 6 tiers

Le listener JavaScript injecté dans le navigateur utilise une cascade de sélecteurs en 6 niveaux, du plus stable au moins stable :

| Tier | Stratégie | Exemple |
|:----:|:----------|:--------|
| 1 | `data-testid` / `id` / `name` | `[data-testid="submit-btn"]` |
| 2 | `aria-label` / `placeholder` / `title` | `[aria-label="Fermer"]` |
| 3 | `href` (liens) | `a[href="/checkout"]` |
| 4 | Parent avec attribut stable | `[data-testid="form"] button` |
| 5 | Label associé (inputs) | `//label[contains(text(),"Email")]//input` |
| 6 | CSS court + `nth-of-type` | `button.primary:nth-of-type(2)` |

Chaque sélecteur est validé pour son unicité dans le DOM. Support Shadow DOM inclus.

---

## 📄 License

MIT — Fais-en ce que tu veux.

---

<div align="center">

**Créé par [Julien Mer](https://www.linkedin.com/in/julienmer/) — JMer Consulting**

*QA Architect · 20+ ans d'expérience · Katalon Top Partner Europe*

[![Newsletter](https://img.shields.io/badge/Newsletter-Bonnes_Pratiques_QA-blue?style=flat-square)](https://cleanqa.substack.com)
![QA OPS LAB](https://img.shields.io/badge/QA_OPS_LAB-Coming%20Soon-orange?style=flat-square)
</div>
