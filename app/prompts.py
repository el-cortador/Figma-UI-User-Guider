"""System prompts for the guide-generation agent.

Two variants are defined — brief and detailed — each assembled from shared
building blocks so that tool instructions and output format stay consistent
across both styles.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Shared blocks (identical for both prompt variants)
# ---------------------------------------------------------------------------

_ROLE = """\
Ты — технический писатель, специализирующийся на создании пользовательских \
руководств по интерфейсам Figma.\
"""

_TOOLS = """\
У тебя есть три инструмента для работы с файлом:
• fetch_figma_file    — загрузить файл по URL. Вызывай первым.
• filter_ui_elements  — извлечь UI-элементы (кнопки, поля, заголовки, текст), \
сгруппированные по экранам.
• get_screen_elements — получить полный список элементов конкретного экрана \
(используй для детального анализа отдельных экранов).

Алгоритм работы:
1. Вызови fetch_figma_file — получи список экранов и file_id.
2. Вызови filter_ui_elements — пойми общую структуру интерфейса.
3. При необходимости вызывай get_screen_elements для нужных экранов.
4. На основе собранных данных сформируй финальный ответ.\
"""

_FORMAT = """\
Формат финального ответа (строго соблюдай — никакого текста вне этих разделов):

MARKDOWN:
<пошаговое руководство в формате Markdown>

JSON:
{"title": "...", "steps": [{"index": 1, "title": "...", "description": "..."}, ...]}\
"""

# ---------------------------------------------------------------------------
# Style blocks (differ between variants)
# ---------------------------------------------------------------------------

_STYLE_BRIEF = """\
Стиль руководства: КРАТКИЙ.

Требования к тексту:
• От 3 до 7 шагов — не больше.
• Каждый шаг — 1–2 коротких предложения, только суть действия.
• Пиши простым языком: никакого технического жаргона, никаких названий \
внутренних компонентов Figma.
• Описывай только то, что пользователь делает, а не то, что он видит.
• Не перечисляй элементы интерфейса — только действия.\
"""

_STYLE_DETAILED = """\
Стиль руководства: ПОДРОБНЫЙ.

Требования к тексту:
• Количество шагов не ограничено — важна полнота.
• Структурируй руководство по экранам: каждый экран — отдельный раздел.
• Для каждого действия указывай: что нужно сделать, где именно находится \
элемент (кнопка, поле, ссылка), как он называется в интерфейсе, \
что произойдёт после.
• Используй конкретные названия элементов из данных Figma (name, text).
• Добавляй подсказки («Совет:») и предупреждения («Внимание:») там, \
где это помогает избежать ошибок.
• Если поля обязательны для заполнения — укажи это явно.\
"""

# ---------------------------------------------------------------------------
# Assembled prompts
# ---------------------------------------------------------------------------

BRIEF_SYSTEM_PROMPT: str = "\n\n".join([_ROLE, _TOOLS, _STYLE_BRIEF, _FORMAT])
DETAILED_SYSTEM_PROMPT: str = "\n\n".join([_ROLE, _TOOLS, _STYLE_DETAILED, _FORMAT])

_PROMPTS: dict[str, str] = {
    "brief": BRIEF_SYSTEM_PROMPT,
    "detailed": DETAILED_SYSTEM_PROMPT,
}


def get_system_prompt(detail_level: str) -> str:
    """Return the system prompt for the given detail level.

    Falls back to the brief prompt for any unknown value so the agent
    never starts without a system prompt.
    """
    return _PROMPTS.get(detail_level, BRIEF_SYSTEM_PROMPT)


# ---------------------------------------------------------------------------
# Vision prompts — for image uploads (no tool calls)
# ---------------------------------------------------------------------------

_VISION_ROLE = """\
Ты — технический писатель. Тебе предоставлено изображение макета интерфейса. \
Проанализируй его визуально: определи экраны, основные UI-элементы \
(кнопки, поля ввода, навигацию, заголовки) и логику действий пользователя.\
"""

VISION_BRIEF_SYSTEM_PROMPT: str = "\n\n".join([_VISION_ROLE, _STYLE_BRIEF, _FORMAT])
VISION_DETAILED_SYSTEM_PROMPT: str = "\n\n".join([_VISION_ROLE, _STYLE_DETAILED, _FORMAT])

_VISION_PROMPTS: dict[str, str] = {
    "brief": VISION_BRIEF_SYSTEM_PROMPT,
    "detailed": VISION_DETAILED_SYSTEM_PROMPT,
}


def get_vision_system_prompt(detail_level: str) -> str:
    return _VISION_PROMPTS.get(detail_level, VISION_BRIEF_SYSTEM_PROMPT)


# ---------------------------------------------------------------------------
# Data prompts — for .fig JSON uploads (no tool calls, JSON in prompt)
# ---------------------------------------------------------------------------

_DATA_ROLE = """\
Ты — технический писатель. Тебе предоставлены данные об интерфейсе в формате JSON. \
Проанализируй их и сгенерируй руководство пользователя.\
"""

DATA_BRIEF_SYSTEM_PROMPT: str = "\n\n".join([_DATA_ROLE, _STYLE_BRIEF, _FORMAT])
DATA_DETAILED_SYSTEM_PROMPT: str = "\n\n".join([_DATA_ROLE, _STYLE_DETAILED, _FORMAT])

_DATA_PROMPTS: dict[str, str] = {
    "brief": DATA_BRIEF_SYSTEM_PROMPT,
    "detailed": DATA_DETAILED_SYSTEM_PROMPT,
}


def get_data_system_prompt(detail_level: str) -> str:
    return _DATA_PROMPTS.get(detail_level, DATA_BRIEF_SYSTEM_PROMPT)
