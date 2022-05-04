FROM python:3.6-alpine
RUN pip3 install --no-cache-dir pygsheets==2.0.5 pytelegrambotapi==4.5.0
WORKDIR /opt/fingram/
COPY bot.py .
COPY main.py .
ENTRYPOINT ["python"]
CMD ["bot.py"]