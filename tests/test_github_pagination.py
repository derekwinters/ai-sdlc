"""API-020 to API-026 — following pages without losing or duplicating items."""

import unittest

from _support import RecordingTransport, Response, page
from lib.github import PAGE_SIZE, GitHub


def paged(*bodies):
    transport = RecordingTransport([Response(200, b) for b in bodies])
    return GitHub("s3cret", "derekwinters/ai-sdlc", transport=transport), transport


class TestFollowingPages(unittest.TestCase):
    def test_a_short_page_is_returned_whole(self):  # API-020
        client, transport = paged(page(3))
        self.assertEqual(len(client.paginate("/issues")), 3)
        self.assertEqual(len(transport.requests), 1)

    def test_a_full_page_is_followed_by_another_request(self):  # API-020
        client, transport = paged(page(PAGE_SIZE), page(2, start=PAGE_SIZE + 1))
        self.assertEqual(len(client.paginate("/issues")), PAGE_SIZE + 2)
        self.assertEqual(len(transport.requests), 2)

    def test_several_full_pages_are_all_collected(self):  # API-020
        client, _ = paged(
            page(PAGE_SIZE),
            page(PAGE_SIZE, start=PAGE_SIZE + 1),
            page(1, start=2 * PAGE_SIZE + 1),
        )
        self.assertEqual(len(client.paginate("/issues")), 2 * PAGE_SIZE + 1)

    def test_items_keep_their_order(self):  # API-021
        client, _ = paged(page(PAGE_SIZE), page(2, start=PAGE_SIZE + 1))
        numbers = [item["number"] for item in client.paginate("/issues")]
        self.assertEqual(numbers, sorted(numbers))

    def test_an_exactly_full_last_page_costs_one_empty_request(self):  # API-022
        client, transport = paged(page(PAGE_SIZE), "[]")
        self.assertEqual(len(client.paginate("/issues")), PAGE_SIZE)
        self.assertEqual(len(transport.requests), 2)

    def test_an_empty_first_page_is_an_empty_result(self):  # API-023
        client, _ = paged("[]")
        self.assertEqual(client.paginate("/issues"), [])

    def test_a_null_page_is_treated_as_empty(self):  # API-024
        client, _ = paged("null")
        self.assertEqual(client.paginate("/issues"), [])


class TestTheCap(unittest.TestCase):
    def test_the_page_cap_stops_a_runaway(self):  # API-025
        transport = RecordingTransport(Response(200, page(PAGE_SIZE)))
        client = GitHub("s3cret", "derekwinters/ai-sdlc", transport=transport, max_pages=3)
        client.paginate("/issues")
        self.assertEqual(len(transport.requests), 3)

    def test_reaching_the_cap_is_visible(self):  # API-026
        transport = RecordingTransport(Response(200, page(PAGE_SIZE)))
        client = GitHub("s3cret", "derekwinters/ai-sdlc", transport=transport, max_pages=2)
        client.paginate("/issues")
        self.assertTrue(client.truncated)

    def test_not_reaching_the_cap_leaves_it_unset(self):  # API-026
        client, _ = paged(page(2))
        client.paginate("/issues")
        self.assertFalse(client.truncated)


class TestQueryParameters(unittest.TestCase):
    def test_the_page_size_is_requested_explicitly(self):
        client, transport = paged(page(1))
        client.paginate("/issues")
        self.assertIn(f"per_page={PAGE_SIZE}", transport.requests[0]["url"])

    def test_filters_reach_the_query_string(self):
        client, transport = paged(page(1))
        client.paginate("/issues", state="open")
        self.assertIn("state=open", transport.requests[0]["url"])


if __name__ == "__main__":
    unittest.main()
