"""Bounded read-only adapters: HA media folders, connected Jellyfin, UK availability."""
import asyncio
from functools import partial
from itertools import chain
import json
import os
from pathlib import Path
from time import monotonic
from urllib.parse import quote, urlsplit

from .media_search import PROVIDER_NAMES, SUBSCRIPTIONS, recommendations_link, summarize, title_match
from .media_search_config import current

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".webm", ".mpg", ".mpeg", ".ts"}


async def _wait(awaitable, seconds=8):
    return await asyncio.wait_for(awaitable, timeout=seconds)


def _source(name, status, message="", matches=None):
    return {"name": name, "status": status, "message": message, "matches": matches or []}


def _scan_local(media_dirs, query, year):
    """Inspect names only, never open media files or follow directory symlinks."""
    matches, count, folders = [], 0, 0
    deadline = monotonic() + 5
    partial_result = False
    def failed(_error):
        nonlocal partial_result
        partial_result = True
    for source_id, root in list(media_dirs.items())[:10]:
        matched_folders = []
        if not Path(root).is_dir():
            partial_result = True
            continue
        for directory, dirs, files in os.walk(root, followlinks=False, onerror=failed):
            folders += 1
            dirs[:] = [name for name in dirs if not name.startswith(".") and
                       not Path(directory, name).is_symlink()]
            for name, kind in chain(((name, "folder") for name in dirs), ((name, "video") for name in files)):
                count += 1
                if count > 5000 or folders > 300 or monotonic() > deadline:
                    partial_result = True
                    break
                if name.startswith(".") or (kind == "video" and Path(name).suffix.lower() not in VIDEO_EXTENSIONS):
                    continue
                if kind == "video" and Path(directory, name).is_symlink():
                    continue
                if kind == "video":
                    for folder, item in matched_folders:
                        if Path(directory).is_relative_to(folder):
                            item["contains_video"] = True
                match = title_match(query, name)
                if match:
                    if year and str(year) not in name:
                        continue
                    relative = Path(directory, name).relative_to(root).as_posix()
                    item = {"title": name, "kind": kind, "match": match,
                            "media_id": "media-source://media_source/" +
                            quote(str(source_id), safe="") + "/" + quote(relative, safe="/")}
                    if kind == "folder":
                        item["contains_video"] = False
                        matched_folders.append((Path(directory, name), item))
                    matches.append(item)
            if partial_result or len(matches) >= 20:
                partial_result = True
                break
        if partial_result:
            break
    if len(media_dirs) > 10:
        partial_result = True
    matches.sort(key=lambda item: (item["match"] != "exact", item["kind"] != "folder", item["title"]))
    message = "The bounded folder scan was incomplete; absence is not confirmed." if partial_result else ""
    if (any(item["kind"] == "folder" and item["match"] == "exact" for item in matches)
            and not any(item["match"] == "exact" and (item["kind"] == "video" or item.get("contains_video")) for item in matches)):
        message += " A matching folder exists, but no video file was confirmed; other sources will still be checked."
    return _source("Home Assistant media", "partial" if partial_result else "complete", message.strip(), matches[:10])


async def search_local(hass, query, year):
    dirs = getattr(hass.config, "media_dirs", {})
    if not isinstance(dirs, dict) or not dirs:
        return _source("Home Assistant media", "not_configured", "No HA media folders are configured.")
    try:
        return await _wait(hass.async_add_executor_job(_scan_local, dict(dirs), query, year))
    except (OSError, ValueError, TimeoutError):
        return _source("Home Assistant media", "unavailable", "The media folders could not be checked.")


async def search_jellyfin(hass, query, year):
    entries = hass.config_entries.async_entries("jellyfin")
    if not entries:
        return _source("Jellyfin", "not_configured", "Connect Jellyfin through its Home Assistant integration.")
    matches, checked, failed, incomplete = [], 0, False, len(entries) > 3
    deadline = monotonic() + 10
    for entry in entries[:3]:
        client = getattr(getattr(entry, "runtime_data", None), "api_client", None)
        api = getattr(client, "jellyfin", None)
        method = getattr(api, "search_media_items", None)
        if method is None:
            failed = True
            continue
        try:
            # The existing HA Jellyfin session supplies its user and credentials.
            terms = [query]
            words = query.split()
            if len(words) > 1:
                terms.append(max(words, key=len))
            for term in dict.fromkeys(terms):
                if monotonic() > deadline:
                    incomplete = True
                    break
                payload = await _wait(hass.async_add_executor_job(partial(
                    method, term=term, year=year, media="Movie,Series", limit=30)), 5)
                if not isinstance(payload, dict) or not isinstance(payload.get("Items"), list):
                    raise ValueError("Invalid library response")
                checked += 1
                if payload.get("TotalRecordCount", 0) > 30:
                    incomplete = True
                found = []
                for item in payload["Items"][:30]:
                    if not isinstance(item, dict) or item.get("Type") not in {"Movie", "Series"}:
                        continue
                    name = item.get("Name")
                    if not isinstance(name, str):
                        continue
                    match = title_match(query, name)
                    if match and (not year or item.get("ProductionYear") == year):
                        found.append({"title": name, "year": item.get("ProductionYear"),
                                      "kind": "series" if item["Type"] == "Series" else "movie",
                                      "match": match})
                matches.extend(found)
                if any(item["match"] == "exact" for item in found):
                    break
        except (OSError, ValueError, KeyError, TypeError, TimeoutError):
            failed = True
        except Exception:
            # Jellyfin clients use several HTTP exception types. Never surface
            # their exception messages, which can contain authenticated URLs.
            failed = True
    unique = {(item["title"], item.get("year"), item["kind"]): item for item in matches}
    matches = sorted(unique.values(), key=lambda item: item["match"] != "exact")[:10]
    if not checked:
        return _source("Jellyfin", "unavailable", "The connected Jellyfin library could not be checked.")
    return _source("Jellyfin", "partial" if failed or incomplete else "complete",
                   "Some Jellyfin results could not be checked; absence is not confirmed." if failed or incomplete else "",
                   matches)


async def _tmdb_json(hass, token, path, params=None):
    # No user-controlled host, playback URL resolution, cookies or account login.
    from homeassistant.helpers.aiohttp_client import async_get_clientsession
    from aiohttp import ClientTimeout
    session = async_get_clientsession(hass)
    async with session.get(
            "https://api.themoviedb.org/3/" + path,
            params=params, headers={"Authorization": "Bearer " + token},
            timeout=ClientTimeout(total=5), allow_redirects=False) as response:
        if response.status != 200:
            raise ValueError("Catalogue request failed")
        raw = await response.content.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ValueError("Catalogue response too large")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("Invalid catalogue response")
        return result


def _provider_key(name):
    return next((key for key, names in PROVIDER_NAMES.items() if name.casefold() in names), None)


def _watch_link(link):
    if not isinstance(link, str):
        return None
    parsed = urlsplit(link)
    if parsed.scheme == "https" and parsed.hostname in {"www.themoviedb.org", "themoviedb.org"} and not parsed.username:
        return link
    return None


async def search_streaming(hass, query, year):
    config = current(hass)
    token = config.get("tmdb_token")
    if not token:
        return {"status": "not_configured", "matches": [],
                "message": "UK subscription catalogues were not checked. Add a TMDB API read access token in Media search settings."}
    try:
        payload = await _tmdb_json(hass, token, "search/multi",
                                   {"query": query, "include_adult": "false", "language": "en-GB"})
        candidates = payload.get("results", [])
        if not isinstance(candidates, list):
            raise ValueError("Invalid catalogue results")
        # A second title-only search helps common split-word transcriptions.
        if not candidates and len(query.split()) > 1:
            words = query.split()
            retry = " ".join(words[:-2] + ["".join(words[-2:])])
            payload = await _tmdb_json(hass, token, "search/multi",
                                       {"query": retry, "include_adult": "false", "language": "en-GB"})
            candidates = payload.get("results", [])
            if not isinstance(candidates, list):
                raise ValueError("Invalid catalogue results")
        exact, possible = [], []
        for item in candidates[:20]:
            if not isinstance(item, dict) or item.get("media_type") not in {"movie", "tv"}:
                continue
            if not isinstance(item.get("id"), int) or isinstance(item["id"], bool) or item["id"] <= 0:
                continue
            title = item.get("title") or item.get("name")
            date = item.get("release_date") or item.get("first_air_date") or ""
            if not isinstance(title, str) or not isinstance(date, str):
                continue
            if year and date[:4] != str(year):
                continue
            match = title_match(query, title)
            if match:
                entry = {**item, "_title": title, "_year": date[:4]}
                (exact if match == "exact" else possible).append(entry)
        # Never silently choose a remake or a fuzzy title for provider claims.
        distinct = {(item["media_type"], item["id"]): item for item in exact}
        if len(distinct) != 1:
            options = list(distinct.values()) or possible
            if options:
                return {"status": "ambiguous", "matches": [],
                        "candidates": [item["_title"] + " (" + (item["_year"] or "year unknown") +
                                       ", " + item["media_type"] + ")" for item in options[:4]]}
            return {"status": "complete", "matches": [], "attribution": "JustWatch via TMDB"}
        item = next(iter(distinct.values()))
        payload = await _tmdb_json(hass, token, item["media_type"] + "/" + str(item["id"]) + "/watch/providers")
        regions = payload.get("results")
        if not isinstance(regions, dict):
            raise ValueError("Invalid provider results")
        offers = regions.get("GB", {})
        if not isinstance(offers, dict):
            raise ValueError("Invalid regional results")
        selected, other = [], []
        for offer_type, label in [("flatrate", "subscription"), ("free", "free"),
                                  ("ads", "with adverts"), ("rent", "rent"), ("buy", "buy")]:
            providers = offers.get(offer_type, [])
            if not isinstance(providers, list):
                raise ValueError("Invalid provider list")
            for provider in providers[:50]:
                if not isinstance(provider, dict) or not isinstance(provider.get("provider_name"), str):
                    continue
                name = provider["provider_name"]
                key = _provider_key(name)
                if offer_type == "flatrate" and key in config.get("subscriptions", list(SUBSCRIPTIONS)):
                    selected.append(name)
                else:
                    other.append(name + " (" + label + ")")
        return {"status": "complete", "attribution": "JustWatch via TMDB", "matches": [{
            "title": item["_title"], "year": item["_year"], "kind": item["media_type"],
            "selected_subscriptions": list(dict.fromkeys(selected)),
            "other_offers": list(dict.fromkeys(other)),
            "url": _watch_link(offers.get("link")),
        }]}
    except Exception:
        # Include no token, private URL, response body or exception text.
        return {"status": "unavailable", "matches": [],
                "message": "UK availability could not be checked. A provider failure is not a not-found result."}


async def search(hass, request):
    """Search in priority order. Never call a household or media-player service."""
    query, year = request["query"], request.get("year")
    report = {"query": query, "region": "GB", "sources": [], "streaming": {"status": "skipped", "matches": []}}
    for adapter in (search_local, search_jellyfin):
        source = await adapter(hass, query, year)
        report["sources"].append(source)
        if any(item.get("match") == "exact" and (item.get("kind") != "folder" or item.get("contains_video"))
               for item in source.get("matches", [])):
            report["response"] = summarize(report)
            return report
    report["streaming"] = await search_streaming(hass, query, year)
    report["recommendation_url"] = recommendations_link(query)
    report["response"] = summarize(report)
    return report
