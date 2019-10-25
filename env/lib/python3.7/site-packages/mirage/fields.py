from django.db import models
from .crypto import Crypto
from .exceptions import EncryptedFieldException


class EncryptedMixin(models.Field):
    internal_type = "CharField"
    prepared_max_length = None

    def __init__(self, key=None, **kwargs):
        kwargs.setdefault('max_length', self.prepared_max_length)
        self.crypto = Crypto(key)
        super().__init__(**kwargs)

    def get_db_prep_value(self, value, connection, prepared=False):
        value = super().get_db_prep_value(value, connection, prepared)
        if value is not None:
            encrypted_text = self.crypto.encrypt(value)
            if self.max_length and len(encrypted_text) > self.max_length:
                raise EncryptedFieldException(
                    f"Field {self.name} max_length={self.max_length} encrypted_len={len(encrypted_text)}"
                )
            return encrypted_text
        return None

    def from_db_value(self, value, expression, connection, context):
        if value is not None:
            return self.to_python(self.crypto.decrypt(value))
        return None

    def get_internal_type(self):
        return self.internal_type


class EncryptedTextField(EncryptedMixin, models.TextField):
    internal_type = "TextField"


class EncryptedCharField(EncryptedMixin, models.CharField):
    prepared_max_length =255


class EncryptedEmailField(EncryptedMixin, models.EmailField):
    prepared_max_length = 254


class EncryptedIntegerField(EncryptedMixin, models.CharField):
    prepared_max_length = 64

    def to_python(self, value):
        if value is None:
            return value
        try:
            return int(value)
        except (TypeError, ValueError):
            raise exceptions.ValidationError(
                self.error_messages['invalid'],
                code='invalid',
                params={'value': value},
            )

    def check(self, **kwargs):
        return [
            *super(models.CharField, self).check(**kwargs),
        ]
