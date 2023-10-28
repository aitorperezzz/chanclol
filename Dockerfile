FROM python:3.10-bullseye
RUN pip3 install discord.py python-dotenv
COPY . /app
WORKDIR /app
CMD python3 main.py