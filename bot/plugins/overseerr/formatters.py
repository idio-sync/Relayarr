# mIRC color codes
BOLD = "\x02"
COLOR = "\x03"
RESET = "\x0f"
GREEN = "03"
YELLOW = "08"
GREY = "14"

# Overseerr media status codes
STATUS_AVAILABLE = 5
STATUS_PARTIALLY_AVAILABLE = 4
STATUS_PROCESSING = 3
STATUS_PENDING = 2

STATUS_LABELS = {
    STATUS_AVAILABLE: "Available",
    STATUS_PARTIALLY_AVAILABLE: "Partial",
    STATUS_PROCESSING: "Processing",
    STATUS_PENDING: "Pending",
}

STATUS_COLORS = {
    STATUS_AVAILABLE: GREEN,
    STATUS_PARTIALLY_AVAILABLE: YELLOW,
    STATUS_PROCESSING: YELLOW,
    STATUS_PENDING: YELLOW,
}

MAX_SYNOPSIS_LEN = 80


class ResultFormatter:
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

    def _status_tag(self, media_info: dict | None) -> str:
        if not media_info:
            return ""
        status = media_info.get("status")
        label = STATUS_LABELS.get(status, "")
        if not label:
            return ""
        color = STATUS_COLORS.get(status, GREY)
        return " " + self._color(f"[{label}]", color)

    def _truncate(self, text: str, max_len: int = MAX_SYNOPSIS_LEN) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len - 3] + "..."

    def _get_title(self, result: dict) -> str:
        return result.get("title") or result.get("name", "Unknown")

    def _get_year(self, result: dict) -> str:
        date = result.get("releaseDate") or result.get("firstAirDate", "")
        return date[:4] if date else "????"

    def _tmdb_url(self, result: dict) -> str:
        media_type = result.get("mediaType", "movie")
        tmdb_id = result.get("id", "")
        return f"https://www.themoviedb.org/{media_type}/{tmdb_id}"

    def format_search_results(self, results: list[dict]) -> list[str]:
        if not results:
            return ["No results found."]
        lines = [f"Found {len(results)} result(s):"]
        for i, r in enumerate(results, 1):
            title = self._get_title(r)
            year = self._get_year(r)
            rating = r.get("voteAverage", 0)
            status = self._status_tag(r.get("mediaInfo"))
            title_line = f"{i}. {self._bold(title)} ({year}) - \u2605 {rating:.1f}{status}"
            lines.append(title_line)
            overview = r.get("overview", "")
            if overview:
                lines.append(f"   {self._truncate(overview)}")
            lines.append(f"   {self._tmdb_url(r)}")
        lines.append("Select with !select <number>")
        return lines

    def format_request_success(self, title: str, year: int | str) -> str:
        check = self._color("\u2713", GREEN) if self._colors else "\u2713"
        return f"{check} Request submitted for {self._bold(title)} ({year}). Use !status to track."

    def format_already_available(self, title: str, year: int | str) -> str:
        return f"{self._bold(title)} ({year}) is already available in your library!"
