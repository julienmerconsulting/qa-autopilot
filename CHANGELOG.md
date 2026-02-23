# Changelog

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
