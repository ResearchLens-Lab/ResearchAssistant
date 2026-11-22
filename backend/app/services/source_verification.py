"""Explicit, DOI-only lookups against public scholarly metadata registries."""

import asyncio
import re
from typing import Any
from urllib.parse import quote

import httpx

from backend.app.models.paper import Paper


_DOI_PREFIX = re.compile(r"^\s*(?:https?://(?:dx\.)?doi\.org/)?", re.IGNORECASE)
_DOI_VALID = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    doi = _DOI_PREFIX.sub("", value).strip().rstrip(".,;)").lower()
    return doi if _DOI_VALID.fullmatch(doi) else None


def _norm(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()


def _authors_from_crossref(work: dict[str, Any]) -> list[str]:
    return [" ".join(x for x in (item.get("given"), item.get("family")) if x).strip()
            for item in work.get("author", []) if isinstance(item, dict)]


def _authors_from_openalex(work: dict[str, Any]) -> list[str]:
    return [item.get("author", {}).get("display_name", "")
            for item in work.get("authorships", []) if isinstance(item, dict)]


def _year_crossref(work: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "published", "created"):
        parts = work.get(key, {}).get("date-parts", [])
        if parts and parts[0] and isinstance(parts[0][0], int):
            return parts[0][0]
    return None


def _year_openalex(work: dict[str, Any]) -> int | None:
    year = work.get("publication_year")
    return year if isinstance(year, int) else None


def _author_match(expected: list[str] | None, actual: list[str]) -> bool | None:
    if not expected:
        return None
    # Compare normalized family names so initials and ordering differences do
    # not create false mismatches. This remains a transparent heuristic.
    surnames = lambda names: {_norm(name).split()[-1] for name in names if _norm(name)}
    expected_names, actual_names = surnames(expected), surnames(actual)
    if not expected_names or not actual_names:
        return None
    return expected_names == actual_names


class SourceVerificationService:
    """Fetch and compare bibliographic metadata; never sends document contents."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client

    async def verify(self, paper: Paper) -> dict[str, Any]:
        from backend.app.core.config import get_settings
        if self.client is None and not get_settings().external_lookups_enabled:
            return {
                "status": "DISABLED",
                "doi": paper.doi,
                "external_checks_performed": False,
                "message": "Online verification is off. ResearchLens keeps everything on this computer.",
                "privacy": "Nothing was sent.",
            }

        doi = normalize_doi(paper.doi)
        if not doi:
            return {
                "status": "UNVERIFIED", "doi": paper.doi,
                "message": "A valid DOI is not recorded for this paper.",
                "external_checks_performed": False,
                "privacy": "Only DOI and bibliographic metadata are sent; document text is never sent.",
            }

        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=8.0, headers={"User-Agent": "ResearchLens/1.0 (scholarly metadata verification)"})
        crossref: dict[str, Any] | None = None
        openalex: dict[str, Any] | None = None
        errors: dict[str, str] = {}
        try:
            encoded = quote(doi, safe="")
            crossref_response, openalex_response = await asyncio.gather(
                client.get(f"https://api.crossref.org/works/{encoded}"),
                client.get(f"https://api.openalex.org/works/https://doi.org/{quote(doi, safe='/')}", params={"select": "id,doi,title,authorships,publication_year,primary_location,open_access,is_retracted"}),
                return_exceptions=True,
            )
            for name, response in (("crossref", crossref_response), ("openalex", openalex_response)):
                if isinstance(response, Exception):
                    errors[name] = "unavailable"
                    continue
                if response.status_code == 200:
                    try:
                        payload = response.json()
                        if name == "crossref":
                            crossref = payload.get("message")
                        else:
                            openalex = payload
                    except ValueError:
                        errors[name] = "invalid_response"
                elif response.status_code == 404:
                    errors[name] = "not_found"
                else:
                    errors[name] = "unavailable"
        finally:
            if owns_client:
                await client.aclose()

        if not crossref and not openalex:
            status = "UNVERIFIED" if errors and all(value == "not_found" for value in errors.values()) else "EXTERNAL VERIFICATION UNAVAILABLE"
            return {
                "status": status, "doi": doi, "registries": {"crossref": "not_found" if errors.get("crossref") == "not_found" else "unavailable", "openalex": "not_found" if errors.get("openalex") == "not_found" else "unavailable"},
                "message": "No matching registry record was found. This does not establish that the work is fake." if status == "UNVERIFIED" else "One or more public metadata registries could not be reached.",
                "external_checks_performed": True,
                "privacy": "Only DOI and bibliographic metadata are sent; document text is never sent.",
            }

        title = (crossref.get("title") or [None])[0] if crossref else None
        authors = _authors_from_crossref(crossref) if crossref else []
        year = _year_crossref(crossref) if crossref else None
        venue = ((crossref.get("container-title") or [None])[0] if crossref else None)
        if openalex:
            title = title or openalex.get("title")
            authors = authors or _authors_from_openalex(openalex)
            year = year or _year_openalex(openalex)
            location = openalex.get("primary_location") or {}
            source = location.get("source") or {}
            venue = venue or source.get("display_name")

        mismatches: list[str] = []
        if paper.title and title and _norm(paper.title) != _norm(title):
            mismatches.append("title")
        author_match = _author_match(paper.authors, authors)
        if author_match is False:
            mismatches.append("authors")
        if paper.publication_year and year and paper.publication_year != year:
            mismatches.append("publication_year")
        if paper.venue and venue and _norm(paper.venue) != _norm(venue):
            mismatches.append("venue")

        updates = crossref.get("update-to", []) if crossref else []
        update_types = {str(item.get("update-type", "")).casefold() for item in updates if isinstance(item, dict)}
        retraction_flag = any("retract" in item for item in update_types) or bool(openalex and openalex.get("is_retracted"))
        correction_flag = any("correct" in item or "errat" in item for item in update_types)
        oa = openalex.get("open_access") if openalex else None
        status = "METADATA MISMATCH" if mismatches else (
            "VERIFIED METADATA" if crossref and openalex and not errors else "PARTIALLY VERIFIED"
        )
        if retraction_flag or correction_flag:
            status = "RETRACTION/CORRECTION FLAG"

        return {
            "status": status,
            "doi": doi,
            "resolved_doi": (crossref or {}).get("DOI") or (openalex or {}).get("doi"),
            "title": title,
            "authors": authors,
            "publication_year": year,
            "venue": venue,
            "publisher": (crossref or {}).get("publisher"),
            "issn": (crossref or {}).get("ISSN", []),
            "orcid": [a.get("ORCID") for a in (crossref or {}).get("author", []) if a.get("ORCID")],
            "metadata_mismatches": mismatches,
            "expected": {"title": paper.title, "authors": paper.authors, "publication_year": paper.publication_year, "venue": paper.venue},
            "registries": {"crossref": "matched" if crossref else errors.get("crossref", "not_checked"), "openalex": "matched" if openalex else errors.get("openalex", "not_checked")},
            "retraction_flag": retraction_flag,
            "correction_flag": correction_flag,
            "open_access": oa.get("is_oa") if oa else None,
            "open_access_url": oa.get("oa_url") if oa else None,
            "links": {
                "doi": f"https://doi.org/{doi}",
                "crossref": f"https://api.crossref.org/works/{encoded}",
                "openalex": (openalex or {}).get("id"),
            },
            "confidence_note": "Registry metadata agreement indicates bibliographic consistency, not scientific validity or claim accuracy.",
            "external_checks_performed": True,
            "privacy": "Only DOI and bibliographic metadata are sent; document text is never sent.",
        }
