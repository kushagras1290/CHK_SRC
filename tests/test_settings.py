from chakra_scraper.settings import Settings


def test_allowed_hosts_can_parse_comma_string() -> None:
    settings = Settings(allowed_hosts="a.example,b.example")

    assert settings.allowed_hosts == ["a.example", "b.example"]
