import pytest

CATEGORIES_URL = "/api/v1/categories"


def test_list_categories_is_public_and_sorted_by_name(client, make_category):
    make_category(name="Storage", slug="storage")
    make_category(name="Memory", slug="memory")

    response = client.get(CATEGORIES_URL)

    assert response.status_code == 200
    assert [c["name"] for c in response.json()] == ["Memory", "Storage"]
    assert set(response.json()[0]) == {"id", "name", "slug", "description", "created_at"}


def test_list_categories_empty(client):
    assert client.get(CATEGORIES_URL).json() == []


def test_get_category(client, category):
    response = client.get(f"{CATEGORIES_URL}/{category.id}")

    assert response.status_code == 200
    assert response.json()["slug"] == "graphics-cards"


def test_get_category_not_found(client):
    response = client.get(f"{CATEGORIES_URL}/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Category not found"}


def test_admin_create_category(client, admin_headers):
    response = client.post(CATEGORIES_URL, json={"name": "Gaming Accessories", "description": "Mice and more"}, headers=admin_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Gaming Accessories"
    assert body["slug"] == "gaming-accessories"  # generated
    assert body["description"] == "Mice and more"
    assert client.get(f"{CATEGORIES_URL}/{body['id']}").status_code == 200


def test_admin_create_category_with_explicit_slug(client, admin_headers):
    response = client.post(CATEGORIES_URL, json={"name": "Cooling", "slug": "pc-cooling"}, headers=admin_headers)

    assert response.json()["slug"] == "pc-cooling"


def test_create_category_duplicate_name_is_case_insensitive(client, category, admin_headers):
    response = client.post(CATEGORIES_URL, json={"name": "graphics cards"}, headers=admin_headers)

    assert response.status_code == 409


def test_create_category_duplicate_slug(client, category, admin_headers):
    response = client.post(CATEGORIES_URL, json={"name": "Other", "slug": "graphics-cards"}, headers=admin_headers)

    assert response.status_code == 409


@pytest.mark.parametrize("payload", [{"name": "x"}, {"name": ""}, {}, {"name": "Valid", "slug": "Bad Slug"}])
def test_create_category_validation(client, admin_headers, payload):
    assert client.post(CATEGORIES_URL, json=payload, headers=admin_headers).status_code == 422


def test_admin_update_category(client, category, admin_headers):
    response = client.patch(f"{CATEGORIES_URL}/{category.id}", json={"name": "GPUs", "description": "Graphics"}, headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["name"] == "GPUs"
    assert response.json()["description"] == "Graphics"
    assert response.json()["slug"] == "graphics-cards"  # slug is stable unless changed explicitly


def test_update_category_errors(client, category, make_category, admin_headers):
    other = make_category(name="Memory", slug="memory")

    assert client.patch(f"{CATEGORIES_URL}/999", json={"name": "Nope"}, headers=admin_headers).status_code == 404
    assert client.patch(f"{CATEGORIES_URL}/{category.id}", json={"name": "MEMORY"}, headers=admin_headers).status_code == 409
    assert client.patch(f"{CATEGORIES_URL}/{category.id}", json={"slug": other.slug}, headers=admin_headers).status_code == 409
    assert client.patch(f"{CATEGORIES_URL}/{category.id}", json={"name": None}, headers=admin_headers).status_code == 422
    # keeping your own name / slug is not a conflict
    assert client.patch(f"{CATEGORIES_URL}/{category.id}", json={"name": "Graphics Cards"}, headers=admin_headers).status_code == 200


def test_admin_delete_empty_category(client, category, admin_headers):
    response = client.delete(f"{CATEGORIES_URL}/{category.id}", headers=admin_headers)

    assert response.status_code == 204
    assert client.get(f"{CATEGORIES_URL}/{category.id}").status_code == 404


def test_cannot_delete_a_category_that_has_products(client, category, product, admin_headers):
    response = client.delete(f"{CATEGORIES_URL}/{category.id}", headers=admin_headers)

    assert response.status_code == 409
    assert "product" in response.json()["detail"]
    assert client.get(f"{CATEGORIES_URL}/{category.id}").status_code == 200


def test_delete_unknown_category(client, admin_headers):
    assert client.delete(f"{CATEGORIES_URL}/999", headers=admin_headers).status_code == 404


def test_customer_cannot_modify_categories(client, category, customer_headers):
    assert client.post(CATEGORIES_URL, json={"name": "Hacked"}, headers=customer_headers).status_code == 403
    assert client.patch(f"{CATEGORIES_URL}/{category.id}", json={"name": "Hacked"}, headers=customer_headers).status_code == 403
    assert client.delete(f"{CATEGORIES_URL}/{category.id}", headers=customer_headers).status_code == 403
    assert client.get(f"{CATEGORIES_URL}/{category.id}").json()["name"] == "Graphics Cards"


def test_anonymous_cannot_modify_categories(client, category):
    assert client.post(CATEGORIES_URL, json={"name": "Hacked"}).status_code == 401
    assert client.patch(f"{CATEGORIES_URL}/{category.id}", json={"name": "Hacked"}).status_code == 401
    assert client.delete(f"{CATEGORIES_URL}/{category.id}").status_code == 401
