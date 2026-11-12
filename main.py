"""Configuration, validation and append-only expense storage."""
import json
import os
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo


def load_settings(path=None):
    path = Path(path or os.environ.get('FINGRAM_CONFIG', 'vars/variables.local.json'))
    with path.open() as stream:
        settings = json.load(stream)
    sheets = settings['gsheet']['sheets']
    if len(sheets) != 1 or not all(k.isdecimal() and int(k) > 0 for k in sheets):
        raise ValueError('Configure exactly one positive Telegram user ID')
    secret = Path(settings['gsheet']['service_secret'])
    if not secret.is_absolute():
        secret = path.parent / secret
    settings['gsheet']['service_secret'] = str(secret)
    if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+', settings['telegram']['token']):
        raise ValueError('Invalid Telegram token configuration')
    for url in sheets.values():
        if not re.fullmatch(r'https://docs\.google\.com/spreadsheets/d/[A-Za-z0-9_-]+(?:/[^\s]*)?', url):
            raise ValueError('Invalid spreadsheet URL')
    ZoneInfo(settings.get('timezone', 'Europe/Tallinn'))
    return settings


def parse_expense(text):
    parts = text.strip().split(maxsplit=1)
    if len(parts) != 2 or not re.fullmatch(r'-?\d{1,10}(?:[.,]\d{1,2})?', parts[0]):
        raise ValueError('Use: 12.50 description (at most two decimal places)')
    description = parts[1].strip()
    if not description or len(description) > 500 or any(ord(c) < 32 for c in description):
        raise ValueError('Description must contain 1–500 characters without control characters')
    return float(Decimal(parts[0].replace(',', '.'))), description


class ExpenseStore:
    def __init__(self, settings):
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2.service_account import Credentials
        self.settings = settings
        credentials = Credentials.from_service_account_file(
            settings['gsheet']['service_secret'],
            scopes=['https://www.googleapis.com/auth/spreadsheets'])
        # No transport retries or automatic replay after a 401 on an append.
        self.session = AuthorizedSession(credentials, max_refresh_attempts=0)

    def append(self, user, amount, description):
        url = self.settings['gsheet']['sheets'][str(user)]
        spreadsheet_id = re.search(r'/d/([A-Za-z0-9_-]+)', url).group(1)
        endpoint = 'https://sheets.googleapis.com/v4/spreadsheets/' + spreadsheet_id
        response = self.session.get(endpoint, params={'fields': 'sheets(properties(sheetId,index))'},
                                    timeout=30, allow_redirects=False)
        response.raise_for_status()
        sheets = response.json()['sheets']
        sheet_id = min(sheets, key=lambda s: s['properties']['index'])['properties']['sheetId']
        today = datetime.now(ZoneInfo(self.settings.get('timezone', 'Europe/Tallinn'))).date()
        serial_date = (today - date(1899, 12, 30)).days
        # Typed cells store an actual date while keeping descriptions literal.
        # Append values and formatting together, without a second write or retries.
        response = self.session.post(
            endpoint + ':batchUpdate',
            json={'requests': [{'appendCells': {
                'sheetId': sheet_id,
                'rows': [{'values': [
                    {'userEnteredValue': {'numberValue': serial_date},
                     'userEnteredFormat': {'numberFormat': {'type': 'DATE', 'pattern': 'dd.mm.yyyy'}}},
                    {'userEnteredValue': {'numberValue': amount}},
                    {'userEnteredValue': {'stringValue': description}},
                ]}],
                'fields': 'userEnteredValue,userEnteredFormat.numberFormat',
            }}]},
            timeout=30, allow_redirects=False)
        response.raise_for_status()
        if response.status_code != 200:
            raise RuntimeError('Unexpected append response')
