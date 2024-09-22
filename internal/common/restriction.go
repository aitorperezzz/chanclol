package common

import "time"

// A restriction means that only the specified number of requests
// are allowed for a specific time duration
type Restriction struct {
	requests int
	duration time.Duration
}

// Analyse the recent history of requests and find out
// if a new request at the current time should be allowed or not
func (rest *Restriction) Analyse(history []time.Time) Analysis {

	// Compute the number of requests that have been served in my duration.
	// Start counting from the end.
	// If one request is too old, the rest will be too
	currentTime := time.Now()
	count := 0
	for i := len(history) - 1; i >= 0; i-- {
		if currentTime.Sub(history[i]) > rest.duration {
			break
		} else {
			count++
		}
	}
	oldestRequestTime := history[len(history)-count]

	// Return the result of the analysis
	if count >= rest.requests {
		return Analysis{false, oldestRequestTime.Sub(currentTime.Add(-rest.duration))}
	} else {
		return Analysis{true, 0}
	}
}
