FROM golang:1.23.1-bookworm
COPY . /app
WORKDIR /app
RUN go build
CMD go run chanclol
