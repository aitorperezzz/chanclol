package common

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sync"
)

type Database struct {
	filename string
	mu       *sync.Mutex
}

func NewDatabase(filename string) Database {
	return Database{filename: filename, mu: &sync.Mutex{}}
}

func (database *Database) Load(destination any) error {
	database.mu.Lock()
	defer database.mu.Unlock()

	data, err := os.ReadFile(database.filename)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil
		}
		return err
	}
	if len(data) == 0 {
		return nil
	}

	return json.Unmarshal(data, destination)
}

func (database *Database) Save(source any) error {
	database.mu.Lock()
	defer database.mu.Unlock()

	if dir := filepath.Dir(database.filename); dir != "." {
		if err := os.MkdirAll(dir, 0755); err != nil {
			return err
		}
	}

	data, err := json.MarshalIndent(source, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(database.filename, data, 0644)
}
