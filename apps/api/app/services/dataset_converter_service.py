from app.domain.datasets import NormalizedConversation, NormalizedMessage, SemanticMapping


class DatasetConverterService:
    def convert_rows(self, rows: list[dict], mapping: SemanticMapping) -> list[NormalizedConversation]:
        conversations: list[NormalizedConversation] = []
        for row in rows:
            messages: list[NormalizedMessage] = []
            system_content = self._read_value(row, mapping.system) if mapping.system else ""
            if system_content:
                messages.append(NormalizedMessage(role="system", content=system_content))

            user_content = self._build_user_content(row, mapping)
            assistant_content = self._read_value(row, mapping.assistant)
            if user_content:
                messages.append(NormalizedMessage(role="user", content=user_content))
            if assistant_content:
                messages.append(NormalizedMessage(role="assistant", content=assistant_content))

            conversations.append(NormalizedConversation(messages=messages))
        return conversations

    def _build_user_content(self, row: dict, mapping: SemanticMapping) -> str:
        content_parts = [self._read_value(row, column) for column in mapping.user]
        context_parts = [self._read_value(row, column) for column in mapping.context]
        values = [value for value in [*context_parts, *content_parts] if value]
        return "\n".join(values)

    @staticmethod
    def _read_value(row: dict, column: str | None) -> str:
        if column is None:
            return ""
        value = row.get(column)
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()
