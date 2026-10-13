CI_GLFW_VERSION = 3.5.1
CI_GLFW_SHA256 = 5234f4f29473e9a06bc7847d8371858dd135d38466eeeaa652fdc9f8f9ff0c20

build/ci-glfw/glfw.tar.gz:
	mkdir -p $(@D)
	curl --fail --location --retry 3 https://github.com/glfw/glfw/archive/refs/tags/$(CI_GLFW_VERSION).tar.gz -o $@.tmp
	printf '%s  %s\n' '$(CI_GLFW_SHA256)' '$@.tmp' | shasum -a 256 --check
	mv $@.tmp $@

build/ci-glfw/source/src/nsgl_context.m: build/ci-glfw/glfw.tar.gz build/tooling/tools/glfw-software-source
	mkdir -p build/ci-glfw/source
	tar -xzf $< --strip-components=1 -C build/ci-glfw/source
	./build/tooling/tools/glfw-software-source $@ $@.tmp
	mv $@.tmp $@

.PHONY: prepare-macos-graphics
prepare-macos-graphics: build/ci-glfw/source/src/nsgl_context.m
	test "$$(uname -s)" = Darwin
	cmake -S build/ci-glfw/source -B build/ci-glfw/objects -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$(CURDIR)/build/ci-glfw/install" -DBUILD_SHARED_LIBS=OFF -DGLFW_BUILD_DOCS=OFF -DGLFW_BUILD_EXAMPLES=OFF -DGLFW_BUILD_TESTS=OFF
	cmake --build build/ci-glfw/objects --parallel 2
	cmake --install build/ci-glfw/objects

.PHONY: check-glfw-software-source
check-glfw-software-source: build/tooling/tests/glfw-software-source build/tooling/tools/glfw-software-source build/ci-glfw/glfw.tar.gz
	./build/tooling/tests/glfw-software-source ./build/tooling/tools/glfw-software-source build/ci-glfw/glfw.tar.gz
