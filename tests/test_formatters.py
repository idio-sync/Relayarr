from bot.plugins.overseerr.formatters import ResultFormatter

SAMPLE_RESULTS = [
    {
        "id": 157336, "title": "Interstellar", "releaseDate": "2014-11-05",
        "overview": "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.",
        "voteAverage": 8.6, "mediaType": "movie",
        "mediaInfo": {"status": 5},
    },
    {
        "id": 399404, "title": "Interstellar Wars", "releaseDate": "2016-06-02",
        "overview": "Aliens attack Earth and a group of fighter pilots must save the world.",
        "voteAverage": 2.1, "mediaType": "movie",
        "mediaInfo": None,
    },
]


class TestResultFormatter:
    def test_format_results_with_colors(self):
        fmt = ResultFormatter(irc_colors=True)
        lines = fmt.format_search_results(SAMPLE_RESULTS)
        assert len(lines) > 0
        assert any("1." in line for line in lines)
        assert any("Interstellar" in line for line in lines)

    def test_format_results_without_colors(self):
        fmt = ResultFormatter(irc_colors=False)
        lines = fmt.format_search_results(SAMPLE_RESULTS)
        for line in lines:
            assert "\x03" not in line

    def test_format_includes_tmdb_link(self):
        fmt = ResultFormatter(irc_colors=False)
        lines = fmt.format_search_results(SAMPLE_RESULTS)
        text = "\n".join(lines)
        assert "themoviedb.org/movie/157336" in text

    def test_format_includes_synopsis(self):
        fmt = ResultFormatter(irc_colors=False)
        lines = fmt.format_search_results(SAMPLE_RESULTS)
        text = "\n".join(lines)
        assert "wormhole" in text

    def test_synopsis_truncated(self):
        fmt = ResultFormatter(irc_colors=False)
        lines = fmt.format_search_results(SAMPLE_RESULTS)
        for line in lines:
            assert len(line.encode("utf-8")) <= 512

    def test_available_status_shown(self):
        fmt = ResultFormatter(irc_colors=False)
        lines = fmt.format_search_results(SAMPLE_RESULTS)
        text = "\n".join(lines)
        assert "[Available]" in text

    def test_no_status_for_unrequested(self):
        fmt = ResultFormatter(irc_colors=False)
        lines = fmt.format_search_results(SAMPLE_RESULTS)
        wars_lines = [l for l in lines if "Interstellar Wars" in l]
        for line in wars_lines:
            assert "[Available]" not in line

    def test_format_tv_link(self):
        tv_results = [
            {
                "id": 1399, "name": "Breaking Bad", "firstAirDate": "2008-01-20",
                "overview": "A chemistry teacher turns to crime.",
                "voteAverage": 9.5, "mediaType": "tv", "mediaInfo": None,
            }
        ]
        fmt = ResultFormatter(irc_colors=False)
        lines = fmt.format_search_results(tv_results)
        text = "\n".join(lines)
        assert "themoviedb.org/tv/1399" in text
        assert "Breaking Bad" in text

    def test_format_request_success(self):
        fmt = ResultFormatter(irc_colors=False)
        msg = fmt.format_request_success("Interstellar Wars", 2016)
        assert "Interstellar Wars" in msg
        assert "2016" in msg

    def test_format_already_available(self):
        fmt = ResultFormatter(irc_colors=False)
        msg = fmt.format_already_available("Interstellar", 2014)
        assert "already available" in msg.lower()
