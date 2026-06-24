"""
Google Sheets export for Firmoscope.
Requires: gspread, google-auth-oauthlib
OAuth2 client secret: place client_secret.json in ~/.config/firmoscope/ or project dir.
Token cached at ~/.config/firmoscope/token.json after first login.
"""

from pathlib import Path
import sys

CONFIG_DIR = Path.home() / ".config" / "firmoscope"
TOKEN_PATH = CONFIG_DIR / "token.json"
SECRET_PATHS = [
    CONFIG_DIR / "client_secret.json",
    Path("client_secret.json"),
]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = ["Nazwa", "Telefon", "Email", "Adres", "Strona WWW", "Ma stronę", "Link Google Maps"]


def _find_secret() -> Path:
    for p in SECRET_PATHS:
        if p.exists():
            return p
    raise FileNotFoundError(
        "Nie znaleziono client_secret.json.\n"
        f"Pobierz go z Google Cloud Console i wrzuć do:\n  {SECRET_PATHS[0]}\nlub katalogu projektu."
    )


def _get_client():
    try:
        import gspread
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
    except ImportError:
        print("\n  [ERROR] Brakuje zależności. Uruchom:\n  pip install gspread google-auth-oauthlib\n")
        sys.exit(1)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        # ponytail: if saved token lacks required scopes, force re-auth
        if creds and not all(s in (creds.scopes or []) for s in SCOPES):
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            secret = _find_secret()
            flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    return gspread.Client(auth=creds)


def export(results: list, sheet_id: str = None) -> str:
    """
    Export results to Google Sheets.
    sheet_id=None → create new sheet.
    Returns the URL of the sheet.
    """
    import gspread

    gc = _get_client()
    rows = [
        [
            r.get("name", ""),
            r.get("phone", ""),
            r.get("email", ""),
            r.get("address", ""),
            r.get("website", ""),
            "Tak" if r.get("website") else "Nie",
            r.get("maps_url", ""),
        ]
        for r in results
    ]

    if sheet_id:
        try:
            sh = gc.open_by_url(sheet_id) if sheet_id.startswith("http") else gc.open_by_key(sheet_id)
            ws = sh.sheet1
            if ws.row_count == 0 or ws.cell(1, 1).value != "Nazwa":
                ws.insert_row(HEADERS, 1)
            ws.append_rows(rows)
        except gspread.exceptions.SpreadsheetNotFound:
            raise ValueError(f"Nie znaleziono arkusza: {sheet_id}")
    else:
        from datetime import datetime
        title = f"Firmoscope {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        sh = gc.create(title)
        sh.share(None, perm_type="anyone", role="reader")
        ws = sh.sheet1
        ws.append_row(HEADERS)
        ws.append_rows(rows)

    return f"https://docs.google.com/spreadsheets/d/{sh.id}"
