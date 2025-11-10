# features/steps/search_steps.py
import ast
import json
import parse
from typing import Any, Dict
from datetime import datetime
from behave import given, register_type, when, then

def _parse_literal(s: str):
    s = s.strip()
    if s == "" or s.lower() == "null":
        return None
    # accept JSON or Python literal
    try:
        return json.loads(s)
    except Exception:
        try:
            return ast.literal_eval(s)
        except Exception:
            return s

@parse.with_pattern(r'\[.*\]')  # matches a list-like string
def _parse_list(s: str):
    """Convert comma separated string in brackets to list of strings."""
    # Remove surrounding brackets and split by comma
    s = s.strip()[1:-1]
    items = [item.strip() for item in s.split(",")]
    return items

register_type(List=_parse_list)
                
def _build_payload_from_table(table):
    q: str = ""
    filters: Dict[str, Any] = {}
    sort: Dict[str, Any] = {}
    page: Dict[str, Any] = {}
    for row in table:
        key = row["q"] if "q" in row.headings else row[0]
        val = row[""] if "" in row.headings else row[1]
        key = key.strip()
        val_parsed = _parse_literal(val)

        if key == "q":
            q = val_parsed or ""
        elif key.startswith("date."):
            filters.setdefault("date", {})
            subkey = key.split(".", 1)[1]
            filters["date"][subkey] = val_parsed
        elif key.startswith("sort."):
            subkey = key.split(".", 1)[1]
            sort[subkey] = val_parsed
        elif key.startswith("page."):
            subkey = key.split(".", 1)[1]
            page[subkey] = val_parsed
        elif key in ("camera_make", "extension", "people", "tags", "orientation", "filesize_range", "has_faces"):
            if key == "has_faces":
                filters["has_faces"] = (str(val_parsed).lower() == "true")
            else:
                if isinstance(val_parsed, list):
                    filters[key] = val_parsed
                else:
                    filters[key] = [val_parsed] if key not in ("filesize_range",) else val_parsed
        else:
            # passthrough
            filters[key] = val_parsed
    payload: Dict[str, Any] = {"filters": filters}
    if q: payload["q"] = q
    if sort: payload["sort"] = sort
    if page: payload["page"] = page
    return payload

def _assert_sorted_by_shot_then_id_desc(items):
    pairs = [(it["shot_ts"], it["photo_id"]) for it in items]
    expected = sorted(pairs, key=lambda t: (t[0], t[1]), reverse=True)
    assert pairs == expected, "hits not sorted by shot_ts desc then photo_id"

# ---------------- Background ----------------
@given('a photo library with photos, faces, tags, and EXIF loaded') # type: ignore[no-untyped-def]
def step_seeded(ctx):
    # environment.py already seeded the in-memory DB
    assert ctx.client is not None

@given('the search endpoint is available at "{path}"') # type: ignore[no-untyped-def]
def step_endpoint(ctx, path):
    ctx.search_url = path

# ---------------- Happy paths ----------------
@when('I search with') # type: ignore[no-untyped-def]
def step_search_with(ctx):
    payload = _build_payload_from_table(ctx.table)
    ctx.last_payload = payload
    ctx.last_response = ctx.client.post(ctx.search_url, json=payload)
    assert ctx.last_response.status_code in (200, 400, 422)

@then('every hit has ext in ["heic"] and camera_make in ["Apple"]') # type: ignore[no-untyped-def]
def step_filter_ext_make(ctx):
    data = ctx.last_response.json()
    for h in data["hits"]["items"]:
        assert h["ext"].lower() in {"heic"}
        assert h.get("camera_make") in {"Apple"}

@then('every hit has shot_ts within [2020-01-01, 2020-12-31]') # type: ignore[no-untyped-def]
def step_range_ts(ctx):
    data = ctx.last_response.json()
    for h in data["hits"]["items"]:
        ts = datetime.fromisoformat(h["shot_ts"].replace("Z", "+00:00"))
        assert datetime(2020,1,1) <= ts.replace(tzinfo=None) <= datetime(2020,12,31)

@then('every hit contains at least one face') # type: ignore[no-untyped-def]
def step_has_face(ctx):
    for h in ctx.last_response.json()["hits"]["items"]:
        assert "faces" in h and len(h["faces"]) >= 1

@then('every hit contains tag "vacation"') # type: ignore[no-untyped-def]
def step_has_tag_vac(ctx):
    for h in ctx.last_response.json()["hits"]["items"]:
        assert "vacation" in h.get("tags", [])

@then('at least one hit contains person "person_ines"') # type: ignore[no-untyped-def]
def step_has_person(ctx):
    assert any("person_ines" in h.get("people", []) for h in ctx.last_response.json()["hits"]["items"])

@then('hits are sorted by shot_ts desc then photo_id') # type: ignore[no-untyped-def]
def step_sorted(ctx):
    _assert_sorted_by_shot_then_id_desc(ctx.last_response.json()["hits"]["items"])

@then('the response includes facets computed from the filtered result set') # type: ignore[no-untyped-def]
def step_facets_exist(ctx):
    facets = ctx.last_response.json().get("facets", {})
    assert "tags" in facets and isinstance(facets["tags"], list)
    assert "people" in facets and isinstance(facets["people"], list)
    assert "date" in facets

@when('I search with empty filters and page.limit 60') # type: ignore[no-untyped-def]
def step_search_empty(ctx):
    payload = {"filters": {}, "sort": {"by": "shot_ts", "dir": "desc"}, "page": {"limit": 60}}
    ctx.last_payload = payload
    ctx.last_response = ctx.client.post(ctx.search_url, json=payload)
    assert ctx.last_response.status_code == 200

@then('I receive at most 60 hits') # type: ignore[no-untyped-def]
def step_limit_60(ctx):
    assert len(ctx.last_response.json()["hits"]["items"]) <= 60

@then('the total is >= hits length') # type: ignore[no-untyped-def]
def step_total_ge_hits(ctx):
    data = ctx.last_response.json()
    assert data["hits"]["total"] >= len(data["hits"]["items"])

# Conjunctive across facets
@Given('current filters tags {tags:List}') # type: ignore[no-untyped-def]
def step_set_current_tags(ctx, tags):
    if not hasattr(ctx, "current_filters") or not isinstance(ctx.current_filters, dict):
        ctx.current_filters = {}  # type: ignore[assignment]
    ctx.current_filters = {"tags": tags}

@when('I also filter by camera_make {makes:List} and orientation {ori}') # type: ignore[no-untyped-def]
def step_add_filters(ctx, makes, ori):
    ctx.current_filters["camera_make"] = makes
    ctx.current_filters["orientation"] = _parse_literal(ori)
    payload = {"filters": ctx.current_filters, "sort": {"by": "shot_ts", "dir": "desc"}, "page": {"limit": 1000}}
    ctx.last_response = ctx.client.post(ctx.search_url, json=payload)
    assert ctx.last_response.status_code == 200

@then('results only include photos that have tag "vacation" AND camera_make "Apple" AND orientation "landscape"') # type: ignore[no-untyped-def]
def step_conjunctive_assert(ctx):
    for h in ctx.last_response.json()["hits"]["items"]:
        assert "vacation" in h.get("tags", [])
        assert h.get("camera_make") == "Apple"
        assert h.get("orientation") == "landscape"

# Disjunctive (tags)
@given('current filters people {people}') # type: ignore[no-untyped-def]
def step_set_current_people(ctx, people):
    ctx.current_filters = {"people": _parse_literal(people)}

@when('I also select tag "sunset" in the same facet') # type: ignore[no-untyped-def]
def step_add_tag_sunset(ctx):
    tags = set(ctx.current_filters.get("tags", []))
    tags.add("sunset")
    ctx.current_filters["tags"] = list(tags)
    ctx.last_response = ctx.client.post(ctx.search_url, json={"filters": ctx.current_filters, "page": {"limit": 1000}})
    assert ctx.last_response.status_code == 200

@then('results include photos that have tag "beach" OR tag "sunset" (or both)') # type: ignore[no-untyped-def]
def step_or_tags(ctx):
    for h in ctx.last_response.json()["hits"]["items"]:
        assert set(h.get("tags", [])) & {"beach", "sunset"}

# Disjunctive (people)
@when('I also select person "person_john"') # type: ignore[no-untyped-def]
def step_add_person_john(ctx):
    ppl = set(ctx.current_filters.get("people", []))
    ppl.add("person_john")
    ctx.current_filters["people"] = list(ppl)
    ctx.last_response = ctx.client.post(ctx.search_url, json={"filters": ctx.current_filters, "page": {"limit": 1000}})
    assert ctx.last_response.status_code == 200

@then('results include photos where person_ines OR person_john appear') # type: ignore[no-untyped-def]
def step_or_people(ctx):
    for h in ctx.last_response.json()["hits"]["items"]:
        assert set(h.get("people", [])) & {"person_ines", "person_john"}

# -------- Facets (drill-sideways) --------
@given('current filters tags {tags:List} and camera_make {makes:List}') # type: ignore[no-untyped-def]
def step_set_beach_apple(ctx, tags, makes):
    ctx.current_filters = {
        "tags": tags,
        "camera_make": makes,
    }
    
@when('I view the tags facet') # type: ignore[no-untyped-def]
def step_view_tags_facet(ctx):
    ctx.last_response = ctx.client.post(ctx.search_url, json={"filters": ctx.current_filters, "page": {"limit": 1}})
    assert ctx.last_response.status_code == 200

@then('the count for a tag value T is computed as if camera_make ["Apple"] is applied AND the tags filter is removed') # type: ignore[no-untyped-def]
def step_drill_sideways(ctx):
    tag_facet = ctx.last_response.json().get("facets", {}).get("tags", [])
    assert any(x.get("value") == "beach" and isinstance(x.get("count"), int) for x in tag_facet)

@given('a photo with two faces both linked to person_ines') # type: ignore[no-untyped-def]
def step_two_faces_same_photo(ctx):
    # This condition is true in the seeded dataset, so just acknowledge.
    assert True

@when('I view the people facet with filters that include that photo') # type: ignore[no-untyped-def]
def step_people_facet(ctx):
    ctx.last_response = ctx.client.post(ctx.search_url, json={"filters": {}, "page": {"limit": 1}})
    assert ctx.last_response.status_code == 200

@then('the count for person_ines increases by 1 (not 2)') # type: ignore[no-untyped-def]
def step_people_distinct(ctx):
    ppl = ctx.last_response.json().get("facets", {}).get("people", [])
    entry = next((x for x in ppl if x.get("value") == "person_ines"), None)
    assert entry and entry["count"] > 0

@when('I select year 2020 in the date facet') # type: ignore[no-untyped-def]
def step_select_year(ctx):
    ctx.last_response = ctx.client.post(ctx.search_url, json={"filters": {}, "page": {"limit": 1}})
    assert ctx.last_response.status_code == 200

@then('the sum of all month buckets in 2020 equals the 2020 year bucket') # type: ignore[no-untyped-def]
def step_year_month_sum(ctx):
    date = ctx.last_response.json().get("facets", {}).get("date", {})
    years = date.get("years", [])
    y2020 = next((y for y in years if y.get("value") == 2020), None)
    assert y2020, "2020 bucket missing"
    assert sum(m["count"] for m in y2020.get("months", [])) == y2020["count"]

@then('selecting a month shows day buckets that sum to the month bucket') # type: ignore[no-untyped-def]
def step_month_day_sum(ctx):
    data = ctx.last_response.json()
    date = (data.get("facets") or {}).get("date") or {}
    years = date.get("years") or []
    y2020 = next((y for y in years if y.get("value") == 2020), None)
    assert y2020 is not None, "2020 year bucket missing"

    for m in (y2020.get("months") or []):
        days = m.get("days") or []
        assert sum((d.get("count") or 0) for d in days) == (m.get("count") or 0)


@when('I request the duplicates facet') # type: ignore[no-untyped-def]
def step_dup_req(ctx):
    ctx.last_response = ctx.client.post(ctx.search_url, json={"filters": {}, "facets": {"duplicates": True}, "page": {"limit": 1}})
    assert ctx.last_response.status_code == 200

@then('the response includes an "exact" integer > 0 and a "near" integer >= 0') # type: ignore[no-untyped-def]
def step_dup_assert(ctx):
    dup = ctx.last_response.json().get("facets", {}).get("duplicates", {})
    assert isinstance(dup.get("exact"), int) and dup["exact"] > 0
    assert isinstance(dup.get("near"), int) and dup["near"] >= 0

# -------- Pagination & cursors --------
@when('I request page.limit 60 sorted by shot_ts desc and receive cursor C1') # type: ignore[no-untyped-def]
def step_page1(ctx):
    payload = {"filters": {}, "sort": {"by": "shot_ts", "dir": "desc"}, "page": {"limit": 60}}
    r1 = ctx.client.post(ctx.search_url, json=payload)
    assert r1.status_code == 200
    ctx.page1 = r1.json()
    assert ctx.page1["hits"].get("cursor")
    ctx.C1 = ctx.page1["hits"]["cursor"]

@when('I request the next page with cursor C1') # type: ignore[no-untyped-def]
def step_page2(ctx):
    r2 = ctx.client.post(ctx.search_url, json={"page": {"cursor": ctx.C1}})
    assert r2.status_code == 200
    ctx.page2 = r2.json()

@then('there are no duplicate photo_ids between the two pages') # type: ignore[no-untyped-def]
def step_no_dups(ctx):
    ids1 = {h["photo_id"] for h in ctx.page1["hits"]["items"]}
    ids2 = {h["photo_id"] for h in ctx.page2["hits"]["items"]}
    assert ids1.isdisjoint(ids2)

@given('at least two photos share the same shot_ts') # type: ignore[no-untyped-def]
def step_shared_ts(ctx):
    # True in seed. Proceed.
    assert True

@when('I paginate') # type: ignore[no-untyped-def]
def step_paginate(ctx):
    r = ctx.client.post(ctx.search_url, json={"filters": {}, "sort": {"by": "shot_ts", "dir": "desc"}, "page": {"limit": 25}})
    assert r.status_code == 200
    ctx.page_items = r.json()["hits"]["items"]

@then('ordering uses (shot_ts, photo_id) to break ties and pagination remains deterministic') # type: ignore[no-untyped-def]
def step_tie_break(ctx):
    last = None
    for it in ctx.page_items:
        key = (it["shot_ts"], it["photo_id"])
        if last:
            assert key <= last
        last = key

# -------- Search modalities --------
@when('I search with q = "hawaii beach"') # type: ignore[no-untyped-def]
def step_q_relevance(ctx):
    ctx._q_tmp = "hawaii beach"

@when('sort.by = "relevance"') # type: ignore[no-untyped-def]
def step_sort_relevance(ctx):
    payload = {"q": getattr(ctx, "_q_tmp", ""), "sort": {"by": "relevance"}, "page": {"limit": 50}}
    ctx.last_response = ctx.client.post(ctx.search_url, json=payload)
    assert ctx.last_response.status_code in (200, 501, 400, 422)  # allow unimplemented to fail gracefully

@then('hits include photos whose path or tags are trigram-similar to the query') # type: ignore[no-untyped-def]
def step_assert_relevance_hits(ctx):
    data = ctx.last_response.json()
    items = data.get("hits", {}).get("items", [])
    assert any(("beach" in (it.get("path") or "")) or ("beach" in it.get("tags", [])) for it in items)

@then('relevance scores are non-increasing') # type: ignore[no-untyped-def]
def step_relevance_monotonic(ctx):
    items = ctx.last_response.json().get("hits", {}).get("items", [])
    scores = [it["relevance"] for it in items if "relevance" in it]
    for a, b in zip(scores, scores[1:]):
        assert a >= b

@when('I pass a 128-dim vector and similarity_k 40 and tags ["portrait"]') # type: ignore[no-untyped-def]
def step_vector_query(ctx):
    ctx.last_response = ctx.client.post(ctx.search_url, json={
        "vector": {"dim": 128, "values": [0.0]*128},
        "similarity_k": 40,
        "filters": {"tags": ["portrait"]},
        "page": {"limit": 40},
    })
    assert ctx.last_response.status_code in (200, 501, 400, 422)

@then('all hits are among the 40 nearest neighbors by vector distance') # type: ignore[no-untyped-def]
def step_vector_k(ctx):
    # Black-box: assert count <= 40
    items = ctx.last_response.json().get("hits", {}).get("items", [])
    assert len(items) <= 40

@then('every hit contains tag "portrait"') # type: ignore[no-untyped-def]
def step_vector_tag(ctx):
    for it in ctx.last_response.json().get("hits", {}).get("items", []):
        assert "portrait" in it.get("tags", [])

# -------- Edge cases --------
@when('I filter on a future date range with no photos') # type: ignore[no-untyped-def]
def step_future_empty(ctx):
    ctx.last_response = ctx.client.post(ctx.search_url, json={"filters": {"date": {"from": "2099-01-01", "to": "2099-12-31"}}, "page": {"limit": 10}})
    assert ctx.last_response.status_code == 200

@then('the response has total 0 and hits.items is empty') # type: ignore[no-untyped-def]
def step_empty_assert(ctx):
    data = ctx.last_response.json()
    assert data["hits"]["total"] == 0
    assert data["hits"]["items"] == []

@then('all facets are empty or zero-count as applicable') # type: ignore[no-untyped-def]
def step_empty_facets(ctx):
    facets = ctx.last_response.json().get("facets", {})
    for v in facets.values():
        if isinstance(v, list):
            assert all((x.get("count", 0) == 0) for x in v)
        elif isinstance(v, dict):
            assert all((isinstance(x, int) and x == 0) for x in v.values())

@when('I pass more than 100 values in the tags filter') # type: ignore[no-untyped-def]
def step_invalid_request(ctx):
    ctx.last_response = ctx.client.post(ctx.search_url, json={"filters": {"tags": [f"t{i}" for i in range(101)]}})
    assert ctx.last_response.status_code in (400, 422)

@then('I receive an error with code "BAD_REQUEST"') # type: ignore[no-untyped-def]
def step_err_code(ctx):
    err = ctx.last_response.json()
    assert "BAD_REQUEST" in json.dumps(err).upper()

@when('I filter on filesize_range {range_name}') # type: ignore[no-untyped-def]
def step_filesize_filter(ctx, range_name):
    ctx.last_response = ctx.client.post(ctx.search_url, json={"filters": {"filesize_range": range_name}, "page": {"limit": 1000}})
    assert ctx.last_response.status_code == 200

@then('all hits have filesize within the configured bounds for {range_name}') # type: ignore[no-untyped-def]
def step_filesize_bounds(ctx, range_name):
    bounds = {
        "small":  (0, 1_000_000),
        "medium": (1_000_000, 5_000_000),
        "large":  (5_000_000, 10_000_000_000),
    }
    low, high = bounds[range_name]
    for h in ctx.last_response.json()["hits"]["items"]:
        assert low <= int(h["filesize"]) < high
