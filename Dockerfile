FROM python:3.6-alpine

RUN pip3 install pygsheets pytelegrambotapi

ADD / /opt/fingram/

CMD ["python", "/opt/fingram/bot.py"]