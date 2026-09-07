from app.connectors.jira.adf import adf_to_text


def test_adf_to_text_handles_none():
    assert adf_to_text(None) == ""


def test_adf_to_text_joins_paragraphs():
    doc = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Première phrase."}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "Deuxième phrase."}]},
        ],
    }

    assert adf_to_text(doc) == "Première phrase.\n\nDeuxième phrase."


def test_adf_to_text_renders_bullet_list_items():
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "Item 1"}]}
                        ],
                    },
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "Item 2"}]}
                        ],
                    },
                ],
            }
        ],
    }

    assert adf_to_text(doc) == "- Item 1\n- Item 2"


def test_adf_to_text_handles_hard_break_and_mention():
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Ligne 1"},
                    {"type": "hardBreak"},
                    {"type": "text", "text": "Ligne 2, cc "},
                    {"type": "mention", "attrs": {"text": "@Alice"}},
                ],
            }
        ],
    }

    assert adf_to_text(doc) == "Ligne 1\nLigne 2, cc @Alice"
