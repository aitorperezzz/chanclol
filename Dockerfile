FROM golang:1.23.1-bookworm AS builder

WORKDIR /src

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN go test ./...
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/chanclol .

FROM gcr.io/distroless/static-debian12

WORKDIR /app

COPY --from=builder /out/chanclol /app/chanclol
COPY --from=builder /src/config.json /app/config.json

CMD ["/app/chanclol"]
