#!/bin/bash
# 시안(시연)용 실행 파일: 종합관리_시안.exe
#   bash tools/build_sian.sh
# 결과: build/시안/종합관리_시안.exe  +  build/시안/종합관리_시안_v<버전>.zip
#
# 실제 종합관리와 섞이지 않게:
#   · 풀리는 곳  %LOCALAPPDATA%\CourtSearchSian (실제는 CourtSearch)
#   · 자료       %LOCALAPPDATA%\CourtSearchSian\demo 의 시연 자료만 씀 (회사 자료 폴더는 안 건드림)
#   · 법원 사이트 대신 꾸며 낸 결과 (조회해도 실제 사이트에 접속하지 않음)
#   · 바탕화면 아이콘 「종합관리 시안」 따로, dist/ 의 실제 배포본은 지우지 않음
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PYV=3.12.10
VER=$(grep -E '^VERSION' app/bridge.py | cut -d'"' -f2)
CACHE="$ROOT/build/cache"
OUT="$ROOT/build/CourtSearchSian"
DIST="$ROOT/build/시안"
LCH="$ROOT/build/launcher_sian"
TOOLS="$ROOT/.tools"
GO=${GO:-$TOOLS/go/bin/go}; GOBIN_DIR=${GOBIN_DIR:-$TOOLS/bin}
export GOCACHE=${GOCACHE:-$TOOLS/gocache} GOPATH=${GOPATH:-$TOOLS/gopath} GOFLAGS=${GOFLAGS:--mod=mod}
PY=${PYTHON:-python3}

rm -rf build/CourtSearchSian build/시안 build/launcher_sian build/mail_sian
mkdir -p "$DIST" "$OUT/runtime" "$OUT/lib" "$CACHE"

# 1) 파이썬 (Windows 임베디드판)
EMB="$CACHE/python-$PYV-embed-amd64.zip"
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

# 2) 부품 (실제 빌드와 같음)
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
rm -f "$OUT"/runtime/sqlite3.dll "$OUT"/runtime/_sqlite3.pyd

# 3) 프로그램 — 시연 파일(demo.py)을 넣는다
rsync -a --exclude "__pycache__" --exclude ".DS_Store" --exclude ".claude" app/ "$OUT/app/"
cp packaging/app.ico "$OUT/app/app.ico"
BUILD=$(cd "$OUT/app" && find . -type f | LC_ALL=C sort | xargs shasum | shasum | cut -c1-8)
STAMP="$VER-sian-$BUILD"
echo "$STAMP" > "$OUT/app/VERSION"
perl -pi -e 's/(<(?:script|link)[^>]*(?:src|href)="[^"?:]+\.(?:js|css))"/$1?v='"$STAMP"'"/g' "$OUT/app/ui/index.html"
grep -q "app.js?v=$VER" "$OUT/app/ui/index.html" || { echo "판 번호 붙이기 실패"; exit 1; }

# 4) 시안용 실행기: 실제 실행기를 복사해 이름·폴더·시연 모드만 바꿈 (launcher/ 원본은 그대로)
cp -R launcher "$LCH"
rm -f "$LCH"/*.syso
M="$LCH/main.go"
perl -pi -e 's/appTitle     = "종합관리"/appTitle     = "종합관리 시안"/' "$M"
perl -pi -e 's/exeName      = "종합관리.exe"/exeName      = "종합관리_시안.exe"/' "$M"
perl -pi -e 's/shortcutName = "종합관리.lnk"/shortcutName = "종합관리 시안.lnk"/' "$M"
perl -pi -e 's/oldExeName   = "사건조회도우미.exe"/oldExeName   = "_없음_시안.exe"/' "$M"
perl -pi -e 's/oldShortcut  = "사건 조회 도우미.lnk"/oldShortcut  = "_없음_시안.lnk"/' "$M"
perl -pi -e 's/CourtSearchSetup/CourtSearchSianSetup/' "$M"
perl -pi -e 's/base := filepath.Join\(local, "CourtSearch"\)/base := filepath.Join(local, "CourtSearchSian")/' "$M"
# 시연 자료 폴더로 실행 + 기록·화면 캐시도 시안 폴더 안으로 (LOCALAPPDATA 를 시안 폴더로)
perl -pi -e 's/cmd := exec.Command\(pyw, append\(\[\]string\{mainPy\}, os.Args\[1:\]\.\.\.\)\.\.\.\)/cmd := exec.Command(pyw, append([]string{mainPy, "--demo", filepath.Join(base, "demo")}, os.Args[1:]...)...)/' "$M"
perl -pi -e 's/cmd.Env = append\(os.Environ\(\), "CSH_LAUNCHER="\+target\)/cmd.Env = append(os.Environ(), "CSH_LAUNCHER="+target, "LOCALAPPDATA="+base)/' "$M"
perl -pi -e 's/바탕화면에 \[종합관리\] 아이콘/바탕화면에 [종합관리 시안] 아이콘/' "$M"
for k in 'CourtSearchSian")' '"종합관리_시안.exe"' '"--demo"' '"LOCALAPPDATA="+base' 'CourtSearchSianSetup'; do grep -qF -- "$k" "$M" || { echo "실행기 바꾸기 실패: $k"; exit 1; }; done

"$PY" tools/make_zip.py --contents "$OUT" "$LCH/payload.zip"
echo "$STAMP" > "$LCH/version.txt"
IFS=. read -r V1 V2 V3 <<< "$VER"
(cd "$LCH" && "$GOBIN_DIR/go-winres" simply --arch amd64 --icon ../../packaging/icon.png --manifest gui \
   --product-name "종합관리 시안" --file-description "종합관리 시안 (시연 자료)" --original-filename "종합관리_시안.exe" \
   --product-version "$V1.$V2.$V3.0" --file-version "$V1.$V2.$V3.0" --copyright "사내용 · 시연")
EXE="$DIST/종합관리_시안.exe"
(cd "$LCH" && GOOS=windows GOARCH=amd64 CGO_ENABLED=0 "$GO" build -trimpath -ldflags "-H=windowsgui -s -w" -o "$EXE" .)

# 5) 안내문 + zip
cat > "$DIST/시안_먼저_읽어주세요.txt" <<EOF
종합관리 시안 v$VER (시연용)

1. 종합관리_시안.exe 를 더블클릭하면 처음 한 번 풀리고(10~30초) 창이 열립니다.
   바탕화면에 「종합관리 시안」 아이콘이 생깁니다.
2. 모든 자료는 꾸며 낸 시연 자료입니다. 회사 자료 폴더는 열지 않고,
   「조회하기」를 눌러도 법원 사이트에 접속하지 않습니다.
3. 실제 종합관리와 따로 설치됩니다 (%LOCALAPPDATA%\\CourtSearchSian).
   두 프로그램을 같이 켜도 됩니다.
4. 회수 분석 (왼쪽 메뉴 「회수 분석」 묶음)
   · 처음에는 가짜 채무자 4만 명 예시 자료로 모든 화면이 열립니다.
   · 실제 자료 넣기 시험: 「자료 · 회수 자료 넣기」 → 「파일 고르기」로 전산 원자료
     (또는 「예시 파일 만들기」로 만든 엑셀) → 칸 맞추기 → 값 맞추기 → 담아 두기 →
     점검표 확인 → 「이대로 넣기」. 이때부터 넣은 자료로 계산됩니다.
   · 통계: 「분석 › 통계」 — 세무서 미압류 · 실효·폐지 × 급여 압류 · 입금유형별(월·연)
   · 압류 판단 · 처리함 · 이번 달 계획 · 기준값은 껐다 켜도 남습니다.
   · 「넣은 자료 지우기」를 누르면 다시 예시 자료로 돌아갑니다.
5. 설정의 「PC 켤 때 자동 실행」은 시안에서 켜지 마세요 (실제 프로그램 설정과 겹침).
6. 지우기: 바탕화면 아이콘과 %LOCALAPPDATA%\\CourtSearchSian 폴더를 지우면 끝.
EOF
perl -pi -e 's/\r?\n/\r\n/' "$DIST/시안_먼저_읽어주세요.txt"
MAIL="$ROOT/build/mail_sian/종합관리_시안"
mkdir -p "$MAIL"
cp "$EXE" "$DIST/시안_먼저_읽어주세요.txt" "$MAIL/"
ZIP="$DIST/종합관리_시안_v${VER}.zip"
"$PY" tools/make_zip.py "$MAIL" "$ZIP"
du -sh "$EXE" "$ZIP"
echo "완료: $EXE"
