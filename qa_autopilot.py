"""
QA Autopilot — L'intercepteur Playwright intelligent
=====================================================
Par Julien Mer / JMer Consulting

Remplace 23 000 lignes de MCP par ~600 lignes de Python.
Écoute en parallèle de tes tests Playwright, diagnostique
les échecs et propose le fix. Zéro MCP, zéro usine à gaz.

Pipeline :
  1. Hook transparent sur la page Playwright (events natifs)
  2. Capture en parallèle : DOM (listener JS), réseau, console, screenshots
  3. Si le test fail → bundle tout le contexte
  4. Envoie UN prompt à l'IA → diagnostic + fix
  5. Génère le rapport + patch suggéré

Usage :
  # Mode pytest (recommandé) — copier conftest_qa.py dans ton projet
  pytest tests/ --qa-autopilot

  # Mode standalone
  python qa_autopilot.py tests/test_checkout.py

  # Mode import direct
  from qa_autopilot import QAInterceptor
  interceptor = QAInterceptor(page)
  interceptor.start()
  # ... ton test ...
  interceptor.diagnose(error, "test_file.py")

Prérequis :
  pip install playwright openai
  playwright install chromium

Variables d'environnement :
  OPENAI_API_KEY=sk-...
  QA_MODEL=gpt-4.1-mini        (optionnel, défaut: gpt-4.1-mini)
  QA_SCREENSHOT=1               (optionnel, inclut le screenshot dans le prompt)
"""

import json
import os
import time
import base64
import traceback
from datetime import datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ============================================================
# CONFIGURATION
# ============================================================

LLM_MODEL = os.getenv("QA_MODEL", "gpt-4.1-mini")
INCLUDE_SCREENSHOT = os.getenv("QA_SCREENSHOT", "0") == "1"
REPORT_DIR = Path(os.getenv("QA_REPORT_DIR", "qa-reports"))
MAX_NETWORK_BODY = 2000      # chars max pour body requête/réponse
MAX_CONSOLE_ENTRIES = 50      # dernières entrées console gardées
MAX_DOM_ACTIONS = 200         # actions DOM max dans le contexte IA


# ============================================================
# DOM LISTENER JS — Injection navigateur
# (cascade sélecteurs 6 tiers + shadow DOM + scroll)
# ============================================================

DOM_LISTENER_JS = """
(function() {
    if (window.__qaListenerInstalled) return;
    window.__qaListenerInstalled = true;

    function saveEntry(entry) {
        try {
            let log = JSON.parse(localStorage.getItem('__qaLocatorLog') || '[]');
            log.push(entry);
            localStorage.setItem('__qaLocatorLog', JSON.stringify(log));
        } catch(e) {}
    }

    function isInShadowDOM(el) {
        return el.getRootNode() instanceof ShadowRoot;
    }

    function getQuickSelector(el) {
        if (!el || !el.getAttribute) return 'unknown';
        if (el.getAttribute('data-testid')) return '[data-testid="' + el.getAttribute('data-testid') + '"]';
        if (el.id && !el.id.match(/^[0-9]|react|ember|__/)) return '#' + el.id;
        if (el.getAttribute('name')) return el.tagName.toLowerCase() + '[name="' + el.getAttribute('name') + '"]';
        if (el.getAttribute('aria-label')) return '[aria-label="' + el.getAttribute('aria-label') + '"]';
        let sel = el.tagName.toLowerCase();
        if (el.className && typeof el.className === 'string') {
            let cls = el.className.trim().split(/\\s+/).filter(c => c.length > 2 && c.length < 30).slice(0, 2);
            if (cls.length) sel += '.' + cls.join('.');
        }
        return sel;
    }

    function getShadowSelector(el) {
        let chain = [];
        let current = el;
        while (current) {
            let root = current.getRootNode();
            let localSel = getQuickSelector(current);
            if (root instanceof ShadowRoot) {
                chain.unshift({selector: localSel, shadow: true});
                current = root.host;
            } else {
                chain.unshift({selector: localSel, shadow: false});
                break;
            }
        }
        let pwSel = chain.map(c => c.selector).join(' >>> ');
        let jsSel = chain.map((c, i) => {
            if (i === 0) return 'document.querySelector("' + c.selector + '")';
            return '.shadowRoot.querySelector("' + c.selector + '")';
        }).join('');
        return { strategy:'shadow', value:pwSel, inShadowDOM:true, shadowChain:chain,
                 playwrightSelector:pwSel, jsSelector:jsSel, unique:true, matchCount:1 };
    }

    function getBestSelector(el) {
        if (!el || !el.getAttribute) return {strategy:'unknown', value:'unknown', inShadowDOM:false, unique:false, matchCount:0};
        if (isInShadowDOM(el)) return getShadowSelector(el);

        let best = null, strategy = 'unknown';

        // Tier 1 : Attributs stables
        if (el.getAttribute('data-testid')) { best = '[data-testid="' + el.getAttribute('data-testid') + '"]'; strategy = 'data-testid'; }
        else if (el.id && !el.id.match(/^[0-9]|react|ember|__|:/)) { best = '#' + el.id; strategy = 'id'; }
        else if (el.getAttribute('name')) { best = el.tagName.toLowerCase() + '[name="' + el.getAttribute('name') + '"]'; strategy = 'name'; }

        // Tier 2 : Sémantique
        if (!best && el.getAttribute('aria-label')) { best = '[aria-label="' + el.getAttribute('aria-label') + '"]'; strategy = 'aria-label'; }
        if (!best && el.getAttribute('placeholder')) { best = el.tagName.toLowerCase() + '[placeholder="' + el.getAttribute('placeholder') + '"]'; strategy = 'placeholder'; }
        if (!best && el.getAttribute('title')) { best = '[title="' + el.getAttribute('title') + '"]'; strategy = 'title'; }

        // Tier 3 : Href pour les liens
        if (!best && el.tagName === 'A' && el.getAttribute('href')) {
            let href = el.getAttribute('href');
            if (href !== '#' && href !== '/' && href !== 'javascript:void(0)' && href.length < 100) { best = 'a[href="' + href + '"]'; strategy = 'href'; }
        }

        // Tier 4 : Parent avec attribut stable
        if (!best) {
            let parent = el.closest('[aria-label], [data-testid], [title]');
            if (parent && parent !== el) {
                if (parent.getAttribute('aria-label')) { best = '[aria-label="' + parent.getAttribute('aria-label') + '"]'; strategy = 'parent-aria-label'; }
                else if (parent.getAttribute('data-testid')) { best = '[data-testid="' + parent.getAttribute('data-testid') + '"]'; strategy = 'parent-data-testid'; }
                else if (parent.getAttribute('title')) { best = '[title="' + parent.getAttribute('title') + '"]'; strategy = 'parent-title'; }
            }
        }

        // Tier 5 : Label associé (inputs)
        if (!best && ['INPUT','SELECT','TEXTAREA'].includes(el.tagName)) {
            let label = el.id ? document.querySelector('label[for="' + el.id + '"]') : null;
            if (!label) label = el.closest('label');
            if (label) {
                let txt = (label.textContent || '').trim().substring(0, 40);
                if (txt) { best = '//label[contains(text(),"' + txt + '")]//input'; strategy = 'label-xpath'; }
            }
        }

        // Tier 6 : CSS court + nth-of-type
        if (!best) {
            let sel = el.tagName.toLowerCase();
            if (el.className && typeof el.className === 'string') {
                let cls = el.className.trim().split(/\\s+/).filter(c => c.length > 2 && c.length < 30 && !c.match(/active|hover|focus|open|visible|show|selected|current/)).slice(0, 2);
                if (cls.length) sel += '.' + cls.join('.');
            }
            if (el.parentElement) {
                let same = Array.from(el.parentElement.children).filter(s => s.tagName === el.tagName);
                if (same.length > 1) sel += ':nth-of-type(' + (same.indexOf(el) + 1) + ')';
            }
            best = sel; strategy = 'css-short';
        }

        // Validation unicité
        let matchCount = 0;
        try {
            if (strategy === 'label-xpath' || best.startsWith('//')) {
                matchCount = document.evaluate(best, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null).snapshotLength;
            } else { matchCount = document.querySelectorAll(best).length; }
        } catch(e) { matchCount = -1; }

        // Fallback XPath text si multi-match
        let text = (el.innerText || el.textContent || '').trim();
        if (matchCount !== 1 && text && text.length > 0 && text.length < 50 && text.indexOf('\\n') === -1) {
            let xp = '//' + el.tagName.toLowerCase() + '[contains(text(),"' + text.replace(/"/g, "'") + '")]';
            try {
                let xc = document.evaluate(xp, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null).snapshotLength;
                if (xc === 1 || (xc > 0 && xc < matchCount)) { best = xp; strategy = 'xpath-text'; matchCount = xc; }
            } catch(e) {}
        }

        return { strategy:strategy, value:best, inShadowDOM:false, unique:matchCount===1, matchCount:matchCount };
    }

    function getRealTarget(e) {
        let el = e.composedPath && e.composedPath().length > 0 ? e.composedPath()[0] : e.target;
        let tags = ['BUTTON','A','INPUT','SELECT','TEXTAREA'];
        for (let d = 0; d < 5 && el; d++) {
            if (el.id || (el.getAttribute && (el.getAttribute('data-testid') || el.getAttribute('name')))) break;
            if (tags.includes(el.tagName)) break;
            if (el.getAttribute && el.getAttribute('aria-label')) break;
            let p = el.parentElement;
            if (!p) break;
            if (tags.includes(p.tagName) || p.id || (p.getAttribute && (p.getAttribute('data-testid') || p.getAttribute('aria-label')))) { el = p; break; }
            el = p;
        }
        return el;
    }

    document.addEventListener('click', (e) => {
        let el = getRealTarget(e), sel = getBestSelector(el);
        saveEntry({ action:'click', timestamp:Date.now(), tag:el.tagName,
            text:(el.innerText||el.textContent||'').trim().substring(0,80),
            selector:sel, url:location.href, inShadowDOM:sel.inShadowDOM,
            attributes:{ id:el.id||null, name:el.getAttribute?el.getAttribute('name'):null,
                type:el.getAttribute?el.getAttribute('type'):null, href:el.getAttribute?el.getAttribute('href'):null,
                'data-testid':el.getAttribute?el.getAttribute('data-testid'):null,
                'aria-label':el.getAttribute?el.getAttribute('aria-label'):null, role:el.getAttribute?el.getAttribute('role'):null }
        });
    }, true);

    document.addEventListener('input', (e) => {
        let el = getRealTarget(e), sel = getBestSelector(el);
        saveEntry({ action:'input', timestamp:Date.now(), tag:el.tagName, value:el.value||'',
            selector:sel, url:location.href, inShadowDOM:sel.inShadowDOM,
            attributes:{ id:el.id||null, name:el.getAttribute?el.getAttribute('name'):null,
                type:el.getAttribute?el.getAttribute('type'):null, placeholder:el.getAttribute?el.getAttribute('placeholder'):null,
                'data-testid':el.getAttribute?el.getAttribute('data-testid'):null, 'aria-label':el.getAttribute?el.getAttribute('aria-label'):null }
        });
    }, true);

    let _st=null, _sy=window.scrollY;
    window.addEventListener('scroll', () => {
        if(!_st) _sy=window.scrollY;
        clearTimeout(_st);
        _st=setTimeout(()=>{ let d=window.scrollY-_sy; if(Math.abs(d)>50) saveEntry({action:'scroll',timestamp:Date.now(),tag:'WINDOW',
            direction:d>0?'down':'up',deltaY:d,scrollY:window.scrollY,
            viewport:{width:innerWidth,height:innerHeight,docHeight:document.documentElement.scrollHeight},
            url:location.href,selector:{strategy:'window',value:'window.scrollTo(0,'+window.scrollY+')',inShadowDOM:false,unique:true,matchCount:1},
            inShadowDOM:false,attributes:{}}); _st=null; },250);
    }, true);

    console.log('[QA Autopilot] Listener actif sur ' + location.href);
})();
"""


# ============================================================
# STRUCTURES DE DONNÉES
# ============================================================

@dataclass
class CapturedRequest:
    url: str
    method: str
    resource_type: str
    timestamp: float
    status: Optional[int] = None
    status_text: Optional[str] = None
    duration_ms: Optional[float] = None
    request_body: Optional[str] = None
    response_body: Optional[str] = None
    failure: Optional[str] = None

    @property
    def failed(self):
        return self.failure is not None or (self.status and self.status >= 400)


@dataclass
class CapturedConsole:
    type: str         # log, warn, error, info
    text: str
    url: Optional[str] = None
    timestamp: float = 0


@dataclass
class FailureContext:
    """Tout le contexte d'un test en échec, prêt pour l'IA"""
    test_file: str = ""
    test_source: str = ""
    error_message: str = ""
    error_traceback: str = ""
    dom_actions: list = field(default_factory=list)
    network_log: list = field(default_factory=list)
    failed_requests: list = field(default_factory=list)
    console_errors: list = field(default_factory=list)
    console_warnings: list = field(default_factory=list)
    screenshot_b64: Optional[str] = None
    page_url: str = ""
    timestamp: str = ""


# ============================================================
# INTERCEPTEUR PRINCIPAL
# ============================================================

class QAInterceptor:
    """
    Intercepteur non-invasif pour page Playwright.
    Se branche en parallèle, capture tout, diagnostique sur échec.
    """

    def __init__(self, page, config=None):
        self.page = page
        self.config = config or {}
        self._requests: dict[str, CapturedRequest] = {}  # url+method → entry
        self._console: list[CapturedConsole] = []
        self._page_errors: list[str] = []
        self._started = False
        self._start_time = 0

    def start(self):
        """Branche les listeners — appel unique après création de la page"""
        if self._started:
            return
        self._started = True
        self._start_time = time.time()

        # Injecter le DOM listener
        try:
            self.page.evaluate(DOM_LISTENER_JS)
        except Exception:
            pass  # page pas encore chargée, on injecte via add_init_script

        # Réinjecter sur chaque navigation
        self.page.context.add_init_script(DOM_LISTENER_JS)

        # Capturer le réseau
        self.page.on("request", self._on_request)
        self.page.on("response", self._on_response)
        self.page.on("requestfailed", self._on_request_failed)

        # Capturer la console
        self.page.on("console", self._on_console)
        self.page.on("pageerror", self._on_page_error)

    def stop(self):
        """Décroche les listeners proprement"""
        if not self._started:
            return
        try:
            self.page.remove_listener("request", self._on_request)
            self.page.remove_listener("response", self._on_response)
            self.page.remove_listener("requestfailed", self._on_request_failed)
            self.page.remove_listener("console", self._on_console)
            self.page.remove_listener("pageerror", self._on_page_error)
        except Exception:
            pass
        self._started = False

    # ── Event handlers ──

    def _on_request(self, request):
        key = f"{request.method}:{request.url}"
        body = None
        try:
            body = request.post_data
            if body and len(body) > MAX_NETWORK_BODY:
                body = body[:MAX_NETWORK_BODY] + "...[tronqué]"
        except Exception:
            pass
        self._requests[key] = CapturedRequest(
            url=request.url,
            method=request.method,
            resource_type=request.resource_type,
            timestamp=time.time(),
            request_body=body,
        )

    def _on_response(self, response):
        key = f"{response.request.method}:{response.request.url}"
        entry = self._requests.get(key)
        if entry:
            entry.status = response.status
            entry.status_text = response.status_text
            entry.duration_ms = (time.time() - entry.timestamp) * 1000
            # Body seulement pour les erreurs (économie mémoire)
            if response.status >= 400:
                try:
                    body = response.text()
                    if len(body) > MAX_NETWORK_BODY:
                        body = body[:MAX_NETWORK_BODY] + "...[tronqué]"
                    entry.response_body = body
                except Exception:
                    pass

    def _on_request_failed(self, request):
        key = f"{request.method}:{request.url}"
        entry = self._requests.get(key)
        if entry:
            entry.failure = request.failure
        else:
            self._requests[key] = CapturedRequest(
                url=request.url,
                method=request.method,
                resource_type=request.resource_type,
                timestamp=time.time(),
                failure=request.failure,
            )

    def _on_console(self, msg):
        if len(self._console) < MAX_CONSOLE_ENTRIES:
            self._console.append(CapturedConsole(
                type=msg.type,
                text=msg.text,
                url=msg.location.get("url", "") if hasattr(msg, "location") else "",
                timestamp=time.time(),
            ))

    def _on_page_error(self, error):
        self._page_errors.append(str(error))

    # ── Récupération des données ──

    def get_dom_log(self) -> list:
        """Récupère le log DOM depuis localStorage (injecté par le listener JS)"""
        try:
            raw = self.page.evaluate(
                "JSON.parse(localStorage.getItem('__qaLocatorLog') || '[]')"
            )
            return dedup_log(raw)
        except Exception:
            return []

    def get_network_log(self) -> list[dict]:
        """Requêtes réseau filtrées (exclut les assets statiques)"""
        skip_types = {"image", "stylesheet", "font", "media"}
        result = []
        for req in self._requests.values():
            if req.resource_type in skip_types:
                continue
            result.append(asdict(req))
        return sorted(result, key=lambda x: x.get("timestamp", 0))

    def get_failed_requests(self) -> list[dict]:
        """Uniquement les requêtes en erreur (4xx/5xx ou failure)"""
        return [asdict(r) for r in self._requests.values() if r.failed]

    def get_console_errors(self) -> list[dict]:
        """Erreurs et warnings console"""
        return [asdict(c) for c in self._console if c.type in ("error", "warning")]

    def take_screenshot(self) -> Optional[str]:
        """Screenshot base64 PNG de l'état courant"""
        try:
            buf = self.page.screenshot(type="png", full_page=False)
            return base64.b64encode(buf).decode("utf-8")
        except Exception:
            return None

    # ── Construction du contexte d'échec ──

    def build_failure_context(self, error_message: str, error_tb: str = "",
                               test_file: str = "") -> FailureContext:
        """Bundle TOUT le contexte nécessaire au diagnostic — en UN appel"""
        # Lire le source du test
        test_source = ""
        if test_file and Path(test_file).exists():
            try:
                test_source = Path(test_file).read_text(encoding="utf-8")
            except Exception:
                pass

        ctx = FailureContext(
            test_file=test_file,
            test_source=test_source,
            error_message=error_message,
            error_traceback=error_tb,
            dom_actions=self.get_dom_log()[:MAX_DOM_ACTIONS],
            network_log=self.get_network_log(),
            failed_requests=self.get_failed_requests(),
            console_errors=self.get_console_errors(),
            console_warnings=[asdict(c) for c in self._console if c.type == "warning"],
            page_url=self.page.url if self.page else "",
            timestamp=datetime.now().isoformat(),
        )

        if INCLUDE_SCREENSHOT:
            ctx.screenshot_b64 = self.take_screenshot()

        return ctx

    # ── Diagnostic IA ──

    def diagnose(self, error_message: str, test_file: str = "",
                  error_tb: str = "") -> dict:
        """Point d'entrée principal : diagnostic complet d'un échec de test"""
        ctx = self.build_failure_context(error_message, error_tb, test_file)
        diagnosis = ai_diagnose(ctx)

        # Sauvegarder le rapport
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        test_name = Path(test_file).stem if test_file else "unknown"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = REPORT_DIR / f"diag_{test_name}_{ts}.json"
        jira_file = None

        report = {
            "diagnosis": diagnosis,
            "context": {
                "test_file": ctx.test_file,
                "error_message": ctx.error_message,
                "page_url": ctx.page_url,
                "dom_actions_count": len(ctx.dom_actions),
                "network_requests_count": len(ctx.network_log),
                "failed_requests_count": len(ctx.failed_requests),
                "console_errors_count": len(ctx.console_errors),
                "timestamp": ctx.timestamp,
            },
            "dom_actions": ctx.dom_actions,
            "failed_requests": ctx.failed_requests,
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # ── Affichage diagnostic ──
        category = diagnosis.get('category', 'N/A')
        conf = diagnosis.get('confidence', 0)

        CATEGORY_ICONS = {
            "wrong_selector": "🎯", "missing_step": "⏭️", "timing": "⏱️",
            "element_obscured": "🫣", "element_disabled": "🚫", "wrong_action": "🔀",
            "iframe_context": "🖼️", "encoding_mismatch": "🔤", "stale_reference": "👻",
            "test_data": "📊", "app_bug": "🐛", "network": "🌐",
        }
        icon = CATEGORY_ICONS.get(category, "❓")

        print(f"\n{'='*60}")
        print(f"  🔍 QA AUTOPILOT — DIAGNOSTIC")
        print(f"{'='*60}")
        print(f"  Test    : {ctx.test_file}")
        print(f"  Erreur  : {ctx.error_message[:120]}")
        print(f"  Page    : {ctx.page_url}")
        print(f"  Cause   : {diagnosis.get('root_cause', 'N/A')}")
        print(f"  Type    : {icon} {category}")
        print(f"  Confiance: {'🟢' if conf > 0.7 else '🟡' if conf > 0.4 else '🔴'} {conf:.0%}")

        # ── Fix suggéré (si ce n'est pas un app_bug) ──
        if category != "app_bug":
            fix = diagnosis.get("suggested_fix", {})
            if fix.get("description"):
                print(f"\n  💡 FIX SUGGÉRÉ :")
                print(f"     {fix['description']}")
            if fix.get("code"):
                print(f"\n  📝 CODE :")
                for line in fix["code"].split("\n"):
                    print(f"     {line}")

        # ── Sélecteurs à risque ──
        risky = diagnosis.get("selectors_at_risk", [])
        if risky:
            print(f"\n  ⚠️ SÉLECTEURS FRAGILES :")
            for s in risky:
                print(f"     • {s}")

        # ── Ticket Jira (si app_bug) ──
        jira = diagnosis.get("jira_ticket")
        if jira and isinstance(jira, dict):
            jira_file = REPORT_DIR / f"jira_{test_name}_{ts}.md"
            jira_md = _build_jira_markdown(jira, ctx)
            with open(jira_file, "w", encoding="utf-8") as f:
                f.write(jira_md)

            print(f"\n  🐛 APPLICATION BUG DÉTECTÉ — Ne pas modifier le test !")
            print(f"     Titre  : {jira.get('title', 'N/A')}")
            print(f"     Priorité : {jira.get('priority', 'N/A')}")
            print(f"     Steps  : {len(jira.get('steps_to_reproduce', []))} étapes")
            print(f"\n  📋 Ticket Jira → {jira_file}")

        print(f"\n  📁 Rapport → {report_file}")
        print(f"{'='*60}\n")

        return diagnosis


# ============================================================
# GÉNÉRATEUR JIRA MARKDOWN
# ============================================================

def _build_jira_markdown(jira: dict, ctx: FailureContext) -> str:
    """Génère un ticket Jira prêt à copier-coller en Markdown"""
    steps = jira.get("steps_to_reproduce", [])
    steps_str = "\n".join(f"{s}" for s in steps) if steps else "N/A"

    return f"""# 🔴 APPLICATION BUG DETECTED — This is NOT a test issue

## {jira.get('title', '[BUG] Titre manquant')}

**Priorité :** {jira.get('priority', 'Major')}
**Environnement :** {jira.get('environment', 'Playwright + Chromium headless')}
**Test :** `{ctx.test_file}`
**Date :** {ctx.timestamp}

---

### Description

{jira.get('description', 'N/A')}

### Steps to Reproduce

{steps_str}

### Expected

{jira.get('expected', 'N/A')}

### Actual

{jira.get('actual', 'N/A')}

### Technical Details

{jira.get('technical_details', 'N/A')}

- **URL au crash :** `{ctx.page_url}`
- **Requêtes en échec :** {len(ctx.failed_requests)}
- **Erreurs console :** {len(ctx.console_errors)}

---

> ⚠️ **Ne pas modifier le test.** Le test est correct — il a détecté un vrai bug applicatif.
> Laisser le test en échec pour que la CI continue à signaler le problème.

---
*Généré automatiquement par QA Autopilot — JMer Consulting*
"""


# ============================================================
# DÉDUPLICATION (logique de Julien, éprouvée)
# ============================================================

def dedup_log(raw_log: list) -> list:
    """Déduplique : clics/scrolls gardés, inputs = dernière valeur par champ"""
    clean = []
    last_input = {}
    for entry in raw_log:
        if entry.get("action") in ("click", "scroll"):
            clean.append(entry)
        elif entry.get("action") == "input":
            key = (entry.get("selector", {}).get("value", ""), entry.get("url", ""))
            if key in last_input:
                clean[last_input[key]] = entry
            else:
                last_input[key] = len(clean)
                clean.append(entry)
    return clean


# ============================================================
# DIAGNOSTIC IA — UN prompt, UN appel, TOUT le contexte
# ============================================================

def ai_diagnose(ctx: FailureContext) -> dict:
    """Appel IA unique avec tout le contexte de l'échec — prompt v2 enrichi"""
    try:
        from openai import OpenAI
    except ImportError:
        return {"error": "pip install openai", "root_cause": "OpenAI non installé",
                "category": "setup", "confidence": 0}

    # Construire le contexte textuel
    dom_summary = ""
    if ctx.dom_actions:
        steps = []
        for i, a in enumerate(ctx.dom_actions[:30]):
            sel = a.get("selector", {}).get("value", "?")
            unique = "✅" if a.get("selector", {}).get("unique") else "⚠️"
            if a["action"] == "click":
                txt = a.get("text", "")[:40]
                steps.append(f"  {i+1}. CLICK {unique} {sel} (texte: '{txt}')")
            elif a["action"] == "input":
                steps.append(f"  {i+1}. INPUT {unique} {sel} = '{a.get('value', '')}'")
            elif a["action"] == "scroll":
                steps.append(f"  {i+1}. SCROLL {a.get('direction', '?')} {a.get('deltaY', 0)}px")
        dom_summary = "\n".join(steps)

    network_summary = ""
    if ctx.failed_requests:
        lines = []
        for r in ctx.failed_requests[:10]:
            lines.append(f"  ❌ {r.get('method', '?')} {r.get('url', '?')[:80]} → {r.get('status', '?')} {r.get('failure', '')}")
            if r.get("response_body"):
                lines.append(f"     Body: {r['response_body'][:200]}")
        network_summary = "\n".join(lines)

    console_summary = ""
    if ctx.console_errors:
        lines = [f"  🔴 {c.get('text', '')[:120]}" for c in ctx.console_errors[:10]]
        console_summary = "\n".join(lines)

    prompt = f"""Tu es un QA Engineer senior avec 20 ans d'expérience Playwright. Un test a échoué.
Diagnostique la cause racine et propose un fix concret.

═══════════════════════════════════════════════════════════════
CODE DU TEST
═══════════════════════════════════════════════════════════════
Fichier : {ctx.test_file}
```python
{ctx.test_source[:3000] if ctx.test_source else '[source non disponible]'}
```

═══════════════════════════════════════════════════════════════
ERREUR COMPLÈTE (message + call log Playwright)
═══════════════════════════════════════════════════════════════
{ctx.error_message}
{ctx.error_traceback[:1500] if ctx.error_traceback else ''}

═══════════════════════════════════════════════════════════════
URL AU MOMENT DU CRASH
═══════════════════════════════════════════════════════════════
{ctx.page_url}

═══════════════════════════════════════════════════════════════
ACTIONS DOM CAPTURÉES ({len(ctx.dom_actions)} total)
═══════════════════════════════════════════════════════════════
{dom_summary if dom_summary else '[aucune action capturée]'}

═══════════════════════════════════════════════════════════════
REQUÊTES RÉSEAU EN ÉCHEC ({len(ctx.failed_requests)})
═══════════════════════════════════════════════════════════════
{network_summary if network_summary else '[aucune requête en échec]'}

═══════════════════════════════════════════════════════════════
ERREURS CONSOLE ({len(ctx.console_errors)})
═══════════════════════════════════════════════════════════════
{console_summary if console_summary else '[aucune erreur console]'}

═══════════════════════════════════════════════════════════════
GUIDE DE DIAGNOSTIC — LIS ATTENTIVEMENT AVANT DE RÉPONDRE
═══════════════════════════════════════════════════════════════

ÉTAPE 1 — Analyse le CALL LOG Playwright mot par mot.
Ces messages sont la source de vérité n°1. Indices critiques :
  • "element is not visible"         → overlay/bandeau/popup qui recouvre OU iframe
  • "element is not enabled"         → élément DISABLED (attribut disabled/aria-disabled)
  • "element is not stable"          → élément en cours d'animation/transition
  • "locator resolved to N elements" → sélecteur trop large (strict mode violation)
  • "waiting for locator"            → timeout, élément jamais apparu
  • "intercept" ou "click intercepted" → un élément recouvre la cible (cookie banner, modal, overlay)
  • "frame was detached"             → iframe rechargé/supprimé pendant l'action
  • "about:blank"                    → navigation manquante (pas de goto)

ÉTAPE 2 — Compare le ATTENDU vs RÉEL dans l'erreur.
  • Si c'est une assertion to_have_text :
    - Compare caractère par caractère les accents, cédilles, ligatures (é≠e, ç≠c, œ≠oe)
    - Vérifie si le test utilise une regex → la regex matche-t-elle le texte réel ?
    - "Actual value: X" te dit EXACTEMENT ce que la page contient
  • Si c'est une assertion to_have_url :
    - Vérifie les redirections 301/302 (URL finale ≠ URL demandée)
  • Si c'est une assertion to_have_title :
    - Compare le titre attendu avec "Actual value" → souvent copier-coller d'un autre test

ÉTAPE 3 — Analyse le CODE du test pour détecter les erreurs logiques.
  • click() sur un élément qui nécessite dblclick() → l'action passe SANS erreur
    mais l'événement attendu ne se déclenche pas → l'assertion SUIVANTE fail
  • fill() puis click() immédiat sans wait → race condition sur éléments dynamiques
  • locator capturé AVANT un rechargement AJAX puis utilisé APRÈS → stale reference
  • page.locator("tag") dans un iframe → cherche dans le mauvais frame
  • Interaction avec un élément sans goto() préalable → page about:blank

═══════════════════════════════════════════════════════════════
CATÉGORIES DE DIAGNOSTIC (choisis UNE seule)
═══════════════════════════════════════════════════════════════

"wrong_selector"      — Sélecteur cassé, inexistant, ou trop large
                        Indice : "locator resolved to N elements", élément introuvable

"missing_step"        — Le test oublie une interaction requise
                        Indice : cookie banner non fermé, goto manquant, dropdown non sélectionné

"timing"              — Race condition, élément pas encore prêt
                        Indice : fill + click immédiat, stale reference après AJAX, "waiting for"

"element_obscured"    — L'élément existe mais est recouvert par un overlay/modal/bannière
                        Indice : "not visible", "click intercepted", bandeau cookies, popup

"element_disabled"    — L'élément est trouvé mais désactivé (disabled/aria-disabled)
                        Indice : "element is not enabled", "disabled" dans le call log

"wrong_action"        — Mauvaise méthode Playwright (click vs dblclick, fill vs type, etc.)
                        Indice : l'action réussit SANS erreur mais l'assertion suivante fail

"iframe_context"      — Élément cherché dans le mauvais frame (main vs iframe)
                        Indice : "resolved to N elements" dont certains non visibles, frame_locator absent

"encoding_mismatch"   — Problème Unicode/accents/regex dans les assertions
                        Indice : texte attendu vs réel diffère par accents (e vs é, Zidane vs Zidane)

"stale_reference"     — Locator capturé avant un changement DOM, utilisé après
                        Indice : assertion fail avec mauvaise valeur alors que le sélecteur est correct

"test_data"           — Assertion avec mauvaise valeur attendue (copier-coller, données périmées)
                        Indice : to_have_title("Google") sur une page Wikipedia

"app_bug"             — L'application est cassée, PAS le test
                        Indice : erreurs 5xx, exceptions console, UI en état d'erreur
                        IMPORTANT : si c'est un app_bug, ne propose PAS de modifier le test.
                        Génère plutôt un rapport de bug (voir structure jira_ticket ci-dessous).

"network"             — Requêtes réseau en échec (4xx/5xx, timeout, CORS)
                        Indice : failed_requests non vide, fetch/XHR en erreur

═══════════════════════════════════════════════════════════════
CONSIGNES DE RÉPONSE
═══════════════════════════════════════════════════════════════

1. Identifie UNE SEULE cause racine (pas 3 hypothèses)
2. Choisis la catégorie la plus spécifique (ex: "element_disabled" plutôt que "wrong_selector")
3. Propose un fix CONCRET avec le CODE EXACT à modifier
4. Si c'est un app_bug → remplis le champ jira_ticket, ne modifie PAS le test
5. Donne ton niveau de confiance (0.0 à 1.0)
6. Liste les sélecteurs fragiles détectés

Réponds UNIQUEMENT en JSON valide (pas de markdown, pas de commentaires) :
{{
  "root_cause": "explication concise de la cause racine",
  "category": "wrong_selector|missing_step|timing|element_obscured|element_disabled|wrong_action|iframe_context|encoding_mismatch|stale_reference|test_data|app_bug|network",
  "confidence": 0.85,
  "diagnosis": "explication détaillée en 2-3 phrases",
  "suggested_fix": {{
    "file": "{ctx.test_file}",
    "description": "ce qu'il faut changer",
    "code": "le code corrigé (snippet, pas tout le fichier)"
  }},
  "selectors_at_risk": ["liste des sélecteurs non-uniques ou fragiles détectés"],
  "jira_ticket": null
}}

Si category == "app_bug", remplace jira_ticket null par :
{{
  "jira_ticket": {{
    "title": "[BUG] titre concis du bug",
    "priority": "Critical|Major|Minor",
    "description": "description user-facing du problème",
    "steps_to_reproduce": ["1. Naviguer vers ...", "2. Cliquer sur ...", "3. Observer que ..."],
    "expected": "ce qui devrait se passer",
    "actual": "ce qui se passe réellement",
    "technical_details": "endpoint en erreur, status, console errors, etc.",
    "environment": "Playwright + Chromium headless"
  }}
}}"""

    try:
        client = OpenAI()
        print("\n  🤖 Analyse IA en cours...")

        for attempt in range(3):
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "Tu es un expert QA automation Playwright. Tu réponds UNIQUEMENT en JSON valide. Pas de markdown, pas de backticks, pas de commentaires."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                response_format={"type": "json_object"},  # ← ajoute ça
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0]
            try:
                return json.loads(raw.strip())
            except json.JSONDecodeError:
                if attempt < 2:
                    print(f"  ⚠️ JSON invalide (tentative {attempt+1}/3), retry...")
                    continue
                return {"root_cause": "Réponse IA invalide après 3 tentatives",
                        "category": "unknown", "confidence": 0, "raw_response": raw}
    except Exception as e:
        return {"root_cause": f"Erreur appel IA: {e}", "category": "error",
                "confidence": 0}


# ============================================================
# PLUGIN PYTEST — Drop-in, zéro config
# ============================================================

def pytest_addoption(parser):
    """Ajoute le flag --qa-autopilot à pytest"""
    parser.addoption(
        "--qa-autopilot",
        action="store_true",
        default=False,
        help="Active le diagnostic IA automatique sur les tests Playwright en échec",
    )


def pytest_configure(config):
    """Enregistre le marker qa_autopilot"""
    config.addinivalue_line(
        "markers", "qa_autopilot: active le diagnostic IA sur ce test"
    )


try:
    import pytest

    @pytest.fixture(autouse=True)
    def _qa_autopilot_fixture(request):
        """Fixture auto : intercepte les pages Playwright si --qa-autopilot actif"""
        # Vérifier que le flag est actif
        if not request.config.getoption("--qa-autopilot", default=False):
            yield
            return

        # Vérifier que le test utilise une page Playwright
        if "page" not in request.fixturenames:
            yield
            return

        # Récupérer la page et brancher l'intercepteur
        page = request.getfixturevalue("page")
        interceptor = QAInterceptor(page)
        interceptor.start()
        request.node._qa_interceptor = interceptor

        yield

        interceptor.stop()

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(item, call):
        """Hook pytest : déclenche le diagnostic IA si le test échoue"""
        outcome = yield
        report = outcome.get_result()

        if report.when == "call" and report.failed:
            interceptor = getattr(item, "_qa_interceptor", None)
            if interceptor:
                error_msg = str(call.excinfo.value) if call.excinfo else "Unknown"
                error_tb = "".join(traceback.format_exception(
                    type(call.excinfo.value), call.excinfo.value,
                    call.excinfo.value.__traceback__
                )) if call.excinfo else ""
                test_file = str(item.fspath) if item.fspath else ""

                item._qa_diagnosis = interceptor.diagnose(
                    error_message=error_msg,
                    test_file=test_file,
                    error_tb=error_tb,
                )

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(session, exitstatus):
        reports = []
        for item in session.items:
            diag = getattr(item, "_qa_diagnosis", None)
            if diag:
                reports.append({
                    "test": item.name,
                    "category": diag.get("category"),
                    "confidence": diag.get("confidence"),
                    "root_cause": diag.get("root_cause"),
                    "suggested_fix": diag.get("suggested_fix", {}).get("description"),
                })
        if reports:
            REPORT_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_file = REPORT_DIR / f"summary_{ts}.json"
            with open(summary_file, "w", encoding="utf-8") as f:
                json.dump(reports, f, indent=2, ensure_ascii=False)
            print(f"\n📊 Rapport consolidé → {summary_file}")
            
except ImportError:
    pass  # pytest pas installé → mode import direct uniquement


# ============================================================
# CLI — python qa_autopilot.py tests/test_whatever.py
# ============================================================

def main():
    import sys
    import subprocess

    if len(sys.argv) < 2:
        print("""
  🚀 QA Autopilot — L'anti usine à gaz
  ======================================

  Usage :
    python qa_autopilot.py tests/test_checkout.py          # un fichier
    python qa_autopilot.py tests/                           # tout un dossier
    python qa_autopilot.py tests/test_login.py::test_auth   # un test précis
    python qa_autopilot.py tests/ -k "checkout"             # par keyword
    python qa_autopilot.py tests/ --headed                  # avec navigateur visible

  Ou en plugin pytest direct :
    pytest tests/ --qa-autopilot

  Config (variables d'env) :
    OPENAI_API_KEY    → clé API OpenAI (obligatoire)
    QA_MODEL          → modèle IA (défaut: gpt-4.1-mini)
    QA_SCREENSHOT     → 1 pour inclure les screenshots dans le prompt
    QA_REPORT_DIR     → dossier des rapports (défaut: qa-reports/)
        """)
        sys.exit(0)

    # Construire la commande pytest avec notre plugin
    conftest = Path(__file__).parent / "conftest_qa.py"
    cmd = [
        sys.executable, "-m", "pytest",
        "--qa-autopilot",
        "-v",
        "--tb=short",
    ]

    # Si notre conftest existe à côté, l'utiliser
    if conftest.exists():
        cmd.extend(["-c", str(conftest)])

    # Passer tous les arguments utilisateur
    cmd.extend(sys.argv[1:])

    # Ajouter le répertoire courant au PYTHONPATH pour l'import
    env = os.environ.copy()
    parent = str(Path(__file__).parent)
    env["PYTHONPATH"] = f"{parent}:{env.get('PYTHONPATH', '')}"

    print(f"  🚀 Lancement : {' '.join(cmd)}")
    result = subprocess.run(cmd, env=env)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()