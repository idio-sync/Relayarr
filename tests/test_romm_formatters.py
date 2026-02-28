import time

from bot.plugins.romm.formatters import RommFormatter, _format_size

BOLD = "\x02"
COLOR = "\x03"
RESET = "\x0f"


# ---------------------------------------------------------------------------
# _format_size
# ---------------------------------------------------------------------------

class TestFormatSize:
    def test_bytes(self):
        assert _format_size(500) == "500B"

    def test_kilobytes(self):
        assert _format_size(2048) == "2KB"

    def test_megabytes(self):
        assert _format_size(1_572_864) == "1.5MB"

    def test_gigabytes(self):
        assert _format_size(2_684_354_560) == "2.5GB"

    def test_exact_one_gb(self):
        assert _format_size(1_073_741_824) == "1.0GB"

    def test_exact_one_mb(self):
        assert _format_size(1_048_576) == "1.0MB"

    def test_exact_one_kb(self):
        assert _format_size(1024) == "1KB"

    def test_zero_bytes(self):
        assert _format_size(0) == "0B"


# ---------------------------------------------------------------------------
# RommFormatter helpers
# ---------------------------------------------------------------------------

class TestRommFormatterHelpers:
    def test_bold_with_colors(self):
        fmt = RommFormatter(irc_colors=True)
        assert fmt._bold("hi") == f"{BOLD}hi{BOLD}"

    def test_bold_without_colors(self):
        fmt = RommFormatter(irc_colors=False)
        assert fmt._bold("hi") == "hi"

    def test_color_with_colors(self):
        fmt = RommFormatter(irc_colors=True)
        result = fmt._color("hi", "03")
        assert result == f"{COLOR}03hi{RESET}"

    def test_color_without_colors(self):
        fmt = RommFormatter(irc_colors=False)
        assert fmt._color("hi", "03") == "hi"

    def test_download_url_no_domain(self):
        fmt = RommFormatter(domain="")
        url = fmt._download_url(42, "game.zip")
        assert url == "/api/roms/42/content/game.zip"

    def test_download_url_with_domain(self):
        fmt = RommFormatter(domain="https://romm.example.com")
        url = fmt._download_url(42, "game file.zip")
        assert url == "https://romm.example.com/api/roms/42/content/game%20file.zip"

    def test_download_url_encodes_special_chars(self):
        fmt = RommFormatter(domain="https://romm.example.com")
        url = fmt._download_url(1, "Sonic & Knuckles (USA).zip")
        assert " " not in url
        assert "&" not in url or "%26" in url


# ---------------------------------------------------------------------------
# format_search_results
# ---------------------------------------------------------------------------

SAMPLE_ROMS = [
    {"id": 1, "name": "Sonic the Hedgehog", "file_size_bytes": 524_288},
    {"id": 2, "name": "Streets of Rage", "file_size_bytes": 1_048_576},
    {"id": 3, "name": "Golden Axe", "file_size_bytes": 2_097_152},
]


class TestFormatSearchResults:
    def test_empty_returns_no_roms(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_search_results([], "Genesis")
        assert len(lines) == 1
        assert "No ROMs found" in lines[0]
        assert "Genesis" in lines[0]

    def test_header_line(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_search_results(SAMPLE_ROMS, "Genesis")
        assert lines[0].startswith("Found 3 ROM")
        assert "Genesis" in lines[0]

    def test_result_lines_numbered(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_search_results(SAMPLE_ROMS, "Genesis")
        result_lines = [l for l in lines if l.startswith("  ")]
        assert any("1." in l and "Sonic" in l for l in result_lines)
        assert any("2." in l and "Streets" in l for l in result_lines)
        assert any("3." in l and "Golden" in l for l in result_lines)

    def test_result_lines_include_size(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_search_results(SAMPLE_ROMS, "Genesis")
        sonic_line = next(l for l in lines if "Sonic" in l)
        assert "512KB" in sonic_line

    def test_footer_line(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_search_results(SAMPLE_ROMS, "Genesis")
        assert any("!select" in l for l in lines)

    def test_max_ten_results(self):
        roms = [{"id": i, "name": f"ROM {i}", "file_size_bytes": 1024} for i in range(20)]
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_search_results(roms, "NES")
        result_lines = [l for l in lines if l.startswith("  ")]
        assert len(result_lines) <= 10

    def test_bold_applied_with_colors(self):
        fmt = RommFormatter(irc_colors=True)
        lines = fmt.format_search_results(SAMPLE_ROMS, "Genesis")
        text = "\n".join(lines)
        assert BOLD in text

    def test_no_color_codes_without_colors(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_search_results(SAMPLE_ROMS, "Genesis")
        for line in lines:
            assert "\x02" not in line
            assert "\x03" not in line


# ---------------------------------------------------------------------------
# format_rom_details
# ---------------------------------------------------------------------------

SINGLE_ROM = {
    "id": 10,
    "name": "Castlevania",
    "file_size_bytes": 131_072,
    "fs_name": "Castlevania (USA).nes",
    "files": [],
}

MULTI_ROM = {
    "id": 11,
    "name": "Final Fantasy VII",
    "file_size_bytes": 1_610_612_736,
    "fs_name": "Final Fantasy VII (USA)",
    "files": ["disc1.iso", "disc2.iso", "disc3.iso"],
}


class TestFormatRomDetails:
    def test_name_in_first_line(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_rom_details(SINGLE_ROM)
        assert "Castlevania" in lines[0]

    def test_size_in_first_line(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_rom_details(SINGLE_ROM)
        assert "128KB" in lines[0]

    def test_download_url_present(self):
        fmt = RommFormatter(irc_colors=False, domain="https://romm.example.com")
        lines = fmt.format_rom_details(SINGLE_ROM)
        text = "\n".join(lines)
        assert "https://romm.example.com/api/roms/10/content/" in text

    def test_single_file_no_file_count(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_rom_details(SINGLE_ROM)
        text = "\n".join(lines)
        assert "files" not in text.lower() or "0 files" not in text.lower()

    def test_multi_file_shows_count(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_rom_details(MULTI_ROM)
        text = "\n".join(lines)
        assert "3 files" in text

    def test_multi_file_shows_count_line(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_rom_details(MULTI_ROM)
        assert any("3 files" in l for l in lines)


# ---------------------------------------------------------------------------
# format_igdb_results
# ---------------------------------------------------------------------------

IGDB_RESULTS = [
    {
        "name": "Chrono Trigger",
        "first_release_date": 800_006_400,  # 1995
        "genres": [{"name": "RPG"}, {"name": "Adventure"}],
    },
    {
        "name": "Secret of Mana",
        "first_release_date": None,
        "genres": [],
    },
]


class TestFormatIgdbResults:
    def test_header_not_in_collection(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_igdb_results(IGDB_RESULTS, "SNES")
        assert any("Not in collection" in l for l in lines)

    def test_result_numbered(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_igdb_results(IGDB_RESULTS, "SNES")
        result_lines = [l for l in lines if l.startswith("  ")]
        assert any("1." in l and "Chrono Trigger" in l for l in result_lines)

    def test_year_from_timestamp(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_igdb_results(IGDB_RESULTS, "SNES")
        chrono_line = next(l for l in lines if "Chrono Trigger" in l)
        assert "1995" in chrono_line

    def test_genres_shown(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_igdb_results(IGDB_RESULTS, "SNES")
        chrono_line = next(l for l in lines if "Chrono Trigger" in l)
        assert "RPG" in chrono_line

    def test_no_date_handled(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_igdb_results(IGDB_RESULTS, "SNES")
        mana_line = next(l for l in lines if "Secret of Mana" in l)
        assert mana_line  # just verify it renders

    def test_footer_select(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_igdb_results(IGDB_RESULTS, "SNES")
        assert any("!select" in l for l in lines)

    def test_empty_igdb(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_igdb_results([], "SNES")
        assert len(lines) >= 1


# ---------------------------------------------------------------------------
# format_platforms
# ---------------------------------------------------------------------------

PLATFORMS = [
    {"name": "Super Nintendo", "slug": "snes", "rom_count": 150},
    {"name": "Genesis", "slug": "genesis", "rom_count": 87},
    {"name": "Game Boy", "slug": "gb", "rom_count": 42},
]


class TestFormatPlatforms:
    def test_sorted_by_name(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_platforms(PLATFORMS)
        names = [l for l in lines if l.strip()]
        platform_lines = [l for l in names if "(" in l]
        assert "Game Boy" in platform_lines[0]
        assert "Genesis" in platform_lines[1]
        assert "Super Nintendo" in platform_lines[2]

    def test_slug_shown(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_platforms(PLATFORMS)
        text = "\n".join(lines)
        assert "snes" in text
        assert "genesis" in text

    def test_rom_count_shown(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_platforms(PLATFORMS)
        text = "\n".join(lines)
        assert "150" in text
        assert "87" in text

    def test_empty_platforms(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_platforms([])
        assert len(lines) >= 1


# ---------------------------------------------------------------------------
# format_stats
# ---------------------------------------------------------------------------

class TestFormatStats:
    def test_platform_count(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_stats(PLATFORMS)
        text = "\n".join(lines)
        assert "3" in text

    def test_rom_count_sum(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_stats(PLATFORMS)
        text = "\n".join(lines)
        # 150 + 87 + 42 = 279
        assert "279" in text

    def test_structure_contains_platforms_and_roms(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_stats(PLATFORMS)
        text = "\n".join(lines)
        assert "platform" in text.lower()
        assert "rom" in text.lower()


# ---------------------------------------------------------------------------
# format_firmware
# ---------------------------------------------------------------------------

FIRMWARE = [
    {"file_name": "bios.bin", "file_size_bytes": 524_288, "md5_hash": "abc123"},
    {"file_name": "scph1001.bin", "file_size_bytes": 524_288, "md5_hash": "def456"},
]


class TestFormatFirmware:
    def test_header_includes_platform(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_firmware(FIRMWARE, "PlayStation")
        assert any("PlayStation" in l for l in lines)

    def test_filename_shown(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_firmware(FIRMWARE, "PlayStation")
        text = "\n".join(lines)
        assert "bios.bin" in text
        assert "scph1001.bin" in text

    def test_size_shown(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_firmware(FIRMWARE, "PlayStation")
        text = "\n".join(lines)
        assert "512KB" in text

    def test_md5_shown(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_firmware(FIRMWARE, "PlayStation")
        text = "\n".join(lines)
        assert "abc123" in text
        assert "def456" in text

    def test_empty_firmware(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_firmware([], "PlayStation")
        assert len(lines) >= 1


# ---------------------------------------------------------------------------
# format_request_success
# ---------------------------------------------------------------------------

class TestFormatRequestSuccess:
    def test_contains_title(self):
        fmt = RommFormatter(irc_colors=False)
        msg = fmt.format_request_success("Chrono Trigger", 1995, "SNES")
        assert "Chrono Trigger" in msg

    def test_contains_year(self):
        fmt = RommFormatter(irc_colors=False)
        msg = fmt.format_request_success("Chrono Trigger", 1995, "SNES")
        assert "1995" in msg

    def test_contains_platform(self):
        fmt = RommFormatter(irc_colors=False)
        msg = fmt.format_request_success("Chrono Trigger", 1995, "SNES")
        assert "SNES" in msg

    def test_checkmark_present(self):
        fmt = RommFormatter(irc_colors=False)
        msg = fmt.format_request_success("Chrono Trigger", 1995, "SNES")
        assert "\u2713" in msg

    def test_returns_string(self):
        fmt = RommFormatter(irc_colors=False)
        msg = fmt.format_request_success("Chrono Trigger", 1995, "SNES")
        assert isinstance(msg, str)


# ---------------------------------------------------------------------------
# format_random_rom
# ---------------------------------------------------------------------------

RANDOM_ROM = {
    "id": 99,
    "name": "Bubble Bobble",
    "file_size_bytes": 65_536,
    "fs_name": "Bubble Bobble (USA).nes",
}


class TestFormatRandomRom:
    def test_name_present(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_random_rom(RANDOM_ROM, "NES")
        text = "\n".join(lines)
        assert "Bubble Bobble" in text

    def test_size_present(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_random_rom(RANDOM_ROM, "NES")
        text = "\n".join(lines)
        assert "64KB" in text

    def test_platform_present(self):
        fmt = RommFormatter(irc_colors=False)
        lines = fmt.format_random_rom(RANDOM_ROM, "NES")
        text = "\n".join(lines)
        assert "NES" in text

    def test_download_url_present(self):
        fmt = RommFormatter(irc_colors=False, domain="https://romm.example.com")
        lines = fmt.format_random_rom(RANDOM_ROM, "NES")
        text = "\n".join(lines)
        assert "/api/roms/99/content/" in text

    def test_returns_list(self):
        fmt = RommFormatter(irc_colors=False)
        result = fmt.format_random_rom(RANDOM_ROM, "NES")
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# format_new_rom
# ---------------------------------------------------------------------------

NEW_ROM = {
    "id": 55,
    "name": "Contra",
    "file_size_bytes": 131_072,
    "fs_name": "Contra (USA).nes",
}


class TestFormatNewRom:
    def test_name_present(self):
        fmt = RommFormatter(irc_colors=False)
        msg = fmt.format_new_rom(NEW_ROM, "NES")
        assert "Contra" in msg

    def test_size_present(self):
        fmt = RommFormatter(irc_colors=False)
        msg = fmt.format_new_rom(NEW_ROM, "NES")
        assert "128KB" in msg

    def test_platform_present(self):
        fmt = RommFormatter(irc_colors=False)
        msg = fmt.format_new_rom(NEW_ROM, "NES")
        assert "NES" in msg

    def test_download_url_present(self):
        fmt = RommFormatter(irc_colors=False, domain="https://romm.example.com")
        msg = fmt.format_new_rom(NEW_ROM, "NES")
        assert "/api/roms/55/content/" in msg

    def test_returns_string(self):
        fmt = RommFormatter(irc_colors=False)
        result = fmt.format_new_rom(NEW_ROM, "NES")
        assert isinstance(result, str)

    def test_new_rom_label(self):
        fmt = RommFormatter(irc_colors=False)
        msg = fmt.format_new_rom(NEW_ROM, "NES")
        assert "New ROM" in msg
