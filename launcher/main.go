//go:build windows

// 종합관리.exe — 프로그램 전체를 품은 실행 파일 하나. (v1.10 전 이름: 사건조회도우미.exe)
//
// 처음 실행: %LOCALAPPDATA%\CourtSearch\v<버전>\ 에 풀고, 자기 자신을 그 옆에 복사한 뒤
//           바탕화면에 바로가기를 만든다. 다음부터는 바로 실행한다.
// 새 버전 exe 를 실행하면 새 버전 폴더에 다시 풀고 예전 버전 폴더는 지운다.
package main

import (
	"archive/zip"
	"bytes"
	_ "embed"
	"encoding/base64"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"
	"unicode/utf16"
	"unsafe"
)

//go:embed payload.zip
var payload []byte

//go:embed version.txt
var versionText string

const (
	appTitle     = "종합관리"
	exeName      = "종합관리.exe"
	shortcutName = "종합관리.lnk"
	oldExeName   = "사건조회도우미.exe"     // 예전 이름 — 새 이름으로 옮겨 가면 지운다
	oldShortcut  = "사건 조회 도우미.lnk"
	noWindow     = 0x08000000 // CREATE_NO_WINDOW
)

var (
	user32          = syscall.NewLazyDLL("user32.dll")
	kernel32        = syscall.NewLazyDLL("kernel32.dll")
	procMessageBox  = user32.NewProc("MessageBoxW")
	procCreateMutex = kernel32.NewProc("CreateMutexW")
	procWaitForObj  = kernel32.NewProc("WaitForSingleObject")
	procReleaseMtx  = kernel32.NewProc("ReleaseMutex")
)

func msgBox(text string, flags uintptr) {
	t, _ := syscall.UTF16PtrFromString(text)
	c, _ := syscall.UTF16PtrFromString(appTitle)
	procMessageBox.Call(0, uintptr(unsafe.Pointer(t)), uintptr(unsafe.Pointer(c)), flags)
}

func fail(format string, a ...any) {
	msgBox(fmt.Sprintf(format, a...), 0x10) // MB_ICONERROR
	os.Exit(1)
}

func exists(p string) bool { _, err := os.Stat(p); return err == nil }

// 두 번 연달아 눌러도 압축 풀기가 겹치지 않게
func lock() func() {
	name, _ := syscall.UTF16PtrFromString(`Local\CourtSearchSetup`)
	h, _, _ := procCreateMutex.Call(0, 0, uintptr(unsafe.Pointer(name)))
	if h == 0 {
		return func() {}
	}
	procWaitForObj.Call(h, 120000)
	return func() { procReleaseMtx.Call(h); syscall.CloseHandle(syscall.Handle(h)) }
}

func extract(dst string) error {
	zr, err := zip.NewReader(bytes.NewReader(payload), int64(len(payload)))
	if err != nil {
		return err
	}
	root := filepath.Clean(dst) + string(os.PathSeparator)
	for _, f := range zr.File {
		p := filepath.Join(dst, filepath.FromSlash(f.Name))
		if !strings.HasPrefix(p, root) {
			continue
		}
		if f.FileInfo().IsDir() {
			os.MkdirAll(p, 0o755)
			continue
		}
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			return err
		}
		rc, err := f.Open()
		if err != nil {
			return err
		}
		out, err := os.Create(p)
		if err != nil {
			rc.Close()
			return err
		}
		_, err = io.Copy(out, rc)
		rc.Close()
		out.Close()
		if err != nil {
			return err
		}
	}
	return nil
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	tmp := dst + ".new"
	out, err := os.Create(tmp)
	if err != nil {
		return err
	}
	if _, err = io.Copy(out, in); err != nil {
		out.Close()
		return err
	}
	out.Close()
	os.Remove(dst)
	return os.Rename(tmp, dst)
}

// PowerShell 에 한글 경로를 안전하게 넘기려고 UTF-16 Base64 로 보냄
func powershell(script string) error {
	u := utf16.Encode([]rune(script))
	b := make([]byte, len(u)*2)
	for i, v := range u {
		b[2*i], b[2*i+1] = byte(v), byte(v>>8)
	}
	cmd := exec.Command("powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
		"-EncodedCommand", base64.StdEncoding.EncodeToString(b))
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: noWindow}
	return cmd.Run()
}

func psq(s string) string { return "'" + strings.ReplaceAll(s, "'", "''") + "'" }

func makeShortcut(target string) error {
	return powershell(fmt.Sprintf(`$d=[Environment]::GetFolderPath('Desktop')
$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d %s))
$s.TargetPath=%s
$s.WorkingDirectory=%s
$s.IconLocation=%s
$s.Description=%s
$s.Save()`, psq(shortcutName), psq(target), psq(filepath.Dir(target)), psq(target+",0"), psq(appTitle)))
}

// 예전 이름의 바탕화면 바로가기를 지운다 (이 프로그램을 가리키는 것만)
func removeOldShortcut() error {
	return powershell(fmt.Sprintf(`$d=[Environment]::GetFolderPath('Desktop')
$p=Join-Path $d %s
if(Test-Path -LiteralPath $p){$t=(New-Object -ComObject WScript.Shell).CreateShortcut($p).TargetPath
if($t -like '*\CourtSearch\*'){Remove-Item -LiteralPath $p -Force}}`, psq(oldShortcut)))
}

func main() {
	ver := strings.TrimSpace(versionText)
	local := os.Getenv("LOCALAPPDATA")
	if local == "" {
		local = filepath.Join(os.Getenv("USERPROFILE"), "AppData", "Local")
	}
	base := filepath.Join(local, "CourtSearch")
	appDir := filepath.Join(base, "v"+ver)
	done := filepath.Join(appDir, ".complete")

	// 1) 처음이면 풀기
	if !exists(done) {
		unlock := lock()
		if !exists(done) {
			os.MkdirAll(base, 0o755)
			tmp := fmt.Sprintf("%s.tmp%d", appDir, os.Getpid())
			os.RemoveAll(tmp)
			if err := extract(tmp); err != nil {
				os.RemoveAll(tmp)
				unlock()
				fail("프로그램 파일을 풀지 못했습니다.\n\n%v\n\n위치: %s", err, base)
			}
			os.RemoveAll(appDir)
			if err := os.Rename(tmp, appDir); err != nil {
				unlock()
				fail("프로그램 폴더를 만들지 못했습니다.\n\n%v", err)
			}
			os.WriteFile(done, []byte(time.Now().Format(time.RFC3339)), 0o644)
			// 예전 버전 정리
			if olds, _ := filepath.Glob(filepath.Join(base, "v*")); olds != nil {
				for _, o := range olds {
					if o != appDir {
						os.RemoveAll(o)
					}
				}
			}
		}
		unlock()
	}

	// 2) 내 PC 에 실행 파일 사본 + 바탕화면 바로가기 (처음 한 번)
	self, _ := os.Executable()
	localExe := filepath.Join(base, exeName)
	target := self
	if !strings.EqualFold(filepath.Clean(self), filepath.Clean(localExe)) {
		// 내 PC 사본의 버전이 다르면(또는 없으면) 지금 실행한 exe 로 바꾼다
		verFile := localExe + ".version"
		cur, _ := os.ReadFile(verFile)
		if !exists(localExe) || strings.TrimSpace(string(cur)) != ver {
			if copyFile(self, localExe) == nil {
				os.WriteFile(verFile, []byte(ver), 0o644)
			}
		}
	}
	if exists(localExe) {
		target = localExe
	}
	// 예전 이름(사건조회도우미.exe)에서 옮겨 가기: 예전 사본·바로가기를 지우고 새 이름으로 다시 만든다
	oldLocal := filepath.Join(base, oldExeName)
	if exists(localExe) && exists(oldLocal) {
		os.Remove(oldLocal)
		os.Remove(oldLocal + ".version")
	}
	marker := filepath.Join(base, ".shortcut")
	newShortcut, renamed := false, false
	if prev, err := os.ReadFile(marker); err == nil && !strings.EqualFold(filepath.Clean(strings.TrimSpace(string(prev))), filepath.Clean(target)) {
		removeOldShortcut()
		os.Remove(marker)
		renamed = true
	}
	if !exists(marker) && makeShortcut(target) == nil {
		os.WriteFile(marker, []byte(target), 0o644)
		newShortcut = !renamed
	}

	// 3) 실행
	pyw := filepath.Join(appDir, "runtime", "pythonw.exe")
	mainPy := filepath.Join(appDir, "app", "main.py")
	if !exists(pyw) {
		os.Remove(done)
		fail("프로그램 파일이 손상되었습니다. 다시 실행해 주세요.\n(%s)", pyw)
	}
	cmd := exec.Command(pyw, append([]string{mainPy}, os.Args[1:]...)...)
	cmd.Dir = appDir
	cmd.Env = append(os.Environ(), "CSH_LAUNCHER="+target)
	if err := cmd.Start(); err != nil {
		fail("프로그램을 시작하지 못했습니다.\n\n%v", err)
	}
	if newShortcut {
		msgBox("바탕화면에 [종합관리] 아이콘을 만들었습니다.\n다음부터는 그 아이콘으로 실행하세요.", 0x40)
	}

	// 4) 시작하자마자 꺼지면 자가 진단 후 안내
	exited := make(chan error, 1)
	go func() { exited <- cmd.Wait() }()
	select {
	case err := <-exited:
		if err != nil {
			diag := exec.Command(filepath.Join(appDir, "runtime", "python.exe"), mainPy, "--self-test")
			diag.Dir = appDir
			diag.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: noWindow}
			diag.Run()
			msgBox("프로그램이 시작 중에 종료되었습니다.\n\n바탕화면의 「종합관리_자가진단.txt」와\n"+
				filepath.Join(base, "오류기록.txt")+"\n파일을 담당자에게 보내 주세요.", 0x10)
		}
	case <-time.After(10 * time.Second):
	}
}
