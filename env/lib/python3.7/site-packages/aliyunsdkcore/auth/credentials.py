class AccessKeyCredential:
    def __init__(self, access_key_id, access_key_secret):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret


class StsTokenCredential:
    def __init__(self, sts_access_key_id, sts_access_key_secret, sts_token):
        self.sts_access_key_id = sts_access_key_id
        self.sts_access_key_secret = sts_access_key_secret
        self.sts_token = sts_token


class RamRoleArnCredential:
    def __init__(self, sts_access_key_id, sts_access_key_secret, role_arn, session_role_name):
        self.sts_access_key_id = sts_access_key_id
        self.sts_access_key_secret = sts_access_key_secret
        self.role_arn = role_arn
        self.session_role_name = session_role_name


class EcsRamRoleCredential:
    def __init__(self, role_name):
        self.role_name = role_name


class RsaKeyPairCredential:
    def __init__(self, public_key_id, private_key, session_period=3600):
        self.public_key_id = public_key_id
        self.private_key = private_key
        self.session_period = session_period
