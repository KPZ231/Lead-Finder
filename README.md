# 🔍 Firmoscope

> **Business lead scraper CLI powered by Playwright — free, fast, and runs entirely locally.**

Made by [KPZsProductions](https://github.com/KPZsProductions)

---

## What it does

Firmoscope searches Google Maps for businesses matching your query, then extracts contact details — phone numbers, email addresses, websites, and addresses — and saves them to a CSV file. Optionally filters to businesses **without a website** (prime leads), queries an AI model to analyse results, or exports directly to Google Sheets.

---

## Quick start

```bash
# Install
pip install playwright
playwright install chromium

# Run interactively
python firmoscope.py

# Run with arguments
python firmoscope.py "Rybnik Mechanicy"
python firmoscope.py "Katowice Restauracje" --limit 30
python firmoscope.py "Gliwice Dentyści" --limit 50 --output leady_dent.csv

# Only businesses without a website (best leads)
python firmoscope.py "Wrocław Hydraulicy" --no-website

# Watch the browser (non-headless)
python firmoscope.py "Kraków Fryzjer" --no-headless
```

---

## AI mode

Requires `OPENROUTER_API_KEY` set in your environment.

```bash
# One-shot AI question about the results
python firmoscope.py "Rybnik Mechanicy" --limit 10 --ai "które firmy nie mają strony?"

# Interactive chat session
python firmoscope.py "Rybnik Mechanicy" --limit 10 --chat

# Pick a specific model
python firmoscope.py "Rybnik Mechanicy" --chat --model "anthropic/claude-3.5-haiku"
```

---

## Output

CSV file with UTF-8-BOM encoding (opens cleanly in Excel/LibreOffice):

| Column | Description |
|---|---|
| `Nazwa` | Business name |
| `Telefon` | Phone number |
| `Email` | Email address |
| `Adres` | Street address |
| `Strona WWW` | Website URL |
| `Ma stronę` | Has website (Tak/Nie) |
| `Link Google Maps` | Direct Google Maps link |

---

## How it works

```
main()
 └─ run_scraper()          — opens Google Maps, scrolls feed, collects place links
     └─ scrape_business_details()   — extracts phone, address, website, email per place
         └─ try_scrape_website_for_email()  — if no email on Maps, checks /kontakt etc.
```

- Browser runs with Polish locale (`pl-PL`) and a real Chrome user-agent
- No paid APIs — pure Playwright scraping
- Zero external dependencies beyond `playwright` (and optionally `prompt_toolkit`)

---

## Requirements

- Python 3.9+
- `playwright` — `pip install playwright && playwright install chromium`
- `prompt_toolkit` *(optional)* — autocomplete in interactive mode
- `OPENROUTER_API_KEY` *(optional)* — AI analysis features

---

## Legal Notice

> **This tool is provided for educational and legitimate business research purposes only.**

- Firmoscope scrapes publicly visible information from Google Maps. Use of this tool must comply with [Google's Terms of Service](https://policies.google.com/terms) and any applicable local laws and regulations.
- The authors and contributors of this project **do not condone** the use of this software for spam, harassment, unsolicited marketing, or any activity that violates the privacy rights of individuals or organisations.
- Data collected through this tool may be subject to data protection regulations (e.g. GDPR in the European Union). You are solely responsible for how you store, process, and use any data you collect.
- **Use at your own risk.** The authors accept no liability for misuse of this software or for any consequences arising from its use.

---

<p align="center">
  Built with ❤️ by <a href="https://github.com/KPZsProductions">KPZsProductions</a>
</p>
