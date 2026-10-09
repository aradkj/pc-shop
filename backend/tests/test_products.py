import pytest
from sqlalchemy import select

from app.models import Product

PRODUCTS_URL = "/api/v1/products"


def new_product_payload(category, **overrides):
    payload = {
        "name": "ASUS Dual GeForce RTX 4070 Super 12GB",
        "description": "Compact 2-slot graphics card.",
        "price": 599.99,
        "stock": 12,
        "brand": "ASUS",
        "image_url": "https://example.com/rtx-4070-super.png",
        "category_id": category.id,
    }
    return {**payload, **overrides}


# ---------------------------------------------------------------- list / detail


def test_get_products(client, make_product):
    make_product(name="Product A", price="599.99")
    make_product(name="Product B", price="49.50")

    response = client.get(PRODUCTS_URL)

    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["page"], body["limit"], body["pages"]) == (2, 1, 12, 1)
    assert len(body["items"]) == 2
    item = next(i for i in body["items"] if i["name"] == "Product A")
    assert item["price"] == "599.99"  # exact decimal string representation
    assert item["stock"] == 10
    assert item["brand"] == "TestBrand"
    assert item["category"] == {"id": item["category_id"], "name": "Graphics Cards", "slug": "graphics-cards"}


def test_get_products_is_public(client):
    assert client.get(PRODUCTS_URL).json() == {"items": [], "total": 0, "page": 1, "limit": 12, "pages": 0}


def test_inactive_products_are_hidden_from_the_catalogue(client, make_product):
    make_product(name="Visible")
    make_product(name="Hidden", is_active=False)

    names = [item["name"] for item in client.get(PRODUCTS_URL).json()["items"]]

    assert names == ["Visible"]


def test_get_product(client, product):
    response = client.get(f"{PRODUCTS_URL}/{product.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == product.id
    assert body["name"] == "RTX Example"
    assert body["slug"] == "rtx-example"
    assert body["price"] == "599.99"
    assert body["category"]["slug"] == "graphics-cards"
    assert body["is_active"] is True


def test_product_not_found(client):
    response = client.get(f"{PRODUCTS_URL}/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found"}


def test_inactive_product_is_not_found_publicly(client, make_product):
    hidden = make_product(is_active=False)

    assert client.get(f"{PRODUCTS_URL}/{hidden.id}").status_code == 404


def test_product_lookup_by_slug_and_nonexistent(client, make_product):
    product = make_product(name="GeForce RTX 4070")
    # Lookup by slug
    res = client.get(f"{PRODUCTS_URL}/{product.slug}")
    assert res.status_code == 200
    assert res.json()["id"] == product.id
    assert res.json()["slug"] == product.slug

    # Nonexistent identifier gives 404
    assert client.get(f"{PRODUCTS_URL}/nonexistent-slug-xyz").status_code == 404


# ---------------------------------------------------------- search / filter / sort


def test_search_matches_name_brand_and_description_case_insensitively(client, make_product):
    make_product(name="AMD Ryzen 7 7800X3D", brand="AMD", description="Gaming processor")
    make_product(name="Corsair Vengeance", brand="Corsair", description="DDR5 memory kit")
    make_product(name="Samsung 990 PRO", brand="Samsung", description="Fast ryzen-friendly SSD")

    def search(term):
        return sorted(i["name"] for i in client.get(PRODUCTS_URL, params={"search": term}).json()["items"])

    assert search("RYZEN") == ["AMD Ryzen 7 7800X3D", "Samsung 990 PRO"]  # name + description
    assert search("corsair") == ["Corsair Vengeance"]  # brand
    assert search("ryzen x3d") == ["AMD Ryzen 7 7800X3D"]  # every word must match
    assert search("nothing-like-this") == []


def test_search_treats_wildcards_literally(client, make_product):
    make_product(name="Plain product")
    make_product(name="100% Cotton Mouse Pad")

    def names(term):
        return [i["name"] for i in client.get(PRODUCTS_URL, params={"search": term}).json()["items"]]

    assert names("%") == ["100% Cotton Mouse Pad"]
    assert names("_") == []


def test_filter_by_category_slug_and_id(client, make_category, make_product):
    gpus, cpus = make_category(name="GPUs", slug="gpus"), make_category(name="CPUs", slug="cpus")
    make_product(name="GPU one", category=gpus)
    make_product(name="CPU one", category=cpus)

    by_slug = client.get(PRODUCTS_URL, params={"category": "cpus"}).json()
    by_id = client.get(PRODUCTS_URL, params={"category_id": gpus.id}).json()

    assert [i["name"] for i in by_slug["items"]] == ["CPU one"]
    assert [i["name"] for i in by_id["items"]] == ["GPU one"]
    assert client.get(PRODUCTS_URL, params={"category": "unknown"}).json()["total"] == 0


def test_filter_by_brand(client, make_product):
    make_product(name="One", brand="AMD")
    make_product(name="Two", brand="Intel")

    items = client.get(PRODUCTS_URL, params={"brand": "amd"}).json()["items"]

    assert [i["name"] for i in items] == ["One"]


def test_filter_by_price_range_is_inclusive(client, make_product):
    for name, price in [("Cheap", "49.99"), ("Middle", "100.00"), ("Pricey", "999.99")]:
        make_product(name=name, price=price)

    def names(**params):
        return sorted(i["name"] for i in client.get(PRODUCTS_URL, params=params).json()["items"])

    assert names(min_price=100) == ["Middle", "Pricey"]
    assert names(max_price=100) == ["Cheap", "Middle"]
    assert names(min_price=50, max_price=500) == ["Middle"]


def test_price_range_must_be_ordered(client):
    response = client.get(PRODUCTS_URL, params={"min_price": 500, "max_price": 100})

    assert response.status_code == 422


def test_sorting(client, make_product):
    for name, price in [("B product", "20.00"), ("A product", "30.00"), ("C product", "10.00")]:
        make_product(name=name, price=price)

    def names(sort):
        return [i["name"] for i in client.get(PRODUCTS_URL, params={"sort": sort}).json()["items"]]

    assert names("price_asc") == ["C product", "B product", "A product"]
    assert names("price_desc") == ["A product", "B product", "C product"]
    assert names("name") == ["A product", "B product", "C product"]
    assert names("newest") == ["C product", "A product", "B product"]
    assert client.get(PRODUCTS_URL, params={"sort": "random"}).status_code == 422


def test_pagination(client, make_product):
    for n in range(5):
        make_product(name=f"Item {n}")

    def page(number, limit=2):
        return client.get(PRODUCTS_URL, params={"page": number, "limit": limit}).json()

    first, second, third, beyond = page(1), page(2), page(3), page(4)
    assert (first["total"], first["pages"]) == (5, 3)
    assert [len(p["items"]) for p in (first, second, third, beyond)] == [2, 2, 1, 0]
    ids = [i["id"] for p in (first, second, third) for i in p["items"]]
    assert len(set(ids)) == 5  # no duplicates across pages


@pytest.mark.parametrize("params", [{"page": 0}, {"limit": 0}, {"limit": 101}, {"page": "x"}, {"min_price": -1}])
def test_invalid_pagination_and_filter_parameters(client, params):
    assert client.get(PRODUCTS_URL, params=params).status_code == 422


def test_limit_can_be_100(client):
    assert client.get(PRODUCTS_URL, params={"limit": 100}).json()["limit"] == 100


# ---------------------------------------------------------------------- admin CRUD


def test_admin_create_product(client, db, category, admin_headers):
    response = client.post(PRODUCTS_URL, json=new_product_payload(category), headers=admin_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "ASUS Dual GeForce RTX 4070 Super 12GB"
    assert body["slug"] == "asus-dual-geforce-rtx-4070-super-12gb"
    assert body["price"] == "599.99"
    assert body["category"]["id"] == category.id
    assert body["is_active"] is True

    stored = db.scalar(select(Product).where(Product.id == body["id"]))
    assert str(stored.price) == "599.99"  # exact decimal, not a float approximation


@pytest.mark.parametrize("blank", ["", "   ", None])
def test_blank_image_url_is_stored_as_null(client, category, admin_headers, blank):
    response = client.post(PRODUCTS_URL, json=new_product_payload(category, image_url=blank), headers=admin_headers)

    assert response.status_code == 201
    assert response.json()["image_url"] is None


def test_site_relative_image_paths_are_accepted(client, category, admin_headers):
    response = client.post(PRODUCTS_URL, json=new_product_payload(category, image_url="/img/products/x.svg"), headers=admin_headers)

    assert response.json()["image_url"] == "/img/products/x.svg"


def test_image_url_is_returned_by_read(client, category, admin_headers):
    created = client.post(
        PRODUCTS_URL, json=new_product_payload(category, image_url="/images/products/gpu/card.svg"), headers=admin_headers
    ).json()

    assert created["image_url"] == "/images/products/gpu/card.svg"
    assert client.get(PRODUCTS_URL).json()["items"][0]["image_url"] == "/images/products/gpu/card.svg"
    assert client.get(f"{PRODUCTS_URL}/{created['id']}").json()["image_url"] == "/images/products/gpu/card.svg"


def test_patch_can_clear_the_image_url(client, admin_headers, product):
    response = client.patch(f"{PRODUCTS_URL}/{product.id}", json={"image_url": ""}, headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["image_url"] is None


def test_patch_can_set_the_image_url(client, admin_headers, product):
    response = client.patch(
        f"{PRODUCTS_URL}/{product.id}", json={"image_url": "https://cdn.example.com/p.jpg"}, headers=admin_headers
    )

    assert response.json()["image_url"] == "https://cdn.example.com/p.jpg"


def test_patch_rejects_an_unsafe_image_url(client, admin_headers, product):
    response = client.patch(f"{PRODUCTS_URL}/{product.id}", json={"image_url": "javascript:alert(1)"}, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "image_url"]


def test_over_long_image_url_is_rejected(client, category, admin_headers):
    response = client.post(PRODUCTS_URL, json=new_product_payload(category, image_url="/x" * 300), headers=admin_headers)

    assert response.status_code == 422


def test_admin_create_product_generates_unique_slugs(client, category, admin_headers):
    payload = new_product_payload(category, name="Same Name")

    first = client.post(PRODUCTS_URL, json=payload, headers=admin_headers).json()
    second = client.post(PRODUCTS_URL, json=payload, headers=admin_headers).json()

    assert (first["slug"], second["slug"]) == ("same-name", "same-name-2")


def test_admin_create_product_with_explicit_duplicate_slug(client, category, admin_headers, product):
    response = client.post(PRODUCTS_URL, json=new_product_payload(category, slug=product.slug), headers=admin_headers)

    assert response.status_code == 409


def test_admin_create_product_with_unknown_category(client, admin_headers, category):
    response = client.post(PRODUCTS_URL, json=new_product_payload(category, category_id=999), headers=admin_headers)

    assert response.status_code == 400
    assert response.json() == {"detail": "Category does not exist"}


@pytest.mark.parametrize(
    "overrides",
    [
        {"price": -1},
        {"price": 10.999},
        {"price": "abc"},
        {"stock": -1},
        {"name": "x"},
        {"image_url": "javascript:alert(1)"},
        {"image_url": "//evil.example.com/x.png"},
        {"slug": "Not A Slug"},
    ],
)
def test_admin_create_product_validation(client, category, admin_headers, overrides):
    response = client.post(PRODUCTS_URL, json=new_product_payload(category, **overrides), headers=admin_headers)

    assert response.status_code == 422


def test_validation_messages_are_readable(client, category, admin_headers):
    response = client.post(PRODUCTS_URL, json=new_product_payload(category, image_url="javascript:alert(1)"), headers=admin_headers)

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "image_url"]
    assert error["msg"] == "Image URL must be an http(s) link or a path starting with '/'"  # no "Value error, " prefix


def test_admin_update_product(client, db, product, admin_headers):
    response = client.patch(
        f"{PRODUCTS_URL}/{product.id}", json={"price": 549.5, "stock": 3, "name": "RTX Example (Updated)"}, headers=admin_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["price"], body["stock"], body["name"]) == ("549.50", 3, "RTX Example (Updated)")
    assert body["slug"] == "rtx-example"  # untouched
    assert body["brand"] == "TestBrand"  # untouched

    db.refresh(product)
    assert str(product.price) == "549.50"


def test_admin_update_product_can_clear_optional_fields(client, product, admin_headers):
    response = client.patch(f"{PRODUCTS_URL}/{product.id}", json={"description": None, "brand": None}, headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["description"] is None
    assert response.json()["brand"] is None


@pytest.mark.parametrize("field", ["name", "price", "stock", "category_id", "is_active"])
def test_admin_update_cannot_null_required_fields(client, product, admin_headers, field):
    response = client.patch(f"{PRODUCTS_URL}/{product.id}", json={field: None}, headers=admin_headers)

    assert response.status_code == 422


def test_admin_update_product_errors(client, product, make_product, admin_headers):
    other = make_product()

    assert client.patch(f"{PRODUCTS_URL}/999", json={"stock": 1}, headers=admin_headers).status_code == 404
    assert client.patch(f"{PRODUCTS_URL}/{product.id}", json={"slug": other.slug}, headers=admin_headers).status_code == 409
    assert client.patch(f"{PRODUCTS_URL}/{product.id}", json={"category_id": 999}, headers=admin_headers).status_code == 400
    assert client.patch(f"{PRODUCTS_URL}/{product.id}", json={"slug": product.slug}, headers=admin_headers).status_code == 200


def test_admin_can_deactivate_a_product_to_hide_it(client, product, admin_headers):
    client.patch(f"{PRODUCTS_URL}/{product.id}", json={"is_active": False}, headers=admin_headers)

    assert client.get(f"{PRODUCTS_URL}/{product.id}").status_code == 404
    admin_list = client.get("/api/v1/admin/products", headers=admin_headers).json()
    assert [(i["id"], i["is_active"]) for i in admin_list["items"]] == [(product.id, False)]


def test_admin_delete_product(client, db, product, admin_headers):
    product_id = product.id

    response = client.delete(f"{PRODUCTS_URL}/{product_id}", headers=admin_headers)

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"{PRODUCTS_URL}/{product_id}").status_code == 404
    db.expire_all()
    assert db.get(Product, product_id) is None


def test_admin_delete_unknown_product(client, admin_headers):
    assert client.delete(f"{PRODUCTS_URL}/999", headers=admin_headers).status_code == 404


def test_deleting_a_product_removes_it_from_carts(client, db, product, customer_headers, admin_headers):
    client.post("/api/v1/cart/items", json={"product_id": product.id, "quantity": 1}, headers=customer_headers)

    assert client.delete(f"{PRODUCTS_URL}/{product.id}", headers=admin_headers).status_code == 204
    assert client.get("/api/v1/cart", headers=customer_headers).json()["items"] == []


# ------------------------------------------------------------------- authorization


def test_customer_cannot_create_product(client, db, category, customer_headers):
    response = client.post(PRODUCTS_URL, json=new_product_payload(category), headers=customer_headers)

    assert response.status_code == 403
    assert response.json() == {"detail": "Admin privileges required"}
    assert db.scalar(select(Product)) is None


def test_anonymous_cannot_create_product(client, category):
    assert client.post(PRODUCTS_URL, json=new_product_payload(category)).status_code == 401


def test_customer_cannot_update_or_delete_products(client, db, product, customer_headers):
    patch = client.patch(f"{PRODUCTS_URL}/{product.id}", json={"price": 1}, headers=customer_headers)
    delete = client.delete(f"{PRODUCTS_URL}/{product.id}", headers=customer_headers)

    assert (patch.status_code, delete.status_code) == (403, 403)
    db.refresh(product)
    assert str(product.price) == "599.99"


def test_money_decimal_precision_no_float_drift(client, category, admin_headers):
    # In binary float, 0.1 + 0.2 = 0.30000000000000004
    # Test that Decimal preservation prevents binary float drift
    p1 = new_product_payload(category, name="Item 10c", price=0.10, slug="item-10c")
    p2 = new_product_payload(category, name="Item 20c", price=0.20, slug="item-20c")

    res1 = client.post(PRODUCTS_URL, json=p1, headers=admin_headers)
    assert res1.status_code == 201
    assert res1.json()["price"] == "0.10"
    assert isinstance(res1.json()["price"], str)

    res2 = client.post(PRODUCTS_URL, json=p2, headers=admin_headers)
    assert res2.status_code == 201
    assert res2.json()["price"] == "0.20"
    assert isinstance(res2.json()["price"], str)

