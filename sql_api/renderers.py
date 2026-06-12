import base64

import simplejson as json
from common.utils.extend_json_encoder import convert
from rest_framework.renderers import JSONRenderer
from rest_framework.utils import encoders


class SimpleJSONRenderer(JSONRenderer):
    encoder = encoders.JSONEncoder()

    @classmethod
    def sanitize(cls, value):
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                return base64.b64encode(value).decode("ascii")
        if isinstance(value, dict):
            return {
                str(cls.sanitize(key)): cls.sanitize(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [cls.sanitize(item) for item in value]
        if isinstance(value, set):
            return [cls.sanitize(item) for item in value]
        return value

    @classmethod
    def default(cls, obj):
        try:
            return convert(obj)
        except TypeError:
            return cls.encoder.default(obj)

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return b""

        renderer_context = renderer_context or {}
        indent = self.get_indent(accepted_media_type, renderer_context)

        if indent is None:
            separators = self.compact and (",", ":") or (", ", ": ")
        else:
            separators = (",", ": ")

        ret = json.dumps(
            self.sanitize(data),
            indent=indent,
            ensure_ascii=self.ensure_ascii,
            allow_nan=not self.strict,
            separators=separators,
            default=self.default,
        )
        # Keep DRF's default escaping so JSON stays safe if embedded into script content.
        ret = ret.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
        return ret.encode()
