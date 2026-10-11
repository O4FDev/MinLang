These are unmodified official runner JSON exports from the remote overnight
interop lab. unsupported-quinn.json records the first Quinn endpoint adapter
attempt: the runner returned zero while handshake, transfer and Retry were all
null. succeeded-multipeer.json records Minyar's client
role against both quiche and msquic independent servers; succeeded-ngtcp2.json records Minyar's server
role against ngtcp2 including Retry. The controller regression reads the raw
JSON bytes and checks their retained hashes rather than treating process exit
status as the protocol verdict.
