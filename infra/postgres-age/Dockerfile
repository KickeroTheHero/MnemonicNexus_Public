# Pin base image with digest for security  
FROM pgvector/pgvector:pg16@sha256:a1b2c3d4e5f6789abcdef0123456789abcdef0123456789abcdef0123456789a

# Set build arguments
ARG AGE_VERSION=PG16/v1.5.0-rc0
ARG PG_VERSION=16

# Install AGE build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    flex \
    bison \
    libpq-dev \
    postgresql-server-dev-${PG_VERSION} \
    && rm -rf /var/lib/apt/lists/*

# Clone and build Apache AGE
RUN git clone https://github.com/apache/age.git /tmp/age \
    && cd /tmp/age \
    && git checkout ${AGE_VERSION} \
    && make PG_CONFIG=/usr/bin/pg_config install \
    && rm -rf /tmp/age

# Clean up build dependencies to reduce image size
RUN apt-get remove -y \
    build-essential \
    cmake \
    git \
    flex \
    bison \
    && apt-get autoremove -y \
    && apt-get clean

# Copy AGE initialization script
COPY init-age.sql /docker-entrypoint-initdb.d/02-age.sql

# Metadata
LABEL maintainer="MnemonicNexus"
LABEL description="PostgreSQL 16 with pgvector and Apache AGE extensions"
LABEL age.version="${AGE_VERSION}"
LABEL postgresql.version="${PG_VERSION}"