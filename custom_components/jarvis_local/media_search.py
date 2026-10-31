"""Search-only film/TV requests, title matching and honest summaries."""
import re
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import urlencode

SUBSCRIPTIONS = {
    "netflix": "Netflix", "prime": "Prime Video",
    "disney": "Disney+", "paramount": "Paramount+",
}
PROVIDER_NAMES = {
    "netflix": {"netflix", "netflix standard with ads"},
    "prime": {"amazon prime video", "amazon prime video with ads"},
    "disney": {"disney plus", "disney+"},
    "paramount": {"paramount plus", "paramount+", "paramount plus premium",
                  "paramount plus basic with ads"},
}


def parse_search(text):
    text = text.strip()
    preview = False
    for prefix in ("preview ", "dry run ", "what would you do if i said "):
        if text.lower().startswith(prefix):
            preview = True
            text = text[len(prefix):].strip()
            break
    # Consume this entire request before the generic routine/music planner.
    # For this phase the movie-time context does NOT run a household routine.
    movie_context = re.fullmatch(
        r"(?:(?:start|turn on|enable) (?:the )?)?(?:movie time|cinema time|cinema mode)"
        r"\s+(?:and then|and|then)\s+(?:play|watch|find|search for)\s+(.+)", text, re.I)
    match = movie_context or re.fullmatch(
        r"(?:where can i (?:watch|stream|find)|(?:search|look) (?:my |the )?"
        r"(?:ha media library|media library|jellyfin|streaming services) for|"
        r"(?:search|look) for|find|watch|stream|"
        r"play (?:the )?(?:movie|film|tv show|show|series))\s+(.+)", text, re.I)
    if match is None:
        return None
    title = match[1].strip().rstrip(".?!")
    quoted = len(title) >= 2 and title[0] in "\"'" and title[-1] == title[0]
    if quoted:
        title = title[1:-1]
    else:
        title = re.sub(r"^the (?:movie|film|tv show|show|series)\s+", "", title, flags=re.I)
    if not title or len(title) > 200:
        raise ValueError("Which film or TV show should I search for? Please give a title of up to 200 characters.")
    # Never execute a second clause. Keep legitimate titles containing 'and'.
    if re.search(r"\b(?:and|then)\s+(?:turn|switch|dim|brighten|set|start|stop|unlock|lock)\b", title, re.I):
        raise ValueError("Please ask for the title search separately from other device commands.")
    year_match = re.search(r"\s+(?:\(((?:19|20)\d{2})\)|(?:from|released in)\s+((?:19|20)\d{2}))$", title, re.I)
    year = int(year_match[1] or year_match[2]) if year_match else None
    if year_match:
        title = title[:year_match.start()].strip()
    return {
        "kind": "media_search", "query": title, "year": year,
        "movie_context": bool(movie_context), "preview": preview,
        "label": 'search libraries and UK streaming availability for "' + title + '"',
    }


def title_key(text):
    text = unicodedata.normalize("NFKD", text).casefold()
    return "".join(char for char in text if char.isalnum())


def title_match(query, title):
    base = re.sub(r"\.(?:mkv|mp4|avi|mov|m4v|webm|mpg|mpeg|ts)$", "", title, flags=re.I)
    base = re.sub(r"\s*\((?:19|20)\d{2}\)\s*$", "", base)
    left, right = title_key(query), title_key(base)
    if not left or not right:
        return None
    if left == right or re.fullmatch(re.escape(left) + r"(?:s\d{1,2}e\d{1,3}.*|season\d+.*)", right):
        return "exact"
    if min(len(left), len(right)) >= 6 and SequenceMatcher(None, left, right).ratio() >= .84:
        return "possible"
    return None


def recommendations_link(query, region="GB"):
    if region == "GB":
        return "https://www.justwatch.com/uk/search?" + urlencode({"q": query})
    return "https://www.themoviedb.org/search?" + urlencode({"query": query})


def summarize(report):
    query = report["query"]
    lines = []
    for source in report["sources"]:
        matches = source.get("matches", [])
        exact = [item for item in matches if item.get("match") == "exact"]
        if exact:
            names = ", ".join('"' + item["title"] + '"' for item in exact[:3])
            lines.append("Found " + names + " in " + source["name"] + ".")
            if any(item.get("kind") in {"folder", "series"} for item in exact):
                lines.append("A folder or series match does not confirm every episode is present.")
        elif matches:
            lines.append("Possible titles in " + source["name"] + ": " +
                         ", ".join('"' + item["title"] + '"' for item in matches[:3]) + ".")
        if source["status"] == "complete" and not matches:
            lines.append("No title match in " + source["name"] + ".")
        elif source["status"] in {"partial", "unavailable", "not_configured"}:
            lines.append(source["name"] + ": " + source["message"])
        elif source.get("message"):
            lines.append(source["message"])
    streaming = report.get("streaming", {})
    if streaming.get("status") == "ambiguous":
        lines.append("Several catalogue titles match. Say the title followed by from and the year: " +
                     "; ".join(streaming["candidates"]) + ".")
    for item in streaming.get("matches", []):
        if item["selected_subscriptions"]:
            lines.append('"' + item["title"] + '" is listed in the UK on ' +
                         ", ".join(item["selected_subscriptions"]) +
                         ". Availability can depend on your plan; this does not check your account.")
        else:
            lines.append('No listing on your selected subscription services was returned for "' + item["title"] + '".')
        offers = item.get("other_offers", [])
        if offers:
            lines.append("Other options: " + "; ".join(offers[:8]) + ".")
        if not item["selected_subscriptions"] and not offers:
            lines.append("No UK provider listing was returned; that is not proof the title is unavailable.")
    if streaming.get("status") in {"not_configured", "unavailable"}:
        lines.append(streaming["message"])
    if streaming.get("status") == "complete" and not streaming.get("matches"):
        lines.append("No confident film or TV title match was returned by the availability catalogue.")
    if streaming.get("attribution"):
        lines.append("Availability data: JustWatch via TMDB.")
    if report.get("recommendation_url"):
        lines.append("See the search results for a link to check other legal viewing options.")
    lines.append("Search only. I have not started movie time or played anything.")
    return " ".join(lines)
