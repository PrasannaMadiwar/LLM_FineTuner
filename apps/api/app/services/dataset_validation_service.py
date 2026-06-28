from app.domain.datasets import SemanticMapping, ValidationIssue, ValidationReport


class DatasetValidationService:
    def __init__(self, max_content_length: int = 16000):
        self._max_content_length = max_content_length

    def validate_rows(self, rows: list[dict], mapping: SemanticMapping) -> ValidationReport:
        issues: list[ValidationIssue] = []
        seen: set[str] = set()
        valid_rows = 0

        if not mapping.user or not mapping.assistant:
            return ValidationReport(
                is_valid=False,
                total_rows=len(rows),
                valid_rows=0,
                issues=[
                    ValidationIssue(
                        code="unsupported_schema",
                        message="Mapping must include at least one user column and one assistant column.",
                    )
                ],
            )

        for index, row in enumerate(rows):
            row_issues = self._validate_row(index, row, mapping)
            fingerprint = self._fingerprint(row, mapping)
            if fingerprint in seen:
                row_issues.append(
                    ValidationIssue(
                        code="duplicate_row",
                        message="Row duplicates an earlier sample.",
                        row_index=index,
                        severity="warning",
                    )
                )
            seen.add(fingerprint)
            issues.extend(row_issues)
            if not any(issue.severity == "error" for issue in row_issues):
                valid_rows += 1

        return ValidationReport(
            is_valid=not any(issue.severity == "error" for issue in issues),
            total_rows=len(rows),
            valid_rows=valid_rows,
            issues=issues,
        )

    def _validate_row(
        self,
        index: int,
        row: dict,
        mapping: SemanticMapping,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        user_content = self._join_columns(row, mapping.user)
        assistant_content = self._read_value(row, mapping.assistant)

        if not user_content:
            issues.append(
                ValidationIssue(
                    code="missing_user_prompt",
                    message="Row does not contain a usable user prompt.",
                    row_index=index,
                )
            )
        if not assistant_content:
            issues.append(
                ValidationIssue(
                    code="missing_assistant_response",
                    message="Row does not contain an assistant response.",
                    row_index=index,
                )
            )

        for column in [*mapping.user, mapping.assistant, *(mapping.context or [])]:
            if column not in row:
                issues.append(
                    ValidationIssue(
                        code="unsupported_schema",
                        message=f"Mapped column '{column}' is missing from the row.",
                        row_index=index,
                    )
                )
                continue
            value = self._read_value(row, column)
            if len(value) > self._max_content_length:
                issues.append(
                    ValidationIssue(
                        code="sample_too_long",
                        message=f"Column '{column}' exceeds the maximum supported content length.",
                        row_index=index,
                    )
                )
            try:
                value.encode("utf-8")
            except UnicodeError:
                issues.append(
                    ValidationIssue(
                        code="invalid_utf8",
                        message=f"Column '{column}' contains invalid UTF-8 text.",
                        row_index=index,
                    )
                )

        return issues

    def _join_columns(self, row: dict, columns: list[str]) -> str:
        return "\n".join(value for value in (self._read_value(row, column) for column in columns) if value)

    @staticmethod
    def _read_value(row: dict, column: str) -> str:
        value = row.get(column)
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    def _fingerprint(self, row: dict, mapping: SemanticMapping) -> str:
        values = [self._join_columns(row, mapping.user), self._read_value(row, mapping.assistant)]
        return "\n---\n".join(values)
