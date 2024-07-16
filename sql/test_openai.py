import pytest


def test_check_openai(admin_client, setup_sys_config):
    """校验openai配置"""
    setup_sys_config.set("openai_base_url", "https://platform.openai.com/")
    response = admin_client.get("/check/openai/")
    assert response.status_code == 200
    assert response.json()["data"] == False

    setup_sys_config.set("openai_api_key", "sk-test-api-key")
    response = admin_client.get("/check/openai/")
    assert response.status_code == 200
    assert response.json()["data"] == False

    setup_sys_config.set("default_chat_model", "gpt-3.5-turbo")
    response = admin_client.get("/check/openai/")
    assert response.status_code == 200
    assert response.json()["data"] == True


@pytest.mark.parametrize(
    "data, expected_status",
    [
        (dict(), 1),
        (
            dict(
                db_type="mysql",
                query_desc="获取所有用户名为test的记录",
                instance_name="test_instance",
            ),
            1,
        ),
        (
            dict(
                db_type="mysql",
                query_desc="获取所有用户名为test的记录",
                instance_name="some_ins",
            ),
            1,
        ),
    ],
)
def test_generate_sql(admin_client, db_instance, data, expected_status):
    """测试openai生成sql"""
    response = admin_client.post("/query/generate_sql/", data=data)
    assert response.status_code == 200
    assert response.json()["status"] == expected_status
