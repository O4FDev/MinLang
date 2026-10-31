// fgcc: a content-addressed cache in front of Clang for fast-gate shards.
//
// Installed in place of /opt/llvm-23.1.3/bin/clang on a shard (the real driver stays at clang-23), it runs the
// real compiler unless the invocation is one it can prove it may replay: a compile or link whose every input is a
// regular file and whose only output is the -o file. The key covers this program, the real compiler and linker
// binaries, argv (with the -o path replaced by its extension), the working directory, every environment variable
// Clang or the linkers read, the bytes of every input file and library, and for C-family sources the preprocessed
// translation unit. A hit writes the stored output (atomically, like Clang), replays stdout, stderr and the exit
// status, and nothing else; anything it cannot classify runs uncached.
//
// Configuration: /home/agent/fgcc/config, lines KEY=VALUE: mode=off|log|cache|verify, dir=<cache directory>,
// log=<jsonl file>. verify recompiles every hit into a temporary file and records whether the bytes are identical
// (the cached copy is never used when they differ).
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"
)

const version = "fgcc-1"
const realClang = "/opt/llvm-23.1.3/bin/clang-23"
const configPath = "/home/agent/fgcc/config"

var separateValue = map[string]bool{
	"-o": true, "-I": true, "-L": true, "-D": true, "-U": true, "-include": true, "-imacros": true, "-isystem": true,
	"-idirafter": true, "-iquote": true, "-isysroot": true, "-x": true, "-MF": true, "-MT": true, "-MQ": true,
	"-arch": true, "-target": true, "-Xlinker": true, "-Xclang": true, "-Xassembler": true, "-Xpreprocessor": true,
	"-mllvm": true, "-z": true, "-T": true, "-u": true, "-e": true, "--param": true, "-framework": true,
	"-rpath": true, "--sysroot": true, "-resource-dir": true, "-working-directory": true, "-l": true,
}

// Options after which the invocation is not a plain compile/link with one known output.
var uncacheable = []string{
	"-E", "-M", "-MM", "-MD", "-MMD", "-MF", "-MT", "-MQ", "-###", "-v", "--version", "-dumpversion", "-dumpmachine",
	"-fsyntax-only", "-save-temps", "-gsplit-dwarf", "-ftime-trace", "-working-directory", "-", "-fmodules",
	"-fcrash-diagnostics-dir", "-Xclang",
}

var cSource = map[string]bool{".c": true, ".cc": true, ".cpp": true, ".cxx": true, ".m": true, ".mm": true, ".S": true, ".s": true, ".h": true}
var binaryInput = map[string]bool{".ll": true, ".bc": true, ".o": true, ".a": true, ".so": true}

type config struct{ mode, dir, log string }

func readConfig() config {
	c := config{mode: "off"}
	data, err := os.ReadFile(configPath)
	if err != nil {
		return c
	}
	for _, line := range strings.Split(string(data), "\n") {
		k, v, ok := strings.Cut(strings.TrimSpace(line), "=")
		if !ok {
			continue
		}
		switch k {
		case "mode":
			c.mode = v
		case "dir":
			c.dir = v
		case "log":
			c.log = v
		}
	}
	return c
}

func hashFile(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	info, err := f.Stat()
	if err != nil || !info.Mode().IsRegular() {
		return "", fmt.Errorf("not a regular file: %s", path)
	}
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

var identityCache = map[string]string{}

// identity of a tool binary: its resolved path, size and content hash, computed once per box and kept in dir.
func identity(dir, path string) string {
	resolved, err := filepath.EvalSymlinks(path)
	if err != nil {
		return "missing:" + path
	}
	if v, ok := identityCache[resolved]; ok {
		return v
	}
	info, err := os.Stat(resolved)
	if err != nil {
		return "missing:" + resolved
	}
	memo := filepath.Join(dir, "identity", strings.ReplaceAll(resolved, "/", "_")+fmt.Sprintf("-%d-%d", info.Size(), info.ModTime().UnixNano()))
	if data, err := os.ReadFile(memo); err == nil {
		identityCache[resolved] = string(data)
		return string(data)
	}
	h, err := hashFile(resolved)
	if err != nil {
		return "unreadable:" + resolved
	}
	v := resolved + ":" + h
	os.MkdirAll(filepath.Dir(memo), 0o755)
	os.WriteFile(memo, []byte(v), 0o644)
	identityCache[resolved] = v
	return v
}

type analysis struct {
	cacheable bool
	reason    string
	output    string
	key       string
	inputs    []string
}

func environmentKey() []string {
	var keep []string
	for _, entry := range os.Environ() {
		name, _, _ := strings.Cut(entry, "=")
		switch {
		case name == "CPATH" || name == "LIBRARY_PATH" || name == "COMPILER_PATH" || name == "SOURCE_DATE_EPOCH" ||
			name == "LD_RUN_PATH" || name == "LD_LIBRARY_PATH" || name == "SDKROOT" || name == "MACOSX_DEPLOYMENT_TARGET" ||
			name == "ZERO_AR_DATE" || name == "LLVM_PROFILE_FILE" || name == "RC_DEBUG_OPTIONS":
			keep = append(keep, entry)
		case strings.HasPrefix(name, "C_INCLUDE") || strings.HasPrefix(name, "CPLUS_INCLUDE") || strings.HasPrefix(name, "OBJC_INCLUDE") ||
			strings.HasPrefix(name, "CCC_") || strings.HasPrefix(name, "CLANG_") || strings.HasPrefix(name, "LLVM_") ||
			strings.HasPrefix(name, "ASAN_") || strings.HasPrefix(name, "UBSAN_") || strings.HasPrefix(name, "LSAN_"):
			keep = append(keep, entry)
		}
	}
	return keep
}

func findLibrary(name string, dirs []string, static bool) string {
	for _, dir := range dirs {
		for _, file := range []string{"lib" + name + ".so", "lib" + name + ".a"} {
			if static && strings.HasSuffix(file, ".so") {
				continue
			}
			path := filepath.Join(dir, file)
			if info, err := os.Stat(path); err == nil && info.Mode().IsRegular() || err == nil && info.Mode()&os.ModeSymlink != 0 {
				return path
			}
		}
	}
	return ""
}

func analyse(dir string, args []string, cwd string) analysis {
	a := analysis{}
	var inputs, libraries, libDirs []string
	var norm []string
	compileOnly := false
	sources := 0
	for i := 0; i < len(args); i++ {
		arg := args[i]
		for _, bad := range uncacheable {
			if arg == bad {
				a.reason = "option " + arg
				return a
			}
		}
		if strings.HasPrefix(arg, "@") || strings.HasPrefix(arg, "-print") || strings.HasPrefix(arg, "-fprofile") ||
			strings.HasPrefix(arg, "-Wl,@") || strings.Contains(arg, "thinlto-cache") || strings.HasPrefix(arg, "--print") ||
			strings.HasPrefix(arg, "-MF") || strings.HasPrefix(arg, "-fsanitize-ignorelist") || strings.HasPrefix(arg, "-fsanitize-blacklist") ||
			strings.HasPrefix(arg, "-fmodule") || strings.HasPrefix(arg, "-fcrash") || strings.HasPrefix(arg, "-include") ||
			strings.HasPrefix(arg, "-imacros") || strings.HasPrefix(arg, "-fdebug-prefix-map") || strings.HasPrefix(arg, "-ffile-prefix-map") {
			a.reason = "option " + arg
			return a
		}
		if arg == "-c" || arg == "-S" {
			compileOnly = true
		}
		if arg == "-o" && i+1 < len(args) {
			if a.output != "" {
				a.reason = "two outputs"
				return a
			}
			a.output = args[i+1]
			norm = append(norm, "-o", "<OUT>"+filepath.Ext(args[i+1]))
			i++
			continue
		}
		if strings.HasPrefix(arg, "-o") && len(arg) > 2 {
			a.reason = "joined -o"
			return a
		}
		if strings.HasPrefix(arg, "-L") {
			value := strings.TrimPrefix(arg, "-L")
			if value == "" && i+1 < len(args) {
				value = args[i+1]
			}
			libDirs = append(libDirs, value)
		}
		if strings.HasPrefix(arg, "-l") && len(arg) > 2 {
			libraries = append(libraries, arg[2:])
		}
		if strings.HasPrefix(arg, "-Wl,") || arg == "-Xlinker" {
			value := strings.TrimPrefix(arg, "-Wl,")
			if arg == "-Xlinker" && i+1 < len(args) {
				value = args[i+1]
			}
			for _, part := range strings.Split(value, ",") {
				_, path, hasPath := strings.Cut(part, "=")
				if !hasPath {
					path = part
				}
				if path != "" && !strings.HasPrefix(path, "-") {
					if info, err := os.Stat(filepath.Join(cwd, path)); err == nil && !info.IsDir() || filepath.IsAbs(path) && err == nil {
						inputs = append(inputs, path)
					}
				}
			}
		}
		if separateValue[arg] && i+1 < len(args) {
			norm = append(norm, arg, args[i+1])
			if arg == "-x" {
				a.reason = "explicit language"
				return a
			}
			i++
			continue
		}
		norm = append(norm, arg)
		if !strings.HasPrefix(arg, "-") {
			ext := filepath.Ext(arg)
			if !cSource[ext] && !binaryInput[ext] {
				a.reason = "unknown input " + arg
				return a
			}
			if cSource[ext] {
				sources++
			}
			inputs = append(inputs, arg)
		}
	}
	if a.output == "" {
		a.reason = "no -o"
		return a
	}
	if len(inputs) == 0 {
		a.reason = "no inputs"
		return a
	}
	if sources > 1 {
		a.reason = "several C sources"
		return a
	}
	h := sha256.New()
	// The implicit link inputs (crt objects, libc, libgcc) come from the system packages: dpkg's status file names them.
	fmt.Fprintf(h, "%s\x00%s\x00%s\x00%s\x00%s\x00", version, identity(dir, realClang), identity(dir, "/opt/llvm-23.1.3/bin/ld.lld"),
		identity(dir, "/usr/bin/ld"), identity(dir, "/var/lib/dpkg/status"))
	fmt.Fprintf(h, "argv0=%s\x00cwd=%s\x00compile=%v\x00", filepath.Base(os.Args[0]), cwd, compileOnly)
	for _, arg := range norm {
		fmt.Fprintf(h, "arg=%s\x00", arg)
	}
	for _, entry := range environmentKey() {
		fmt.Fprintf(h, "env=%s\x00", entry)
	}
	for _, input := range inputs {
		path := input
		if !filepath.IsAbs(path) {
			path = filepath.Join(cwd, path)
		}
		digest, err := hashFile(path)
		if err != nil {
			a.reason = "input " + input
			return a
		}
		fmt.Fprintf(h, "input=%s:%s\x00", input, digest)
		a.inputs = append(a.inputs, input+":"+digest[:16])
	}
	if !compileOnly {
		dirs := append(append([]string{}, libDirs...), "/usr/lib/x86_64-linux-gnu", "/lib/x86_64-linux-gnu", "/usr/lib", "/lib", "/usr/local/lib")
		for _, library := range libraries {
			path := findLibrary(library, dirs, false)
			if path == "" {
				a.reason = "library " + library
				return a
			}
			digest, err := hashFile(path)
			if err != nil {
				a.reason = "library " + library
				return a
			}
			fmt.Fprintf(h, "lib=%s:%s:%s\x00", library, path, digest)
		}
	}
	if sources == 1 {
		// The preprocessed unit covers every header and macro; it is produced by the real driver with the same flags.
		var pre []string
		for i := 0; i < len(args); i++ {
			if args[i] == "-o" {
				i++
				continue
			}
			if args[i] == "-c" || args[i] == "-S" || strings.HasPrefix(args[i], "-l") || strings.HasPrefix(args[i], "-Wl,") || strings.HasPrefix(args[i], "-fuse-ld") {
				continue
			}
			if binaryInput[filepath.Ext(args[i])] && !strings.HasPrefix(args[i], "-") {
				continue
			}
			pre = append(pre, args[i])
		}
		pre = append(pre, "-E", "-o", "-")
		cmd := exec.Command(realClang, pre...)
		cmd.Args[0] = os.Args[0]
		cmd.Dir = cwd
		var out, errOut bytes.Buffer
		cmd.Stdout, cmd.Stderr = &out, &errOut
		if err := cmd.Run(); err != nil || errOut.Len() > 0 {
			a.reason = "preprocess"
			return a
		}
		sum := sha256.Sum256(out.Bytes())
		fmt.Fprintf(h, "preprocessed=%x\x00", sum)
	}
	a.cacheable = true
	a.key = hex.EncodeToString(h.Sum(nil))
	return a
}

type entry struct {
	Status int    `json:"status"`
	Stdout string `json:"stdout"`
	Stderr string `json:"stderr"`
	Mode   uint32 `json:"mode"`
}

func runReal(args []string, stdout, stderr io.Writer) int {
	cmd := exec.Command(realClang, args...)
	cmd.Args[0] = os.Args[0]
	cmd.Stdin, cmd.Stdout, cmd.Stderr = os.Stdin, stdout, stderr
	if err := cmd.Run(); err != nil {
		if exit, ok := err.(*exec.ExitError); ok {
			if ws, ok := exit.Sys().(syscall.WaitStatus); ok && ws.Signaled() {
				return 128 + int(ws.Signal())
			}
			return exit.ExitCode()
		}
		fmt.Fprintf(os.Stderr, "fgcc: cannot run %s: %v\n", realClang, err)
		return 127
	}
	return 0
}

func passthrough(args []string) {
	err := syscall.Exec(realClang, append([]string{os.Args[0]}, args...), os.Environ())
	fmt.Fprintf(os.Stderr, "fgcc: exec %s: %v\n", realClang, err)
	os.Exit(127)
}

func writeAtomically(target string, data []byte, mode os.FileMode) error {
	tmp, err := os.CreateTemp(filepath.Dir(target), "."+filepath.Base(target)+".fgcc-")
	if err != nil {
		return err
	}
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		os.Remove(tmp.Name())
		return err
	}
	tmp.Close()
	old := syscall.Umask(0)
	syscall.Umask(old)
	os.Chmod(tmp.Name(), mode&^os.FileMode(old))
	return os.Rename(tmp.Name(), target)
}

type record struct {
	Start     float64  `json:"t"`
	Duration  float64  `json:"d"`
	Cwd       string   `json:"cwd"`
	Args      []string `json:"args"`
	Cacheable bool     `json:"ok"`
	Reason    string   `json:"why,omitempty"`
	Key       string   `json:"key,omitempty"`
	Inputs    []string `json:"in,omitempty"`
	Result    string   `json:"res"`
	Status    int      `json:"st"`
	Analysis  float64  `json:"ad"`
	Label     string   `json:"label,omitempty"`
}

func logRecord(path string, r record) {
	if path == "" {
		return
	}
	line, _ := json.Marshal(r)
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return
	}
	f.Write(append(line, '\n'))
	f.Close()
}

func main() {
	args := os.Args[1:]
	c := readConfig()
	if c.mode == "off" || c.dir == "" {
		passthrough(args)
	}
	start := time.Now()
	cwd, _ := os.Getwd()
	a := analyse(c.dir, args, cwd)
	r := record{Start: float64(start.UnixNano()) / 1e9, Cwd: cwd, Args: args, Cacheable: a.cacheable, Reason: a.reason, Key: a.key,
		Inputs: a.inputs, Analysis: time.Since(start).Seconds(), Label: os.Getenv("MINYAR_CHECK_LABEL")}
	if !a.cacheable || c.mode == "log" {
		var status int
		status = runReal(args, os.Stdout, os.Stderr)
		r.Result, r.Status, r.Duration = "run", status, time.Since(start).Seconds()
		logRecord(c.log, r)
		os.Exit(status)
	}
	output := a.output
	if !filepath.IsAbs(output) {
		output = filepath.Join(cwd, output)
	}
	entryDir := filepath.Join(c.dir, a.key[:2], a.key)
	if meta, err := os.ReadFile(filepath.Join(entryDir, "meta.json")); err == nil {
		var e entry
		data, err2 := os.ReadFile(filepath.Join(entryDir, "output"))
		if json.Unmarshal(meta, &e) == nil && err2 == nil {
			if c.mode == "verify" {
				fresh := output + ".fgcc-verify"
				vargs := append([]string{}, args...)
				for i := range vargs {
					if vargs[i] == "-o" && i+1 < len(vargs) {
						vargs[i+1] = fresh
					}
				}
				var so, se bytes.Buffer
				status := runReal(vargs, &so, &se)
				freshData, _ := os.ReadFile(fresh)
				os.Remove(fresh)
				same := status == e.Status && bytes.Equal(freshData, data) && so.String() == e.Stdout && se.String() == e.Stderr
				r.Result = map[bool]string{true: "verified", false: "MISMATCH"}[same]
				if !same {
					// Never trust a mismatching entry: run the real compile for this invocation.
					status = runReal(args, os.Stdout, os.Stderr)
					r.Status, r.Duration = status, time.Since(start).Seconds()
					logRecord(c.log, r)
					os.Exit(status)
				}
			} else {
				r.Result = "hit"
			}
			if err := writeAtomically(output, data, os.FileMode(e.Mode)); err == nil {
				os.Stdout.WriteString(e.Stdout)
				os.Stderr.WriteString(e.Stderr)
				r.Status, r.Duration = e.Status, time.Since(start).Seconds()
				logRecord(c.log, r)
				os.Exit(e.Status)
			}
		}
	}
	var so, se bytes.Buffer
	status := runReal(args, io.MultiWriter(os.Stdout, &so), io.MultiWriter(os.Stderr, &se))
	r.Result, r.Status = "miss", status
	if status == 0 {
		if data, err := os.ReadFile(output); err == nil {
			info, _ := os.Stat(output)
			e := entry{Status: status, Stdout: so.String(), Stderr: se.String(), Mode: uint32(info.Mode().Perm())}
			meta, _ := json.Marshal(e)
			tmpDir, err := os.MkdirTemp(c.dir, ".fill-")
			if err == nil {
				os.WriteFile(filepath.Join(tmpDir, "output"), data, 0o644)
				os.WriteFile(filepath.Join(tmpDir, "meta.json"), meta, 0o644)
				os.MkdirAll(filepath.Dir(entryDir), 0o755)
				if os.Rename(tmpDir, entryDir) != nil {
					os.RemoveAll(tmpDir)
				}
			}
		}
	}
	r.Duration = time.Since(start).Seconds()
	logRecord(c.log, r)
	os.Exit(status)
}
