#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE USER docker;
    CREATE DATABASE tvosauth;
    GRANT ALL PRIVILEGES ON DATABASE tvosauth TO docker;
EOSQL