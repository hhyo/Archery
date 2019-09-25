"""Package signing."""
try:
    import cPickle as pickle
except ImportError:
    import pickle

from django_q import core_signing as signing

from django_q.conf import Conf

BadSignature = signing.BadSignature


class SignedPackage(object):

    """Wraps Django's signing module with custom Pickle serializer."""

    @staticmethod
    def dumps(obj, compressed=Conf.COMPRESSED):
        return signing.dumps(obj,
                             key=Conf.SECRET_KEY,
                             salt=Conf.PREFIX,
                             compress=compressed,
                             serializer=PickleSerializer)

    @staticmethod
    def loads(obj):
        return signing.loads(obj,
                             key=Conf.SECRET_KEY,
                             salt=Conf.PREFIX,
                             serializer=PickleSerializer)


class PickleSerializer(object):

    """Simple wrapper around Pickle for signing.dumps and signing.loads."""

    @staticmethod
    def dumps(obj):
        return pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def loads(data):
        return pickle.loads(data)
