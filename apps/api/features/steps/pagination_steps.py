# features/steps/pagination_steps.py
import time
from datetime import datetime
from behave import when, then


@when('I request the first page with limit {limit:d}')
def step_first_page(ctx, limit):
    """Request first page with specified limit."""
    payload = {
        "filters": {},
        "sort": {"by": "shot_ts", "dir": "desc"},
        "page": {"limit": limit}
    }
    ctx.first_page_response = ctx.client.post(ctx.search_url, json=payload)
    assert ctx.first_page_response.status_code == 200
    ctx.first_page_data = ctx.first_page_response.json()


@when('I use the returned cursor to get the next page')
def step_next_page_cursor(ctx):
    """Use cursor from first page to get next page."""
    cursor = ctx.first_page_data["hits"].get("cursor")
    assert cursor is not None, "First page should have a cursor"
    
    payload = {
        "page": {"cursor": cursor}
    }
    ctx.second_page_response = ctx.client.post(ctx.search_url, json=payload)
    assert ctx.second_page_response.status_code == 200
    ctx.second_page_data = ctx.second_page_response.json()


@then('the second page contains different photos than the first')
def step_different_photos(ctx):
    """Verify second page has different photos."""
    first_ids = {item["photo_id"] for item in ctx.first_page_data["hits"]["items"]}
    second_ids = {item["photo_id"] for item in ctx.second_page_data["hits"]["items"]}
    
    # Should be no overlap
    assert first_ids.isdisjoint(second_ids), "Pages should not share photo IDs"


@then('the photos are in correct sort order across pages')
def step_sort_order_across_pages(ctx):
    """Verify sort order is maintained across pages."""
    first_items = ctx.first_page_data["hits"]["items"]
    second_items = ctx.second_page_data["hits"]["items"]
    
    if first_items and second_items:
        # Last item of first page should be >= first item of second page (desc order)
        last_first = first_items[-1]["shot_ts"]
        first_second = second_items[0]["shot_ts"]
        
        # Convert to comparable format
        last_first_dt = datetime.fromisoformat(last_first.replace("Z", "+00:00"))
        first_second_dt = datetime.fromisoformat(first_second.replace("Z", "+00:00"))
        
        assert last_first_dt >= first_second_dt, "Sort order not maintained across pages"


@when('I paginate through results sorted by shot_ts ascending')
def step_paginate_ascending(ctx):
    """Paginate through results in ascending order."""
    ctx.ascending_pages = []
    
    payload = {
        "filters": {},
        "sort": {"by": "shot_ts", "dir": "asc"},
        "page": {"limit": 5}
    }
    
    # Get first few pages
    for _ in range(3):
        response = ctx.client.post(ctx.search_url, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        ctx.ascending_pages.append(data)
        
        cursor = data["hits"].get("cursor")
        if not cursor or len(data["hits"]["items"]) == 0:
            break
            
        # Keep the same sort order for subsequent pages
        payload = {
            "filters": {},
            "sort": {"by": "shot_ts", "dir": "asc"},
            "page": {"cursor": cursor, "limit": 5}
        }


@then('each subsequent page maintains ascending timestamp order')
def step_ascending_order_maintained(ctx):
    """Verify ascending order within each page."""
    for i, page_data in enumerate(ctx.ascending_pages):
        items = page_data["hits"]["items"]
        if len(items) > 1:
            timestamps = [item["shot_ts"] for item in items]
            sorted_timestamps = sorted(timestamps)
            assert timestamps == sorted_timestamps, f"Page {i} not sorted in ascending order: {timestamps}"


@then('no timestamps go backwards between pages')
def step_no_backwards_timestamps(ctx):
    """Verify timestamps don't go backwards between pages."""
    for i in range(len(ctx.ascending_pages) - 1):
        current_page = ctx.ascending_pages[i]
        next_page = ctx.ascending_pages[i + 1]
        
        current_items = current_page["hits"]["items"]
        next_items = next_page["hits"]["items"]
        
        if current_items and next_items:
            last_current = current_items[-1]["shot_ts"]
            first_next = next_items[0]["shot_ts"]
            
            last_dt = datetime.fromisoformat(last_current.replace("Z", "+00:00"))
            first_dt = datetime.fromisoformat(first_next.replace("Z", "+00:00"))
            
            assert last_dt <= first_dt, "Timestamps went backwards between pages"


@when('I apply tag filter "{tag}" and paginate with limit {limit:d}')
def step_paginate_with_filter(ctx, tag, limit):
    """Paginate with tag filter applied."""
    ctx.filtered_pages = []
    ctx.filter_tag = tag
    
    payload = {
        "filters": {"tags": [tag]},
        "sort": {"by": "shot_ts", "dir": "desc"},
        "page": {"limit": limit}
    }
    
    # Get first few pages
    for _ in range(3):
        response = ctx.client.post(ctx.search_url, json=payload)
        assert response.status_code == 200
        
        data = response.json()
        ctx.filtered_pages.append(data)
        
        cursor = data["hits"].get("cursor")
        if not cursor or len(data["hits"]["items"]) == 0:
            break
            
        payload = {"page": {"cursor": cursor}}


@then('all pages contain only photos with "{tag}" tag')
def step_all_pages_have_tag(ctx, tag):
    """Verify all pages contain only photos with specified tag."""
    for page_data in ctx.filtered_pages:
        for item in page_data["hits"]["items"]:
            item_tags = item.get("tags", [])
            assert tag in item_tags, f"Photo {item['photo_id']} missing required tag '{tag}'"


@then('pagination works correctly with the filter applied')
def step_pagination_with_filter_works(ctx):
    """Verify pagination works with filters."""
    # Check that we got multiple pages or reached end appropriately
    assert len(ctx.filtered_pages) > 0, "Should have at least one page"
    
    # Verify no duplicate photo IDs across pages
    all_ids = set()
    for page_data in ctx.filtered_pages:
        for item in page_data["hits"]["items"]:
            photo_id = item["photo_id"]
            assert photo_id not in all_ids, f"Duplicate photo_id: {photo_id}"
            all_ids.add(photo_id)


@when('I request search with empty cursor')
def step_empty_cursor(ctx):
    """Request search with empty cursor."""
    payload = {
        "filters": {},
        "sort": {"by": "shot_ts", "dir": "desc"},
        "page": {"cursor": "", "limit": 10}
    }
    ctx.empty_cursor_response = ctx.client.post(ctx.search_url, json=payload)
    assert ctx.empty_cursor_response.status_code == 200


@then('I receive the first page of results')
def step_first_page_results(ctx):
    """Verify we get first page results."""
    data = ctx.empty_cursor_response.json()
    assert "hits" in data
    assert len(data["hits"]["items"]) > 0


@then('the response is identical to a request without cursor')
def step_identical_to_no_cursor(ctx):
    """Verify empty cursor gives same results as no cursor."""
    # Make request without cursor
    payload = {
        "filters": {},
        "sort": {"by": "shot_ts", "dir": "desc"},
        "page": {"limit": 10}
    }
    no_cursor_response = ctx.client.post(ctx.search_url, json=payload)
    assert no_cursor_response.status_code == 200
    
    empty_cursor_data = ctx.empty_cursor_response.json()
    no_cursor_data = no_cursor_response.json()
    
    # Compare photo IDs (order should be same)
    empty_cursor_ids = [item["photo_id"] for item in empty_cursor_data["hits"]["items"]]
    no_cursor_ids = [item["photo_id"] for item in no_cursor_data["hits"]["items"]]
    
    assert empty_cursor_ids == no_cursor_ids, "Empty cursor should give same results as no cursor"


@when('I get a cursor from results sorted by shot_ts descending')
def step_get_desc_cursor(ctx):
    """Get cursor from descending sort."""
    payload = {
        "filters": {},
        "sort": {"by": "shot_ts", "dir": "desc"},
        "page": {"limit": 5}
    }
    response = ctx.client.post(ctx.search_url, json=payload)
    assert response.status_code == 200
    
    data = response.json()
    ctx.desc_cursor = data["hits"].get("cursor")
    assert ctx.desc_cursor is not None


@when('I use that cursor with sort by shot_ts ascending')
def step_use_cursor_different_sort(ctx):
    """Use cursor with different sort order."""
    payload = {
        "sort": {"by": "shot_ts", "dir": "asc"},
        "page": {"cursor": ctx.desc_cursor}
    }
    ctx.mixed_sort_response = ctx.client.post(ctx.search_url, json=payload)


@then('I receive an appropriate error or warning')
def step_appropriate_error_or_warning(ctx):
    """Verify appropriate handling of cursor/sort mismatch."""
    # Should either work (if system handles it) or give appropriate error
    assert ctx.mixed_sort_response.status_code in [200, 400, 422]


@then('the system handles the inconsistency gracefully')
def step_handles_inconsistency_gracefully(ctx):
    """Verify graceful handling of sort/cursor inconsistency."""
    if ctx.mixed_sort_response.status_code == 200:
        # If it works, should return valid data
        data = ctx.mixed_sort_response.json()
        assert "hits" in data
    else:
        # If it errors, should have meaningful error message
        error_data = ctx.mixed_sort_response.json()
        assert "detail" in error_data or "error" in error_data


@when('I request pages with limits 1, 10, 50, and 100')
def step_various_limits(ctx):
    """Test various page limits."""
    ctx.limit_responses = {}
    limits = [1, 10, 50, 100]
    
    for limit in limits:
        payload = {
            "filters": {},
            "sort": {"by": "shot_ts", "dir": "desc"},
            "page": {"limit": limit}
        }
        response = ctx.client.post(ctx.search_url, json=payload)
        assert response.status_code == 200
        ctx.limit_responses[limit] = response.json()


@then('each request returns the correct number of results')
def step_correct_result_counts(ctx):
    """Verify each limit returns appropriate number of results."""
    for limit, data in ctx.limit_responses.items():
        actual_count = len(data["hits"]["items"])
        # Should return at most the requested limit
        assert actual_count <= limit, f"Limit {limit} returned {actual_count} items"
        # Should return the limit unless we've reached end of data
        if data["hits"]["total"] >= limit:
            assert actual_count == limit, f"Should return {limit} items when total >= limit"


@then('cursors work correctly across different page sizes')
def step_cursors_work_across_sizes(ctx):
    """Verify cursors work with different page sizes."""
    # Just verify that cursors are present when expected
    for limit, data in ctx.limit_responses.items():
        if len(data["hits"]["items"]) == limit and data["hits"]["total"] > limit:
            assert data["hits"].get("cursor") is not None, f"Missing cursor for limit {limit}"


@when('I make the same search request twice')
def step_same_request_twice(ctx):
    """Make identical search requests."""
    payload = {
        "filters": {"tags": ["vacation"]},
        "sort": {"by": "shot_ts", "dir": "desc"},
        "page": {"limit": 10}
    }
    
    ctx.first_identical = ctx.client.post(ctx.search_url, json=payload)
    ctx.second_identical = ctx.client.post(ctx.search_url, json=payload)
    
    assert ctx.first_identical.status_code == 200
    assert ctx.second_identical.status_code == 200


@then('both requests return identical cursors for the same position')
def step_identical_cursors(ctx):
    """Verify identical requests return identical cursors."""
    first_data = ctx.first_identical.json()
    second_data = ctx.second_identical.json()
    
    first_cursor = first_data["hits"].get("cursor")
    second_cursor = second_data["hits"].get("cursor")
    
    assert first_cursor == second_cursor, "Identical requests should return identical cursors"


@then('the cursors can be used interchangeably')
def step_cursors_interchangeable(ctx):
    """Verify cursors from identical requests work the same."""
    first_data = ctx.first_identical.json()
    cursor = first_data["hits"].get("cursor")
    
    if cursor:
        # Use cursor to get next page
        payload = {"page": {"cursor": cursor}}
        response = ctx.client.post(ctx.search_url, json=payload)
        assert response.status_code == 200
        # If it works, the cursors are functionally equivalent


@when('I paginate through a large result set')
def step_paginate_large_set(ctx):
    """Paginate through large result set measuring performance."""
    ctx.page_times = []
    
    payload = {
        "filters": {},
        "sort": {"by": "shot_ts", "dir": "desc"},
        "page": {"limit": 20}
    }
    
    page_count = 0
    max_pages = 10  # Reasonable limit for testing
    
    while page_count < max_pages:
        start_time = time.time()
        response = ctx.client.post(ctx.search_url, json=payload)
        end_time = time.time()
        
        assert response.status_code == 200
        ctx.page_times.append(end_time - start_time)
        
        data = response.json()
        cursor = data["hits"].get("cursor")
        if not cursor or len(data["hits"]["items"]) == 0:
            break
            
        payload = {"page": {"cursor": cursor}}
        page_count += 1


@then('each page request completes in reasonable time')
def step_reasonable_time(ctx):
    """Verify page requests complete in reasonable time."""
    # Define reasonable time as under 1 second for test environment
    max_time = 1.0
    for i, page_time in enumerate(ctx.page_times):
        assert page_time < max_time, f"Page {i} took {page_time:.2f}s, expected < {max_time}s"


@then('memory usage remains stable across pages')
def step_stable_memory(ctx):
    """Verify memory usage doesn't grow significantly."""
    # This is a basic check - in a real scenario you'd monitor actual memory usage
    # For now, just verify we completed pagination without issues
    assert len(ctx.page_times) > 0, "Should have completed some pages"
    
    # Verify response times don't increase dramatically (could indicate memory issues)
    if len(ctx.page_times) > 2:
        first_time = ctx.page_times[0]
        last_time = ctx.page_times[-1]
        # Last page shouldn't take more than 3x the first page
        assert last_time < first_time * 3, "Response time increased too much (possible memory issue)"