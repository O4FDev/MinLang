#!/bin/sh
# conformance-runner.sh OUT: build Google's Protocol Buffers conformance_test_runner at OUT, from the pinned
# Protocol Buffers 36.2 release and jsoncpp 1.9.6 sources (downloaded once and checked against their SHA-256), against
# the installed libprotobuf and protoc of the same version (pkg-config protobuf). `make check-protobuf-conformance`
# runs the suite with it. Set CXX to choose the C++ compiler; on macOS, SDKROOT is passed through to the link.
set -eu
out=$1
version=36.2
protobuf_sha256=3d9642a662d10e68ebae5e53f14dcce5105684212d5078f8e0d47d1ab3ae6b64
jsoncpp_version=1.9.6
jsoncpp_sha256=f93b6dd7ce796b13d02c108bc9f79812245a82e577581c4c9aabe57075c90ea2
installed=$(pkg-config --modversion protobuf 2>/dev/null || :)
if [ "$installed" != "$version.0" ]; then
    echo "conformance-runner.sh: needs libprotobuf $version (pkg-config protobuf reports '${installed:-nothing}')" >&2
    exit 1
fi
if [ "$(protoc --version)" != "libprotoc $version" ]; then
    echo "conformance-runner.sh: needs protoc $version on PATH" >&2
    exit 1
fi
cache=${XDG_CACHE_HOME:-$HOME/.cache}/minyar/protobuf-conformance
mkdir -p "$cache"
fetch() {
    url=$1 sum=$2 file=$cache/$3
    if [ ! -f "$file" ]; then
        curl -sSfL -o "$file.part" "$url"
        mv "$file.part" "$file"
    fi
    if [ "$(shasum -a 256 "$file" | cut -d' ' -f1)" != "$sum" ]; then
        echo "conformance-runner.sh: $file does not match its pinned SHA-256" >&2
        exit 1
    fi
}
fetch "https://github.com/protocolbuffers/protobuf/releases/download/v$version/protobuf-$version.tar.gz" "$protobuf_sha256" "protobuf-$version.tar.gz"
fetch "https://github.com/open-source-parsers/jsoncpp/archive/refs/tags/$jsoncpp_version.tar.gz" "$jsoncpp_sha256" "jsoncpp-$jsoncpp_version.tar.gz"
work=$(mktemp -d "${TMPDIR:-/tmp}/protobuf-conformance.XXXXXX")
trap 'rm -rf "$work"' EXIT
tar -xzf "$cache/protobuf-$version.tar.gz" -C "$work"
tar -xzf "$cache/jsoncpp-$jsoncpp_version.tar.gz" -C "$work"
source=$work/protobuf-$version
json=$work/jsoncpp-$jsoncpp_version
mkdir -p "$work/generated" "$work/objects"
protoc --proto_path="$source" --proto_path="$source/src" --cpp_out="$work/generated" \
    conformance/conformance.proto conformance/test_protos/test_messages_edition2023.proto \
    conformance/test_protos/test_messages_edition_unstable.proto \
    editions/golden/test_messages_proto3_editions.proto editions/golden/test_messages_proto2_editions.proto \
    google/protobuf/test_messages_proto3.proto google/protobuf/test_messages_proto2.proto
cxx=${CXX:-c++}
flags="-std=c++17 -O1 -DNDEBUG $(pkg-config --cflags protobuf) -I$work/generated -I$source -I$source/conformance -I$json/include"
objects=
for file in binary_json_conformance_suite binary_wireformat conformance_test conformance_test_main conformance_test_runner \
    failure_list_trie_node fork_pipe_runner text_format_conformance_suite; do
    $cxx $flags -c "$source/conformance/$file.cc" -o "$work/objects/$file.o"
    objects="$objects $work/objects/$file.o"
done
for file in json_reader json_value json_writer; do
    $cxx $flags -c "$json/src/lib_json/$file.cpp" -o "$work/objects/$file.o"
    objects="$objects $work/objects/$file.o"
done
index=0
for file in $(find "$work/generated" -name '*.pb.cc' | sort); do
    $cxx $flags -c "$file" -o "$work/objects/generated$index.o"
    objects="$objects $work/objects/generated$index.o"
    index=$((index + 1))
done
mkdir -p "$(dirname "$out")"
# shellcheck disable=SC2086
$cxx $objects $(pkg-config --libs protobuf) -o "$out.part"
mv "$out.part" "$out"
