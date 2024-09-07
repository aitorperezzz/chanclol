FROM python:3.12-bookworm
RUN pip3 install discord.py python-dotenv
COPY . /app
WORKDIR /app
CMD python3 chanclol/main.py