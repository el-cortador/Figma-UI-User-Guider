# Figma UI User Guider Agent

AI-агент для автоматической генерации пользовательских руководств по макетам Figma.
Агент анализирует структуру интерфейса и создаёт пошаговое руководство в формате Markdown и JSON.

## Как это работает

В отличие от простого пайплайна (Figma → фильтр → промпт → LLM), проект реализован как **AI-агент**: LLM сам управляет процессом и вызывает инструменты в нужном порядке.

```
Запрос пользователя
        │
        ▼
  ┌─────────────┐
  │  Agent Loop │◄──────────────────────┐
  └──────┬──────┘                       │
         │ выбирает инструмент          │ tool result
         ▼                              │
  ┌──────────────────────────────────┐  │
  │           Инструменты            │  │
  │  • fetch_figma_file              │──┘
  │  • filter_ui_elements            │
  │  • get_screen_elements           │
  └──────────────────────────────────┘
         │ финальный ответ
         ▼
   Markdown + JSON руководство
```

**Итерации агента:**
1. `fetch_figma_file` — загружает файл через Figma REST API, возвращает список экранов
2. `filter_ui_elements` — извлекает кнопки, поля ввода, заголовки и текстовые блоки по каждому экрану
3. `get_screen_elements` *(по необходимости)* — детальный анализ конкретного экрана
4. Генерирует финальный ответ в формате `MARKDOWN:` / `JSON:`

## Стек

| Слой        | Технология                         |
|-------------|------------------------------------|
| Backend     | FastAPI + uvicorn                  |
| HTTP-клиент | httpx                              |
| LLM         | OpenRouter (OpenAI-compatible API) |
| Figma       | Figma REST API v1                  |
| Frontend    | Vanilla HTML / CSS / JS            |
| Тесты       | pytest                             |

## Структура проекта

```
├── app/
│   ├── agent.py        # Агентный цикл и ChatClient-протокол
│   ├── config.py       # Конфигурация из .env
│   ├── figma.py        # Figma API-клиент
│   ├── filtering.py    # Фильтрация и структурирование Figma JSON
│   ├── generation.py   # Парсинг вывода LLM
│   ├── llm.py          # OpenRouter-клиент (OpenAI SDK)
│   ├── main.py         # FastAPI-приложение и эндпоинты
│   ├── schemas.py      # Pydantic-модели
│   └── tools.py        # Инструменты агента и ToolContext
├── tests/
│   ├── test_api.py
│   ├── test_figma.py
│   ├── test_filtering.py
│   └── test_generation.py
├── web/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── .env.example
├── requirements.txt
└── pytest.ini
```

## Установка

```bash
git clone <repo-url>
cd Figma-UI-User-Guider_Agent

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Настройка

Скопируйте `.env.example` в `.env` и заполните его нужными значениями:

```bash
cp .env.example .env
```

```env
# Figma API
FIGMA_API_TOKEN=[ваш Figma Personal Access Token]

# OpenRouter
OPENROUTER_API_KEY=[ваш API-ключ из OpenRouter]
LLM_MODEL_NAME=[название модели]

# Опционально
OPENROUTER_SITE_URL=https://your-site.com
OPENROUTER_APP_NAME=Figma UI User Guider
```

**Figma Personal Access Token** — получить в Figma: Settings → Security → Personal access tokens.

**OpenRouter API Key** — получить на [openrouter.ai/keys](https://openrouter.ai/keys).

### Описание переменных окружения

| Переменная            | Значение по умолчанию                    | Описание                                         |
|-----------------------|------------------------------------------|--------------------------------------------------|
| `FIGMA_API_TOKEN`     | —                                        | Figma Personal Access Token                      |
| `FIGMA_API_BASE`      | `https://api.figma.com/v1`               | Base URL Figma API                               |
| `REQUEST_TIMEOUT`     | `15`                                     | Таймаут запросов к Figma (сек)                   |
| `OPENROUTER_API_KEY`  | —                                        | API-ключ OpenRouter                              |
| `LLM_API_BASE`        | `https://openrouter.ai/api/v1`           | Base URL OpenRouter                              |
| `LLM_MODEL_NAME`      | `meta-llama/llama-3.3-70b-instruct`      | Модель                                           |
| `LLM_MAX_TOKENS`      | `4096`                                   | Максимумальное количество токенов в ответе       |
| `LLM_TEMPERATURE`     | `0.2`                                    | Температура модели                               |
| `LLM_TIMEOUT`         | `120`                                    | Таймаут LLM-запроса (сек)                        |
| `OPENROUTER_SITE_URL` | —                                        | URL сайта (заголовок `HTTP-Referer`)             |
| `OPENROUTER_APP_NAME` | `Figma UI User Guider`                   | Имя приложения (заголовок `X-Title`)             |

### Выбор модели

Для работы агента нужна модель с поддержкой function calling / tool use.
Фильтр на OpenRouter: [openrouter.ai/models?supported_parameters=tools](https://openrouter.ai/models?order=top&supported_parameters=tools)

## Запуск

```bash
uvicorn app.main:app --reload
```

Открыть в браузере: [http://localhost:8000](http://localhost:8000)

## Веб-интерфейс

1. Вставьте ссылку на макет Figma (формат `https://www.figma.com/file/...`)
2. Выберите уровень детализации: **Краткий** или **Подробный**
3. Выберите целевую аудиторию: **Пользователь / Разработчик / Инженер**
4. Нажмите «Сгенерировать руководство пользователя»
5. После генерации нажмите «Скачать результат» — результат сохранится в виде файла `guide.md`

## API

| Метод  | Эндпоинт               | Описание                                    |
|--------|------------------------|---------------------------------------------|
| `GET`  | `/`                    | Веб-интерфейс                               |
| `POST` | `/guide/generate`      | Генерация руководства (агент)               |
| `POST` | `/guide/export`        | То же, альтернативный эндпоинт для экспорта |
| `POST` | `/figma/file`          | Сырой Figma JSON (отладка)                  |
| `POST` | `/figma/file/filtered` | Отфильтрованный Figma JSON (отладка)        |

### Пример запроса

```bash
curl -X POST http://localhost:8000/guide/generate \
  -H "Content-Type: application/json" \
  -d '{
    "figma_url": "https://www.figma.com/file/AbCdEf1234/My-File",
    "figma_token": "",
    "language": "ru",
    "detail_level": "brief",
    "audience": "user"
  }'
```

### Пример ответа

```json
{
  "file_id": "AbCdEf1234",
  "markdown": "## Руководство\n\n### Шаг 1. Главный экран\n...",
  "guide_json": {
    "title": "Руководство по интерфейсу",
    "steps": [
      { "index": 1, "title": "Главный экран", "description": "..." }
    ]
  }
}
```

## Тесты

```bash
pytest
```