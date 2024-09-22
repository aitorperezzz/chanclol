package main

import (
	"chanclol/internal/bot"
	"chanclol/internal/common"
	"chanclol/internal/riotapi"
	"fmt"
	"time"
)

func main() {
	fmt.Println("Hello from inside chanclol")

	// TODO: create Discord client

	// Create riot API
	var riotapiDbFilename string
	var apiKey string
	var restrictions []common.Restriction
	riotapi := riotapi.CreateRiotApi(riotapiDbFilename, apiKey, restrictions)
	fmt.Println(riotapi)

	// Create bot
	var botDbFilename string
	var riotapiHousekeeping, offlineThreshold, offlineTimeout, onlineTimeout, mainCycle time.Duration
	bot := bot.CreateBot(botDbFilename, riotapiHousekeeping, offlineThreshold, offlineTimeout, onlineTimeout, mainCycle, &riotapi)
	fmt.Println(bot)

}
