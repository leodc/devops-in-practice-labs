FROM public.ecr.aws/amazonlinux/amazonlinux:2023-minimal

RUN microdnf install -y python3 python3-pip shadow-utils && microdnf clean all
ARG EMULATOR_VERSION=1.0.322
RUN curl -fSL "https://downloads.aws.com/aws-emulator/packages/aws-emulator/LTS/aws-emulator-${EMULATOR_VERSION}-1-$(uname -m).rpm" -o /tmp/aws-emulator.rpm \
    && sha256sum /tmp/aws-emulator.rpm > /opt/emulator-package.sha256 \
    && rpm -i /tmp/aws-emulator.rpm \
    && rm /tmp/aws-emulator.rpm
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir boto3==1.40.75

RUN microdnf install -y nano && microdnf clean all
COPY lab.py writer.json validate.py docker-shell.sh requirements.txt Dockerfile /opt/lab/
ARG LAB_UID=1000
ARG LAB_GID=1000
RUN groupadd --non-unique --gid "$LAB_GID" emulator \
    && useradd --non-unique --create-home --uid "$LAB_UID" --gid emulator emulator \
    && chown -R emulator:emulator /opt/lab
USER emulator
ENV HOME=/home/emulator PATH=/opt/venv/bin:$PATH
WORKDIR /opt/lab
ENTRYPOINT ["bash", "/opt/lab/docker-shell.sh"]
