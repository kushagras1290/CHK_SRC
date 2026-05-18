from chakra_scraper.models import ScrapedRecord
from chakra_scraper.writer import write_csv, write_jsonl


def test_writers_create_expected_files(tmp_path) -> None:  # type: ignore[no-untyped-def]
    record = ScrapedRecord.from_parts(
        source_url="https://chakra.example.com/lead/1",
        data={"name": "Neeru", "phone": "+911234567890"},
        page_title="Lead 1",
        page_text="Name: Neeru",
    )

    csv_path = tmp_path / "out.csv"
    jsonl_path = tmp_path / "out.jsonl"
    write_csv(csv_path, [record])
    write_jsonl(jsonl_path, [record])

    assert "Neeru" in csv_path.read_text(encoding="utf-8")
    assert "Neeru" in jsonl_path.read_text(encoding="utf-8")
