import pytest

from rekuest_next.contrib.sql_lite.retriever import SQLLiteRetriever


@pytest.mark.asyncio
async def test_sqlite_retriever_initializes_schema(tmp_path) -> None:
    db_path = tmp_path / "state.db"
    retriever = SQLLiteRetriever(db_path=str(db_path))

    await retriever.ainitialize()

    boundary = await retriever.aget_task_boundaries("missing-correlation")

    assert boundary is None
