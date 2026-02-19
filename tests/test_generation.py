from app.generation import build_prompt, parse_llm_output


def test_build_prompt_contains_fields() -> None:
    prompt = build_prompt({"file_name": "Demo"}, "ru", "brief", "user")
    assert "Язык" in prompt
    assert "Детализация" in prompt
    assert "Аудитория" in prompt


def test_parse_llm_output_with_json() -> None:
    text = "MARKDOWN:\nШаг 1\n\nJSON:\n{\"title\":\"Demo\",\"steps\":[]}"  # noqa: E501
    markdown, data = parse_llm_output(text)
    assert markdown.startswith("Шаг 1")
    assert data["title"] == "Demo"
