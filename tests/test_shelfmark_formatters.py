from bot.plugins.shelfmark.formatters import ShelfmarkFormatter


SAMPLE_RESULTS = [
    {"id": "abc123", "title": "The Hobbit", "author": "J.R.R. Tolkien", "year": "1937", "format": "epub", "size": "2.1 MB"},
    {"id": "def456", "title": "The Lord of the Rings", "author": "J.R.R. Tolkien", "year": "1954", "format": "pdf", "size": "5.3 MB"},
]


class TestShelfmarkFormatter:
    def test_format_search_results_shows_count(self):
        fmt = ShelfmarkFormatter(irc_colors=False)
        lines = fmt.format_search_results(SAMPLE_RESULTS, "ebook")
        assert "2" in lines[0]
        assert "ebook" in lines[0]

    def test_format_search_results_shows_titles(self):
        fmt = ShelfmarkFormatter(irc_colors=False)
        lines = fmt.format_search_results(SAMPLE_RESULTS, "ebook")
        text = "\n".join(lines)
        assert "The Hobbit" in text
        assert "The Lord of the Rings" in text

    def test_format_search_results_shows_numbered(self):
        fmt = ShelfmarkFormatter(irc_colors=False)
        lines = fmt.format_search_results(SAMPLE_RESULTS, "ebook")
        text = "\n".join(lines)
        assert "1." in text
        assert "2." in text

    def test_format_search_results_shows_author_year(self):
        fmt = ShelfmarkFormatter(irc_colors=False)
        lines = fmt.format_search_results(SAMPLE_RESULTS, "ebook")
        text = "\n".join(lines)
        assert "J.R.R. Tolkien" in text
        assert "1937" in text

    def test_format_search_results_shows_select_hint(self):
        fmt = ShelfmarkFormatter(irc_colors=False)
        lines = fmt.format_search_results(SAMPLE_RESULTS, "ebook")
        assert any("!select" in line for line in lines)

    def test_format_search_results_empty(self):
        fmt = ShelfmarkFormatter(irc_colors=False)
        lines = fmt.format_search_results([], "ebook")
        assert any("No ebook results" in line for line in lines)

    def test_format_search_results_audiobook(self):
        fmt = ShelfmarkFormatter(irc_colors=False)
        lines = fmt.format_search_results(SAMPLE_RESULTS, "audiobook")
        assert "audiobook" in lines[0]

    def test_format_download_queued(self):
        fmt = ShelfmarkFormatter(irc_colors=False)
        msg = fmt.format_download_queued("The Hobbit", "J.R.R. Tolkien")
        assert "The Hobbit" in msg
        assert "queued" in msg.lower() or "download" in msg.lower()

    def test_format_status_with_items(self):
        fmt = ShelfmarkFormatter(irc_colors=False)
        status = {
            "active": [{"title": "The Hobbit", "status": "downloading", "progress": 45}],
            "queue": [{"title": "LOTR", "status": "queued"}],
        }
        lines = fmt.format_status(status)
        text = "\n".join(lines)
        assert "The Hobbit" in text

    def test_format_status_empty(self):
        fmt = ShelfmarkFormatter(irc_colors=False)
        status = {"active": [], "queue": []}
        lines = fmt.format_status(status)
        assert any("no" in line.lower() or "empty" in line.lower() for line in lines)

    def test_format_with_irc_colors(self):
        fmt = ShelfmarkFormatter(irc_colors=True)
        msg = fmt.format_download_queued("The Hobbit", "J.R.R. Tolkien")
        assert "\x02" in msg
