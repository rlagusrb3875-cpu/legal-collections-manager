#!/bin/bash
# Mac에서 Windows용 실행 파일 하나(종합관리.exe)를 만든다.
#   GO=/경로/go GOBIN_DIR=/경로/bin PYTHON=/경로/python bash tools/build_windows.sh
# 결과: dist/종합관리.exe  +  dist/종합관리_v<버전>.zip (exe + 안내문, 메일 첨부용)
# exe 안에 파이썬·부품·프로그램이 모두 들어 있고, 처음 실행 때 %LOCALAPPDATA%\CourtSearch 에 풀린다.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PYV=3.12.10
NAME="CourtSearch"
ZIPNAME="종합관리"
VER=$(grep -E '^VERSION' app/bridge.py | cut -d'"' -f2)
CACHE="$ROOT/build/cache"
OUT="$ROOT/build/$NAME"
DIST="$ROOT/dist"
# 도구: 프로젝트 안 .tools (tools/setup_build_tools.sh 로 받음)가 있으면 그것을 쓴다
TOOLS="$ROOT/.tools"
if [ -z "${GO:-}" ] && [ -x "$TOOLS/go/bin/go" ]; then GO="$TOOLS/go/bin/go"; GOBIN_DIR="$TOOLS/bin"; fi
GO=${GO:-go}
GOBIN_DIR=${GOBIN_DIR:-$("$GO" env GOPATH)/bin}
export GOCACHE=${GOCACHE:-$TOOLS/gocache} GOPATH=${GOPATH:-$TOOLS/gopath} GOFLAGS=${GOFLAGS:--mod=mod}
PY=${PYTHON:-python3}

mkdir -p "$CACHE"
rm -rf "$OUT" "$DIST"
mkdir -p "$DIST" "$OUT/runtime" "$OUT/lib"

# 1) 파이썬 (Windows 임베디드판, 설치 불필요) — 예전 빌드에서 받아 둔 것이 있으면 재사용
EMB="$CACHE/python-$PYV-embed-amd64.zip"
OLD="$ROOT/../file_toolkit/build/cache/python-$PYV-embed-amd64.zip"
[ -f "$EMB" ] || { [ -f "$OLD" ] && cp "$OLD" "$EMB"; } || true
[ -f "$EMB" ] || curl -sSfL -o "$EMB" "https://www.python.org/ftp/python/$PYV/python-$PYV-embed-amd64.zip"
unzip -q "$EMB" -d "$OUT/runtime"
PTH=$(ls "$OUT"/runtime/python3*._pth)
cat > "$PTH" <<EOF
python312.zip
.
..\\lib
..\\app
import site
EOF

# 2) 부품 (Windows 64비트용 휠) — 판 번호 고정: 새 판이 나와도 확인한 판만 넣음 (pypdf 7 은 서류 작성이 깨짐)
"$PY" -m pip install --quiet --disable-pip-version-check --target "$OUT/lib" \
  --platform win_amd64 --python-version 3.12 --implementation cp --abi cp312 \
  --only-binary=:all: --no-deps --cache-dir "$CACHE/pip" \
  pywebview==6.2.1 bottle==0.13.4 typing_extensions==4.16.0 \
  pythonnet==3.2.1 clr_loader==0.3.1 cffi==2.1.1 pycparser==3.12 \
  openpyxl==3.1.5 et_xmlfile==2.0.0 xlrd==2.0.2 truststore==0.10.5 \
  pypdf==6.21.4 pypdfium2==5.15.2 reportlab==5.1.0 pillow==13.0.0 charset-normalizer==3.5.3
"$PY" -m pip install --quiet --disable-pip-version-check --target "$OUT/lib" --no-deps --cache-dir "$CACHE/pip" proxy_tools==0.1.0
find "$OUT/lib" -name "__pycache__" -type d -prune -exec rm -rf {} +
rm -rf "$OUT/lib/bin" "$OUT"/lib/*.dist-info/RECORD
rm -rf "$OUT/lib/webview/platforms/android" "$OUT/lib/webview/lib/WebBrowserInterop.x86.dll" 2>/dev/null || true
# 쓰지 않는 큰 부품 제거
rm -f "$OUT"/runtime/sqlite3.dll "$OUT"/runtime/_sqlite3.pyd

# 3) 프로그램 (점검용 시연 파일은 빼고)
rsync -a --exclude "__pycache__" --exclude ".DS_Store" --exclude "demo.py" --exclude ".claude" app/ "$OUT/app/"
cp packaging/app.ico "$OUT/app/app.ico"
# 빌드 지문: 같은 판 번호로 다시 빌드해도 내용이 바뀌면 PC에서 새로 풀리고(폴더 v판-지문) 화면 캐시도 비워진다
BUILD=$(cd "$OUT/app" && find . -type f | LC_ALL=C sort | xargs shasum | shasum | cut -c1-8)
STAMP="$VER-$BUILD"
echo "$STAMP" > "$OUT/app/VERSION"
# 화면 파일 주소에 판 번호를 붙여 예전 판 js·css 가 캐시에서 나오지 않게 한다 (app.js → app.js?v=1.2.3-지문)
perl -pi -e 's/(<(?:script|link)[^>]*(?:src|href)="[^"?:]+\.(?:js|css))"/$1?v='"$STAMP"'"/g' "$OUT/app/ui/index.html"
grep -q "app.js?v=$VER" "$OUT/app/ui/index.html" || { echo "판 번호 붙이기 실패"; exit 1; }

# 4) 실행 파일: 위 폴더 전체를 exe 안에 넣는다
"$PY" tools/make_zip.py --contents "$OUT" launcher/payload.zip
echo "$STAMP" > launcher/version.txt
IFS=. read -r V1 V2 V3 <<< "$VER"
(cd launcher && rm -f *.syso && "$GOBIN_DIR/go-winres" simply --arch amd64 --icon ../packaging/icon.png --manifest gui \
   --product-name "종합관리" --file-description "종합관리 (사건 조회 · 법조치)" --original-filename "종합관리.exe" \
   --product-version "$V1.$V2.$V3.0" --file-version "$V1.$V2.$V3.0" --copyright "사내용")
EXE="$DIST/종합관리.exe"
(cd launcher && GOOS=windows GOARCH=amd64 CGO_ENABLED=0 "$GO" build -trimpath -ldflags "-H=windowsgui -s -w" -o "$EXE" .)
rm -f launcher/payload.zip

# 5) 메일 첨부용 zip (exe + 안내문)
MAIL="$ROOT/build/mail/$ZIPNAME"
rm -rf "$MAIL" && mkdir -p "$MAIL"
cp "$EXE" "$MAIL/"
cp packaging/처음_읽어주세요.txt "$MAIL/"
perl -pi -e 's/\r?\n/\r\n/' "$MAIL/처음_읽어주세요.txt"
cp "$MAIL/처음_읽어주세요.txt" "$DIST/"
ZIP="$DIST/${ZIPNAME}_v${VER}.zip"
"$PY" tools/make_zip.py "$MAIL" "$ZIP"
du -sh "$OUT" "$EXE" "$ZIP"
echo "완료: $EXE"
