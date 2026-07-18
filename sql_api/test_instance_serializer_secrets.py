import pytest
from sql.models import Instance
from sql_api.serializers import InstanceSerializer, InstanceDetailSerializer


@pytest.mark.django_db
def test_instance_serializer_hides_client_key_and_cert():
    ins = Instance.objects.create(
        instance_name="sec_ins",
        type="slave",
        db_type="mqtt",
        host="127.0.0.1",
        port=8883,
        user="",
        password="secret-pass",
        client_cert="CERTPEM",
        client_key="KEYPEM",
    )
    data = InstanceSerializer(ins).data
    assert "password" not in data or data.get("password") in (None, "", "******")
    # password 已是 write_only：键通常不在 data
    assert "client_key" not in data
    assert "client_cert" not in data
    detail = InstanceDetailSerializer(ins).data
    assert "client_key" not in detail
    assert "client_cert" not in detail
