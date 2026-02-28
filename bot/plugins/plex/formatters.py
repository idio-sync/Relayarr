from bot.plugins.overseerr.formatters import BOLD, COLOR, RESET, GREEN, YELLOW, GREY


class PlexFormatter:
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

    def _format_episode(self, item: dict) -> str:
        show = item.get("grandparentTitle", "Unknown")
        season = int(item.get("parentIndex", 0))
        episode = int(item.get("index", 0))
        return f"{show} S{season:02d}E{episode:02d}"

    def _format_track(self, item: dict) -> str:
        artist = item.get("grandparentTitle") or item.get("parentTitle", "Unknown")
        title = item.get("title", "Unknown")
        return f"{artist} \u2014 {title}"

    def _format_item_title(self, item: dict) -> str:
        media_type = item.get("type", "")
        if media_type == "episode":
            return self._format_episode(item)
        elif media_type == "track":
            return self._format_track(item)
        elif media_type == "album":
            artist = item.get("parentTitle", "")
            title = item.get("title", "Unknown")
            return f"{artist} \u2014 {title}" if artist else title
        else:
            title = item.get("title", "Unknown")
            year = item.get("year", "")
            return f"{title} ({year})" if year else title

    # --- Now Playing (Plex API) ---

    def format_now_playing_plex(self, sessions: list[dict]) -> list[str]:
        if not sessions:
            return ["No active streams on Plex."]
        count = len(sessions)
        lines = [self._bold(f"Now Playing ({count} stream{'s' if count != 1 else ''}):")]
        for s in sessions:
            user = s.get("User", {}).get("title", "Unknown")
            title = self._format_item_title(s)
            lines.append(f"  \u25b6 {self._bold(user)} is watching {title}")
        return lines

    # --- Now Playing (Tautulli) ---

    def format_now_playing_tautulli(self, sessions: list[dict]) -> list[str]:
        if not sessions:
            return ["No active streams on Plex."]
        count = len(sessions)
        lines = [self._bold(f"Now Playing ({count} stream{'s' if count != 1 else ''}):")]
        for s in sessions:
            user = s.get("friendly_name", "Unknown")
            title = s.get("full_title", "Unknown")
            quality = s.get("quality_profile", "")
            transcode = s.get("transcode_decision", "").title()
            progress = s.get("progress_percent", "0")
            detail = f" \u2014 {quality} {transcode} [{progress}%]" if quality else ""
            lines.append(f"  \u25b6 {self._bold(user)} is watching {title}{detail}")
        return lines

    # --- Library Stats ---

    def format_library_stats(self, libraries: list[dict]) -> list[str]:
        lines = [self._bold("Plex Libraries:")]
        for lib in libraries:
            title = lib["title"]
            lib_type = lib.get("type", "")
            count = lib.get("count", 0)
            added = lib.get("added_7d", 0)
            growth = f" ({self._color(f'+{added}', GREEN)} this week)" if added > 0 else ""

            if lib_type == "show":
                child_count = lib.get("child_count", 0)
                lines.append(
                    f"  \U0001f4fa {self._bold(title)}: {count:,} shows / {child_count:,} episodes{growth}"
                )
            elif lib_type == "artist":
                lines.append(f"  \U0001f3b5 {self._bold(title)}: {count:,} artists{growth}")
            else:
                lines.append(f"  \U0001f3ac {self._bold(title)}: {count:,}{growth}")
        return lines

    # --- Recently Added ---

    def format_recently_added(self, items: list[dict]) -> list[str]:
        if not items:
            return ["No recently added items on Plex."]
        lines = [self._bold("Recently Added:")]
        for item in items:
            title = self._format_item_title(item)
            library = item.get("librarySectionTitle", "")
            suffix = f" \u2014 {library}" if library else ""
            lines.append(f"  \u2022 {title}{suffix}")
        return lines

    # --- Auto-Announce ---

    def format_announcement(self, item: dict) -> str:
        title = self._format_item_title(item)
        library = item.get("librarySectionTitle", "")
        return f"New on Plex: {self._bold(title)} added to {library}"
