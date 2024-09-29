FROM golang:1.23.1-bookworm
COPY . /app
RUN go build
CMD go run chanclol