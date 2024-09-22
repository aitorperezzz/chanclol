package main

import (
	"chanclol/internal/bot"
	"chanclol/internal/riotapi"
	"fmt"
)

func main() {
	fmt.Println("Hello from inside chanclol")

	bot := bot.Bot{}
	fmt.Println(bot)
	riotapi := riotapi.RiotApi{}
	fmt.Println(riotapi)
}
