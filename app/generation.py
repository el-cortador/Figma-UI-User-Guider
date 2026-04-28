from __future__ import annotations


def _limit_elements(filtered_json: dict, limit: int = 20) -> dict:
    if not filtered_json or "screens" not in filtered_json:
        return filtered_json

    trimmed = {"file_name": filtered_json.get("file_name"), "screens": []}
    remaining = limit
    for screen in filtered_json.get("screens", []):
        if remaining <= 0:
            break
        elements = screen.get("elements", [])
        trimmed_elements = elements[:remaining]
        remaining -= len(trimmed_elements)
        trimmed["screens"].append(
            {
                "id": screen.get("id"),
                "name": screen.get("name"),
                "type": screen.get("type"),
                "elements": trimmed_elements,
            }
        )

    return trimmed


def build_prompt(
    filtered_json: dict,
    language: str,
    detail_level: str,
) -> str:
    import json

    limited_json = _limit_elements(filtered_json, limit=20)
    return (
        "Ты — технический писатель. Сгенерируй пошаговое руководство по интерфейсу в формате Markdown.\n\n"
        f"Язык: {language}\n"
        f"Детализация: {detail_level}\n\n"
        "Данные об интерфейсе (JSON):\n"
        f"{json.dumps(limited_json, ensure_ascii=False)}\n\n"
        "Формат ответа:\n"
        "MARKDOWN:\n<текст>"
    )


def parse_llm_output(text: str) -> str:
    """Extract the Markdown section from the LLM response."""
    cleaned = text
    while "<think>" in cleaned and "</think>" in cleaned:
        start = cleaned.find("<think>")
        end = cleaned.find("</think>", start)
        if end == -1:
            break
        cleaned = cleaned[:start] + cleaned[end + len("</think>"):]

    cleaned = cleaned.replace("<think>", "").replace("</think>", "")

    if "MARKDOWN:" in cleaned:
        cleaned = cleaned.split("MARKDOWN:", 1)[1]

    return cleaned.strip()
