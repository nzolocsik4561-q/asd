package main

import (
    "crypto/sha1"
    "encoding/hex"
    "fmt"
    "os"
)

func checksum(parts ...string) string {
    h := sha1.New()
    for _, part := range parts {
        h.Write([]byte(part))
    }
    return hex.EncodeToString(h.Sum(nil))[:12]
}

func main() {
    args := os.Args[1:]
    if len(args) == 0 {
        fmt.Println(checksum("codex", "demo"))
        return
    }
    fmt.Println(checksum(args...))
}
