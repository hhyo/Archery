#!/bin/sh

set -e
set -x

openssl version | tee openssl_version_p384.txt

# Private key
openssl ecparam -name secp384r1 -genkey -noout -conv_form uncompressed -out ecc_p384_private.pem
openssl ec -in ecc_p384_private.pem -outform DER -out ecc_p384_private.der
openssl pkcs8 -in ecc_p384_private.der -inform DER -out ecc_p384_private_p8_clear.der -outform DER -nocrypt -topk8
openssl pkcs8 -in ecc_p384_private.der -inform DER -out ecc_p384_private_p8_clear.pem -outform PEM -nocrypt -topk8
openssl ec -in ecc_p384_private.pem -text -out ecc_p384.txt

# Encrypted private key
openssl pkcs8 -in ecc_p384_private.der -inform DER -passout 'pass:secret' -out ecc_p384_private_p8.der -outform DER -topk8
openssl pkcs8 -in ecc_p384_private.der -inform DER -passout 'pass:secret' -out ecc_p384_private_p8.pem -outform PEM -topk8
openssl ec -in ecc_p384_private.pem -des3 -out ecc_p384_private_enc_des3.pem -passout 'pass:secret' -outform PEM
openssl ec -in ecc_p384_private.pem -aes128 -out ecc_p384_private_enc_aes128.pem -passout 'pass:secret' -outform PEM
openssl ec -in ecc_p384_private.pem -aes192 -out ecc_p384_private_enc_aes192.pem -passout 'pass:secret' -outform PEM
openssl ec -in ecc_p384_private.pem -aes-256-gcm -out ecc_p384_private_enc_aes256_gcm.pem -passout 'pass:secret' -outform PEM

# Public key
openssl ec -in ecc_p384_private.pem -pubout -out ecc_p384_public.pem
openssl ec -pubin -in ecc_p384_public.pem -outform DER -out ecc_p384_public.der
openssl ec -pubin -in ecc_p384_public.pem -outform DER -conv_form compressed -out ecc_p384_public_compressed.der
openssl ec -pubin -in ecc_p384_public.pem -outform PEM -conv_form compressed -out ecc_p384_public_compressed.pem

# X.509 cert
openssl req -new -key ecc_p384_private.pem -days 365 -x509 -out ecc_p384_x509.pem -subj '/C=GB/CN=example.com'
openssl x509 -in ecc_p384_x509.pem -out ecc_p384_x509.der -outform DER

# OpenSSH
chmod 600 ecc_p384_private.pem
ssh-keygen -f ecc_p384_private.pem -y > ecc_p384_public_openssh.txt
