#!/bin/bash
# exe 를 만드는 데 필요한 도구(Go, go-winres)를 프로젝트 안 .tools 에 받는다. 한 번만 하면 된다.
#   bash tools/setup_build_tools.sh
set -euo pipefail
cd "$(dirname "$0")/.."
T="$(pwd)/.tools"
GOV=1.23.4
mkdir -p "$T"
if [ ! -x "$T/go/bin/go" ]; then
  ARCH=$(uname -m); [ "$ARCH" = "x86_64" ] && ARCH=amd64
  curl -sSfL -o "$T/go.tgz" "https://go.dev/dl/go$GOV.darwin-$ARCH.tar.gz"
  tar -xzf "$T/go.tgz" -C "$T" && rm -f "$T/go.tgz"
fi
if [ ! -x "$T/bin/go-winres" ]; then
  GOPATH="$T/gopath" GOBIN="$T/bin" GOCACHE="$T/gocache" "$T/go/bin/go" install github.com/tc-hib/go-winres@v0.3.3
fi
"$T/go/bin/go" version
ls "$T/bin"
