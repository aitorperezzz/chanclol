package main

import (
	"chanclol/internal/bot"
	"chanclol/internal/common"
	"chanclol/internal/riotapi"
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"strconv"
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
	zerolog.CallerMarshalFunc = func(pc uintptr, file string, line int) string {
		return filepath.Base(file) + ":" + strconv.Itoa(line)
	}
	zerolog.SetGlobalLevel(zerolog.DebugLevel)
	log.Logger = log.Output(zerolog.ConsoleWriter{Out: os.Stderr}).With().Caller().Logger()

	// Read configuration file
	jsonFile, err := os.Open("config.json")
	if err != nil {
		log.Error().Err(err)
		return
	}
	defer jsonFile.Close()
	// unmarshal
	byteValue, err := io.ReadAll(jsonFile)
	if err != nil {
		log.Error().Err(err)
		return
	}
	var config Config
	if err := json.Unmarshal(byteValue, &config); err != nil {
		log.Error().Err(err)
		return
	}

	// Create riot API
	log.Info().Msg("Creating riot API")
	restrictions := make([]common.Restriction, 0)
	for _, restriction := range config.Restrictions {
		restrictionDuration := time.Duration(int64(restriction.IntervalSeconds) * int64(time.Second))
		restrictions = append(restrictions, common.Restriction{Requests: restriction.NumRequests, Duration: restrictionDuration})
	}
	riotapi := riotapi.NewRiotApi(config.RiotapiDbFilename, riotapiKey, restrictions)

	// Create bot
	log.Info().Msg("Creating discord bot")
	riotapiHousekeeping := time.Duration(int64(config.RiotapiHousekeepingCycleHrs) * int64(60*60) * int64(time.Second))
	offlineThreshold := time.Duration(int64(config.OfflineThresholdMins) * int64(time.Minute))
	offlineTimeout := time.Duration(int64(config.OfflineTimeoutSecs) * int64(time.Second))
	onlineTimeout := time.Duration(int64(config.OnlineTimeoutSecs) * int64(time.Second))
	mainCycle := time.Duration(int64(config.MainLoopCycleSecs) * int64(time.Second))
	bot, err := bot.NewBot(discordToken, config.BotDbFilename, riotapiHousekeeping, offlineThreshold, offlineTimeout, onlineTimeout, mainCycle, &riotapi)
	if err != nil {
		log.Error().Msg("Could not create discord bot")
		return
	}

	// Run bot
	bot.Run()
}
