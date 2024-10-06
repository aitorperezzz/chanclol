package common

import (
	"time"
)

// A restriction means that only the specified number of requests
// are allowed for a specific time duration
type Restriction struct {
	Requests int
	Duration time.Duration
}

// Analyse the recent history of requests and find out
// if a new request at the current time should be allowed or not
func (rest *Restriction) Analyse(history *[]time.Time) Analysis {

	// If there is no history, simply allow
	if len(*history) == 0 {
		return Analysis{allowed: true}
	}

	// Count the number of requests that have been served in my duration.
	// Start counting from the end.
	// If one request is too old, the rest will be too
	currentTime := time.Now()
	count := 0
	for i := len(*history) - 1; i >= 0; i-- {
		if (*history)[i].Add(rest.Duration).Before(currentTime) {
			break
		} else {
			count++
		}
	}
	// If there are no requests served in my duration, simply allow
	if count == 0 {
		return Analysis{allowed: true}
	}

	// Finally decide
	oldestRequestTime := (*history)[len(*history)-count]
	if count >= rest.Requests {
		// I need to wait at least until the oldest request exits my duration
		return Analysis{allowed: false, wait: oldestRequestTime.Sub(currentTime.Add(-rest.Duration)) + time.Duration(10*time.Millisecond)}
	} else {
		return Analysis{allowed: true}
	}
}
