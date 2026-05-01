FROM ubuntu:noble as python-builder

RUN apt-get update && \
    apt-get install -y python3.12 python3.12-venv && \
    rm -rf /var/lib/apt/lists/*

RUN python3.12 -m venv /venv && \
    /venv/bin/pip install -U pip setuptools

COPY requirements.txt /app/requirements.txt
RUN  /venv/bin/pip install --no-deps --requirement /app/requirements.txt

# In order for template loading to work correctly, this has to be an editable mode install
COPY . /app
RUN /venv/bin/pip install --no-deps -e /app


FROM ubuntu:noble

# Don't buffer stdout and stderr as it breaks realtime logging
ENV PYTHONUNBUFFERED 1

# Make httpx use the system trust roots
# By default, this means we use the roots baked into the image
ENV SSL_CERT_FILE /etc/ssl/certs/ca-certificates.crt

# Create the user that will be used to run the app
ENV APP_UID 1001
ENV APP_GID 1001
ENV APP_USER app
ENV APP_GROUP app
RUN groupadd --gid $APP_GID $APP_GROUP && \
    useradd \
      --no-create-home \
      --no-user-group \
      --gid $APP_GID \
      --shell /sbin/nologin \
      --uid $APP_UID \
      $APP_USER

RUN apt-get update && \
    apt-get install -y \
      --no-install-recommends \
      --no-install-suggests \
      ca-certificates python3.12 tini \
    && \
    rm -rf /var/lib/apt/lists/*

COPY --from=python-builder /venv /venv
COPY --from=python-builder /app /app

USER $APP_UID
ENTRYPOINT ["tini", "-g", "--"]
CMD ["/venv/bin/kopf", "run", "--module", "perftest.operator", "--all-namespaces"]
