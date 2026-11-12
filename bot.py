"""Single-user Telegram expense bot."""
import logging
import time

from main import ExpenseStore, load_settings, parse_expense

LOG = logging.getLogger('fingram')


def notify(bot, chat_id, text):
    try:
        bot.send_message(chat_id, text)
    except Exception as error:
        LOG.warning('Notification failed (%s)', type(error).__name__)


def handle_message(bot, store, allowed_id, message):
    if (message.from_user is None or message.from_user.id != allowed_id
            or message.chat.type != 'private' or message.chat.id != allowed_id):
        return
    try:
        amount, description = parse_expense(message.text)
    except ValueError as error:
        notify(bot, allowed_id, str(error))
        return
    try:
        store.append(allowed_id, amount, description)
    except Exception as error:
        LOG.error('Spreadsheet operation failed (%s)', type(error).__name__)
        notify(bot, allowed_id, 'Could not confirm the write. Check the sheet before resending; it may already be saved.')
        return
    notify(bot, allowed_id, 'Your cost has been added!')


def run():
    from telebot import TeleBot, apihelper
    # Third-party exceptions can include request URLs, tokens or message bodies.
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    logging.getLogger().setLevel(logging.CRITICAL)
    LOG.setLevel(logging.INFO)
    logging.getLogger('TeleBot').disabled = True
    apihelper.RETRY_ON_ERROR = False
    settings = load_settings()
    allowed_id = int(next(iter(settings['gsheet']['sheets'])))
    store = ExpenseStore(settings)
    bot = TeleBot(settings['telegram']['token'], threaded=False)
    bot.register_message_handler(
        lambda message: handle_message(bot, store, allowed_id, message), content_types=['text'])
    while True:
        try:
            bot.polling(non_stop=True, interval=1, timeout=30,
                        long_polling_timeout=20, allowed_updates=['message'])
            return
        except Exception as error:
            LOG.warning('Polling interrupted (%s); reconnecting', type(error).__name__)
            time.sleep(5)


if __name__ == '__main__':
    try:
        run()
    except Exception as error:
        LOG.critical('Startup failed (%s); check configuration and credentials', type(error).__name__)
        raise SystemExit(1) from None
