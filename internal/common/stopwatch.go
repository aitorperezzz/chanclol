package common

import (
	"time"
)

// This stopwatch keeps track of time. You can set a timeout for it,
// make it start counting time, and ask it if the timeout has been reached
type Stopwatch struct {
	timeout   time.Duration
	startTime time.Time
	running   bool
}

func CreateStopwatch(timeout time.Duration) Stopwatch {
	return Stopwatch{timeout, time.Time{}, false}
}

func (s *Stopwatch) Start() {
	s.running = true
	s.startTime = time.Now()
}

func (s *Stopwatch) Stop() {
	s.running = false
}

// Return the time elapsed since this stopwatch
// stopped (reached its timeout).
// Note that if the number is negative, the timeout still
// has not been reached
func (s *Stopwatch) TimeStopped() time.Duration {
	currentTime := time.Now()
	return currentTime.Sub(s.startTime.Add(s.timeout))
}
