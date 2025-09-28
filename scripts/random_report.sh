#!/usr/bin/env bash
            set -euo pipefail

            project=${1:-sample}
            seed=${2:-$RANDOM}

            hash=$(printf '%s:%s' "$project" "$seed" | shasum | cut -c1-12)
            metric=$((seed % 100 + 1))

            printf 'project=%s
seed=%s
hash=%s
metric=%s
' "$project" "$seed" "$hash" "$metric"
