set -eu
makefile=${1:-/src/ngtcp2/examples/Makefile.am}
block=$(sed -n '/^if ENABLE_EXAMPLE_BORINGSSL$/,/^endif # ENABLE_EXAMPLE_BORINGSSL$/p' "$makefile" | sed \
    -e 's/bsslclient/bsslhqclient/g' -e 's/bsslserver/bsslhqserver/g' \
    -e 's/WITH_EXAMPLE_HTTP3_PROTO_CODEC/WITH_EXAMPLE_HQ_PROTO_CODEC/g' \
    -e 's/http3_client_proto_codec/hq_client_proto_codec/g' -e 's/http3_server_proto_codec/hq_server_proto_codec/g' \
    -e 's|bsslhqserver_CPPFLAGS = ${bsslhqclient_CPPFLAGS}|& -I$(top_srcdir)/third-party|' \
    -e 's|bsslhqserver_LDADD = ${bsslhqclient_LDADD}|& $(top_builddir)/third-party/libhttp-parser.la|')
[ -n "$block" ]
printf '\n%s\n' "$block" >>"$makefile"
