# Changelog

## v1.2.3 (2026-04-08)

### Improved
- Enriched PyPI metadata for better discoverability:
  - Expanded keywords from 7 to 31, including all supported LLM providers (OpenAI, Anthropic, DeepSeek, Ollama, Mistral, Groq), self-healing, root-cause-analysis, and RGPD/GDPR variants
  - Expanded classifiers from 12 to 32, including AI category, Debuggers, Testing sub-topics (Acceptance/BDD/Unit), Web Environment, and Natural Language declarations
  - Enriched description: now highlights multi-LLM, RGPD-friendly, and open source positioning
  - Added project URLs: Changelog, Source Code, Bug Tracker
  - Bumped Development Status from Beta to Production/Stable
- No code changes — metadata-only release

## v1.2.2 (2026-04-08)

### 🔒 Sécurité & RGPD — Redaction par défaut
- **Redaction côté navigateur** — Le DOM listener JS détecte automatiquement les champs sensibles (`type=password`, `type=email`, `type=tel`, ou nom/id/placeholder/aria-label/autocomplete contenant `password`, `passwd`, `pwd`, `secret`, `token`, `cvv`, `card`, `ssn`, `auth`, `pin`, `api_key`, `credit`, `iban`, `bic`, `swift`, `client_secret`) et remplace la valeur par `[REDACTED]` **avant** tout stockage en localStorage. La vraie valeur ne quitte jamais le navigateur.
- **Redaction du code source** — Le fichier `.py` du test est scanné avant envoi au LLM. Les `page.fill()` / `.type()` / `.press_sequentially()` / `.input_value()` sur sélecteurs sensibles, ainsi que les variables Python (`PASSWORD = "..."`, `token = "..."`, `api_key = "..."`, `client_secret = "..."`, `access_token = "..."`, etc.) sont automatiquement redactés.
- **Warning éducatif** — Quand qa-autopilot redacte un credential hardcodé dans le source, il affiche un warning incitant à utiliser `os.environ` ou des fixtures pytest.
- **Prompt LLM mis à jour** — Le LLM est explicitement informé que `[REDACTED]` ne signifie PAS un champ vide ou cassé, mais une protection RGPD. Le diagnostic se fait sans connaître la valeur réelle.
- **Kill switch** — `QA_REDACT_INPUTS=0` pour désactiver (déconseillé, à utiliser uniquement sur des données fictives).
- **Documentation** — Nouvelle section "Sécurité & RGPD" dans le README avec tableau des données envoyées et instructions de vérification (`grep` + `mitmproxy`).

### Pourquoi ce changement ?
Tous les outils sérieux qui capturent du contexte de test en production (Sentry, Datadog, New Relic, Bugsnag) redactent par défaut les champs sensibles. C'est un standard de l'industrie, pas une option. qa-autopilot v1.2.2 s'aligne sur ce standard pour être déployable sans risque dans tout environnement enterprise (banque, santé, e-commerce avec données client réelles en staging).

## v1.0.0 (2026-02-23)

### 🚀 Initial Release
- **QAInterceptor** — Hook non-invasif sur page Playwright
- **DOM Listener** — Cascade 6 tiers avec support Shadow DOM
- **Capture réseau** — Requêtes/réponses avec filtrage automatique
- **Capture console** — Erreurs et warnings
- **Screenshots** — Optionnel, envoyé au prompt IA
- **Prompt v2** — 12 catégories de diagnostic documentées
- **JSON mode** — `response_format` OpenAI pour zéro parse error
- **Retry** — 3 tentatives sur appel IA avec nettoyage JSON
- **Plugin pytest** — Un flag `--qa-autopilot`, zéro config
- **Rapport consolidé** — `summary_*.json` par run
- **Rapports individuels** — `diag_*.json` par test en échec
- **Tickets Jira** — Génération automatique si `app_bug` détecté
- **CLI** — `python -m qa_autopilot tests/`
- **Scorecard** — 6/6 à 95% sur suite de tests pièges