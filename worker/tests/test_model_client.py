import pytest

from open_collar.model_client import GeminiChatModel, ModelClientError, create_model_client


def test_create_model_client_builds_gemini_client() -> None:
    client = create_model_client(
        {
            "provider": "gemini",
            "modelName": "gemini-2.5-flash",
            "apiKey": "test-key",
        }
    )

    assert isinstance(client, GeminiChatModel)
    assert client.model_name == "gemini-2.5-flash"


def test_create_model_client_requires_gemini_api_key() -> None:
    with pytest.raises(ModelClientError):
        create_model_client(
            {
                "provider": "gemini",
                "modelName": "gemini-2.5-flash",
                "apiKey": "",
            }
        )
