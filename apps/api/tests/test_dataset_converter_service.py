from app.domain.datasets import SemanticMapping
from app.services.dataset_converter_service import DatasetConverterService


def test_converter_creates_messages_format():
    service = DatasetConverterService()
    rows = [{"instruction": "Summarize", "input": "A long article", "output": "Short summary"}]
    mapping = SemanticMapping(user=["instruction", "input"], assistant="output")

    conversations = service.convert_rows(rows, mapping)

    assert conversations[0].model_dump() == {
        "messages": [
            {"role": "user", "content": "Summarize\nA long article"},
            {"role": "assistant", "content": "Short summary"},
        ]
    }


def test_converter_includes_optional_system_and_context():
    service = DatasetConverterService()
    rows = [{"system": "Be terse", "context": "Policy", "prompt": "Answer", "response": "Done"}]
    mapping = SemanticMapping(
        user=["prompt"],
        assistant="response",
        system="system",
        context=["context"],
    )

    conversations = service.convert_rows(rows, mapping)

    assert [message.role for message in conversations[0].messages] == ["system", "user", "assistant"]
    assert conversations[0].messages[1].content == "Policy\nAnswer"
