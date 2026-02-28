from bot.plugins.lidarr.formatters import ArtistFormatter

SAMPLE_ARTIST = {
    "artistName": "Radiohead",
    "disambiguation": "UK rock band",
    "foreignArtistId": "a74b1b7f-71a5-4011-9441-d0b5e4122711",
    "overview": "Radiohead are an English rock band formed in Abingdon, Oxfordshire, in 1985.",
    "rating": {"value": 85, "count": 1234},
    "artistType": "Group",
}

SAMPLE_ARTISTS = [
    SAMPLE_ARTIST,
    {
        "artistName": "Radiohead Tribute",
        "disambiguation": "",
        "foreignArtistId": "deadbeef-0000-0000-0000-000000000000",
        "overview": "A tribute act performing Radiohead songs.",
        "rating": {"value": 20, "count": 5},
        "artistType": "Group",
    },
]


class TestArtistFormatter:
    def test_format_results_with_colors(self):
        fmt = ArtistFormatter(irc_colors=True)
        lines = fmt.format_search_results(SAMPLE_ARTISTS)
        assert len(lines) > 0
        assert any("1." in line for line in lines)
        assert any("Radiohead" in line for line in lines)
        # Bold codes should be present
        assert any("\x02" in line for line in lines)

    def test_format_results_without_colors(self):
        fmt = ArtistFormatter(irc_colors=False)
        lines = fmt.format_search_results(SAMPLE_ARTISTS)
        for line in lines:
            assert "\x03" not in line
            assert "\x02" not in line
            assert "\x0f" not in line

    def test_format_includes_musicbrainz_link(self):
        fmt = ArtistFormatter(irc_colors=False)
        lines = fmt.format_search_results([SAMPLE_ARTIST])
        text = "\n".join(lines)
        assert "musicbrainz.org/artist/a74b1b7f-71a5-4011-9441-d0b5e4122711" in text

    def test_format_includes_disambiguation(self):
        fmt = ArtistFormatter(irc_colors=False)
        lines = fmt.format_search_results([SAMPLE_ARTIST])
        text = "\n".join(lines)
        assert "(UK rock band)" in text

    def test_format_no_disambiguation(self):
        artist_no_disambig = {
            "artistName": "Muse",
            "foreignArtistId": "11111111-2222-3333-4444-555555555555",
            "overview": "An English rock band.",
            "rating": {"value": 90, "count": 500},
        }
        fmt = ArtistFormatter(irc_colors=False)
        lines = fmt.format_search_results([artist_no_disambig])
        text = "\n".join(lines)
        assert "Muse" in text
        # No empty parentheses should appear
        assert "()" not in text

    def test_format_request_success(self):
        fmt = ArtistFormatter(irc_colors=False)
        msg = fmt.format_request_success("Radiohead")
        assert "Radiohead" in msg
        assert "Artist added" in msg
        assert "Albums will begin downloading" in msg

    def test_format_already_monitored(self):
        fmt = ArtistFormatter(irc_colors=False)
        msg = fmt.format_already_monitored("Radiohead")
        assert "already in your library" in msg.lower()
        assert "Radiohead" in msg

    def test_synopsis_truncated(self):
        long_overview_artist = {
            "artistName": "Verbose Artist",
            "foreignArtistId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "overview": "A" * 200,
            "rating": {"value": 50, "count": 10},
        }
        fmt = ArtistFormatter(irc_colors=False)
        lines = fmt.format_search_results([long_overview_artist])
        overview_lines = [l for l in lines if l.startswith("   A")]
        assert len(overview_lines) == 1
        # 3 leading spaces + truncated text should respect MAX_SYNOPSIS_LEN
        content = overview_lines[0].strip()
        assert len(content) <= 80
        assert content.endswith("...")

    def test_format_empty_results(self):
        fmt = ArtistFormatter(irc_colors=False)
        lines = fmt.format_search_results([])
        assert lines == ["No artists found."]

    def test_format_already_monitored_tag(self):
        monitored_artist = dict(SAMPLE_ARTIST, _already_monitored=True)
        fmt = ArtistFormatter(irc_colors=False)
        lines = fmt.format_search_results([monitored_artist])
        text = "\n".join(lines)
        assert "[In Library]" in text
