package main

import (
	"chanclol/internal/bot"
	"chanclol/internal/common"
	"chanclol/internal/riotapi"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"time"

	"github.com/joho/godotenv"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
)

type Config struct {
	LogFilename                 string `json:"log_filename"`
	BotDbFilename               string `json:"database_filename_bot"`
	RiotapiDbFilename           string `json:"database_filename_riotapi"`
	OfflineThresholdMins        int    `json:"offline_threshold_mins"`
	OnlineTimeoutSecs           int    `json:"timeout_online_secs"`
	OfflineTimeoutSecs          int    `json:"timeout_offline_secs"`
	MainLoopCycleSecs           int    `json:"main_loop_cycle_secs"`
	RiotapiHousekeepingCycleHrs int    `json:"riotapi_housekeeping_cycle_hrs"`
	Restrictions                []struct {
		NumRequests     int `json:"num_requests"`
		IntervalSeconds int `json:"interval_seconds"`
	} `json:"restrictions"`
}

func main() {

	// .env variables
	err := godotenv.Load()
	if err != nil {
		log.Fatal().Msg("Error loading .env file")
		return
	}
	riotapiKey := os.Getenv("RIOT_API_KEY")
	discordToken := os.Getenv("DISCORD_TOKEN")

	// Configure logger
	// TODO: read log level from config file
	zerolog.SetGlobalLevel(zerolog.DebugLevel)
	log.Logger = log.Output(zerolog.ConsoleWriter{Out: os.Stderr}).With().Caller().Logger()

	// Read configuration file
	jsonFile, err := os.Open("config.json")
	if err != nil {
		fmt.Println(err)
		return
	}
	defer jsonFile.Close()
	// unmarshal
	byteValue, err := io.ReadAll(jsonFile)
	if err != nil {
		fmt.Println(err)
		return
	}
	var config Config
	if json.Unmarshal(byteValue, &config) != nil {
		fmt.Println("Could not unmarshal configuration file")
		return
	}

	// Create riot API
	fmt.Println("Creating Riot API")
	restrictions := make([]common.Restriction, len(config.Restrictions))
	for _, restriction := range config.Restrictions {
		restrictionDuration := time.Duration(int64(restriction.IntervalSeconds) * int64(time.Second))
		restrictions = append(restrictions, common.Restriction{Requests: restriction.NumRequests, Duration: restrictionDuration})
	}
	riotapi := riotapi.CreateRiotApi(config.RiotapiDbFilename, riotapiKey, restrictions)

	// Create bot
	fmt.Println("Creating bot")
	riotapiHousekeeping := time.Duration(int64(config.RiotapiHousekeepingCycleHrs) * int64(60*60) * int64(time.Second))
	offlineThreshold := time.Duration(int64(config.OfflineThresholdMins) * int64(time.Minute))
	offlineTimeout := time.Duration(int64(config.OfflineTimeoutSecs) * int64(time.Second))
	onlineTimeout := time.Duration(int64(config.OnlineTimeoutSecs) * int64(time.Second))
	mainCycle := time.Duration(int64(config.MainLoopCycleSecs) * int64(time.Second))
	bot, err := bot.CreateBot(discordToken, config.BotDbFilename, riotapiHousekeeping, offlineThreshold, offlineTimeout, onlineTimeout, mainCycle, &riotapi)
	if err != nil {
		fmt.Printf("Could not create discord bot")
		return
	}

	// Run bot
	bot.Run()
}
