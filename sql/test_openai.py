from typing import List
import pytest
from common.utils.openai import OpenaiClient


def test_check_openai(admin_client, setup_sys_config):
    """校验openai配置"""
    setup_sys_config.set("openai_base_url", "https://api.openai.com")
    response = admin_client.get("/check/openai/")
    assert response.status_code == 200
    assert response.json()["data"] == False

    setup_sys_config.set("openai_api_key", "sk-xxxx")
    response = admin_client.get("/check/openai/")
    assert response.status_code == 200
    assert response.json()["data"] == True


@pytest.fixture
def openai_client(setup_sys_config):
    # 使用mock来模拟SysConfig
    setup_sys_config.set("openai_base_url", "https://api.openai.com")
    setup_sys_config.set("openai_api_key", "sk-xxxx")
    setup_sys_config.set("default_chat_model", "gpt-3.5-turbo")
    yield OpenaiClient()


def test_init(openai_client):
    assert openai_client.base_url == "https://api.openai.com"
    assert openai_client.api_key == "sk-xxxx"
    assert openai_client.default_chat_model == "gpt-3.5-turbo"
    openai_client.client.close()


def test_request_chat_completion(openai_client, mocker):
    mock_response = {
        "id": "cmpl-123",
        "object": "text_completion",
        "created": 1234567890,
        "choices": [{"message": {"content": "SELECT * FROM table"}}],
    }
    mocker.patch.object(
        openai_client.client.chat.completions, "create", return_value=mock_response
    )
    result = openai_client.request_chat_completion(
        messages=[{"role": "user", "content": "test message"}]
    )
    assert result == mock_response


class ChatCompletionMessage:
    def __init__(self, content):
        self.content = content


class Choice:
    def __init__(self, message: ChatCompletionMessage):
        self.message = message


class ChatCompletion:
    def __init__(self, choices: List[Choice]):
        self.choices = choices


def test_generate_sql_by_openai(openai_client, mocker):
    mock_response = ChatCompletion(
        choices=[Choice(message=ChatCompletionMessage(content="SELECT * FROM table"))]
    )
    mocker.patch.object(
        openai_client, "request_chat_completion", return_value=mock_response
    )
    db_type = "MySQL"
    table_schema = "table_schema_description"
    query_desc = "query_description"
    result = openai_client.generate_sql_by_openai(db_type, table_schema, query_desc)
    assert result == "SELECT * FROM table"
    # exception
    mocker.patch.object(
        openai_client, "request_chat_completion", side_effect=ValueError("API Error")
    )
    with pytest.raises(ValueError) as excinfo:
        openai_client.generate_sql_by_openai(
            "MySQL", "table_schema_description", "query_description"
        )
    assert str(excinfo.value) == "请求openai生成查询语句失败: API Error"


@pytest.mark.parametrize(
    "data, expected_msg",
    [
        ({}, "query_desc or db_type不存在"),
        (
            {
                "db_type": "",
                "query_desc": "获取所有用户名为test的记录",
                "instance_name": "some_ins",
            },
            "query_desc or db_type不存在",
        ),
        (
            {
                "db_type": "MySQL",
                "query_desc": "获取所有用户名为test的记录",
                "instance_name": "test_instance",
            },
            "实例不存在",
        ),
    ],
)
def test_generate_sql(admin_client, db_instance, data, expected_msg):
    """测试openai生成sql"""
    response = admin_client.post("/query/generate_sql/", data=data)
    assert response.status_code == 200
    assert response.json()["msg"] == expected_msg
