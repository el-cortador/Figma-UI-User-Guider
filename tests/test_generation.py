from app.generation import build_prompt, parse_llm_output


def test_build_prompt_contains_fields() -> None:
    prompt = build_prompt({"file_name": "Demo"}, "ru", "brief")
    assert "Язык" in prompt
    assert "Детализация" in prompt


def test_parse_llm_output_with_markdown_prefix() -> None:
    text = "MARKDOWN:\nШаг 1\nШаг 2"
    result = parse_llm_output(text)
    assert result.startswith("Шаг 1")


def test_parse_llm_output_without_prefix() -> None:
    result = parse_llm_output("Шаг 1\nШаг 2")
    assert result == "Шаг 1\nШаг 2"


def test_parse_llm_output_strips_think_tags() -> None:
    text = "<think>думаю</think>\nMARKDOWN:\nГотово"
    assert parse_llm_output(text) == "Готово"
