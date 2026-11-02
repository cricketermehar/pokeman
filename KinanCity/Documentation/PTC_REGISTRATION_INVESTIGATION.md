# PTC Registration Investigation Report

> **Generated:** 2026-10-23 04:21:26
> **Tool:** KinanCity Python Automation — `ptc_investigator.py`
> **Purpose:** Document current Pokémon Trainer Central registration flow
> **Scope:** Read-only probes. No real accounts created. No credentials used.

---

## Executive Summary

This report documents the current state of the Pokémon Trainer Central registration flow as of the investigation date. The legacy KinanCity registration code targets `club.pokemon.com` URLs that now redirect to `trainer.pokemon.com`. The current flow uses a different HTML structure, CSRF mechanism, and CAPTCHA implementation than the legacy code assumes.

---

## Probe 1 — Legacy KinanCity Signup URL

**Target:** `https://club.pokemon.com/us/pokemon-trainer-club/sign-up/`

**Redirect chain:**
```
  HTTP 302  https://club.pokemon.com/us/pokemon-trainer-club/sign-up/ → https://trainer.pokemon.com/profile
  HTTP 200  https://trainer.pokemon.com/profile
```

> ⚠️ **FINDING:** The old signup URL now redirects to `trainer.pokemon.com`. The legacy KinanCity registration endpoint no longer exists at this path.


**Also probed:** `https://club.pokemon.com/us/pokemon-trainer-club/parents/sign-up`

```
  HTTP 302  https://club.pokemon.com/us/pokemon-trainer-club/parents/sign-up → https://trainer.pokemon.com/profile
  HTTP 200  https://trainer.pokemon.com/profile
```


## Probe 2 — trainer.pokemon.com Landing Page

- **Final URL:** `https://trainer.pokemon.com/`
- **HTTP Status:** 200
- **Content-Type:** text/html
- **Response Size:** 890 bytes


## Probe 3 — Current Signup Page Structure

**GET** `https://trainer.pokemon.com/en-us/profile/signup` → HTTP 200 (final: `https://trainer.pokemon.com/en-us/profile/signup`)
  *(Install beautifulsoup4 for deeper HTML analysis)*


**GET** `https://trainer.pokemon.com/signup` → HTTP 200 (final: `https://trainer.pokemon.com/signup`)
  *(Install beautifulsoup4 for deeper HTML analysis)*


**GET** `https://trainer.pokemon.com/register` → HTTP 200 (final: `https://trainer.pokemon.com/register`)
  *(Install beautifulsoup4 for deeper HTML analysis)*



## Probe 4 — Dummy POST (Fake Credentials)

> This POST uses obviously fake/invalid data to document how the server responds to a malformed registration attempt. No real account is created and no real credentials are used.

- Dummy username: `TestUser9999x` (not a real account)
- Dummy email: `noreply@example-test-kinancity.invalid` (invalid domain)

**POST** `https://club.pokemon.com/us/pokemon-trainer-club/parents/sign-up`
- HTTP 200 (final: `https://trainer.pokemon.com/profile`)
- Response size: 890 bytes

**POST** `https://trainer.pokemon.com/en-us/profile/signup`
- HTTP 403 (final: `https://trainer.pokemon.com/en-us/profile/signup`)
- Response size: 1,265 bytes
  - ✓ `403 Forbidden` detected in response


## Probe 5 — Username Verify API

**Target:** `https://club.pokemon.com/api/signup/verify-username`

- **HTTP Status:** 200
- **Response:** `<!doctype html><html lang="en"><head><script src="/Pearkd-him-hithinock-my-dulour-pronor-to-make-th" async></script><meta charset="utf-8"/><link rel="icon" href="/favicon.ico" data-react-helmet="true"/><link rel="apple-touch-icon" href="/logo192.png" data-react-helmet="true"/><link rel="manifest" hr`

> ✅ API endpoint is still responding


---

## CAPTCHA Compatibility and Solver Plan

The KinanCity Java codebase already includes solver modules for:

| Service | Module | Status |
|---|---|---|
| 2Captcha | `KinanCity-captcha-2captcha` | ✅ Compiled |
| AntiCaptcha | `KinanCity-captcha-AntiCaptcha` | ✅ Compiled |
| CapSolver | `KinanCity-captcha-capsolver` | ✅ Compiled |
| DeathByCaptcha | `KinanCity-captcha-deathbycaptcha` | ✅ Compiled |
| ImageTypers | `KinanCity-captcha-ImageTypers` | ✅ Compiled |

**To activate CAPTCHA solving:**
1. Obtain a valid API key from any of the services above.
2. Pass `-ck <your-api-key> -cp 2captcha` to the KinanCity CLI.
3. For the Python backend, set `captcha_api_key` in `config.ini`.

> ⚠️ **No bypass is active by default.** A valid paid API key is required.
> The solver modules in the Java codebase are the correct integration point.

---

## Legacy KinanCity Code Compatibility Verdict

| Component | Legacy Assumption | Current Reality | Compatible? |
|---|---|---|---|
| Signup URL | `club.pokemon.com/.../sign-up/` | Redirects to `trainer.pokemon.com` | ❌ No |
| Parent signup URL | `club.pokemon.com/.../parents/sign-up` | Redirects to `trainer.pokemon.com` | ❌ No |
| CSRF mechanism | `csrfmiddlewaretoken` (Django) | TBD by investigation | ⚠️ Unverified |
| Form fields | Legacy HTML form | New site structure | ⚠️ Unverified |
| CAPTCHA type | reCAPTCHA v2 assumed | TBD by investigation | ⚠️ Unverified |
| Username API | `club.pokemon.com/api/signup/verify-username` | May be deprecated | ⚠️ Unverified |
| Activation URL | Old club.pokemon.com format | New trainer.pokemon.com format | ⚠️ Unverified |

> **Conclusion:** The old registration code cannot create accounts without adapting to the new `trainer.pokemon.com` flow. This is a new implementation task, not a simple URL change.

---

## Recommended Next Steps

1. **Review the redirect chain** from Probe 1 to confirm the current final URL.
2. **Manually load** `trainer.pokemon.com` and document the signup flow.
3. **Obtain one real activation email** — save as `.eml` for local KinanCity-mail testing.
4. **Implement new PTC session** targeting `trainer.pokemon.com` endpoints.
5. **Wire a CAPTCHA solver** from the existing KinanCity captcha modules.
6. **Test with one account** before running any batch.

---

*Investigation completed in 9.0s — 2026-10-23 04:21:35*

> ⚠️ This document was auto-generated by `ptc_investigator.py`. Review all findings manually before implementation.