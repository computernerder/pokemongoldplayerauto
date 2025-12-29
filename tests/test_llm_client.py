from unittest.mock import Mock, patch

import llm_client


def test_chat_posts_payload_and_returns_json():
    fake_response = {"choices": [{"message": {"content": "Rhymed reply"}}]}

    with patch("llm_client.requests.post") as post:
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = fake_response

        messages = [
            {"role": "system", "content": "Always answer in rhymes. Today is Thursday"},
            {"role": "user", "content": "What day is it today?"},
        ]
        result = llm_client.chat(messages, model="qwen/qwen3-14b", temperature=0.5, max_tokens=-1, stream=False)

        assert result == fake_response

        post.assert_called_once()
        args, kwargs = post.call_args
        assert kwargs["json"]["model"] == "qwen/qwen3-14b"
        assert kwargs["json"]["messages"] == messages
        assert kwargs["json"]["temperature"] == 0.5
        assert kwargs["json"]["max_tokens"] == -1
        assert kwargs["json"]["stream"] is False


def test_chat_allows_extra_payload():
    fake_response = {"ok": True}

    with patch("llm_client.requests.post") as post:
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = fake_response

        extra = {"top_p": 0.9, "presence_penalty": 0.1}
        llm_client.chat([], extra=extra)

        args, kwargs = post.call_args
        payload = kwargs["json"]
        for k, v in extra.items():
            assert payload[k] == v
