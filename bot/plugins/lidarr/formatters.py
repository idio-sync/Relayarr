from bot.plugins.overseerr.formatters import BOLD, COLOR, RESET, GREEN, GREY, MAX_SYNOPSIS_LEN


class ArtistFormatter:
    def __init__(self, irc_colors: bool = True):
        self._colors = irc_colors

    def _bold(self, text: str) -> str:
        if self._colors:
            return f"{BOLD}{text}{BOLD}"
        return text

    def _color(self, text: str, color_code: str) -> str:
        if self._colors:
            return f"{COLOR}{color_code}{text}{RESET}"
        return text

    def _truncate(self, text: str, max_len: int = MAX_SYNOPSIS_LEN) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len - 3] + "..."

    def _musicbrainz_url(self, result: dict) -> str:
        mbid = result.get("foreignArtistId", "")
        return f"https://musicbrainz.org/artist/{mbid}"

    def format_search_results(self, results: list[dict]) -> list[str]:
        if not results:
            return ["No artists found."]
        lines = [f"Found {len(results)} artist(s):"]
        for i, r in enumerate(results, 1):
            name = r.get("artistName", "Unknown")
            disambiguation = r.get("disambiguation", "")
            rating = r.get("rating", {}).get("value", 0) or 0

            title_line = f"{i}. {self._bold(name)}"
            if disambiguation:
                title_line += f" ({disambiguation})"
            title_line += f" - \u2605 {rating:.0f}%"

            # Mark already monitored artists
            if r.get("_already_monitored"):
                title_line += " " + self._color("[In Library]", GREEN)

            lines.append(title_line)
            overview = r.get("overview", "")
            if overview:
                lines.append(f"   {self._truncate(overview)}")
            lines.append(f"   {self._musicbrainz_url(r)}")
        lines.append("Select with !select <number>")
        return lines

    def format_request_success(self, artist_name: str) -> str:
        check = self._color("\u2713", GREEN) if self._colors else "\u2713"
        return f"{check} Artist added: {self._bold(artist_name)}. Albums will begin downloading."

    def format_already_monitored(self, artist_name: str) -> str:
        return f"{self._bold(artist_name)} is already in your library!"
