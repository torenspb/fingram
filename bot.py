from main import *
from telebot import TeleBot

bot = TeleBot(TOKEN)


@bot.message_handler(content_types=['text'])
def autorize_user(message):
    if message.from_user.id not in ALLOWED_IDs:
        bot.send_message(message.from_user.id,
                         "Sorry, you aren't allowed to use this bot. "
                         "Only VIP access. Please contact administrator "
                         "if you think you're VIP (ha-ha, nope).")
    else:
        try:
            add_costs(message.text)
            bot.send_message(message.from_user.id,
                             "Your cost has been added!")
        except:
            bot.send_message(message.from_user.id,
                             "Ops! Something gone wrong!")


if __name__ == '__main__':
    bot.polling(none_stop=True, interval=1)
