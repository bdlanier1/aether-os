FROM ghcr.io/ublue-os/bazzite-nvidia:stable

RUN rpm-ostree install \
    python3-pyside6 \
    curl \
    unzip \
    && rpm-ostree cleanup -m

RUN curl -fsSL https://ollama.com/install.sh | sh && \
    systemctl enable ollama.service || true

COPY system_files/ /
COPY flatpaks/system-flatpaks.txt /usr/share/aether-os/system-flatpaks.txt

RUN sed -i 's/\r$//' /usr/bin/aether-first-boot /usr/bin/aether-hub && \
    chmod +x /usr/bin/aether-first-boot /usr/bin/aether-hub && \
    ostree container commit
