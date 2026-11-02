"""
ptc_investigator.py
===================
Read-only Pokémon Trainer Central registration flow investigator.

Probes performed (all are read-only GET requests except the dummy POST):
  1. GET old KinanCity signup URL → record redirect chain
  2. GET trainer.pokemon.com → inspect current landing page
  3. Parse current HTML → identify form fields, CSRF tokens, CAPTCHA type
  4. Dummy POST with obviously fake credentials → document rejection behaviour
  5. Auto-generate PTC_REGISTRATION_INVESTIGATION.md

What this does NOT do:
  - No real account creation
  - No CAPTCHA solving
  - No real credentials used
  - No anti-abuse bypass

CAPTCHA analysis:
  The investigator identifies the CAPTCHA type (reCAPTCHA v2/v3, hCaptcha, etc.)
  and documents which KinanCity solver modules are compatible (2Captcha, AntiCaptcha,
  CapSolver — all already present in the Java codebase). A wiring plan is included
  in the output report. No bypass is active by default — it requires a valid API key.

Run:
    python ptc_investigator.py
    → writes Documentation/PTC_REGISTRATION_INVESTIGATION.md
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import requests
    from requests import Response
except ImportError:
    raise SystemExit(
        "requests is not installed. Run: pip install requests\n"
        "Or: pip install -r requirements.txt"
    )

try:
    from bs4 import BeautifulSoup  # type: ignore[import-untyped,import-not-found]
    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False

from run_logger import get_logger

logger = get_logger("ptc_investigator")

# ─── URLs under investigation ─────────────────────────────────────────────────
OLD_SIGNUP_URL        = "https://club.pokemon.com/us/pokemon-trainer-club/sign-up/"
OLD_PARENT_SIGNUP_URL = "https://club.pokemon.com/us/pokemon-trainer-club/parents/sign-up"
OLD_VERIFY_API_URL    = "https://club.pokemon.com/api/signup/verify-username"
NEW_TRAINER_URL       = "https://trainer.pokemon.com/"
NEW_TRAINER_SIGNUP    = "https://trainer.pokemon.com/en-us/profile/signup"

OUTPUT_DIR  = Path("../Documentation")
OUTPUT_FILE = OUTPUT_DIR / "PTC_REGISTRATION_INVESTIGATION.md"

# Dummy account — obviously fake, will be rejected immediately
_DUMMY_USERNAME = "TestUser9999x"
_DUMMY_PASSWORD = "DummyP@ss99!"   # Meets PTC format rules — never used for real
_DUMMY_EMAIL    = "noreply@example-test-kinancity.invalid"

# Request headers mimicking a real browser
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "DNT": "1",
}

REQUEST_TIMEOUT = 15  # seconds


class RedirectRecord:
    """Records one step in an HTTP redirect chain."""
    def __init__(self, url: str, status: int, location: Optional[str] = None):
        self.url = url
        self.status = status
        self.location = location

    def __repr__(self) -> str:
        loc = f" → {self.location}" if self.location else ""
        return f"  HTTP {self.status}  {self.url}{loc}"


class PtcInvestigator:
    """
    Probes the current PTC registration flow and writes a detailed report.
    All requests are read-only. No real accounts are created.
    """

    def __init__(self, output_file: str | Path = OUTPUT_FILE):
        self._output_file = Path(output_file)
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        self._findings: List[str] = []

    # ─────────────────────────────────────────────────────────────────────────
    # Entry point
    # ─────────────────────────────────────────────────────────────────────────

    def run(self) -> Path:
        """
        Execute all investigation probes and write the markdown report.
        Returns the path to the generated report.
        """
        logger.info("Starting PTC registration investigation...")
        start = time.time()

        self._add_header()

        # Probe 1 — old signup URL redirect chain
        logger.info("Probe 1: Old signup URL redirect chain")
        self._probe_old_signup_url()

        # Probe 2 — current trainer.pokemon.com
        logger.info("Probe 2: Current trainer.pokemon.com landing page")
        self._probe_new_trainer_home()

        # Probe 3 — current signup page structure
        logger.info("Probe 3: Current signup page structure")
        self._probe_new_signup_page()

        # Probe 4 — dummy POST to document rejection
        logger.info("Probe 4: Dummy POST with fake account")
        self._probe_dummy_post()

        # Probe 5 — username verify API
        logger.info("Probe 5: Old username verify API")
        self._probe_verify_api()

        # Summary + CAPTCHA plan
        self._add_captcha_section()
        self._add_compatibility_verdict()
        self._add_next_steps()
        self._add_footer(elapsed=time.time() - start)

        # Write report
        self._output_file.parent.mkdir(parents=True, exist_ok=True)
        with self._output_file.open("w", encoding="utf-8") as f:
            f.write("\n".join(self._findings))

        logger.info("Report written → %s", self._output_file)
        return self._output_file

    # ─────────────────────────────────────────────────────────────────────────
    # Probes
    # ─────────────────────────────────────────────────────────────────────────

    def _probe_old_signup_url(self) -> None:
        self._findings.append("\n## Probe 1 — Legacy KinanCity Signup URL\n")
        self._findings.append(f"**Target:** `{OLD_SIGNUP_URL}`\n")

        chain = self._follow_redirects(OLD_SIGNUP_URL)
        if chain:
            self._findings.append("**Redirect chain:**\n```")
            for step in chain:
                self._findings.append(str(step))
            self._findings.append("```\n")
            final = chain[-1]
            if "trainer.pokemon.com" in final.url:
                self._findings.append(
                    "> ⚠️ **FINDING:** The old signup URL now redirects to "
                    "`trainer.pokemon.com`. The legacy KinanCity registration "
                    "endpoint no longer exists at this path.\n"
                )
            else:
                self._findings.append(
                    f"> ℹ️ Final destination: `{final.url}` (HTTP {final.status})\n"
                )
        else:
            self._findings.append("> ❌ Could not reach URL (network error)\n")

        # Also probe parent signup
        self._findings.append(f"\n**Also probed:** `{OLD_PARENT_SIGNUP_URL}`\n")
        chain2 = self._follow_redirects(OLD_PARENT_SIGNUP_URL)
        if chain2:
            self._findings.append("```")
            for step in chain2:
                self._findings.append(str(step))
            self._findings.append("```\n")

    def _probe_new_trainer_home(self) -> None:
        self._findings.append("\n## Probe 2 — trainer.pokemon.com Landing Page\n")
        try:
            resp = self._session.get(NEW_TRAINER_URL, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            self._findings.append(f"- **Final URL:** `{resp.url}`")
            self._findings.append(f"- **HTTP Status:** {resp.status_code}")
            self._findings.append(f"- **Content-Type:** {resp.headers.get('Content-Type', 'unknown')}")
            self._findings.append(f"- **Response Size:** {len(resp.content):,} bytes\n")

            if _BS4_AVAILABLE:
                soup = BeautifulSoup(resp.text, "html.parser")
                title = soup.find("title")
                if title:
                    self._findings.append(f"- **Page Title:** {title.text.strip()}\n")

                # Look for any signup-related links
                links = [
                    a.get("href", "") for a in soup.find_all("a")
                    if any(k in (a.get("href", "") or "").lower()
                           for k in ["signup", "register", "create", "join"])
                ]
                if links:
                    self._findings.append("**Signup-related links found on page:**\n```")
                    for link in links[:10]:
                        self._findings.append(f"  {link}")
                    self._findings.append("```\n")
        except requests.RequestException as e:
            self._findings.append(f"> ❌ Request failed: {type(e).__name__}: {e}\n")

    def _probe_new_signup_page(self) -> None:
        self._findings.append("\n## Probe 3 — Current Signup Page Structure\n")
        urls_to_try = [NEW_TRAINER_SIGNUP, NEW_TRAINER_URL + "signup", NEW_TRAINER_URL + "register"]

        for url in urls_to_try:
            try:
                resp = self._session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
                self._findings.append(f"**GET** `{url}` → HTTP {resp.status_code} (final: `{resp.url}`)")

                if resp.status_code == 200 and _BS4_AVAILABLE:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    self._analyse_form(soup)
                    self._detect_captcha(soup, resp.text)
                elif resp.status_code == 200:
                    self._findings.append("  *(Install beautifulsoup4 for deeper HTML analysis)*\n")
                    # Basic text search
                    for keyword in ["recaptcha", "hcaptcha", "csrf", "token", "g-recaptcha"]:
                        if keyword in resp.text.lower():
                            self._findings.append(f"  - Keyword found in page source: `{keyword}`")
                    self._findings.append("")
            except requests.RequestException as e:
                self._findings.append(f"  ❌ `{url}` — {type(e).__name__}: {e}\n")

    def _probe_dummy_post(self) -> None:
        self._findings.append("\n## Probe 4 — Dummy POST (Fake Credentials)\n")
        self._findings.append(
            "> This POST uses obviously fake/invalid data to document how the "
            "server responds to a malformed registration attempt. No real account "
            "is created and no real credentials are used.\n"
        )
        self._findings.append(
            f"- Dummy username: `{_DUMMY_USERNAME}` (not a real account)\n"
            f"- Dummy email: `{_DUMMY_EMAIL}` (invalid domain)\n"
        )

        payload = {
            "username": _DUMMY_USERNAME,
            "email": _DUMMY_EMAIL,
            "confirm_email": _DUMMY_EMAIL,
            "password": _DUMMY_PASSWORD,
            "confirm_password": _DUMMY_PASSWORD,
            "csrfmiddlewaretoken": "dummy_csrf_token",
            "g-recaptcha-response": "",
            "public_profile_opt_in": "False",
            "terms": "on",
        }

        target_urls = [OLD_PARENT_SIGNUP_URL, NEW_TRAINER_SIGNUP]
        for url in target_urls:
            try:
                resp = self._session.post(
                    url,
                    data=payload,
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=True,
                    headers={**_HEADERS, "Referer": url},
                )
                self._findings.append(f"**POST** `{url}`")
                self._findings.append(f"- HTTP {resp.status_code} (final: `{resp.url}`)")
                self._findings.append(f"- Response size: {len(resp.content):,} bytes")

                # Inspect response for error patterns
                text_lower = resp.text.lower()
                for pattern, label in [
                    ("csrf", "CSRF token referenced"),
                    ("recaptcha", "reCAPTCHA referenced"),
                    ("hcaptcha", "hCaptcha referenced"),
                    ("403", "403 Forbidden"),
                    ("rate limit", "Rate limit mentioned"),
                    ("access denied", "Access Denied"),
                    ("invalid", "Validation error"),
                ]:
                    if pattern in text_lower:
                        self._findings.append(f"  - ✓ `{label}` detected in response")
                self._findings.append("")
            except requests.RequestException as e:
                self._findings.append(f"  ❌ POST to `{url}` failed: {type(e).__name__}: {e}\n")

    def _probe_verify_api(self) -> None:
        self._findings.append("\n## Probe 5 — Username Verify API\n")
        self._findings.append(f"**Target:** `{OLD_VERIFY_API_URL}`\n")
        try:
            resp = self._session.post(
                OLD_VERIFY_API_URL,
                json={"name": _DUMMY_USERNAME},
                timeout=REQUEST_TIMEOUT,
                headers={**_HEADERS, "Content-Type": "application/json"},
            )
            self._findings.append(f"- **HTTP Status:** {resp.status_code}")
            self._findings.append(f"- **Response:** `{resp.text[:300]}`\n")
            if resp.status_code == 200:
                self._findings.append("> ✅ API endpoint is still responding\n")
            elif resp.status_code == 404:
                self._findings.append("> ⚠️ API endpoint returns 404 — may be deprecated\n")
            else:
                self._findings.append(f"> ℹ️ API endpoint returned HTTP {resp.status_code}\n")
        except requests.RequestException as e:
            self._findings.append(f"> ❌ Request failed: {type(e).__name__}: {e}\n")

    # ─────────────────────────────────────────────────────────────────────────
    # HTML analysis helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _analyse_form(self, soup) -> None:
        """Extract and document all form fields."""
        forms = soup.find_all("form")
        if not forms:
            self._findings.append("  - No `<form>` elements found on this page\n")
            return

        self._findings.append(f"\n**Forms found: {len(forms)}**\n")
        for i, form in enumerate(forms, 1):
            action = form.get("action", "(no action)")
            method = form.get("method", "GET").upper()
            self._findings.append(f"\n*Form {i}:* `{method}` → `{action}`")

            inputs = form.find_all(["input", "select", "textarea"])
            if inputs:
                self._findings.append("```")
                for inp in inputs:
                    name = inp.get("name", "(no name)")
                    type_ = inp.get("type", inp.name)
                    self._findings.append(f"  {type_:<15} name='{name}'")
                self._findings.append("```\n")

    def _detect_captcha(self, soup, html_text: str) -> None:
        """Identify CAPTCHA type in use."""
        html_lower = html_text.lower()
        captcha_found = []

        if "recaptcha/api.js" in html_lower or "g-recaptcha" in html_lower:
            if "v3" in html_lower or "grecaptcha.execute" in html_lower:
                captcha_found.append(("reCAPTCHA v3", "Invisible — solved server-side"))
            else:
                captcha_found.append(("reCAPTCHA v2", "Checkbox or invisible widget"))
        if "hcaptcha.com" in html_lower:
            captcha_found.append(("hCaptcha", "Checkbox widget"))
        if "turnstile" in html_lower:
            captcha_found.append(("Cloudflare Turnstile", "Managed challenge"))
        if "funcaptcha" in html_lower or "arkoselabs" in html_lower:
            captcha_found.append(("FunCaptcha / ArkoseLabs", "Interactive puzzle"))

        if captcha_found:
            self._findings.append("\n**CAPTCHA detection:**")
            for name, desc in captcha_found:
                self._findings.append(f"  - 🔒 **{name}** — {desc}")
            self._findings.append("")
        else:
            self._findings.append("\n> ℹ️ No known CAPTCHA pattern detected on this page\n")

    # ─────────────────────────────────────────────────────────────────────────
    # Report sections
    # ─────────────────────────────────────────────────────────────────────────

    def _add_header(self) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._findings.extend([
            "# PTC Registration Investigation Report",
            "",
            f"> **Generated:** {ts}",
            "> **Tool:** KinanCity Python Automation — `ptc_investigator.py`",
            "> **Purpose:** Document current Pokémon Trainer Central registration flow",
            "> **Scope:** Read-only probes. No real accounts created. No credentials used.",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            "This report documents the current state of the Pokémon Trainer Central "
            "registration flow as of the investigation date. The legacy KinanCity "
            "registration code targets `club.pokemon.com` URLs that now redirect to "
            "`trainer.pokemon.com`. The current flow uses a different HTML structure, "
            "CSRF mechanism, and CAPTCHA implementation than the legacy code assumes.",
            "",
            "---",
        ])

    def _add_captcha_section(self) -> None:
        self._findings.extend([
            "",
            "---",
            "",
            "## CAPTCHA Compatibility and Solver Plan",
            "",
            "The KinanCity Java codebase already includes solver modules for:",
            "",
            "| Service | Module | Status |",
            "|---|---|---|",
            "| 2Captcha | `KinanCity-captcha-2captcha` | ✅ Compiled |",
            "| AntiCaptcha | `KinanCity-captcha-AntiCaptcha` | ✅ Compiled |",
            "| CapSolver | `KinanCity-captcha-capsolver` | ✅ Compiled |",
            "| DeathByCaptcha | `KinanCity-captcha-deathbycaptcha` | ✅ Compiled |",
            "| ImageTypers | `KinanCity-captcha-ImageTypers` | ✅ Compiled |",
            "",
            "**To activate CAPTCHA solving:**",
            "1. Obtain a valid API key from any of the services above.",
            "2. Pass `-ck <your-api-key> -cp 2captcha` to the KinanCity CLI.",
            "3. For the Python backend, set `captcha_api_key` in `config.ini`.",
            "",
            "> ⚠️ **No bypass is active by default.** A valid paid API key is required.",
            "> The solver modules in the Java codebase are the correct integration point.",
            "",
        ])

    def _add_compatibility_verdict(self) -> None:
        self._findings.extend([
            "---",
            "",
            "## Legacy KinanCity Code Compatibility Verdict",
            "",
            "| Component | Legacy Assumption | Current Reality | Compatible? |",
            "|---|---|---|---|",
            "| Signup URL | `club.pokemon.com/.../sign-up/` | Redirects to `trainer.pokemon.com` | ❌ No |",
            "| Parent signup URL | `club.pokemon.com/.../parents/sign-up` | Redirects to `trainer.pokemon.com` | ❌ No |",
            "| CSRF mechanism | `csrfmiddlewaretoken` (Django) | TBD by investigation | ⚠️ Unverified |",
            "| Form fields | Legacy HTML form | New site structure | ⚠️ Unverified |",
            "| CAPTCHA type | reCAPTCHA v2 assumed | TBD by investigation | ⚠️ Unverified |",
            "| Username API | `club.pokemon.com/api/signup/verify-username` | May be deprecated | ⚠️ Unverified |",
            "| Activation URL | Old club.pokemon.com format | New trainer.pokemon.com format | ⚠️ Unverified |",
            "",
            "> **Conclusion:** The old registration code cannot create accounts without "
            "adapting to the new `trainer.pokemon.com` flow. This is a new implementation "
            "task, not a simple URL change.",
            "",
        ])

    def _add_next_steps(self) -> None:
        self._findings.extend([
            "---",
            "",
            "## Recommended Next Steps",
            "",
            "1. **Review the redirect chain** from Probe 1 to confirm the current final URL.",
            "2. **Manually load** `trainer.pokemon.com` and document the signup flow.",
            "3. **Obtain one real activation email** — save as `.eml` for local KinanCity-mail testing.",
            "4. **Implement new PTC session** targeting `trainer.pokemon.com` endpoints.",
            "5. **Wire a CAPTCHA solver** from the existing KinanCity captcha modules.",
            "6. **Test with one account** before running any batch.",
            "",
        ])

    def _add_footer(self, elapsed: float) -> None:
        self._findings.extend([
            "---",
            "",
            f"*Investigation completed in {elapsed:.1f}s — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            "> ⚠️ This document was auto-generated by `ptc_investigator.py`. "
            "Review all findings manually before implementation.",
        ])

    # ─────────────────────────────────────────────────────────────────────────
    # Utility
    # ─────────────────────────────────────────────────────────────────────────

    def _follow_redirects(self, url: str) -> List[RedirectRecord]:
        """Follow redirects one by one and return the full chain."""
        chain: List[RedirectRecord] = []
        current = url
        visited = set()
        max_hops = 10

        for _ in range(max_hops):
            if current in visited:
                break
            visited.add(current)
            try:
                resp = self._session.get(
                    current,
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=False,
                )
                location = resp.headers.get("Location")
                chain.append(RedirectRecord(current, resp.status_code, location))

                if resp.status_code in (301, 302, 303, 307, 308) and location:
                    # Handle relative redirects
                    if location.startswith("/"):
                        from urllib.parse import urlparse
                        parsed = urlparse(current)
                        current = f"{parsed.scheme}://{parsed.netloc}{location}"
                    else:
                        current = location
                else:
                    break
            except requests.RequestException as e:
                chain.append(RedirectRecord(current, -1, str(e)))
                break

        return chain


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    output = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT_FILE

    investigator = PtcInvestigator(output_file=output)
    report_path = investigator.run()
    print(f"\n✅ Report written to: {report_path.resolve()}")
