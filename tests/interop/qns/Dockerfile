FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends python3 openssl libssl3t64 && rm -rf /var/lib/apt/lists/* && mkdir -p /opt/minyar /logs /downloads && chown 65534:65534 /logs /downloads
COPY server client /opt/minyar/
COPY endpoint.py /opt/minyar/endpoint.py
USER 65534:65534
ENTRYPOINT ["python3", "/opt/minyar/endpoint.py"]
