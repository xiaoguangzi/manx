package main

import (
	"os"

	"github.com/xiaoguangzi/manx/internal/manx"
)

func main() {
	os.Exit(manx.Run(os.Args[1:]))
}
