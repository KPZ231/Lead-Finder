#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════╗
║          FIRMOSCOPE  ·  Business Lead Scraper CLI             ║
║          Powered by Playwright · Free · Fast · Local          ║
╚═══════════════════════════════════════════════════════════════╝
"""

import asyncio
import csv
import sys
import os
import re
import json
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("\n  [ERROR] Playwright is not installed.")
    print("  Run: pip install playwright && playwright install chromium\n")
    sys.exit(1)

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.styles import Style as PTStyle
    _PT = True
except ImportError:
    _PT = False

# Commands available for autocomplete
_COMMANDS = ["/search", "/swarm", "/export sheets", "/provider", "/help", "/exit"]
_CMD_COMPLETER = WordCompleter(_COMMANDS, sentence=True) if _PT else None

# ─────────────────────────────────────────────────
#  ANSI STYLES
# ─────────────────────────────────────────────────

class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    ITALIC  = "\033[3m"
    WHITE   = "\033[97m"
    GRAY    = "\033[90m"
    LGRAY   = "\033[37m"
    TEAL    = "\033[38;5;73m"
    LTEAL   = "\033[38;5;116m"
    MINT    = "\033[38;5;122m"
    GOLD    = "\033[38;5;221m"
    ORANGE  = "\033[38;5;215m"
    RED     = "\033[38;5;203m"
    GREEN   = "\033[38;5;156m"
    BLUE    = "\033[38;5;111m"
    PURPLE  = "\033[38;5;141m"
    BG_DARK = "\033[48;5;235m"
    BG_TEAL = "\033[48;5;23m"

def style(text, *codes):
    return "".join(codes) + str(text) + C.RESET

def dim(text):    return style(text, C.DIM, C.GRAY)
def teal(text):   return style(text, C.BOLD, C.TEAL)
def lteal(text):  return style(text, C.LTEAL)
def gold(text):   return style(text, C.GOLD)
def mint(text):   return style(text, C.MINT)
def orange(text): return style(text, C.ORANGE)
def red(text):    return style(text, C.BOLD, C.RED)
def green(text):  return style(text, C.BOLD, C.GREEN)
def white(text):  return style(text, C.BOLD, C.WHITE)
def gray(text):   return style(text, C.GRAY)
def blue(text):   return style(text, C.BLUE)

# ─────────────────────────────────────────────────
#  UI HELPERS
# ─────────────────────────────────────────────────

LOGO = f"""
{style('  ╔════════════════════════════════════════════════════════╗', C.TEAL, C.DIM)}
{style('  ║', C.TEAL, C.DIM)}  {style('FIRMOSCOPE', C.BOLD, C.TEAL)}  {style('·', C.GRAY)}  {style('Business Intelligence Scraper', C.LTEAL)}       {style('║', C.TEAL, C.DIM)}
{style('  ║', C.TEAL, C.DIM)}  {gray('Playwright  ·  Google Maps  ·  Free  ·  CSV Output')}  {style('║', C.TEAL, C.DIM)}
{style('  ╚════════════════════════════════════════════════════════╝', C.TEAL, C.DIM)}
"""

DIVIDER = style("  " + "─" * 56, C.DIM, C.GRAY)

def print_logo():   print(LOGO)
def print_divider(): print(DIVIDER)

def log_info(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  {dim(ts)}  {gray('·')}  {lteal(msg)}")

def log_step(icon, label, value=""):
    ts = datetime.now().strftime("%H:%M:%S")
    val = f"  {style(value, C.GRAY)}" if value else ""
    print(f"  {dim(ts)}  {teal(icon)}  {white(label)}{val}")

def log_found(i, name, phone, email, address, has_website):
    ws_badge = gold("✦ no-web") if not has_website else dim("✓ has-web")
    ph_str   = mint(phone) if phone else gray("—")
    em_str   = blue(email) if email else gray("—")
    num      = style(f"{i:>3}.", C.DIM, C.GRAY)
    print(f"  {num}  {white(name[:38]+'…' if len(name)>40 else name):<42} {ph_str:<28} {em_str:<38} {ws_badge}")

def log_warn(msg):    print(f"  {orange('⚠')}  {style(msg, C.ORANGE)}")
def log_error(msg):   print(f"  {red('✗')}  {style(msg, C.RED)}")
def log_success(msg): print(f"  {green('✓')}  {style(msg, C.GREEN)}")

def spinner_start(msg):
    sys.stdout.write(f"  {style('◌', C.TEAL, C.BOLD)}  {lteal(msg)}  ")
    sys.stdout.flush()

def spinner_end(result=""):
    r = f"{green(result)}" if result else ""
    sys.stdout.write(f"{r}\n")
    sys.stdout.flush()

_pt_session = None  # ponytail: single shared PromptSession (keeps history)

def prompt(symbol="❯", color=C.TEAL, completer=None):
    global _pt_session
    if _PT and completer is not None:
        if _pt_session is None:
            _pt_session = PromptSession()
        try:
            # ponytail: prompt_toolkit rejects raw ANSI — use plain prefix
            return _pt_session.prompt(f"  {symbol} ", completer=completer).strip()
        except (KeyboardInterrupt, EOFError):
            return None
    sys.stdout.write(f"  {style(symbol, C.BOLD, color)} ")
    sys.stdout.flush()
    try:
        return input().strip()
    except (KeyboardInterrupt, EOFError):
        return None

# ─────────────────────────────────────────────────
#  REGEX HELPERS
# ─────────────────────────────────────────────────

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
PHONE_RE = re.compile(r'(\+?[\d\s\-().]{7,18}\d)')

def extract_emails_from_text(text: str) -> list:
    return list(set(EMAIL_RE.findall(text)))

def clean_phone(raw: str) -> str:
    return raw.strip()

# ─────────────────────────────────────────────────
#  AI PROVIDER ABSTRACTION
# ─────────────────────────────────────────────────

DEFAULT_OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
DEFAULT_OLLAMA_MODEL     = "llama3.1"

_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".firmoscope_config.json")

def _load_config() -> dict:
    try:
        with open(_CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_config(data: dict):
    try:
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def normalize_response(data: dict, provider: str) -> tuple:
    """
    Returns (content: str, tool_calls: list) from a raw API response dict.
    tool_calls items: {"id": str, "function": {"name": str, "arguments": str}}
    """
    if provider == "openrouter":
        msg = data["choices"][0]["message"]
        content    = msg.get("content") or ""
        tool_calls = msg.get("tool_calls") or []
    elif provider == "ollama":
        msg = data["message"]
        content    = msg.get("content") or ""
        tool_calls = msg.get("tool_calls") or []
        # Ollama tool_calls: {"function": {"name": ..., "arguments": {...}}}
        # Normalize arguments to JSON string (matches OpenRouter shape)
        normalized = []
        for i, tc in enumerate(tool_calls):
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            normalized.append({
                "id": tc.get("id", f"call_{i}"),
                "function": {
                    "name": fn.get("name", ""),
                    "arguments": json.dumps(args) if isinstance(args, dict) else args,
                },
            })
        tool_calls = normalized
    else:
        raise ValueError(f"Unknown provider: {provider}")
    return content, tool_calls


def ask_ai(messages: list, provider: str, model: str, tools: list = None) -> tuple:
    """Returns (content, tool_calls). tool_calls may be empty list."""
    try:
        if provider == "openrouter":
            api_key = os.environ.get("OPENROUTER_API_KEY", "")
            if not api_key:
                log_error("OPENROUTER_API_KEY not set in environment.")
                return "", []
            body = {"model": model, "messages": messages}
            if tools:
                body["tools"] = tools
            data_bytes = json.dumps(body).encode()
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=data_bytes,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
        elif provider == "ollama":
            body = {"model": model, "messages": messages, "stream": False}
            if tools:
                body["tools"] = tools
            data_bytes = json.dumps(body).encode()
            req = urllib.request.Request(
                "http://localhost:11434/api/chat",
                data=data_bytes,
                headers={"Content-Type": "application/json"},
            )
        else:
            log_error(f"Unknown provider: {provider}")
            return "", []

        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return normalize_response(data, provider)

    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:500]
        except Exception:
            pass
        log_error(f"AI error: HTTP {e.code} — {body or e.reason}")
        return "", []
    except Exception as e:
        log_error(f"AI error: {e}")
        return "", []


# ─────────────────────────────────────────────────
#  SEARCH TOOL SCHEMA (OpenAI format — works for both backends)
# ─────────────────────────────────────────────────

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_businesses",
        "description": (
            "Search Google Maps for businesses matching a query and scrape their "
            "contact details (phone, email, address, website). "
            "Call this whenever the user asks to find, search, or look up businesses."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query, e.g. 'Mechanics in Rybnik' or 'Dentists Warsaw'",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of results to collect (default 20)",
                    "default": 20,
                },
                "no_website_only": {
                    "type": "boolean",
                    "description": "If true, only return businesses that have no website (good leads)",
                    "default": False,
                },
            },
            "required": ["query"],
        },
    },
}


def results_to_tool_content(results: list) -> str:
    """Compact JSON summary of scraper results to feed back to the model."""
    rows = [
        {
            "name": r["Name"],
            "phone": r["Phone"] or None,
            "email": r["Email"] or None,
            "address": r["Address"] or None,
            "website": r["Website"] or None,
            "has_website": r["Has Website"] == "YES",
        }
        for r in results
    ]
    return json.dumps({"count": len(rows), "businesses": rows}, ensure_ascii=False)


# ─────────────────────────────────────────────────
#  CORE SCRAPER
# ─────────────────────────────────────────────────

async def scrape_business_details(page, url: str) -> dict:
    """Scrape phone, email, address, website from a Google Maps place panel."""
    details = {"phone": "", "email": "", "address": "", "website": ""}
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(1800)
        html = await page.content()

        # Phone from aria-label or text
        phone_els = await page.query_selector_all('[data-item-id*="phone"], [aria-label*="Phone"], [aria-label*="Telefon"]')
        for el in phone_els[:3]:
            lbl = await el.get_attribute("aria-label") or ""
            txt = await el.text_content() or ""
            raw = lbl or txt
            m = PHONE_RE.search(raw)
            if m:
                details["phone"] = clean_phone(m.group(0))
                break

        if not details["phone"]:
            m = PHONE_RE.search(html)
            if m:
                candidate = clean_phone(m.group(0))
                if len(candidate.replace(" ", "")) >= 7:
                    details["phone"] = candidate

        # Address
        addr_els = await page.query_selector_all('[data-item-id*="address"], [aria-label*="Address"], [aria-label*="Adres"]')
        for el in addr_els[:2]:
            lbl = await el.get_attribute("aria-label") or await el.text_content() or ""
            lbl = lbl.replace("Address:", "").replace("Adres:", "").strip()
            if lbl and len(lbl) > 5:
                details["address"] = lbl[:120]
                break

        # Website
        web_els = await page.query_selector_all('[data-item-id*="authority"], a[href*="url?q="], [aria-label*="website"], [aria-label*="Website"]')
        for el in web_els[:3]:
            href = await el.get_attribute("href") or ""
            if "url?q=" in href:
                details["website"] = href.split("url?q=")[1].split("&")[0]
                break
            elif href.startswith("http") and "google" not in href:
                details["website"] = href
                break

        # Email from Maps HTML
        emails = extract_emails_from_text(html)
        filtered = [e for e in emails if not any(x in e.lower() for x in ["google", "gstatic", "sentry", "schema", "example"])]
        if filtered:
            details["email"] = filtered[0]

    except Exception:
        pass

    return details


async def try_scrape_website_for_email(page, website_url: str) -> str:
    """Visit the business website and look for an email address."""
    if not website_url:
        return ""
    try:
        await page.goto(website_url, wait_until="domcontentloaded", timeout=10000)
        await page.wait_for_timeout(1000)
        html = await page.content()
        emails = extract_emails_from_text(html)
        filtered = [e for e in emails if not any(x in e.lower() for x in ["google", "example", "schema", "sentry"])]
        if filtered:
            return filtered[0]
        for path in ["/contact", "/kontakt", "/about", "/o-nas"]:
            try:
                base = website_url.rstrip("/")
                await page.goto(base + path, wait_until="domcontentloaded", timeout=7000)
                await page.wait_for_timeout(800)
                html2 = await page.content()
                emails2 = extract_emails_from_text(html2)
                filtered2 = [e for e in emails2 if not any(x in e.lower() for x in ["google", "example", "schema"])]
                if filtered2:
                    return filtered2[0]
            except Exception:
                pass
    except Exception:
        pass
    return ""


def save_and_summarize(results: list, output_file: str):
    """Write results to CSV and print the summary block."""
    if results:
        spinner_start(f"Saving {len(results)} results to CSV")
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        spinner_end(f"OK  →  {output_file}")

        print()
        with_phone   = sum(1 for r in results if r["Phone"])
        with_email   = sum(1 for r in results if r["Email"])
        no_web_count = sum(1 for r in results if r["Has Website"] == "NO")

        print_divider()
        print(f"  {teal('◈')}  {white('SUMMARY')}")
        print_divider()
        print(f"  {gray('Total businesses  :')}  {white(str(len(results)))}")
        print(f"  {gray('With phone        :')}  {mint(str(with_phone))}")
        print(f"  {gray('With email        :')}  {blue(str(with_email))}")
        print(f"  {gray('No website        :')}  {gold(str(no_web_count))}  {dim('← potential leads')}")
        print_divider()
        log_success(f"Done! File: {output_file}")
        # ponytail: os.startfile is Windows-only; add xdg-open/open branch if this ever runs on Linux/mac
        try:
            os.startfile(Path(output_file).resolve())
        except Exception as e:
            log_warn(f"Could not auto-open CSV: {e}")
    else:
        log_error("No results found. Check your query.")
    print()


async def run_scraper(query: str, max_results: int = 20, output_file: str = None,
                      headless: bool = True, no_website_only: bool = False,
                      silent: bool = False, write_csv: bool = True) -> list:
    """
    Run the Google Maps scraper. Returns list of result dicts.
    silent=True suppresses the logo/divider (used when called from AI tool).
    write_csv=False skips the CSV write + summary (used by swarm sub-runs).
    """
    if not output_file:
        safe_q = re.sub(r'[^\w\s-]', '', query).strip().replace(' ', '_')
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        output_file = f"firmoscope_{safe_q}_{ts}.csv"

    if not silent:
        print_logo()
    print_divider()
    log_step("◎", "Query", query)
    log_step("◎", "Limit", str(max_results))
    log_step("◎", "Output file", output_file)
    log_step("◎", "No-website filter", "ON" if no_website_only else "OFF")
    print_divider()

    results = []
    maps_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"

    async with async_playwright() as pw:
        spinner_start("Launching Chromium (headless)")
        browser = await pw.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--lang=en-US",
                # ponytail: prefer OS resolver — Chromium's built-in async/DoH
                # resolver is what throws ERR_NAME_NOT_RESOLVED while the OS resolves fine
                "--disable-features=UseDnsHttpsSvcb,UseDnsHttpsSvcbHttps,AsyncDns",
                "--dns-over-https-mode=off",
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()
        spinner_end("OK")

        spinner_start(f"Loading Google Maps: {query}")
        # ponytail: single retry — transient DNS/IPv6 blips shouldn't kill the run
        last_err = None
        for attempt in range(2):
            try:
                await page.goto(maps_url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(2500)
                last_err = None
                break
            except Exception as e:
                last_err = e
                await page.wait_for_timeout(1500)
        if last_err is not None:
            spinner_end()
            log_error(f"Failed to load Google Maps: {last_err}")
            if "ERR_NAME_NOT_RESOLVED" in str(last_err):
                log_warn("DNS could not resolve google.com — check your internet / VPN / DNS.")
            await browser.close()
            return []
        spinner_end("loaded")

        # Accept cookies if prompted
        try:
            for sel in ['button[aria-label*="Accept"]', 'button[aria-label*="Zaakceptuj"]',
                        'button[jsname="b3VHJd"]', 'form[action*="consent"] button']:
                btn = await page.query_selector(sel)
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(800)
                    break
        except Exception:
            pass

        print_divider()
        log_step("⟳", "Collecting business links...")
        print()

        business_links = []
        scroll_attempts = 0
        max_scrolls = 40
        dry_runs = 0
        results_panel_sel = 'div[role="feed"]'

        while len(business_links) < max_results and scroll_attempts < max_scrolls:
            cards = await page.query_selector_all('a[href*="/maps/place/"]')
            seen_hrefs = set(business_links)
            new_count = 0
            for card in cards:
                href = await card.get_attribute("href")
                if href and "/maps/place/" in href and href not in seen_hrefs:
                    business_links.append(href)
                    seen_hrefs.add(href)
                    new_count += 1

            if len(business_links) >= max_results:
                break

            if new_count == 0:
                dry_runs += 1
                if dry_runs >= 3:
                    log_warn("End of Google Maps results")
                    break
            else:
                dry_runs = 0

            try:
                panel = await page.query_selector(results_panel_sel)
                if panel:
                    await panel.evaluate("el => el.scrollBy(0, 1500)")
                else:
                    await page.mouse.wheel(0, 1500)
                await page.wait_for_timeout(1500)
            except Exception:
                await page.mouse.wheel(0, 1500)
                await page.wait_for_timeout(1500)

            scroll_attempts += 1

        business_links = business_links[:max_results]
        log_step("◉", "Business links found", str(len(business_links)))
        print()

        header_line = (
            f"  {gray('No.')}  "
            f"{white('Business Name'):<44} "
            f"{teal('Phone'):<28} "
            f"{blue('Email'):<38} "
            f"{gold('Status')}"
        )
        print(header_line)
        print(DIVIDER)

        for idx, link in enumerate(business_links, 1):
            try:
                details = await scrape_business_details(page, link)

                name = ""
                try:
                    name_match = re.search(r'/maps/place/([^/@]+)', link)
                    if name_match:
                        name = name_match.group(1).replace("+", " ").replace("%20", " ")
                        name = re.sub(r'%[0-9A-Fa-f]{2}', ' ', name).strip()
                except Exception:
                    pass

                if not name:
                    try:
                        el = await page.query_selector('h1')
                        if el:
                            name = await el.text_content() or ""
                    except Exception:
                        name = f"Business #{idx}"

                has_website = bool(details.get("website"))

                if no_website_only and has_website:
                    continue

                email = details.get("email", "")
                if not email and has_website:
                    email = await try_scrape_website_for_email(page, details["website"])

                result = {
                    "Name":             name,
                    "Phone":            details.get("phone", ""),
                    "Email":            email,
                    "Address":          details.get("address", ""),
                    "Website":          details.get("website", ""),
                    "Has Website":      "YES" if has_website else "NO",
                    "Google Maps Link": link,
                }
                results.append(result)
                log_found(len(results), name, details.get("phone", ""), email,
                          details.get("address", ""), has_website)

            except Exception as e:
                log_warn(f"Error at business #{idx}: {str(e)[:60]}")
                continue

        print()
        print_divider()
        await browser.close()

    if write_csv:
        save_and_summarize(results, output_file)
    return results


# ─────────────────────────────────────────────────
#  AGENT SWARM
# ─────────────────────────────────────────────────

SWARM_SPLIT_PROMPT = (
    "Split this business search into {n} DISTINCT, non-overlapping sub-searches "
    "that together cover it more thoroughly — by district/neighbourhood or by "
    "business subcategory. Reply with ONLY a JSON array of {n} short query strings.\n\n"
    "Search: {q}"
)


def parse_query_list(text: str, n: int) -> list:
    """Extract up to n query strings from an LLM reply (JSON array, fenced or raw)."""
    m = re.search(r'\[.*\]', text or "", re.S)
    if m:
        try:
            arr = json.loads(m.group(0))
            qs = [str(q).strip() for q in arr if str(q).strip()]
            if qs:
                return qs[:n]
        except Exception:
            pass
    return []  # caller falls back to [base_query]


async def run_swarm(base_query: str, provider: str, model: str, n: int = 3,
                    max_results: int = 20, no_website_only: bool = False,
                    output_file: str = None) -> list:
    """Fan out N scraper agents over LLM-generated sub-scopes, merge + dedupe.
    ponytail: N parallel browsers is the ceiling — fine for small N, add a
    concurrency cap if someone runs huge N."""
    print_divider()
    log_step("◈", "SWARM", f"{base_query}  ·  {n} agents")
    print_divider()

    msgs = [{"role": "user", "content": SWARM_SPLIT_PROMPT.format(n=n, q=base_query)}]
    spinner_start("Planning search scopes...")
    content, _ = ask_ai(msgs, provider, model)
    spinner_end()
    queries = parse_query_list(content, n) or [base_query]
    log_step("◉", "Swarm scopes", "  ·  ".join(queries))
    print()

    batches = await asyncio.gather(*[
        run_scraper(q, max_results, None, True, no_website_only,
                    silent=True, write_csv=False)
        for q in queries
    ], return_exceptions=True)

    seen, merged = set(), []
    for b in batches:
        if isinstance(b, Exception):
            log_warn(f"Agent failed: {str(b)[:60]}")
            continue
        for r in b:
            k = r["Google Maps Link"]
            if k not in seen:
                seen.add(k)
                merged.append(r)

    if not output_file:
        safe = re.sub(r'[^\w\s-]', '', base_query).strip().replace(' ', '_')
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        output_file = f"firmoscope_swarm_{safe}_{ts}.csv"
    save_and_summarize(merged, output_file)
    return merged


# ─────────────────────────────────────────────────
#  AI REPL
# ─────────────────────────────────────────────────

AI_SYSTEM = (
    "You are an AI assistant embedded in FIRMOSCOPE, a Google Maps business lead scraper. "
    "You help users find businesses and analyze the scraped data. "
    "When the user asks to find, search, or look up businesses, call the search_businesses tool. "
    "After a search, summarize the results helpfully: highlight businesses without websites (good leads), "
    "those with emails, and any patterns you notice. Be concise."
)

COMMANDS_HELP = (
    f"  {gray('Commands:')}  "
    f"{teal('/search')} manual scrape  ·  "
    f"{teal('/swarm')} parallel multi-scope  ·  "
    f"{teal('/export sheets')} → Google Sheets  ·  "
    f"{teal('/provider')} switch AI backend  ·  "
    f"{teal('/exit')} quit"
)


def _fetch_ollama_models() -> list:
    """Return list of locally installed Ollama model names, empty on error."""
    try:
        import urllib.request, json
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as r:
            return [m["name"] for m in json.loads(r.read())["models"]]
    except Exception:
        return []


def pick_provider() -> tuple:
    """Interactive provider + model picker. Returns (provider, model)."""
    cfg = _load_config()
    saved_provider = cfg.get("provider")
    saved_model    = cfg.get("model")

    print_divider()
    print(f"  {teal('◈')}  {white('Select AI provider')}")
    print_divider()
    print(f"  {gray('1)')}  {white('Ollama')}  {gray('— local, no API key needed')}")
    print(f"  {gray('2)')}  {white('OpenRouter')}  {gray('— cloud, requires OPENROUTER_API_KEY')}")
    if saved_provider and saved_model:
        print(f"  {gray('Enter)')} {white('Użyj poprzedniego')}  {gray(f'— {saved_provider} · {saved_model}')}")
    print()

    while True:
        choice = prompt("❯")
        if choice == "" and saved_provider and saved_model:
            # ponytail: skip picker entirely, reuse saved config
            log_success(f"Provider: {saved_provider}  ·  Model: {saved_model}")
            print()
            return saved_provider, saved_model
        elif choice in ("1", "ollama"):
            provider = "ollama"
            default_model = saved_model if saved_provider == "ollama" else DEFAULT_OLLAMA_MODEL
            break
        elif choice in ("2", "openrouter"):
            provider = "openrouter"
            default_model = saved_model if saved_provider == "openrouter" else DEFAULT_OPENROUTER_MODEL
            if not os.environ.get("OPENROUTER_API_KEY"):
                log_warn("OPENROUTER_API_KEY not set — AI calls will fail.")
            break
        elif choice is None:
            sys.exit(0)
        else:
            log_warn("Enter 1 lub 2.")

    print()
    if provider == "ollama":
        ollama_models = _fetch_ollama_models()
        if ollama_models:
            print(f"  {teal('◎')}  {white('Dostępne modele Ollama:')}")
            for i, m in enumerate(ollama_models, 1):
                marker = teal("►") if m == default_model else gray(f"{i})")
                print(f"  {marker}  {white(m)}")
            print()
            print(f"  {gray('Wpisz numer lub nazwę modelu')}  {gray(f'(Enter = {default_model})')}")
            model_input = prompt("❯")
            if model_input and model_input.isdigit():
                idx = int(model_input) - 1
                model = ollama_models[idx] if 0 <= idx < len(ollama_models) else default_model
            else:
                model = (model_input if model_input else default_model)
        else:
            print(f"  {teal('◎')}  {white('Model')}  {gray(f'(Enter = {default_model})')}")
            model_input = prompt("❯")
            model = (model_input if model_input else default_model)
    else:
        print(f"  {teal('◎')}  {white('Model')}  {gray(f'(Enter = {default_model})')}")
        model_input = prompt("❯")
        model = (model_input if model_input else default_model)

    _save_config({"provider": provider, "model": model})
    print()
    log_success(f"Provider: {provider}  ·  Model: {model}")
    print()
    return provider, model


def do_manual_search():
    """Prompt user for query + limit and run scraper directly."""
    print_divider()
    print(f"  {teal('◎')}  {white('Manual Search')}")
    print_divider()
    print(f"  {gray('Enter search query (e.g. Mechanics Rybnik):')}")
    query = prompt("❯")
    if not query:
        log_warn("Cancelled.")
        return

    print(f"  {gray('Result limit (Enter = 20):')}")
    limit_raw = prompt("❯")
    limit = int(limit_raw) if limit_raw and limit_raw.isdigit() else 20

    print(f"  {gray('Only businesses without a website? (y/N):')}")
    no_web_raw = prompt("❯")
    no_website_only = no_web_raw.lower() in ("y", "yes") if no_web_raw else False

    try:
        asyncio.run(run_scraper(
            query=query,
            max_results=limit,
            no_website_only=no_website_only,
            silent=False,
        ))
    except KeyboardInterrupt:
        log_warn("Search interrupted.")


def _do_sheets_export(results: list):
    """Interactive Google Sheets export — called from /export sheets."""
    print()
    print(f"  {teal('◈')}  {white('Google Sheets Export')}")
    print(f"  {gray('1)')} Utwórz nowy arkusz")
    print(f"  {gray('2)')} Wpisz do istniejącego (podaj ID lub URL)")
    print()
    choice = prompt("❯")
    if choice == "2":
        sheet_id = prompt("ID lub URL arkusza ❯")
        if not sheet_id:
            log_warn("Anulowano.")
            return
    else:
        sheet_id = None

    spinner_start("Łączenie z Google Sheets...")
    try:
        import sheets as _sheets
        url = _sheets.export(results, sheet_id)
        spinner_end("OK")
        log_success(f"Wgrano {len(results)} wierszy → {url}")
    except Exception as e:
        spinner_end()
        log_error(str(e))


def run_ai_repl(provider: str, model: str):
    """AI-first chat loop with the search_businesses tool."""
    print_divider()
    print(f"  {teal('◈')}  {white('AI CHAT')}  {gray(f'· {provider} · {model}')}")
    print_divider()
    print(COMMANDS_HELP)
    print(f"  {gray('Ask me to find businesses or analyze data. I can trigger searches.')}")
    print()

    messages = [{"role": "system", "content": AI_SYSTEM}]
    _last_results = []  # ponytail: session cache for /export sheets

    while True:
        line = prompt("❯", C.BLUE, completer=_CMD_COMPLETER)
        if line is None:
            break

        # Commands
        if line.startswith("/"):
            parts = line[1:].split(None, 1)
            cmd = parts[0].lower()
            cmd_arg = parts[1] if len(parts) > 1 else ""
            if cmd in ("exit", "quit", "q"):
                break
            elif cmd == "search":
                if cmd_arg:
                    # ponytail: inline search with arg, skip interactive prompt
                    import re as _re
                    # ponytail: accept "--limit N" or a bare trailing number
                    limit_m = _re.search(r"--limit\s+(\d+)|\s(\d+)\s*$", cmd_arg)
                    limit = int(limit_m.group(1) or limit_m.group(2)) if limit_m else 20
                    query = _re.sub(r"--limit\s+\d+|\s\d+\s*$", "", cmd_arg).strip()
                    _last_results = asyncio.run(run_scraper(query, limit, None, True, True)) or _last_results
                else:
                    do_manual_search()
                print()
                print(COMMANDS_HELP)
                print()
                continue
            elif cmd == "swarm":
                if not cmd_arg:
                    log_warn("Użycie: /swarm <query> [--limit N] [--agents K]")
                else:
                    import re as _re
                    limit_m  = _re.search(r"--limit\s+(\d+)", cmd_arg)
                    agents_m = _re.search(r"--agents\s+(\d+)", cmd_arg)
                    limit  = int(limit_m.group(1)) if limit_m else 20
                    agents = int(agents_m.group(1)) if agents_m else 3
                    query  = _re.sub(r"--(limit|agents)\s+\d+", "", cmd_arg).strip()
                    _last_results = asyncio.run(
                        run_swarm(query, provider, model, agents, limit)
                    ) or _last_results
                print()
                print(COMMANDS_HELP)
                print()
                continue
            elif cmd == "export" and cmd_arg.strip().lower() == "sheets":
                if not _last_results:
                    log_warn("Brak danych. Najpierw wykonaj wyszukiwanie.")
                else:
                    _do_sheets_export(_last_results)
                print()
                continue
            elif cmd == "provider":
                provider, model = pick_provider()
                print(COMMANDS_HELP)
                print()
                continue
            elif cmd in ("help", "?"):
                print(COMMANDS_HELP)
                print()
                continue
            else:
                log_warn(f"Unknown command: /{cmd}")
                continue

        if not line:
            continue

        messages.append({"role": "user", "content": line})

        # Agentic tool-call loop (max 3 rounds to avoid runaway)
        for _ in range(3):
            spinner_start("Thinking...")
            content, tool_calls = ask_ai(messages, provider, model, tools=[SEARCH_TOOL])
            spinner_end()

            if not tool_calls:
                break

            # Append assistant message WITH tool_calls (required by spec).
            # ponytail: Ollama wants arguments as an object, OpenRouter as a JSON
            # string — echoing the wrong shape gives Ollama a 400 ("can't find '}'").
            def _echo_fn(fn):
                if provider == "ollama":
                    try:
                        return {"name": fn["name"], "arguments": json.loads(fn["arguments"])}
                    except Exception:
                        return {"name": fn["name"], "arguments": {}}
                return fn
            messages.append({
                "role": "assistant",
                "content": content or "",
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": _echo_fn(tc["function"]),
                    }
                    for tc in tool_calls
                ],
            })

            for tc in tool_calls:
                fn_name = tc["function"]["name"]
                try:
                    fn_args = json.loads(tc["function"]["arguments"])
                except Exception:
                    fn_args = {}

                if fn_name == "search_businesses":
                    query        = fn_args.get("query", "")
                    limit        = fn_args.get("limit", 20)
                    no_web_only  = fn_args.get("no_website_only", False)
                    print()
                    log_step("◉", f"AI triggered search: {query}", f"limit={limit}")
                    print()
                    try:
                        results = asyncio.run(run_scraper(
                            query=query,
                            max_results=limit,
                            no_website_only=no_web_only,
                            silent=True,
                        ))
                        if results:
                            _last_results = results
                        tool_result = results_to_tool_content(results)
                    except Exception as e:
                        tool_result = json.dumps({"error": str(e)})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_result,
                    })
                else:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps({"error": f"Unknown tool: {fn_name}"}),
                    })

        # Final response after tool calls (or direct answer)
        if content:
            messages.append({"role": "assistant", "content": content})
            print(f"\n  {blue('AI')}  {content}\n")
        elif not tool_calls:
            log_warn("AI returned empty response.")
            print()


# ─────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────

def _resolve_provider(model_override: str = None) -> tuple:
    """Provider/model from saved config (or interactive pick), model overridable."""
    cfg = _load_config()
    if cfg.get("provider") and (model_override or cfg.get("model")):
        return cfg["provider"], (model_override or cfg["model"])
    provider, model = pick_provider()
    return provider, (model_override or model)


def main():
    import argparse

    if "--selftest" in sys.argv:
        print_logo()
        _selftest()
        return

    p = argparse.ArgumentParser(
        prog="firmoscope",
        description="Google Maps business lead scraper. No query → interactive AI chat.",
    )
    p.add_argument("query", nargs="?", help="Search query, e.g. 'Rybnik Mechanicy'")
    p.add_argument("--limit", type=int, default=20, help="Max results (default 20)")
    p.add_argument("--output", help="Output CSV filename (auto-generated if omitted)")
    p.add_argument("--no-website", action="store_true",
                   help="Only businesses without a website (leads)")
    p.add_argument("--no-headless", action="store_true", help="Show the browser window")
    p.add_argument("--ai", metavar="QUESTION",
                   help="Scrape QUERY then ask the AI this question about the results")
    p.add_argument("--chat", action="store_true", help="Open the interactive AI chat")
    p.add_argument("--model", help="Override AI model id")
    p.add_argument("--swarm", type=int, metavar="K",
                   help="Fan out K parallel agents over AI-generated sub-scopes")
    p.add_argument("--selftest", action="store_true", help="Run self-check and exit")
    args = p.parse_args()

    print_logo()

    # Interactive chat: explicit --chat, or no query given at all
    if args.chat or not args.query:
        provider, model = _resolve_provider(args.model)
        run_ai_repl(provider, model)
        print()
        log_success("Goodbye!")
        print()
        return

    # Swarm: parallel multi-scope scrape
    if args.swarm:
        provider, model = _resolve_provider(args.model)
        asyncio.run(run_swarm(
            base_query=args.query,
            provider=provider,
            model=model,
            n=args.swarm,
            max_results=args.limit,
            no_website_only=args.no_website,
            output_file=args.output,
        ))
        return

    # One-shot scrape
    results = asyncio.run(run_scraper(
        query=args.query,
        max_results=args.limit,
        output_file=args.output,
        headless=not args.no_headless,
        no_website_only=args.no_website,
    ))

    # Optional AI analysis of the scraped results
    if args.ai:
        provider, model = _resolve_provider(args.model)
        messages = [
            {"role": "system", "content": AI_SYSTEM},
            {"role": "user", "content": (
                f"{args.ai}\n\nScraped results:\n{results_to_tool_content(results)}"
            )},
        ]
        spinner_start("Analyzing...")
        content, _ = ask_ai(messages, provider, model)
        spinner_end()
        if content:
            print(f"\n  {blue('AI')}  {content}\n")


def _selftest():
    """Assert-based self-check for normalize_response. No network."""
    # Fake OpenRouter response
    fake_or = {
        "choices": [{
            "message": {
                "content": "Here are the results.",
                "tool_calls": [
                    {"id": "call_1", "function": {"name": "search_businesses", "arguments": '{"query":"test","limit":5}'}}
                ]
            }
        }]
    }
    content, tool_calls = normalize_response(fake_or, "openrouter")
    assert content == "Here are the results.", f"OR content fail: {content!r}"
    assert len(tool_calls) == 1
    assert tool_calls[0]["function"]["name"] == "search_businesses"
    args = json.loads(tool_calls[0]["function"]["arguments"])
    assert args["query"] == "test"

    # Fake Ollama response
    fake_ol = {
        "message": {
            "content": "",
            "tool_calls": [
                {"id": "call_0", "function": {"name": "search_businesses", "arguments": {"query": "mechanics", "limit": 10}}}
            ]
        }
    }
    content2, tool_calls2 = normalize_response(fake_ol, "ollama")
    assert content2 == ""
    assert len(tool_calls2) == 1
    args2 = json.loads(tool_calls2[0]["function"]["arguments"])
    assert args2["query"] == "mechanics"

    # Unknown provider
    try:
        normalize_response({}, "unknown")
        assert False, "Should have raised"
    except ValueError:
        pass

    # parse_query_list — fenced JSON, cap at n, garbage → []
    fenced = 'Sure!\n```json\n["a", "b", "c", "d"]\n```'
    assert parse_query_list(fenced, 3) == ["a", "b", "c"]
    assert parse_query_list('["x","y"]', 5) == ["x", "y"]
    assert parse_query_list("no array here", 3) == []
    assert parse_query_list("", 3) == []

    print(green("✓") + "  Self-test passed.")


if __name__ == "__main__":
    main()
