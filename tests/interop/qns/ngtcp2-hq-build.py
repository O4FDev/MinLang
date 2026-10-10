"""Wire upstream's existing HQ codec to its existing BoringSSL TLS adapter.
Only Makefile.am target declarations change; every protocol/TLS source remains
the exact pinned upstream revision. No interoperability assertions are changed.
"""
from pathlib import Path
path=Path('/src/ngtcp2/examples/Makefile.am');text=path.read_text()
begin=text.index('if ENABLE_EXAMPLE_BORINGSSL\n');end=text.index('endif # ENABLE_EXAMPLE_BORINGSSL',begin)+len('endif # ENABLE_EXAMPLE_BORINGSSL')
block=text[begin:end].replace('bsslclient','bsslhqclient').replace('bsslserver','bsslhqserver').replace('WITH_EXAMPLE_HTTP3_PROTO_CODEC','WITH_EXAMPLE_HQ_PROTO_CODEC').replace('http3_client_proto_codec','hq_client_proto_codec').replace('http3_server_proto_codec','hq_server_proto_codec')
block=block.replace('bsslhqserver_CPPFLAGS = ${bsslhqclient_CPPFLAGS}','bsslhqserver_CPPFLAGS = ${bsslhqclient_CPPFLAGS} -I$(top_srcdir)/third-party')
block=block.replace('bsslhqserver_LDADD = ${bsslhqclient_LDADD}','bsslhqserver_LDADD = ${bsslhqclient_LDADD} $(top_builddir)/third-party/libhttp-parser.la')
path.write_text(text+'\n'+block+'\n')
