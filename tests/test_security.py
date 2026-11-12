import json
from datetime import datetime, date
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from bot import handle_message
from main import ExpenseStore, load_settings, parse_expense


class SecurityTests(unittest.TestCase):
    def message(self, user=123, chat='private'):
        return NS(from_user=NS(id=user), chat=NS(id=user, type=chat), text='12.50 =1+1')

    def test_unauthorized_and_group_messages_are_silent(self):
        for message in [self.message(456), self.message(chat='group'),
                        NS(from_user=None, chat=NS(type='channel'))]:
            bot, store = Mock(), Mock()
            handle_message(bot, store, 123, message)
            bot.send_message.assert_not_called()
            store.append.assert_not_called()

    def test_validation(self):
        for text in ['nan lunch', 'inf lunch', '=1+1 lunch', '1.123 lunch',
                     '1', '1 ' + 'a' * 501, '1 hello\nworld', '10000000000 lunch']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_expense(text)
        self.assertEqual(parse_expense('-12,50 refund'), (-12.5, 'refund'))
        self.assertEqual(parse_expense('12 =1+1'), (12, '=1+1'))

    def test_invalid_input_never_writes(self):
        bot, store = Mock(), Mock()
        message = self.message()
        message.text = 'nan lunch'
        handle_message(bot, store, 123, message)
        store.append.assert_not_called()

    def test_notification_failure_does_not_repeat_write_or_leak(self):
        bot, store = Mock(), Mock()
        bot.send_message.side_effect = RuntimeError('SECRET_TOKEN')
        with self.assertLogs('fingram') as logs:
            handle_message(bot, store, 123, self.message())
        store.append.assert_called_once_with(123, 12.5, '=1+1')
        self.assertEqual(bot.send_message.call_count, 1)
        self.assertNotIn('SECRET_TOKEN', str(logs.output))

    def test_uncertain_write_is_not_retried(self):
        bot, store = Mock(), Mock()
        store.append.side_effect = TimeoutError('SECRET_DATA')
        with self.assertLogs('fingram') as logs:
            handle_message(bot, store, 123, self.message())
        store.append.assert_called_once()
        self.assertIn('Check the sheet', bot.send_message.call_args.args[1])
        self.assertNotIn('SECRET_DATA', str(logs.output))

    def test_typed_date_append_and_no_retry_on_timeout(self):
        store = ExpenseStore.__new__(ExpenseStore)
        store.settings = {'gsheet': {'sheets': {'123': 'https://docs.google.com/spreadsheets/d/abc/edit'}}}
        store.session = Mock()
        store.session.get.return_value.json.return_value = {
            'sheets': [{'properties': {'index': 0, 'sheetId': 42}}]}
        store.session.post.side_effect = TimeoutError()
        with patch('main.datetime') as clock:
            clock.now.return_value = datetime(2026, 11, 12)
            with self.assertRaises(TimeoutError):
                store.append(123, 12.5, '=1+1')
        store.session.post.assert_called_once()
        args = store.session.post.call_args.kwargs
        request = args['json']['requests'][0]['appendCells']
        self.assertEqual(request['sheetId'], 42)
        cells = request['rows'][0]['values']
        self.assertEqual(cells[0]['userEnteredValue'],
                         {'numberValue': (date(2026, 11, 12) - date(1899, 12, 30)).days})
        self.assertEqual(cells[0]['userEnteredFormat']['numberFormat'],
                         {'type': 'DATE', 'pattern': 'dd.mm.yyyy'})
        self.assertEqual(cells[1]['userEnteredValue'], {'numberValue': 12.5})
        self.assertEqual(cells[2]['userEnteredValue'], {'stringValue': '=1+1'})
        self.assertFalse(args['allow_redirects'])
        self.assertEqual(args['timeout'], 30)

    def test_configuration_is_explicit_and_single_user(self):
        settings = {'gsheet': {'service_secret': 'key.json', 'sheets': {
            '123': 'https://docs.google.com/spreadsheets/d/abc/edit'}},
            'telegram': {'token': '123:abc'}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps(settings))
            loaded = load_settings(path)
            self.assertEqual(loaded['gsheet']['service_secret'], str(Path(directory) / 'key.json'))
            settings['gsheet']['sheets']['456'] = settings['gsheet']['sheets']['123']
            path.write_text(json.dumps(settings))
            with self.assertRaises(ValueError):
                load_settings(path)

    def test_authorized_session_does_not_replay_writes(self):
        with patch('google.oauth2.service_account.Credentials.from_service_account_file') as credentials:
            store = ExpenseStore({'gsheet': {'service_secret': 'unused'}})
        self.assertEqual(store.session._max_refresh_attempts, 0)
        self.assertEqual(store.session.get_adapter('https://').max_retries.total, 0)
        credentials.assert_called_once()


if __name__ == '__main__':
    unittest.main()
