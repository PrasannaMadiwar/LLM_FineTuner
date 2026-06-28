from app.domain.datasets import SemanticMapping
from app.services.dataset_validation_service import DatasetValidationService


def test_validation_accepts_valid_rows():
    service = DatasetValidationService()
    rows = [{"instruction": "Say hi", "output": "Hi"}]
    mapping = SemanticMapping(user=["instruction"], assistant="output")

    report = service.validate_rows(rows, mapping)

    assert report.is_valid is True
    assert report.valid_rows == 1
    assert report.issues == []


def test_validation_reports_missing_required_values_and_duplicates():
    service = DatasetValidationService()
    rows = [
        {"instruction": "Say hi", "output": ""},
        {"instruction": "Say hi", "output": ""},
    ]
    mapping = SemanticMapping(user=["instruction"], assistant="output")

    report = service.validate_rows(rows, mapping)

    assert report.is_valid is False
    assert {issue.code for issue in report.issues} == {
        "missing_assistant_response",
        "duplicate_row",
    }


def test_validation_reports_unsupported_schema():
    service = DatasetValidationService()
    rows = [{"prompt": "Say hi", "completion": "Hi"}]
    mapping = SemanticMapping(user=["instruction"], assistant="output")

    report = service.validate_rows(rows, mapping)

    assert report.is_valid is False
    assert "unsupported_schema" in {issue.code for issue in report.issues}
