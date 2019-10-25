import base64

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from django.conf import settings
from django.utils.encoding import force_bytes, force_text


class Crypto:

    def __init__(self, key=None):
        if key is None:
            key = getattr(settings, "SECRET_KEY")
            assert len(key) >= 32, "settings.SECRET_KEY length must more than 32!"
            self.key = base64.urlsafe_b64encode(force_bytes(key))[:32]
        else:
            assert len(key) >= 32, "key length must more than 32!"
            self.key = key[:32]

    def encrypt(self, text):
        if text is None:
            return None
        try:
            self.try_decrypt(text)
            return text
        except Exception:
            return self.try_encrypt(text)

    def try_encrypt(self, text):
        encryptor = Cipher(algorithms.AES(self.key), modes.ECB(), default_backend()).encryptor()
        padder = padding.PKCS7(algorithms.AES(self.key).block_size).padder()
        padded_data = padder.update(force_bytes(text)) + padder.finalize()
        encrypted_text = encryptor.update(padded_data) + encryptor.finalize()
        return force_text(base64.urlsafe_b64encode(encrypted_text))

    def try_decrypt(self, encrypted_text):
        decryptor = Cipher(algorithms.AES(self.key), modes.ECB(), default_backend()).decryptor()
        padder = padding.PKCS7(algorithms.AES(self.key).block_size).unpadder()
        decrypted_text = decryptor.update(base64.urlsafe_b64decode(encrypted_text))
        unpadded_text = padder.update(decrypted_text) + padder.finalize()
        return force_text(unpadded_text)

    def decrypt(self, encrypted_text):
        if encrypted_text is None:
            return None
        try:
            return self.try_decrypt(encrypted_text)
        except Exception:
            return encrypted_text
