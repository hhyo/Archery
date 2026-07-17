#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-docs/superpowers/testdata/mq-certs}"
mkdir -p "$OUT"
openssl req -x509 -newkey rsa:2048 -days 3650 -nodes \
  -keyout "$OUT/ca.key" -out "$OUT/ca.crt" \
  -subj "/CN=ArcheryMQTestCA"
openssl req -newkey rsa:2048 -nodes -keyout "$OUT/server.key" -out "$OUT/server.csr" \
  -subj "/CN=localhost"
openssl x509 -req -in "$OUT/server.csr" -CA "$OUT/ca.crt" -CAkey "$OUT/ca.key" -CAcreateserial \
  -out "$OUT/server.crt" -days 3650
openssl req -newkey rsa:2048 -nodes -keyout "$OUT/client.key" -out "$OUT/client.csr" \
  -subj "/CN=archery-client"
openssl x509 -req -in "$OUT/client.csr" -CA "$OUT/ca.crt" -CAkey "$OUT/ca.key" -CAcreateserial \
  -out "$OUT/client.crt" -days 3650
echo "certs written to $OUT"
