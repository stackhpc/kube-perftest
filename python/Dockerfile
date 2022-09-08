FROM python:3.9

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

# Install tini, which we will use to marshal the processes
RUN apt-get update && \
    apt-get install -y tini && \
    rm -rf /var/lib/apt/lists/*

# Don't buffer stdout and stderr as it breaks realtime logging
ENV PYTHONUNBUFFERED 1

# Install dependencies
# Doing this separately by copying only the requirements file enables better use of the build cache
COPY ./requirements.txt /perftest/
RUN pip install --no-deps --requirement /perftest/requirements.txt

# Install the perftest package
COPY . /perftest
RUN pip install --no-deps -e /perftest

# By default, run the operator using kopf
USER $APP_UID
ENTRYPOINT ["tini", "-g", "--"]
CMD ["kopf", "run", "--module", "perftest.operator", "--all-namespaces"]
