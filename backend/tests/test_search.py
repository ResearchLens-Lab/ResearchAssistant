from .conftest import create_paper


async def seed(client, headers):
    await create_paper(
        client, headers,
        title="Attention Is All You Need",
        abstract="Transformer architecture with self-attention.",
        authors=["Ashish Vaswani"], publication_year=2017,
    )
    await create_paper(
        client, headers,
        title="BERT: Pre-training of Deep Bidirectional Transformers",
        abstract="Masked language modeling.",
        authors=["Jacob Devlin"], publication_year=2019,
    )
    await create_paper(
        client, headers,
        title="ResNet",
        abstract="Deep residual learning for image recognition.",
        authors=["Kaiming He"], publication_year=2016,
    )


async def test_search_by_title(client, auth_headers):
    await seed(client, auth_headers)
    resp = await client.get("/api/v1/search?q=attention", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Attention Is All You Need"


async def test_search_matches_abstract(client, auth_headers):
    await seed(client, auth_headers)
    resp = await client.get("/api/v1/search?q=residual", headers=auth_headers)
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["title"] == "ResNet"


async def test_search_by_author(client, auth_headers):
    await seed(client, auth_headers)
    resp = await client.get("/api/v1/search?author=Devlin", headers=auth_headers)
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"].startswith("BERT")


async def test_search_by_year(client, auth_headers):
    await seed(client, auth_headers)
    resp = await client.get("/api/v1/search?year=2016", headers=auth_headers)
    assert resp.json()["total"] == 1


async def test_search_combined_filters(client, auth_headers):
    await seed(client, auth_headers)
    resp = await client.get(
        "/api/v1/search?q=transformer&year=2019", headers=auth_headers
    )
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["publication_year"] == 2019


async def test_search_no_results(client, auth_headers):
    await seed(client, auth_headers)
    resp = await client.get("/api/v1/search?q=quantum", headers=auth_headers)
    assert resp.json()["total"] == 0


async def test_search_scoped_to_owner(client, auth_headers, second_user_headers):
    await seed(client, auth_headers)
    resp = await client.get("/api/v1/search?q=attention", headers=second_user_headers)
    assert resp.json()["total"] == 0


async def test_search_pagination(client, auth_headers):
    await seed(client, auth_headers)
    resp = await client.get(
        "/api/v1/search?page=1&page_size=2", headers=auth_headers
    )
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["total_pages"] == 2


async def test_search_requires_auth(client):
    resp = await client.get("/api/v1/search?q=anything")
    assert resp.status_code == 401
