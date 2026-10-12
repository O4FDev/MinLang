# Proposed neo-vm zstd shim removal

This is a reviewable migration patch, not a change to neo-vm. The Minyar
`zstd` package supplies the same raw buffer operation with an explicit reusable
`DCtx`, stable negative errors, bounded complete-frame decoding, and RAW/by-copy
dictionaries. Each `LazyImage` keeps one context and uses it exclusively on one
thread. Copies share close state; `close` is idempotent. Concurrent workers must
have distinct decoder owners. There is no implicit global or TLS cache.

The patch closes the temporary `fetchIndex` owner on both connection failure
and response completion. It removes the whole existing C shim and native
`linux` declaration, switches the chunk call, and compiles Minyar's provider
with the matched **real static** libzstd archive. `CC` must be an executable
path; provider flags remain separate argv elements. This custom build still
links neo-vm's unrelated Linux/net objects.

The note was generated from these read-only source identities:

- `shim/zstd.c` SHA256 `42967a94a69e66304c1a09d6d568ce1c85ca4d2a950e316fe4f8b0e195fbd69a`
- `mlib/linux.min` SHA256 `543d38f856d4d1cf565783abfa7295aa5b433e27ed84c81029d308cbeb67fbf2`
- `image/lazy.min` SHA256 `d72a0ba1bc2675a50a0cd629b647aaaf181650ea4dd75dee452364282a950e51`
- `tools/mbuild` SHA256 `241b388ebb123221ce64f60bc8113fe8b8cb769d021e1b2ab76d6d70c0f561ef`

```diff
--- a/shim/zstd.c
+++ /dev/null
@@ -1,22 +0,0 @@
-/*
- * zstd decompression for neo-vm's lazy chunk fetcher (Minyar gap IMAGE-1: the
- * Minyar standard library has no DEFLATE/zstd decoder). One function behind
- * `native "linux"`; tools/mbuild links this object (and libzstd) only into
- * programs that reference it. Returns the decompressed size or -1.
- */
-#include <stddef.h>
-
-typedef struct ZSTD_DCtx_s ZSTD_DCtx;
-ZSTD_DCtx *ZSTD_createDCtx(void);
-size_t ZSTD_decompressDCtx(ZSTD_DCtx *dctx, void *dst, size_t dstCapacity, const void *src, size_t compressedSize);
-unsigned ZSTD_isError(size_t code);
-
-/* One decompression context per thread, reused for every chunk (ZSTD_decompress would
- * allocate and initialise a fresh one per call, on the pull-to-first-byte path). */
-static __thread ZSTD_DCtx *dctx;
-
-long long minyar_linux_zstdDecompress(long long src, long long srcLen, long long dst, long long dstCap) {
-    if (!dctx && !(dctx = ZSTD_createDCtx())) return -1;
-    size_t n = ZSTD_decompressDCtx(dctx, (void *)(long)dst, (size_t)dstCap, (const void *)(long)src, (size_t)srcLen);
-    return ZSTD_isError(n) ? -1 : (long long)n;
-}
--- a/mlib/linux.min
+++ b/mlib/linux.min
@@ -6,8 +6,6 @@
 public function vcpuStart(slot: Integer): Integer { native "linux" }
 public function vcpuKick(thread: Integer): Integer { native "linux" }
 public function vcpuJoin(thread: Integer): Integer { native "linux" }
-// zstd-decompress src[0..srcLen) into dst (capacity dstCap); size or -1 (shim/zstd.c, gap IMAGE-1).
-public function zstdDecompress(src: Integer, srcLen: Integer, dst: Integer, dstCap: Integer): Integer { native "linux" }
 // Let vCPU threads answer virtio-mmio InterruptStatus/ACK for [base, base + count * 4 KiB).
 public function fastpath(base: Integer, count: Integer): Integer { native "linux" }
 
--- a/image/lazy.min
+++ b/image/lazy.min
@@ -15,6 +15,7 @@
 // An empty remoteBase means the cache must already hold every chunk.
 use "machine" as machine
 use "linux" as linux
+use "zstd" as zstd
 use "./sys.min" as sys
 use "./sha256.min" as sha
 use "./chunk.min" as chunk
@@ -53,6 +54,7 @@
     plainFallbacks: Integer
     wireBytes: Integer
     hasher: sha.Hasher
+    decoder: zstd.DCtx
     body: Bytes
     // First-touch order of chunks (for working-set traces).
     touched: List<Integer>
@@ -79,12 +81,12 @@
     let header = Bytes(chunk.HEADER)
     for i in 0..8 { header[i] = Bytes("NVIDX001")[i] }
     let img = openBytes(header, "", remoteBase)
-    if connect(img) < 0 { return -111 }
+    if connect(img) < 0 { close(img); return -111 }
     sys.writeBytes(img.sock, Bytes("GET " + img.prefix + "/" + name + ".idx HTTP/1.1\r\nHost: " + img.host + "\r\n\r\n"))
     let reader = Reader { pending: Bytes(); start: 0 }
     let state = Bytes(1)
     let status = readResponse(img, reader, state)
-    disconnect(img)
+    close(img)
     if status != 200 { return -2 }
     let tmp = outPath + ".part"
     writeBytesFile(tmp, img.body)
@@ -122,10 +124,11 @@
         index: index; indexAddress: 0; count: count; size: index.getInt64(8); cacheDir: cacheDir
         host: host; port: port; prefix: prefix; sock: -1
         present: Bytes(count); fds: fds; opened: []; openedHead: 0
-        verify: true; batch: 32; readahead: 32; compressed: false; plainFallbacks: 0; wireBytes: 0; hasher: sha.new(); body: Bytes(); touched: []
+        verify: true; batch: 32; readahead: 32; compressed: false; plainFallbacks: 0; wireBytes: 0; hasher: sha.new(); decoder: zstd.createDCtx(); body: Bytes(); touched: []
         reads: 0; bytesRead: 0; chunksFetched: 0; bytesFetched: 0; fetchNanos: 0; requests: 0; connects: 0; cacheHits: 0
         error: ""
     }
+    if !zstd.isOpenDCtx(img.decoder) { fail("cannot initialize zstd decoder") }
     img.indexAddress = machine.address(img.index)
     return img
 }
@@ -300,7 +303,7 @@
     img.wireBytes += body.length
     if img.compressed {
         let raw = Bytes(chunkLength(img, i))
-        let n = linux.zstdDecompress(machine.address(body), body.length, machine.address(raw), raw.length)
+        let n = zstd.decompressCtxRaw(img.decoder, machine.address(body), body.length, machine.address(raw), raw.length)
         if n < 0 { img.error = "chunk " + Text(i) + ": zstd decode failed"; return -5 }
         raw.resize(n)
         body = raw
@@ -548,6 +551,7 @@
 
 public function close(img: LazyImage) {
     disconnect(img)
+    zstd.closeDCtx(img.decoder)
     for i in 0..img.count {
         if img.fds[i] >= 0 { linux.close(img.fds[i]); img.fds[i] = -1 }
     }
--- a/tools/mbuild
+++ b/tools/mbuild
@@ -18,11 +18,24 @@
   [ -f "$root/out/obj/net.o" ] || $CC -O2 -c -iquote "$M/runtime" "$M/runtime/native/net.c" -o "$root/out/obj/net.o"
   extra="$root/out/obj/net.o"
 fi
-# zstd (lazy chunk decompression) only for dynamic programs: static ones (nv-init) never fetch chunks.
-if [ "$static" != "--static" ] && grep -q 'minyar_linux_zstdDecompress' "$ll"; then
-  [ "$root/out/obj/zstd.o" -nt "$root/shim/zstd.c" ] || $CC -O2 -c "$root/shim/zstd.c" -o "$root/out/obj/zstd.o"
-  extra="$extra $root/out/obj/zstd.o -l:libzstd.so.1"
-fi
-flags="-O2"
-[ "$static" = "--static" ] && flags="-O2 -static"
-$CC $flags "$ll" "$M/build/minyar-default-runtime.o" "$obj" $extra -lm -pthread -o "$out"
+# Keep native-provider flags as argv, including prefixes containing spaces.
+python3 - "$M" "$CC" "$ll" "$obj" "$extra" "$out" "$static" <<'PYLINK'
+from pathlib import Path
+import subprocess
+import sys
+minyar, cc, llvm, linux, net, output, static = sys.argv[1:]
+sys.path.insert(0, str(Path(minyar) / 'tools'))
+from compression_provider import codec_provider
+flags = ['-O2'] + (['-static'] if static == '--static' else [])
+native = [linux] + ([net] if net else [])
+ir = Path(llvm).read_text()
+if '; minyar-native-library: zstd\n' in ir:
+    cflags, libraries = codec_provider('zstd', cc, ['-O2'], flags)
+    obj = Path(output).resolve().parent / (Path(output).name + '.zstd.o')
+    subprocess.run([cc, '-O2', *cflags, '-c',
+                    str(Path(minyar) / 'runtime/native/zstd.c'), '-o', str(obj)], check=True)
+    native += [str(obj), *libraries]
+subprocess.run([cc, *flags, llvm,
+                str(Path(minyar) / 'build/minyar-default-runtime.o'),
+                *native, '-lm', '-pthread', '-o', output], check=True)
+PYLINK
```

Minyar's normal/custom-link compression suites exercise the raw context call,
context reuse after malformed input, shared close state, exact output limits,
and independent zstd interoperability. This patch itself still needs neo-vm's
Linux workload qualification after Minyar integration. IMAGE-3 can separately
replace neo-vm's hashing implementation with standalone `sha256`; tar now
provides the reader/writer portion of IMAGE-4. erofs/ext4 writing remains open.
