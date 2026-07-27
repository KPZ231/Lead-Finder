# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install playwright
playwright install chromium

# Run (interactive prompt)
python firmoscope.py

# Run with args
python firmoscope.py "Rybnik Mechanicy"
python firmoscope.py "Katowice Restauracje" --limit 30
python firmoscope.py "Gliwice Dentyści" --limit 50 --output leady_dent.csv
python firmoscope.py "Wrocław Hydraulicy" --no-website
python firmoscope.py "Kraków Fryzjer" --no-headless

# Tryb AI (wymaga OPENROUTER_API_KEY w env)
python firmoscope.py "Rybnik Mechanicy" --limit 10 --ai "które firmy nie mają strony?"
python firmoscope.py "Rybnik Mechanicy" --limit 10 --chat
python firmoscope.py "Rybnik Mechanicy" --chat --model "anthropic/claude-3.5-haiku"

# Swarm — AI splits the query into K sub-scopes, scrapes them in parallel, merges to one CSV
python firmoscope.py "Rybnik Mechanicy" --swarm 3 --limit 20
# In chat: /swarm Rybnik Mechanicy --limit 20 --agents 3
```

## Architecture

Single-file scraper (`firmoscope.py`). `main.py` is empty.

**Flow:**
1. `main()` — parses CLI args or prompts interactively, auto-generates CSV filename
2. `run_scraper()` — launches Playwright Chromium, opens Google Maps, scrolls the results feed to collect `a[href*="/maps/place/"]` links (up to `--limit`)
3. `scrape_business_details()` — visits each place URL, extracts phone (aria-label selectors + regex fallback), address, website, and email from page HTML
4. `try_scrape_website_for_email()` — if no email found on Maps, visits the business website and tries `/kontakt`, `/contact`, `/o-nas`, `/about` paths
5. Results written to UTF-8-sig CSV

**Key details:**
- Language: Polish UI strings throughout (errors, prompts, CSV column headers)
- CSV columns: `Nazwa`, `Telefon`, `Email`, `Adres`, `Strona WWW`, `Ma stronę`, `Link Google Maps`
- `--no-website` flag filters to businesses without a website (lead generation use case)
- Browser launched with Polish locale (`pl-PL`) and a real Chrome UA to reduce bot detection
- No external deps beyond `playwright`; regex-only email/phone extraction
