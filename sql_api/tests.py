from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class InfoTest(TestCase):
    def setUp(self) -> None:
        self.superuser = User.objects.create(username='super', is_superuser=True)
        self.client.force_login(self.superuser)

    def tearDown(self) -> None:
        self.superuser.delete()

    def test_info_api(self):
        r = self.client.get('/api/info')
        r_json = r.json()
        self.assertIsInstance(r_json['archery']['version'], str)

    def test_debug_api(self):
        r = self.client.get('/api/debug')
        r_json = r.json()
        self.assertIsInstance(r_json['archery']['version'], str)
