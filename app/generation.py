from __future__ import annotations

import json


def build_prompt(
    filtered_json: dict,
    language: str,
    detail_level: str,
    audience: str,
) -> str:
    return (
        "Ты — технический писатель. Сгенерируй пошаговое руководство по интерфейсу. "
        "Ответ должен содержать два раздела: MARKDOWN и JSON. "
        "В JSON укажи: title, steps (массив объектов с полями index, title, description).\n\n"
        f"Язык: {language}\n"
        f"Детализация: {detail_level}\n"
        f"Аудитория: {audience}\n\n"
        "Данные об интерфейсе (JSON):\n"
        f"{json.dumps(filtered_json, ensure_ascii=False)}\n\n"
        "Формат ответа:\n"
        "MARKDOWN:\n<текст>\n\nJSON:\n<json>"
    )


def parse_llm_output(text: str) -> tuple[str, dict]:
    if "JSON:" not in text:
        return text.strip(), {"markdown": text.strip()}

    markdown_part, json_part = text.split("JSON:", 1)
    markdown = markdown_part.replace("MARKDOWN:", "").strip()
    json_str = json_part.strip()

    try:
        data = json.loads(json_str)
        return markdown, data
    except json.JSONDecodeError:
        return markdown, {"markdown": markdown}
