from app.retrieval.citation import CitationBuilder


class FakeChunk:
    chunk_id = "c1"
    doc_id = "d1"
    title = "黄芪条目"
    source = "药典"
    section = "功效"
    text = "黄芪补气升阳。"


def test_citation_builder_and_validator() -> None:
    builder = CitationBuilder()
    context, citations = builder.build([FakeChunk()])
    assert "[1]" in context
    report = builder.validate("黄芪可以补气 [1]", citations)
    assert report.valid is True


def test_out_of_range_citation_is_invalid() -> None:
    builder = CitationBuilder()
    _, citations = builder.build([FakeChunk()])
    report = builder.validate("黄芪可以补气 [2]", citations)
    assert report.valid is False
    assert report.invalid_indexes == [2]
