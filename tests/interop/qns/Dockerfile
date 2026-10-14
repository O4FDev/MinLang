FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends openssl libssl3t64 && rm -rf /var/lib/apt/lists/* && mkdir -p /opt/minyar /logs /downloads && chown 65534:65534 /logs /downloads
COPY server client endpoint /opt/minyar/
USER 65534:65534
ENTRYPOINT ["/opt/minyar/endpoint"]
