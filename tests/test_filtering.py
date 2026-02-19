from app.filtering import filter_figma_json


def test_filter_figma_json_extracts_text_and_button() -> None:
    figma_json = {
        "name": "Demo",
        "document": {
            "id": "0:0",
            "name": "Root",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": "1:1",
                    "name": "Main Screen",
                    "type": "FRAME",
                    "children": [
                        {
                            "id": "2:1",
                            "name": "Primary Button",
                            "type": "COMPONENT",
                        },
                        {
                            "id": "2:2",
                            "name": "Header",
                            "type": "TEXT",
                            "characters": "Добро пожаловать",
                        },
                    ],
                }
            ],
        },
    }

    result = filter_figma_json(figma_json)
    assert result["file_name"] == "Demo"
    assert len(result["screens"]) == 1
    elements = result["screens"][0]["elements"]
    assert any(item["kind"] == "button" for item in elements)
    assert any(item["kind"] == "text" and item["text"] == "Добро пожаловать" for item in elements)
