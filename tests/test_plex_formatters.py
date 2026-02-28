import pytest

from bot.plugins.plex.formatters import PlexFormatter


@pytest.fixture
def fmt():
    return PlexFormatter(irc_colors=False)


@pytest.fixture
def fmt_colors():
    return PlexFormatter(irc_colors=True)


class TestFormatNowPlaying:
    def test_no_streams(self, fmt):
        lines = fmt.format_now_playing_plex([])
        assert len(lines) == 1
        assert "no active streams" in lines[0].lower()

    def test_movie_session(self, fmt):
        sessions = [
            {
                "User": {"title": "jake"},
                "title": "The Matrix",
                "year": 1999,
                "type": "movie",
            }
        ]
        lines = fmt.format_now_playing_plex(sessions)
        assert "1 stream" in lines[0]
        assert "jake" in lines[1]
        assert "The Matrix" in lines[1]
        assert "1999" in lines[1]

    def test_tv_session(self, fmt):
        sessions = [
            {
                "User": {"title": "alice"},
                "grandparentTitle": "Breaking Bad",
                "parentIndex": 3,
                "index": 7,
                "title": "One Minute",
                "type": "episode",
            }
        ]
        lines = fmt.format_now_playing_plex(sessions)
        assert "alice" in lines[1]
        assert "Breaking Bad" in lines[1]
        assert "S03E07" in lines[1]

    def test_music_session(self, fmt):
        sessions = [
            {
                "User": {"title": "bob"},
                "grandparentTitle": "Radiohead",
                "parentTitle": "OK Computer",
                "title": "Paranoid Android",
                "type": "track",
            }
        ]
        lines = fmt.format_now_playing_plex(sessions)
        assert "bob" in lines[1]
        assert "Radiohead" in lines[1]
        assert "Paranoid Android" in lines[1]

    def test_tautulli_enriched(self, fmt):
        sessions = [
            {
                "friendly_name": "jake",
                "full_title": "The Matrix (1999)",
                "media_type": "movie",
                "progress_percent": "45",
                "quality_profile": "1080p",
                "transcode_decision": "direct play",
                "state": "playing",
            }
        ]
        lines = fmt.format_now_playing_tautulli(sessions)
        assert "1 stream" in lines[0]
        assert "jake" in lines[1]
        assert "The Matrix" in lines[1]
        assert "1080p" in lines[1]
        assert "Direct Play" in lines[1]
        assert "45%" in lines[1]

    def test_tautulli_empty(self, fmt):
        lines = fmt.format_now_playing_tautulli([])
        assert "no active streams" in lines[0].lower()


class TestFormatLibraryStats:
    def test_single_movie_library(self, fmt):
        libraries = [
            {"title": "Movies", "type": "movie", "count": 1234, "added_7d": 12}
        ]
        lines = fmt.format_library_stats(libraries)
        assert "Plex Libraries" in lines[0]
        assert "Movies" in lines[1]
        assert "1,234" in lines[1]
        assert "+12" in lines[1]

    def test_tv_library(self, fmt):
        libraries = [
            {
                "title": "TV Shows",
                "type": "show",
                "count": 456,
                "child_count": 12345,
                "added_7d": 89,
            }
        ]
        lines = fmt.format_library_stats(libraries)
        assert "TV Shows" in lines[1]
        assert "456" in lines[1]
        assert "12,345" in lines[1]

    def test_no_growth(self, fmt):
        libraries = [
            {"title": "Movies", "type": "movie", "count": 100, "added_7d": 0}
        ]
        lines = fmt.format_library_stats(libraries)
        assert "+0" not in lines[1]

    def test_colors_enabled(self, fmt_colors):
        libraries = [
            {"title": "Movies", "type": "movie", "count": 100, "added_7d": 5}
        ]
        lines = fmt_colors.format_library_stats(libraries)
        assert "\x02" in lines[1]  # Bold


class TestFormatRecentlyAdded:
    def test_movie(self, fmt):
        items = [
            {"title": "The Matrix Resurrections", "year": 2021, "type": "movie", "librarySectionTitle": "Movies"}
        ]
        lines = fmt.format_recently_added(items)
        assert "Recently Added" in lines[0]
        assert "The Matrix Resurrections" in lines[1]
        assert "2021" in lines[1]
        assert "Movies" in lines[1]

    def test_episode(self, fmt):
        items = [
            {
                "grandparentTitle": "Breaking Bad",
                "parentIndex": 5,
                "index": 16,
                "title": "Felina",
                "type": "episode",
                "librarySectionTitle": "TV Shows",
            }
        ]
        lines = fmt.format_recently_added(items)
        assert "Breaking Bad" in lines[1]
        assert "S05E16" in lines[1]

    def test_album(self, fmt):
        items = [
            {
                "parentTitle": "The Beatles",
                "title": "Abbey Road",
                "type": "album",
                "librarySectionTitle": "Music",
            }
        ]
        lines = fmt.format_recently_added(items)
        assert "Abbey Road" in lines[1]
        assert "Music" in lines[1]

    def test_empty(self, fmt):
        lines = fmt.format_recently_added([])
        assert "no recently added" in lines[0].lower()


class TestFormatAnnouncement:
    def test_movie_announcement(self, fmt):
        item = {"title": "The Matrix Resurrections", "year": 2021, "type": "movie", "librarySectionTitle": "Movies"}
        line = fmt.format_announcement(item)
        assert "New on Plex" in line
        assert "The Matrix Resurrections" in line
        assert "2021" in line
        assert "Movies" in line

    def test_episode_announcement(self, fmt):
        item = {
            "grandparentTitle": "Breaking Bad",
            "parentIndex": 5,
            "index": 16,
            "title": "Felina",
            "type": "episode",
            "librarySectionTitle": "TV Shows",
        }
        line = fmt.format_announcement(item)
        assert "Breaking Bad" in line
        assert "S05E16" in line
