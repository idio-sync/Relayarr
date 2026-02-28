import pytest
from aioresponses import aioresponses
from bot.plugins.lidarr.api import LidarrClient, LidarrError


BASE_URL = "http://lidarr:8686"
API_KEY = "test-key"
QUALITY_PROFILE_ID = 1
METADATA_PROFILE_ID = 1
ROOT_FOLDER_PATH = "/music"


@pytest.fixture
def api():
    return LidarrClient(
        base_url=BASE_URL,
        api_key=API_KEY,
        quality_profile_id=QUALITY_PROFILE_ID,
        metadata_profile_id=METADATA_PROFILE_ID,
        root_folder_path=ROOT_FOLDER_PATH,
    )


SEARCH_RESPONSE = [
    {
        "artistName": "Radiohead",
        "foreignArtistId": "a74b1b7f-71a5-4011-9441-d0b5e4122711",
        "overview": "English rock band from Abingdon, Oxfordshire.",
        "images": [],
    },
    {
        "artistName": "Radiohead Tribute Band",
        "foreignArtistId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "overview": "A tribute act.",
        "images": [],
    },
]

ADD_ARTIST_RESPONSE = {
    "id": 1,
    "artistName": "Radiohead",
    "foreignArtistId": "a74b1b7f-71a5-4011-9441-d0b5e4122711",
    "monitored": True,
}

ARTISTS_RESPONSE = [
    {"id": 1, "artistName": "Radiohead", "foreignArtistId": "a74b1b7f-71a5-4011-9441-d0b5e4122711"},
    {"id": 2, "artistName": "Pink Floyd", "foreignArtistId": "83d91898-7763-47d7-b03b-b92132375c47"},
]


class TestLidarrSearchArtist:
    async def test_search_artist_returns_results(self, api):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/api/v1/artist/lookup?term=Radiohead", payload=SEARCH_RESPONSE)
            results = await api.search_artist("Radiohead")
            assert len(results) == 2
            assert results[0]["artistName"] == "Radiohead"

    async def test_search_artist_sends_api_key(self, api):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/api/v1/artist/lookup?term=test", payload=[])
            await api.search_artist("test")
            call = list(m.requests.values())[0][0]
            assert call.kwargs["headers"]["X-Api-Key"] == API_KEY

    async def test_search_artist_empty_results(self, api):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/api/v1/artist/lookup?term=zzzznonexistent", payload=[])
            results = await api.search_artist("zzzznonexistent")
            assert results == []


class TestLidarrAddArtist:
    async def test_add_artist_sends_correct_payload(self, api):
        with aioresponses() as m:
            m.post(f"{BASE_URL}/api/v1/artist", payload=ADD_ARTIST_RESPONSE)
            result = await api.add_artist(
                artist_name="Radiohead",
                foreign_artist_id="a74b1b7f-71a5-4011-9441-d0b5e4122711",
            )
            assert result["id"] == 1

            call = list(m.requests.values())[0][0]
            payload = call.kwargs["json"]
            assert payload["qualityProfileId"] == QUALITY_PROFILE_ID
            assert payload["metadataProfileId"] == METADATA_PROFILE_ID
            assert payload["rootFolderPath"] == ROOT_FOLDER_PATH
            assert payload["addOptions"]["searchForMissingAlbums"] is True
            assert payload["artistName"] == "Radiohead"
            assert payload["foreignArtistId"] == "a74b1b7f-71a5-4011-9441-d0b5e4122711"
            assert payload["monitored"] is True


class TestLidarrGetArtists:
    async def test_get_artists_returns_list(self, api):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/api/v1/artist", payload=ARTISTS_RESPONSE)
            results = await api.get_artists()
            assert len(results) == 2
            assert results[0]["artistName"] == "Radiohead"
            assert results[1]["artistName"] == "Pink Floyd"


class TestLidarrErrorHandling:
    async def test_api_error_raises_lidarr_error(self, api):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/api/v1/artist/lookup?term=test", status=500)
            with pytest.raises(LidarrError, match="API error"):
                await api.search_artist("test")


class TestLidarrSession:
    async def test_close_closes_session(self, api):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/api/v1/artist", payload=[])
            await api.get_artists()
            assert api._session is not None
            assert not api._session.closed
            await api.close()
            assert api._session.closed
