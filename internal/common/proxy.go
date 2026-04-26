package common

import (
	"fmt"
	"io"
	"net/http"
	"strconv"
	"time"

	"github.com/rs/zerolog/log"
)

const (
	OK                     int = 200
	BAD_REQUEST            int = 400
	UNAUTHORIZED           int = 401
	FORBIDDEN              int = 403
	DATA_NOT_FOUND         int = 404
	METHOD_NOT_ALLOWED     int = 405
	UNSUPPORTED_MEDIA_TYPE int = 415
	RATE_LIMIT_EXCEEDED    int = 429
	INTERNAL_SERVER_ERROR  int = 500
	BAD_GATEWAY            int = 502
	SERVICE_UNAVAILABLE    int = 503
	GATEWAY_TIMEOUT        int = 504
)

var messages = map[int]string{
	OK:                     "OK",
	BAD_REQUEST:            "Bad request",
	UNAUTHORIZED:           "Unauthorized",
	FORBIDDEN:              "Forbidden",
	DATA_NOT_FOUND:         "Data not found",
	METHOD_NOT_ALLOWED:     "Method not allowed",
	UNSUPPORTED_MEDIA_TYPE: "Unsupported media type",
	RATE_LIMIT_EXCEEDED:    "Rate limit exceeded",
	INTERNAL_SERVER_ERROR:  "Internal server error",
	BAD_GATEWAY:            "Bad gateway",
	SERVICE_UNAVAILABLE:    "Service unavailable",
	GATEWAY_TIMEOUT:        "Gateway timeout",
}

type Proxy struct {
	header      map[string]string
	client      http.Client
	rateLimiter RateLimiter
}

func NewProxy(header map[string]string, restrictions []Restriction) Proxy {
	return Proxy{header, http.Client{}, NewRateLimiter(restrictions)}
}

// Make a request to the provided url, indicating if it is vital.
// The request will be performed depending on the status of the rate limiter
func (proxy *Proxy) Request(url string, vital bool) []byte {

	// ask for permission to execute the request
	// and wait if necessary
	allowedChan := make(chan bool)
	go proxy.rateLimiter.Allowed(vital, allowedChan)
	allowed := <-allowedChan
	if !allowed {
		log.Warn().Msg("Rate limiter is not allowing the request")
		return nil
	}

	// Create the request and add the header
	request, err := http.NewRequest("GET", url, nil)
	if err != nil {
		log.Error().Msg(fmt.Sprintf("Could not create request for url %s", url))
		return nil
	}
	for key, value := range proxy.header {
		request.Header.Set(key, value)
	}

	// Perform the request
	res, err := proxy.client.Do(request)
	if err != nil {
		log.Error().Msg("Could not perform request")
		return nil
	}
	defer res.Body.Close()

	// Check if the status of the request is understood
	message, ok := messages[res.StatusCode]
	if !ok {
		log.Error().Msg(fmt.Sprintf("Status code of request (%d) is not understood", res.StatusCode))
		return nil
	}

	logMessage := fmt.Sprintf("%d %s", res.StatusCode, message)
	switch res.StatusCode {
	case OK:
		log.Debug().Msg(logMessage)
		// Read the response
		stream, err := io.ReadAll(res.Body)
		if err != nil {
			log.Debug().Msg(fmt.Sprintf("Could not extract the response for url %s", url))
			return nil
		}
		return stream
	case DATA_NOT_FOUND:
		log.Debug().Msg(logMessage)
		return nil
	case RATE_LIMIT_EXCEEDED:
		log.Warn().Msg(logMessage)
		proxy.rateLimiter.ReceivedRateLimit(retryAfter(res.Header))
		return nil
	default:
		log.Error().Msg(logMessage)
		// Read body for more info
		bodyBytes, err := io.ReadAll(res.Body)
		if err != nil {
			log.Error().Err(err).Msg("Could not read response body")
			return nil
		}
		// Print the raw body
		log.Error().Msgf("Body: %s", string(bodyBytes))
		// Print headers (useful for rate limits!)
		for key, val := range res.Header {
			log.Debug().Msgf("Header %s: %v", key, val)
		}
		return nil
	}
}

func retryAfter(header http.Header) time.Duration {
	for _, name := range []string{"Retry-After", "X-Rate-Limit-Reset-After"} {
		value := header.Get(name)
		if value == "" {
			continue
		}
		seconds, err := strconv.ParseFloat(value, 64)
		if err != nil {
			log.Warn().Err(err).Msg(fmt.Sprintf("Could not parse %s header %q", name, value))
			continue
		}
		return time.Duration(seconds*float64(time.Second)) + 250*time.Millisecond
	}

	return 0
}
