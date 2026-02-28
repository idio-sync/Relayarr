from datetime import datetime, timezone
from urllib.parse import quote

# mIRC color codes
BOLD = "\x02"
COLOR = "\x03"
RESET = "\x0f"
GREEN = "03"

_GB = 1_073_741_824
_MB = 1_048_576
_KB = 1_024


def _format_size(size_bytes: int) -> str:
    if size_bytes >= _GB:
        return f"{size_bytes / _GB:.1f}GB"
    if size_bytes >= _MB:
        return f"{size_bytes / _MB:.1f}MB"
    if size_bytes >= _KB:
        return f"{size_bytes // _KB}KB"
    return f"{size_bytes}B"


class RommFormatter:
    def __init__(self, irc_colors: bool = True, domain: str = ""):
        self._colors = irc_colors
        self._domain = domain.rstrip("/")

    def _bold(self, text: str) -> str:
        if self._colors:
            return f"{BOLD}{text}{BOLD}"
        return text

    def _color(self, text: str, code: str) -> str:
        if self._colors:
            return f"{COLOR}{code}{text}{RESET}"
        return text

    def _download_url(self, rom_id: int, fs_name: str) -> str:
        encoded = quote(fs_name, safe="")
        return f"{self._domain}/api/roms/{rom_id}/content/{encoded}"

    # ------------------------------------------------------------------

    def format_search_results(self, results: list[dict], platform: str) -> list[str]:
        if not results:
            return [f"No ROMs found on {self._bold(platform)}."]
        lines = [f"Found {len(results)} ROM(s) on {self._bold(platform)}:"]
        for i, rom in enumerate(results[:10], 1):
            name = rom.get("name", "Unknown")
            size = _format_size(rom.get("file_size_bytes", 0))
            lines.append(f"  {i}. {self._bold(name)} ({size})")
        lines.append("Select with !select <number> for details + download link")
        return lines

    def format_rom_details(self, rom: dict) -> list[str]:
        name = rom.get("name", "Unknown")
        size = _format_size(rom.get("file_size_bytes", 0))
        lines = [f"{self._bold(name)} | {size}"]
        files = rom.get("files", [])
        if files:
            lines.append(f"  {len(files)} files in this ROM")
        url = self._download_url(rom["id"], rom.get("fs_name", ""))
        lines.append(url)
        return lines

    def format_igdb_results(self, results: list[dict], platform: str) -> list[str]:
        if not results:
            return ["No IGDB results found."]
        lines = ["Not in collection. Found on IGDB \u2014 select to request:"]
        for i, entry in enumerate(results, 1):
            name = entry.get("name", "Unknown")
            ts = entry.get("first_release_date")
            if ts:
                year = datetime.fromtimestamp(ts, tz=timezone.utc).year
            else:
                year = "????"
            genres_raw = entry.get("genres") or []
            genres = ", ".join(g["name"] for g in genres_raw) if genres_raw else ""
            line = f"  {i}. {self._bold(name)} ({year})"
            if genres:
                line += f" - {genres}"
            lines.append(line)
        lines.append("Select with !select <number> to request")
        return lines

    def format_platforms(self, platforms: list[dict]) -> list[str]:
        if not platforms:
            return ["No platforms found."]
        sorted_platforms = sorted(platforms, key=lambda p: p.get("name", ""))
        lines = []
        for p in sorted_platforms:
            name = p.get("name", "Unknown")
            slug = p.get("slug", "")
            count = p.get("rom_count", 0)
            lines.append(f"  {self._bold(name)} ({slug}) - {count} ROMs")
        return lines

    def format_stats(self, platforms: list[dict]) -> list[str]:
        num_platforms = len(platforms)
        total_roms = sum(p.get("rom_count", 0) for p in platforms)
        return [
            f"Collection: {self._bold(str(num_platforms))} platforms, {self._bold(str(total_roms))} ROMs"
        ]

    def format_firmware(self, firmware: list[dict], platform: str) -> list[str]:
        lines = [f"Firmware for {self._bold(platform)}:"]
        if not firmware:
            lines.append("  No firmware found.")
            return lines
        for fw in firmware:
            filename = fw.get("file_name", "unknown")
            size = _format_size(fw.get("file_size_bytes", 0))
            md5 = fw.get("md5_hash", "")
            lines.append(f"  {filename} ({size}) - MD5: {md5}")
        return lines

    def format_request_success(self, title: str, year: int | str, platform: str) -> str:
        check = self._color("\u2713", GREEN) if self._colors else "\u2713"
        return f"{check} Request submitted for {self._bold(title)} ({year}) on {platform}."

    def format_random_rom(self, rom: dict, platform: str) -> list[str]:
        name = rom.get("name", "Unknown")
        size = _format_size(rom.get("file_size_bytes", 0))
        url = self._download_url(rom["id"], rom.get("fs_name", ""))
        lines = [
            f"{self._bold(name)} | {size} | {platform}",
            url,
        ]
        return lines

    def format_new_rom(self, rom: dict, platform: str) -> str:
        name = rom.get("name", "Unknown")
        size = _format_size(rom.get("file_size_bytes", 0))
        url = self._download_url(rom["id"], rom.get("fs_name", ""))
        return f"New ROM: {self._bold(name)} | {size} | {platform} \u2014 {url}"
