package common

import (
	"time"
)

// This stopwatch keeps track of time. You can set a timeout for it,
// make it start counting time, and ask it if the timeout has been reached
type Stopwatch struct {
	Timeout   time.Duration
	startTime time.Time
	Running   bool
}

func NewStopwatch(timeout time.Duration) Stopwatch {
	return Stopwatch{timeout, time.Time{}, false}
}

func (s *Stopwatch) Start() {
	s.Running = true
	s.startTime = time.Now()
}

func (s *Stopwatch) Stop() {
	s.Running = false
}

// Return a boolean indicating if the stopwatch is already stopped.
// Additionally, return a duration:
// - If stopped, the duration signifies the time the stopwatch has been stopped
// - If not stopped, the duration signifies the time needed for the stopwatch to stop
func (s *Stopwatch) Stopped() (bool, time.Duration) {
	currentTime := time.Now()
	if s.startTime.Add(s.Timeout).Before(currentTime) {
		return true, currentTime.Sub(s.startTime.Add(s.Timeout))
	} else {
		return false, s.startTime.Add(s.Timeout).Sub(currentTime)
	}
}
