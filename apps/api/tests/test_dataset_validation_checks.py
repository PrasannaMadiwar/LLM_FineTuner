from app.domain.datasets import SemanticMapping
from app.services.dataset_validation_service import DatasetValidationService

MAPPING = SemanticMapping(user=["instruction"], assistant="output")


def _codes(report):
    return [issue.code for issue in report.issues]


def test_check_1_mapping_without_user_or_assistant_is_unsupported_schema():
    report = DatasetValidationService().validate_rows(
        [{"instruction": "Say hi", "output": "Hi"}],
        SemanticMapping(user=[], assistant="output"),
    )

    assert report.is_valid is False
    assert report.valid_rows == 0
    assert _codes(report) == ["unsupported_schema"]


def test_check_2_missing_user_prompt():
    report = DatasetValidationService().validate_rows([{"instruction": "   ", "output": "Hi"}], MAPPING)

    assert report.is_valid is False
    assert _codes(report) == ["missing_user_prompt"]
    assert report.issues[0].row_index == 0


def test_check_3_missing_assistant_response():
    report = DatasetValidationService().validate_rows([{"instruction": "Say hi", "output": None}], MAPPING)

    assert report.is_valid is False
    assert _codes(report) == ["missing_assistant_response"]


def test_check_4_mapped_column_missing_from_row_is_unsupported_schema():
    mapping = SemanticMapping(user=["instruction"], assistant="output", context=["input"])

    report = DatasetValidationService().validate_rows([{"instruction": "Say hi", "output": "Hi"}], mapping)

    assert report.is_valid is False
    assert _codes(report) == ["unsupported_schema"]
    assert "'input'" in report.issues[0].message


def test_check_5_sample_too_long():
    service = DatasetValidationService(max_content_length=10)

    report = service.validate_rows([{"instruction": "Say hi", "output": "x" * 11}], MAPPING)

    assert report.is_valid is False
    assert _codes(report) == ["sample_too_long"]


def test_check_5_sample_at_limit_is_accepted():
    service = DatasetValidationService(max_content_length=10)

    report = service.validate_rows([{"instruction": "Say hi", "output": "x" * 10}], MAPPING)

    assert report.is_valid is True


def test_check_6_invalid_utf8():
    # A lone surrogate is a valid Python str but cannot be encoded as UTF-8.
    report = DatasetValidationService().validate_rows([{"instruction": "Say hi", "output": "bad \ud800"}], MAPPING)

    assert report.is_valid is False
    assert _codes(report) == ["invalid_utf8"]


def test_check_7_duplicate_row_is_a_warning_not_an_error():
    rows = [
        {"instruction": "Say hi", "output": "Hi"},
        {"instruction": " Say hi ", "output": "Hi"},
    ]

    report = DatasetValidationService().validate_rows(rows, MAPPING)

    assert report.is_valid is True
    assert report.valid_rows == 2
    assert [(issue.code, issue.severity, issue.row_index) for issue in report.issues] == [
        ("duplicate_row", "warning", 1)
    ]


def test_valid_rows_counts_only_rows_without_errors():
    rows = [
        {"instruction": "Say hi", "output": "Hi"},
        {"instruction": "", "output": "Hi"},
        {"instruction": "Say bye", "output": "Bye"},
    ]

    report = DatasetValidationService().validate_rows(rows, MAPPING)

    assert report.is_valid is False
    assert report.total_rows == 3
    assert report.valid_rows == 2
