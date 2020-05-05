import os
import json
import pygsheets
from datetime import date

VAR_DIR = os.path.dirname(__file__)
VAR_FILE = '/variables.json'

with open(VAR_DIR + VAR_FILE, 'r') as f:
    settings = json.load(f)

SHEET_NAME = settings['gsheet_name']
SERVICE_KEY = VAR_DIR + '/' + settings['gsheet_service_secret']
TOKEN = settings['telegram']['token']
ALLOWED_IDs = settings['telegram']['allowed_users']


def get_sheet(name, secret_path):
    gc = pygsheets.authorize(service_file=secret_path)
    sh = gc.open(name)
    sheet = sh.sheet1
    return sheet


def get_empty_row(sheet, col):
    all_cols = sheet.get_col(col, returnas='cell', include_tailing_empty=False)
    last_col = all_cols[-1].address.index
    next_row = last_col[0] + 1
    return next_row


def add_row(sheet, index, values):
    sheet.update_row(index, values)


def add_costs(message):
    note = message.split(' ', 1)
    current_date = date.today().strftime("%d.%m.%Y")
    note.insert(0, current_date)
    my_sheet = get_sheet(SHEET_NAME, SERVICE_KEY)
    next_empty_row = get_empty_row(my_sheet, 1)
    add_row(my_sheet, next_empty_row, note)
