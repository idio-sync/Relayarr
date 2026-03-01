BOLD = "\x02"
COLOR = "\x03"
RESET = "\x0f"
GREEN = "03"
YELLOW = "08"
GREY = "14"


class ShelfmarkFormatter:
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

    def format_search_results(self, results: list[dict], content_type: str) -> list[str]:
        if not results:
            return [f"No {content_type} results found."]
        lines = [f"Found {len(results)} {content_type} result(s):"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "Unknown")
            author = r.get("author", "Unknown")
            year = r.get("year", "????")
            fmt = r.get("format", "")
            size = r.get("size", "")
            detail = f" [{fmt}]" if fmt else ""
            detail += f" {size}" if size else ""
            lines.append(f"{i}. {self._bold(title)} — {author} ({year}){detail}")
        lines.append("Select with !select <number>")
        return lines

    def format_download_queued(self, title: str, author: str) -> str:
        check = self._color("\u2713", GREEN) if self._colors else "\u2713"
        return f"{check} Download queued for {self._bold(title)} by {author}."

    def format_status(self, status: dict) -> list[str]:
        active = status.get("active", [])
        queue = status.get("queue", [])
        if not active and not queue:
            return ["No active downloads or queued items."]
        lines = []
        if active:
            lines.append(f"Active downloads ({len(active)}):")
            for item in active:
                title = item.get("title", "Unknown")
                st = item.get("status", "unknown")
                progress = item.get("progress")
                prog_str = f" ({progress}%)" if progress is not None else ""
                lines.append(f"  {self._bold(title)} — {self._color(st, YELLOW)}{prog_str}")
        if queue:
            lines.append(f"Queued ({len(queue)}):")
            for item in queue:
                title = item.get("title", "Unknown")
                lines.append(f"  {self._bold(title)}")
        return lines
