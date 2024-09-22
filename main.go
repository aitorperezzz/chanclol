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

	// Create riot API
	var riotapiDbFilename string
	var apiKey string
	var restrictions []common.Restriction
	riotapi := riotapi.CreateRiotApi(riotapiDbFilename, apiKey, restrictions)
	fmt.Println(riotapi)

	// Create bot
	var discordToken string
	var botDbFilename string
	var riotapiHousekeeping, offlineThreshold, offlineTimeout, onlineTimeout, mainCycle time.Duration
	bot, err := bot.CreateBot(discordToken, botDbFilename, riotapiHousekeeping, offlineThreshold, offlineTimeout, onlineTimeout, mainCycle, &riotapi)
	if err != nil {
		fmt.Printf("Could not create discord bot")
		return
	}
	fmt.Println(bot)

	// Run bot
	bot.Run()
}
