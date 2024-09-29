package common

import (
	"time"
)

// Give the timed executor a task and a timeout.
// Call the execute function from time to time.
// If the function gets called when the timeout has been reached,
// the provided task will execute. If not, the call will do nothing
type TimedExecutor struct {
	stopwatch Stopwatch
	task      func()
}

// Create a timed executor provided a timeout and a task
func CreateTimedExecutor(timeout time.Duration, task func()) TimedExecutor {
	return TimedExecutor{CreateStopwatch(timeout), task}
}

// Execute the task if the timeout has been reached, else do nothing
func (te *TimedExecutor) Execute() {
	if te.stopwatch.TimeStopped() > 0 {
		te.stopwatch.Start()
		te.task()
	}
}
