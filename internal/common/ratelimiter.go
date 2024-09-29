package common

import (
	"fmt"
	"math"
	"time"

	"github.com/google/uuid"
	"github.com/rs/zerolog/log"
)

type Analysis struct {
	allowed bool          // If the request is allowed
	wait    time.Duration // The minimal time to wait before the request is allowed
}

type RateLimiter struct {
	restrictions         []Restriction          // Restrictions to consider
	history              []time.Time            // History of requests
	duration             time.Duration          // Min duration to wait for all restrictions to be lifted
	pendingVitalRequests map[uuid.UUID]struct{} // Set of pending vital requests
	stopwatch            Stopwatch
}

func NewRateLimiter(restrictions []Restriction) RateLimiter {
	rl := RateLimiter{}
	// Restrictions are just a copy of the provided ones
	copy(rl.restrictions, restrictions)
	// Duration
	rl.duration = math.MinInt
	for i := 0; i < len(restrictions); i++ {
		if restrictions[i].Duration > rl.duration {
			rl.duration = restrictions[i].Duration
		}
	}
	// Initialise a stopwatch
	rl.stopwatch.Timeout = rl.duration

	return rl
}

// Decide if request is allowed.
// If the request is not allowed but vital, execution
// will block here until it is allowed
func (rl *RateLimiter) Allowed(vital bool, allowed chan bool) {

	// Give this request a unique identifier
	thisuuid := uuid.New()
	for {
		// Trim history first
		rl.trim()
		// Check if the restrictions allow this request
		analysis := rl.analyse()
		if analysis.allowed {
			if vital || (!vital && len(rl.pendingVitalRequests) == 0) {
				log.Debug().Msg("Allowing request")
				// Remove the uuid in case it is there
				for uuid := range rl.pendingVitalRequests {
					if thisuuid == uuid {
						delete(rl.pendingVitalRequests, thisuuid)
					}
				}
				// Include this request in the history as it is allowed
				rl.history = append(rl.history, time.Now())
				allowed <- true
				return

			} else {
				// Request is not vital and the queue is not empty,
				// so we have to reject the request
				log.Warn().Msg("Rejecting non vital request because restrictions allow it but vital queue is not empty")
				allowed <- false
				return
			}
		} else if !vital {
			log.Warn().Msg("Rejecting a non vital request because restrictions do not allow it")
			allowed <- false
			return
		} else {
			// Request is vital and not allowed, so we need
			// to add it to the queue if not there
			_, ok := rl.pendingVitalRequests[thisuuid]
			if !ok {
				rl.pendingVitalRequests[thisuuid] = struct{}{}
			}
			// and sleep for some time
			log.Warn().Msg(fmt.Sprint("Vital request", thisuuid, "delayed", analysis.wait.Seconds(), "seconds"))
			go func() {
				time.Sleep(analysis.wait)
			}()
		}
	}
}

func (rl *RateLimiter) ReceivedRateLimit() {
	rl.stopwatch.Start()
}

// Trim the current history, leaving only the requests
// that are young enough to be affected by at least one restriction
func (rl *RateLimiter) trim() {
	currentTime := time.Now()
	// Find the index from which we need to keep the history.
	// Start searching at the end of the slice.
	// I assume times are stored in chronological order
	index := 0
	for i := len(rl.history) - 1; i >= 0; i-- {
		if currentTime.Sub(rl.history[i]) > rl.duration {
			index = i + 1
			break
		}
	}
	rl.history = rl.history[index:]
}

func (rl *RateLimiter) analyse() Analysis {

	// Perform an analysis for each of the restrictions
	analyses := make([]Analysis, 0)
	for _, restriction := range rl.restrictions {
		analyses = append(analyses, restriction.Analyse(rl.history))
	}

	// Merge the analyses and return
	var wait time.Duration = 0
	allowed := true
	for _, analysis := range analyses {
		allowed = allowed && analysis.allowed
		if analysis.wait > wait {
			wait = analysis.wait
		}
	}
	return Analysis{allowed, wait}
}
