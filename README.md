<div align="center">

# 🚀 QA Autopilot — AI Diagnostic for Playwright Test Failures

### pytest plugin — Real-time AI diagnosis of Playwright test failures
### Multi-LLM (OpenAI · Anthropic · Ollama · DeepSeek) · GDPR by default · Open source

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PyPI](https://img.shields.io/badge/PyPI-qa--autopilot-blue?style=for-the-badge&logo=pypi&logoColor=white)](https://pypi.org/project/qa-autopilot/)
[![Playwright](https://img.shields.io/badge/Playwright-Compatible-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)](https://playwright.dev)
[![LLM](https://img.shields.io/badge/LLM-OpenAI%20%7C%20DeepSeek%20%7C%20Ollama-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com)
[![pytest](https://img.shields.io/badge/pytest-Plugin-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)](https://pytest.org)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![Lines](https://img.shields.io/badge/Lines_of_Code-~600-brightgreen?style=for-the-badge)]()

<br/>

[Installation](#-installation) •
[Quick Start](#-quick-start) •
[Scorecard](#-scorecard) •
[How it works](#-how-it-works) •
[Configuration](#-configuration)

</div>

---

## 🎯 The problem

A Playwright test fails. The error message says:

```
TimeoutError: Page.click: Timeout 5000ms exceeded.
waiting for locator("a[href='/international/']")
```

The selector is correct. The element exists. **So why isn't it working?**

Because the cookie banner is covering everything. Or the element is inside an iframe. Or the DOM was reloaded via AJAX. Or the button is `disabled`. Or you used `click()` instead of `dblclick()`.

**QA Autopilot tells you the real cause in a single command.**

---

## 📊 Scorecard

Results on a suite of **7 trap tests** specifically designed to fool diagnostic tools:

| Test | Trap | AI Diagnosis | Category | Confidence |
|:-----|:------|:-------------|:----------|:---------:|
| 🫣 Cookie overlay | Element covered by banner | ✅ Cookie banner blocks the click | `element_obscured` | 🟢 95% |
| 🖼️ Invisible iframe | Element inside iframe, searched in main frame | ✅ Missing iframe context | `iframe_context` | 🟢 95% |
| 👻 Stale AJAX | Locator captured before DOM reload | ✅ Stale reference after AJAX | `stale_reference` | 🟢 95% |
| ↪️ Silent redirect | URL redirected 301/302 | ✅ Test PASSED (trap detected) | — | ✅ |
| 🚫 Disabled button | Element visible but disabled | ✅ Disabled attribute detected | `element_disabled` | 🟢 95% |
| 🔤 Unicode regex | `Zinedine` vs `Zinédine` | ✅ Regex accent mismatch | `encoding_mismatch` | 🟢 95% |
| 🫣 Double-click | Consent manager intercepts click | ✅ Overlay detected | `element_obscured` | 🟢 95% |

> **6/6 correct diagnoses at 95% confidence** — the 7th test PASSED (no diagnosis needed).

---

## ⚠️ Limitations

> [!CAUTION]
> **Tests over 200 lines:** the context sent to the AI is intentionally truncated.
> An E2E test should stay short — one scenario, one responsibility, under 50 lines.
> Beyond that, it's a design problem, not a diagnostic problem.
> Refactor your tests before looking for the cause of a failure.

## 📦 Installation

**QA Autopilot is a native Python module — available directly on PyPI:**

```bash
pip install qa-autopilot
```

That's it. No config, no server, no account. One line.

With automatic `.env` loading:

```bash
pip install qa-autopilot[dotenv]
```

Or from source:

```bash
git clone https://github.com/julienmerconsulting/qa-autopilot.git
cd qa-autopilot
pip install -e .
```

### Prerequisites

```bash
playwright install chromium
```

### `.env` configuration

Create a `.env` file at the root of your project:

```bash
# OpenAI (default)
OPENAI_API_KEY=sk-...

# Or DeepSeek
BASE_URL=https://api.deepseek.com
API_KEY=sk-...
QA_MODEL=deepseek-chat

# Or local Ollama (zero cost)
BASE_URL=http://localhost:11434/v1
API_KEY=ollama
QA_MODEL=llama3
```

---

## ⚡ Quick Start

### pytest mode (recommended)

Add a single flag to your pytest command:

```bash
pytest tests/ --qa-autopilot -v
```

That's it. Every failing test gets an automatic AI diagnosis.

### With HTML report

```bash
pytest tests/ --qa-autopilot --html=qa-reports/report.html --self-contained-html -v
```

### Standalone mode

```bash
python -m qa_autopilot tests/test_checkout.py
python -m qa_autopilot tests/test_login.py::test_auth
python -m qa_autopilot tests/ -k "checkout" --headed
```

### Direct import mode

```python
from qa_autopilot import QAInterceptor

# Inside your test
interceptor = QAInterceptor(page)
interceptor.start()

# ... your test ...

# On failure
diagnosis = interceptor.diagnose(error_message, "test_file.py")
print(diagnosis["root_cause"])
print(diagnosis["category"])
```

---

## 🔍 How it works

```
┌─────────────────────────────────────────────────────┐
│                YOUR PLAYWRIGHT TEST                  │
│                                                      │
│   page.goto("https://example.com")                  │
│   page.click("#submit")           ← FAIL            │
│   expect(page).to_have_url(...)                     │
└──────────────────────┬──────────────────────────────┘
                       │
         ┌─────────────▼─────────────┐
         │    QA AUTOPILOT HOOK      │
         │   (listens in parallel)   │
         └─────────────┬─────────────┘
                       │
    ┌──────────────────┼──────────────────┐
    ▼                  ▼                  ▼
┌────────┐      ┌──────────┐      ┌───────────┐
│  DOM   │      │ NETWORK  │      │ CONSOLE   │
│Listener│      │ Capture  │      │ Capture   │
│  (JS)  │      │ req/res  │      │ err/warn  │
└───┬────┘      └────┬─────┘      └─────┬─────┘
    │                │                   │
    └────────────────┼───────────────────┘
                     │
         ┌───────────▼───────────┐
         │   CONTEXT BUNDLE      │
         │  code + error + DOM   │
         │  + network + console  │
         │  + screenshot (opt)   │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │    ONE PROMPT → AI    │
         │   (12 categories)     │
         │   diagnosis + fix     │
         └───────────┬───────────┘
                     │
    ┌────────────────┼────────────────┐
    ▼                ▼                ▼
┌────────┐    ┌───────────┐    ┌──────────┐
│Terminal│    │   JSON    │    │  Jira    │
│ Output │    │  Report   │    │ (if bug) │
└────────┘    └───────────┘    └──────────┘
```

### 5-step pipeline

1. **Transparent hook** — Plugs into the Playwright page via native events
2. **Parallel capture** — DOM (injected JS listener), network, console, screenshots
3. **Failure detection** — The pytest hook intercepts the `FAILED` status
4. **Bundle + Prompt** — All context goes out in ONE AI call
5. **Diagnosis** — Root cause + category + concrete fix + JSON report

---

## 🏷️ The 12 diagnosis categories

| Icon | Category | Description |
|:----:|:---------|:------------|
| 🎯 | `wrong_selector` | Broken, missing, or too-broad selector |
| ⏭️ | `missing_step` | Missing step (cookies, goto, dropdown) |
| ⏱️ | `timing` | Race condition, element not ready yet |
| 🫣 | `element_obscured` | Element covered by overlay/modal/banner |
| 🚫 | `element_disabled` | Element found but disabled |
| 🔀 | `wrong_action` | Wrong method (click vs dblclick, fill vs type) |
| 🖼️ | `iframe_context` | Element searched in the wrong frame |
| 🔤 | `encoding_mismatch` | Unicode/accent/regex issue |
| 👻 | `stale_reference` | Stale locator after DOM change |
| 📊 | `test_data` | Assertion with wrong expected value |
| 🐛 | `app_bug` | Application bug (not the test) → generates a Jira ticket |
| 🌐 | `network` | Failed network requests (4xx/5xx) |

---

## ⚙️ Configuration

### Environment variables

| Variable | Default | Description |
|:---------|:--------|:------------|
| `OPENAI_API_KEY` | *(required if no API_KEY)* | OpenAI API key |
| `API_KEY` | *(optional)* | Key for alternative provider (DeepSeek, Ollama…) |
| `BASE_URL` | `None` (native OpenAI) | LLM provider base URL |
| `QA_MODEL` | `gpt-4.1-mini` | AI model to use |
| `QA_SCREENSHOT` | `0` | `1` to include screenshots in the prompt |
| `QA_REPORT_DIR` | `qa-reports/` | Reports directory |
| `QA_REDACT_INPUTS` | `1` | Auto-redaction of sensitive fields (password, credit card, tokens, IBAN…). `0` to disable (not recommended). |

### pytest arguments

```bash
pytest tests/ --qa-autopilot          # Enable AI diagnosis
pytest tests/ --qa-autopilot --headed # With visible browser
pytest tests/ --qa-autopilot -k "login" # Filter by keyword
```

---

## 📁 Report structure

```
qa-reports/
├── summary_20260223_014751.json          # Consolidated run report
├── diag_test_broken_20260223_014713.json # Individual diagnosis
├── diag_test_broken_20260223_014659.json
├── jira_test_broken_20260223_014659.md   # Jira ticket (if app_bug)
└── report.html                           # pytest HTML report
```

### Consolidated report example

```json
[
  {
    "test": "test_element_covered_by_overlay[chromium]",
    "category": "element_obscured",
    "confidence": 0.95,
    "root_cause": "The target element is covered by the cookie banner",
    "suggested_fix": "Close the cookie banner before clicking"
  }
]
```

---

## 🔒 Security & GDPR

QA Autopilot **automatically** redacts sensitive data before any LLM call. This protection is **enabled by default** (`QA_REDACT_INPUTS=1`) and operates on **two fronts**:

### 1. Browser-side redaction (DOM listener)

Values typed into sensitive fields are intercepted **inside the browser**, in the `saveEntry()` function of the JS listener, and replaced with `[REDACTED]` **before** any storage. The real value never leaves the browser.

| Detection criteria | Examples |
|:-------------------|:---------|
| HTML `type` | `password`, `email`, `tel` |
| `name`/`id` contains | `password`, `passwd`, `pwd`, `secret`, `token`, `cvv`, `card`, `ssn`, `auth`, `pin`, `api_key`, `credit`, `iban`, `bic`, `swift`, `client_secret` |
| `placeholder` / `aria-label` contains | same patterns |
| `autocomplete` | `current-password`, `new-password`, `cc-*` (credit card) |

### 2. Source code redaction (before LLM call)

The test `.py` file is also scanned and hardcoded credentials are redacted:

- `page.fill("#password", "...")` / `.type()` / `.press_sequentially()` / `.input_value()` on sensitive selectors
- Python variables: `password = "..."`, `token = "..."`, `api_key = "..."`, `client_secret = "..."`, `access_token = "..."`, etc.
- `os.environ["PASSWORD"] = "..."` (direct assignment)

When a redaction is applied, qa-autopilot prints a warning:

```
⚠️  Hardcoded credentials detected in test_login.py, redacted before LLM call.
    Best practice: use os.environ or pytest fixtures for secrets.
```

### What does the LLM see?

```
CAPTURED DOM ACTIONS (3 total)
  1. INPUT ✅ #username = 'john.doe@example.com'
  2. INPUT ✅ #password = [REDACTED — sensitive field]
  3. CLICK ✅ button[type="submit"] (text: 'Login')

TEST CODE
def test_login(page):
    page.fill("#username", "john.doe@example.com")
    page.fill("#password", "[REDACTED]")
    page.click("button[type='submit']")
```

The LLM is explicitly informed in the prompt that `[REDACTED]` does **not** mean an empty or broken field, but a GDPR protection. The diagnosis is performed without knowing the real value.

### How to verify redaction works?

```bash
# Run a test that types a password
pytest tests/test_login.py --qa-autopilot

# Check the JSON report — you should see [REDACTED] everywhere
grep -i "password\|REDACTED" qa-reports/diag_*.json
```

For the ultra-paranoid: intercept outgoing traffic with `mitmproxy` and verify that requests to `api.openai.com` never contain your real sensitive value.

### Data sent to the LLM

| Data | Sent | Redactable |
|:-----|:----:|:----------:|
| Test source code (3000 chars max) | ✅ | ✅ **by default** (regex on fill/assign/env) |
| Playwright error message | ✅ | ❌ |
| Element selectors | ✅ | ❌ |
| Input values (DOM listener) | ✅ | ✅ **by default** (6-criteria cascade) |
| Page URL | ✅ | ❌ |
| Console errors | ✅ | ❌ |
| 4xx/5xx request bodies (truncated) | ✅ | ❌ |
| Screenshots | only if `QA_SCREENSHOT=1` | n/a |

### Disabling redaction (not recommended)

For the rare cases where the content of a "sensitive" field is legitimately useful to see (false positive on a field name containing `auth` but not actually authentication-related):

```bash
QA_REDACT_INPUTS=0 pytest tests/ --qa-autopilot
```

> ⚠️ **Use only with fictional test data.** When in doubt, keep redaction enabled. Redaction is not an excuse to hardcode credentials: it doesn't catch every exotic case (variables with invented names, concatenated values, etc.). The golden rule remains: **never hardcode secrets**.

---

## 🏗️ Architecture

```
qa-autopilot/
├── qa_autopilot/
│   ├── __init__.py          # Public exports
│   ├── core.py              # QAInterceptor + capture
│   ├── prompt.py            # Prompt v2 (12 categories)
│   ├── diagnose.py          # AI call + retry + JSON mode
│   ├── reporter.py          # JSON + Jira markdown reports
│   ├── listener.js          # DOM listener (browser injection)
│   └── plugin.py            # pytest hooks
├── tests/
│   ├── test_traps.py        # Trap test suite
│   └── conftest.py
├── examples/
│   └── standalone.py        # Direct usage example
├── pyproject.toml
├── LICENSE
└── README.md
```

> **Note:** The current version is a monolithic `qa_autopilot.py` file (~600 lines).
> The structure above is the target for v2.

---

## 🆚 Why not the alternatives?

| | QA Autopilot | Playwright MCP (23K lines) | SaaS (Testim, Mabl...) |
|:--|:--|:--|:--|
| **Lines of code** | ~600 | 23,000+ | Closed |
| **Installation** | `pip install` | MCP server + config | Account + license |
| **Config** | 1 flag | 32 MCP tools | Dashboard + integration |
| **Price** | Free + OpenAI key | Free | $200-500/month/user |
| **Diagnosis** | 12 categories, 95% | Basic | Variable |
| **Vendor lock-in** | None | MCP protocol | Total |

---

## 🛠️ DOM Listener — 6-tier cascade

The JavaScript listener injected into the browser uses a 6-level selector cascade, from most stable to least stable:

| Tier | Strategy | Example |
|:----:|:---------|:--------|
| 1 | `data-testid` / `id` / `name` | `[data-testid="submit-btn"]` |
| 2 | `aria-label` / `placeholder` / `title` | `[aria-label="Close"]` |
| 3 | `href` (links) | `a[href="/checkout"]` |
| 4 | Parent with stable attribute | `[data-testid="form"] button` |
| 5 | Associated label (inputs) | `//label[contains(text(),"Email")]//input` |
| 6 | Short CSS + `nth-of-type` | `button.primary:nth-of-type(2)` |

Every selector is validated for uniqueness in the DOM. Shadow DOM support included.

---

## 🤝 Contributors

| Contributor | Contribution |
|:------------|:-------------|
| [Julien Mer](https://github.com/julienmerconsulting) | Original author |
| [@szwnba](https://github.com/szwnba) | Multi-provider LLM support (DeepSeek, Ollama) + CN translation |

Contributions are welcome — issues, bug reports, pull requests.

---

<sub>**Tags:** pytest plugin · playwright · playwright-python · ai testing · llm · openai · anthropic · deepseek · ollama · mistral · groq · self-healing tests · root cause analysis · test debugging · qa automation · gdpr · rgpd · data protection · multi-llm · open source qa</sub>

---

## 📄 License

MIT — Do whatever you want with it.

---

<div align="center">

**Created by [Julien Mer](https://www.linkedin.com/in/julienmer/) — JMer Consulting**

*QA Architect · 20+ years experience · Katalon Top Partner Europe*

[![Newsletter](https://img.shields.io/badge/Newsletter-Bonnes_Pratiques_QA-blue?style=flat-square)](https://cleanqa.substack.com)
![QA OPS LAB](https://img.shields.io/badge/QA_OPS_LAB-Coming%20Soon-orange?style=flat-square)
</div>