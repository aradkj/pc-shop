from decimal import Decimal
import pytest
from app.models import Category, Product

BUILDER_URL = "/api/v1/pc-builder"


@pytest.fixture
def builder_categories(make_category):
    return {
        "cpu": make_category(name="CPU", slug="cpu"),
        "gpu": make_category(name="GPU", slug="gpu"),
        "ram": make_category(name="RAM", slug="ram"),
        "motherboard": make_category(name="Motherboard", slug="motherboard"),
        "storage": make_category(name="Storage", slug="storage"),
        "psu": make_category(name="PSU", slug="psu"),
        "pc-case": make_category(name="PC Case", slug="pc-case"),
        "cooler": make_category(name="Cooler", slug="cooler"),
    }


@pytest.fixture
def make_builder_product(db):
    def _create(
        name: str,
        category: Category,
        price: str = "100.00",
        stock: int = 10,
        is_active: bool = True,
        specifications: dict | None = None,
    ) -> Product:
        import itertools
        slug = f"{name.lower().replace(' ', '-')}-{id(specifications)}"
        prod = Product(
            name=name,
            slug=slug,
            price=Decimal(price),
            stock=stock,
            is_active=is_active,
            category_id=category.id,
            specifications=specifications or {},
        )
        db.add(prod)
        db.commit()
        db.refresh(prod)
        return prod

    return _create


# ---------------------------------------------------------------------------
# 1. CPU + compatible motherboard -> valid
# ---------------------------------------------------------------------------
def test_cpu_motherboard_compatible(client, builder_categories, make_builder_product):
    cpu = make_builder_product(
        "AMD Ryzen 7 7700X",
        builder_categories["cpu"],
        specifications={"socket": "AM5", "memory_support": "DDR5-5200"},
    )
    mobo = make_builder_product(
        "MSI B650 Gaming Plus",
        builder_categories["motherboard"],
        specifications={"socket": "AM5", "memory_type": "DDR5", "form_factor": "ATX"},
    )

    response = client.post(
        f"{BUILDER_URL}/validate",
        json={"components": {"cpu": cpu.id, "motherboard": mobo.id}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["compatible"] is True
    assert not any(i["type"] == "socket_mismatch" for i in data["issues"])


# ---------------------------------------------------------------------------
# 2. CPU + incompatible motherboard socket -> invalid
# ---------------------------------------------------------------------------
def test_cpu_motherboard_socket_mismatch(client, builder_categories, make_builder_product):
    cpu = make_builder_product(
        "AMD Ryzen 7 7700X",
        builder_categories["cpu"],
        specifications={"socket": "AM5", "memory_support": "DDR5-5200"},
    )
    mobo = make_builder_product(
        "MSI B550 Gaming",
        builder_categories["motherboard"],
        specifications={"socket": "AM4", "memory_type": "DDR4", "form_factor": "ATX"},
    )

    response = client.post(
        f"{BUILDER_URL}/validate",
        json={"components": {"cpu": cpu.id, "motherboard": mobo.id}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["compatible"] is False
    issue = next(i for i in data["issues"] if i["type"] == "socket_mismatch")
    assert issue["severity"] == "error"
    assert "AM5" in issue["message"] and "AM4" in issue["message"]


# ---------------------------------------------------------------------------
# 3. DDR4 RAM + DDR5 motherboard -> invalid
# ---------------------------------------------------------------------------
def test_ddr4_ram_ddr5_motherboard_mismatch(client, builder_categories, make_builder_product):
    ram = make_builder_product(
        "Corsair DDR4 32GB",
        builder_categories["ram"],
        specifications={"memory_type": "DDR4"},
    )
    mobo = make_builder_product(
        "ASUS B650",
        builder_categories["motherboard"],
        specifications={"socket": "AM5", "memory_type": "DDR5"},
    )

    response = client.post(
        f"{BUILDER_URL}/validate",
        json={"components": {"ram": ram.id, "motherboard": mobo.id}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["compatible"] is False
    assert any(i["type"] == "ram_motherboard_mismatch" for i in data["issues"])


# ---------------------------------------------------------------------------
# 4. DDR5 RAM + DDR5 motherboard -> valid
# ---------------------------------------------------------------------------
def test_ddr5_ram_ddr5_motherboard_valid(client, builder_categories, make_builder_product):
    ram = make_builder_product(
        "G.Skill DDR5 32GB",
        builder_categories["ram"],
        specifications={"memory_type": "DDR5"},
    )
    mobo = make_builder_product(
        "ASUS B650",
        builder_categories["motherboard"],
        specifications={"socket": "AM5", "memory_type": "DDR5"},
    )

    response = client.post(
        f"{BUILDER_URL}/validate",
        json={"components": {"ram": ram.id, "motherboard": mobo.id}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["compatible"] is True
    assert not any(i["type"] == "ram_motherboard_mismatch" for i in data["issues"])


# ---------------------------------------------------------------------------
# 5. Compatible cooler socket -> valid
# ---------------------------------------------------------------------------
def test_compatible_cooler_socket(client, builder_categories, make_builder_product):
    cpu = make_builder_product(
        "AMD Ryzen 7 7700X",
        builder_categories["cpu"],
        specifications={"socket": "AM5", "tdp": "105W"},
    )
    cooler = make_builder_product(
        "Thermalright Peerless Assassin",
        builder_categories["cooler"],
        specifications={"socket_support": "AM4, AM5, LGA1700", "cooling_capacity_tdp": "245W"},
    )

    response = client.post(
        f"{BUILDER_URL}/validate",
        json={"components": {"cpu": cpu.id, "cooler": cooler.id}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["compatible"] is True
    assert not any(i["type"] == "cooler_socket_incompatible" for i in data["issues"])


# ---------------------------------------------------------------------------
# 6. Incompatible cooler socket -> invalid
# ---------------------------------------------------------------------------
def test_incompatible_cooler_socket(client, builder_categories, make_builder_product):
    cpu = make_builder_product(
        "AMD Ryzen 7 7700X",
        builder_categories["cpu"],
        specifications={"socket": "AM5", "tdp": "105W"},
    )
    cooler = make_builder_product(
        "Legacy Intel Cooler",
        builder_categories["cooler"],
        specifications={"socket_support": "LGA1200, LGA115x", "cooling_capacity_tdp": "95W"},
    )

    response = client.post(
        f"{BUILDER_URL}/validate",
        json={"components": {"cpu": cpu.id, "cooler": cooler.id}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["compatible"] is False
    assert any(i["type"] == "cooler_socket_incompatible" for i in data["issues"])


# ---------------------------------------------------------------------------
# 7. GPU recommendation returns sensible results
# ---------------------------------------------------------------------------
def test_gpu_recommendations_sensible(client, builder_categories, make_builder_product):
    cpu = make_builder_product(
        "AMD Ryzen 5 7600X",
        builder_categories["cpu"],
        price="219.99",
        specifications={"socket": "AM5", "cores": 6},
    )
    gpu_entry = make_builder_product(
        "RX 6600",
        builder_categories["gpu"],
        price="219.99",
        specifications={"gpu_model": "RX 6600", "recommended_psu": "450W"},
    )
    gpu_mid = make_builder_product(
        "RTX 4070 Super",
        builder_categories["gpu"],
        price="599.99",
        specifications={"gpu_model": "RTX 4070 Super", "recommended_psu": "650W"},
    )
    gpu_flagship = make_builder_product(
        "RTX 4090",
        builder_categories["gpu"],
        price="1799.99",
        specifications={"gpu_model": "RTX 4090", "recommended_psu": "850W"},
    )

    response = client.get(f"{BUILDER_URL}/recommendations/gpu?cpu_id={cpu.id}")
    assert response.status_code == 200
    recs = response.json()
    assert len(recs) == 3

    # Check that each recommendation contains score, match_level, and reason
    for r in recs:
        assert "score" in r
        assert "match_level" in r
        assert "reason" in r
        assert r["match_level"] in ["recommended", "good match", "not ideal"]

    # Highest score should be the balanced GPU (RX 6600 or RTX 4070 Super), not RTX 4090
    flagship_rec = next(r for r in recs if r["product_id"] == gpu_flagship.id)
    assert flagship_rec["match_level"] in ["good match", "not ideal"]


# ---------------------------------------------------------------------------
# 8. Insufficient PSU -> invalid/error
# ---------------------------------------------------------------------------
def test_insufficient_psu_wattage(client, builder_categories, make_builder_product):
    gpu = make_builder_product(
        "RTX 4090",
        builder_categories["gpu"],
        specifications={"recommended_psu": "850W", "power_consumption": "450W"},
    )
    psu = make_builder_product(
        "Basic 500W PSU",
        builder_categories["psu"],
        specifications={"wattage": "500W"},
    )

    response = client.post(
        f"{BUILDER_URL}/validate",
        json={"components": {"gpu": gpu.id, "psu": psu.id}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["compatible"] is False
    assert any(i["type"] == "insufficient_psu_wattage" for i in data["issues"])


# ---------------------------------------------------------------------------
# 9. Sufficient PSU -> valid
# ---------------------------------------------------------------------------
def test_sufficient_psu_wattage(client, builder_categories, make_builder_product):
    gpu = make_builder_product(
        "RTX 4070",
        builder_categories["gpu"],
        specifications={"recommended_psu": "650W", "power_consumption": "200W"},
    )
    psu = make_builder_product(
        "Corsair 850W PSU",
        builder_categories["psu"],
        specifications={"wattage": "850W"},
    )

    response = client.post(
        f"{BUILDER_URL}/validate",
        json={"components": {"gpu": gpu.id, "psu": psu.id}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["compatible"] is True
    assert not any(i["type"] == "insufficient_psu_wattage" for i in data["issues"])


# ---------------------------------------------------------------------------
# 10. Case / form-factor compatibility
# ---------------------------------------------------------------------------
def test_case_form_factor_compatibility(client, builder_categories, make_builder_product):
    mobo_atx = make_builder_product(
        "ATX Mobo",
        builder_categories["motherboard"],
        specifications={"form_factor": "ATX"},
    )
    mobo_matx = make_builder_product(
        "Micro-ATX Mobo",
        builder_categories["motherboard"],
        specifications={"form_factor": "Micro-ATX"},
    )
    case_mid = make_builder_product(
        "Mid-Tower ATX Case",
        builder_categories["pc-case"],
        specifications={"motherboard_support": "ATX, Micro-ATX, Mini-ITX"},
    )
    case_itx = make_builder_product(
        "Mini-ITX Case",
        builder_categories["pc-case"],
        specifications={"motherboard_support": "Mini-ITX"},
    )

    # ATX in ATX Case -> Valid
    r1 = client.post(
        f"{BUILDER_URL}/validate",
        json={"components": {"motherboard": mobo_atx.id, "pc-case": case_mid.id}},
    )
    assert r1.json()["compatible"] is True

    # Micro-ATX in ATX Case -> Valid
    r2 = client.post(
        f"{BUILDER_URL}/validate",
        json={"components": {"motherboard": mobo_matx.id, "pc-case": case_mid.id}},
    )
    assert r2.json()["compatible"] is True

    # ATX in Mini-ITX Case -> Invalid
    r3 = client.post(
        f"{BUILDER_URL}/validate",
        json={"components": {"motherboard": mobo_atx.id, "pc-case": case_itx.id}},
    )
    assert r3.json()["compatible"] is False
    assert any(i["type"] == "case_form_factor_incompatible" for i in r3.json()["issues"])


# ---------------------------------------------------------------------------
# 11. Storage compatibility where data supports the check
# ---------------------------------------------------------------------------
def test_storage_compatibility(client, builder_categories, make_builder_product):
    mobo_no_m2 = make_builder_product(
        "Mobo No M2",
        builder_categories["motherboard"],
        specifications={"m2_slots": 0, "sata_ports": 4},
    )
    storage_nvme = make_builder_product(
        "NVMe M.2 SSD",
        builder_categories["storage"],
        specifications={"type": "NVMe SSD", "form_factor": "M.2 2280"},
    )
    storage_sata = make_builder_product(
        "SATA 2.5 SSD",
        builder_categories["storage"],
        specifications={"type": "SATA SSD", "form_factor": "2.5-inch"},
    )

    # NVMe with 0 M.2 slots -> Invalid
    r1 = client.post(
        f"{BUILDER_URL}/validate",
        json={"components": {"motherboard": mobo_no_m2.id, "storage": storage_nvme.id}},
    )
    assert r1.json()["compatible"] is False
    assert any(i["type"] == "no_m2_slots" for i in r1.json()["issues"])

    # SATA with 4 SATA ports -> Valid
    r2 = client.post(
        f"{BUILDER_URL}/validate",
        json={"components": {"motherboard": mobo_no_m2.id, "storage": storage_sata.id}},
    )
    assert r2.json()["compatible"] is True


# ---------------------------------------------------------------------------
# 12. Missing specification data does not cause false compatibility claims
# ---------------------------------------------------------------------------
def test_missing_specifications_not_falsely_incompatible(client, builder_categories, make_builder_product):
    cpu = make_builder_product(
        "Generic CPU",
        builder_categories["cpu"],
        specifications={},
    )
    mobo = make_builder_product(
        "Generic Mobo",
        builder_categories["motherboard"],
        specifications={},
    )

    response = client.post(
        f"{BUILDER_URL}/validate",
        json={"components": {"cpu": cpu.id, "motherboard": mobo.id}},
    )
    assert response.status_code == 200
    data = response.json()
    # Missing specs trigger warnings, not false errors
    assert data["compatible"] is True
    assert any("Unknown / needs verification" in w["message"] for w in data["warnings"])


# ---------------------------------------------------------------------------
# 13. Inactive products cannot be used
# ---------------------------------------------------------------------------
def test_inactive_product_cannot_be_used(client, builder_categories, make_builder_product):
    cpu = make_builder_product(
        "Discontinued CPU",
        builder_categories["cpu"],
        is_active=False,
        specifications={"socket": "AM5"},
    )

    response = client.post(
        f"{BUILDER_URL}/validate",
        json={"components": {"cpu": cpu.id}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["compatible"] is False
    assert any(i["type"] == "inactive_product" for i in data["issues"])


# ---------------------------------------------------------------------------
# 14. Out-of-stock products cannot be selected for a purchasable build
# ---------------------------------------------------------------------------
def test_out_of_stock_product_validation(client, builder_categories, make_builder_product):
    ram = make_builder_product(
        "Out of Stock RAM",
        builder_categories["ram"],
        stock=0,
        specifications={"memory_type": "DDR5"},
    )

    response = client.post(
        f"{BUILDER_URL}/validate",
        json={"components": {"ram": ram.id}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["compatible"] is False
    assert any(i["type"] == "out_of_stock" for i in data["issues"])


# ---------------------------------------------------------------------------
# 15. Incomplete build -> no 5% discount
# ---------------------------------------------------------------------------
def test_incomplete_build_no_discount(client, builder_categories, make_builder_product):
    cpu = make_builder_product("CPU", builder_categories["cpu"], price="200.00", specifications={"socket": "AM5"})
    mobo = make_builder_product("Mobo", builder_categories["motherboard"], price="100.00", specifications={"socket": "AM5"})

    response = client.post(
        f"{BUILDER_URL}/validate",
        json={"components": {"cpu": cpu.id, "motherboard": mobo.id}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["complete"] is False
    assert data["subtotal"] == "300.00"
    assert data["discount_percent"] == "0"
    assert data["discount_amount"] == "0.00"
    assert data["total"] == "300.00"


# ---------------------------------------------------------------------------
# 16. Complete build -> exactly 5% discount
# ---------------------------------------------------------------------------
def _create_full_build(builder_categories, make_builder_product):
    cpu = make_builder_product("CPU", builder_categories["cpu"], price="300.00", specifications={"socket": "AM5", "memory_support": "DDR5-5200", "tdp": "105W"})
    mobo = make_builder_product("Motherboard", builder_categories["motherboard"], price="200.00", specifications={"socket": "AM5", "memory_type": "DDR5", "form_factor": "ATX", "m2_slots": 2})
    ram = make_builder_product("RAM", builder_categories["ram"], price="100.00", specifications={"memory_type": "DDR5"})
    gpu = make_builder_product("GPU", builder_categories["gpu"], price="600.00", specifications={"recommended_psu": "650W", "power_consumption": "200W"})
    storage = make_builder_product("Storage", builder_categories["storage"], price="100.00", specifications={"type": "NVMe SSD", "form_factor": "M.2 2280"})
    psu = make_builder_product("PSU", builder_categories["psu"], price="100.00", specifications={"wattage": "750W"})
    case = make_builder_product("PC Case", builder_categories["pc-case"], price="100.00", specifications={"motherboard_support": "ATX, Micro-ATX, Mini-ITX"})
    cooler = make_builder_product("Cooler", builder_categories["cooler"], price="100.00", specifications={"socket_support": "AM5, AM4", "cooling_capacity_tdp": "240W"})
    return {
        "cpu": cpu,
        "motherboard": mobo,
        "ram": ram,
        "gpu": gpu,
        "storage": storage,
        "psu": psu,
        "pc-case": case,
        "cooler": cooler,
    }


def test_complete_build_exactly_five_percent_discount(client, builder_categories, make_builder_product):
    build = _create_full_build(builder_categories, make_builder_product)
    components = {cat: prod.id for cat, prod in build.items()}

    response = client.post(f"{BUILDER_URL}/validate", json={"components": components})
    assert response.status_code == 200
    data = response.json()
    assert data["complete"] is True
    assert data["compatible"] is True
    assert data["subtotal"] == "1600.00"
    assert data["discount_percent"] == "5"
    assert data["discount_amount"] == "80.00"  # 1600 * 0.05 = 80.00
    assert data["total"] == "1520.00"


# ---------------------------------------------------------------------------
# 17. Decimal arithmetic is exact
# ---------------------------------------------------------------------------
def test_decimal_arithmetic_exact(client, builder_categories, make_builder_product):
    # Total sum: 199.99 * 8 = 1599.92
    # 5% of 1599.92 = 79.996 -> quantized to 80.00
    # Total: 1599.92 - 80.00 = 1519.92
    components = {}
    for cat in ["cpu", "motherboard", "ram", "gpu", "storage", "psu", "pc-case", "cooler"]:
        p = make_builder_product(
            f"Item {cat}",
            builder_categories[cat],
            price="199.99",
            specifications={
                "socket": "AM5",
                "memory_support": "DDR5-5200",
                "memory_type": "DDR5",
                "form_factor": "ATX",
                "motherboard_support": "ATX",
                "socket_support": "AM5",
                "wattage": "850W",
                "recommended_psu": "550W",
                "type": "NVMe SSD",
                "m2_slots": 2,
            },
        )
        components[cat] = p.id

    response = client.post(f"{BUILDER_URL}/price", json={"components": components})
    assert response.status_code == 200
    data = response.json()
    assert data["subtotal"] == "1599.92"
    assert data["discount_amount"] == "80.00"
    assert data["total"] == "1519.92"


# ---------------------------------------------------------------------------
# 18 & 19. Frontend-supplied fake price / discount cannot manipulate backend totals
# ---------------------------------------------------------------------------
def test_frontend_supplied_fake_values_ignored(client, builder_categories, make_builder_product):
    cpu = make_builder_product("CPU", builder_categories["cpu"], price="200.00")
    forged_body = {
        "components": {"cpu": cpu.id},
        "price": "1.00",
        "subtotal": "1.00",
        "discount_amount": "99.00",
        "total": "1.00",
    }

    response = client.post(f"{BUILDER_URL}/validate", json=forged_body)
    assert response.status_code == 200
    data = response.json()
    assert data["subtotal"] == "200.00"
    assert data["total"] == "200.00"
    assert data["discount_amount"] == "0.00"


# ---------------------------------------------------------------------------
# 20. Build validation with nonexistent product IDs
# ---------------------------------------------------------------------------
def test_validation_with_nonexistent_product_ids(client):
    response = client.post(
        f"{BUILDER_URL}/validate",
        json={"components": {"cpu": 999999, "motherboard": 888888}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["compatible"] is False
    assert any(i["type"] == "nonexistent_product" for i in data["issues"])


# ---------------------------------------------------------------------------
# 21. Duplicate category selections are rejected or handled correctly
# ---------------------------------------------------------------------------
def test_duplicate_category_selection(client, builder_categories, make_builder_product):
    cpu1 = make_builder_product("CPU 1", builder_categories["cpu"])
    cpu2 = make_builder_product("CPU 2", builder_categories["cpu"])

    # Provide two distinct product IDs of the same category via product_ids
    response = client.post(
        f"{BUILDER_URL}/validate",
        json={"product_ids": [cpu1.id, cpu2.id]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["compatible"] is False
    assert any(i["type"] == "duplicate_category" for i in data["issues"])


# ---------------------------------------------------------------------------
# 22. All required categories are required
# ---------------------------------------------------------------------------
def test_all_eight_categories_required(client, builder_categories, make_builder_product):
    build = _create_full_build(builder_categories, make_builder_product)

    # Missing Cooler
    seven_components = {cat: prod.id for cat, prod in build.items() if cat != "cooler"}
    resp = client.post(f"{BUILDER_URL}/validate", json={"components": seven_components})
    assert resp.json()["complete"] is False
    assert resp.json()["discount_percent"] == "0"

    # All eight present
    eight_components = {cat: prod.id for cat, prod in build.items()}
    resp = client.post(f"{BUILDER_URL}/validate", json={"components": eight_components})
    assert resp.json()["complete"] is True
    assert resp.json()["discount_percent"] == "5"


# ---------------------------------------------------------------------------
# Cart & Order checkout integration with complete build discount
# ---------------------------------------------------------------------------
def test_add_build_to_cart_and_order_checkout(client, db, builder_categories, make_builder_product, customer_headers):
    build = _create_full_build(builder_categories, make_builder_product)
    components = {cat: prod.id for cat, prod in build.items()}

    # Add build to cart
    add_resp = client.post(
        f"{BUILDER_URL}/add-to-cart",
        json={"components": components, "clear_existing": True},
        headers=customer_headers,
    )
    assert add_resp.status_code == 201
    cart_data = add_resp.json()
    assert len(cart_data["items"]) == 8

    # Checkout order
    order_resp = client.post("/api/v1/orders", headers=customer_headers)
    assert order_resp.status_code == 201
    order = order_resp.json()

    # Build subtotal is 1600.00, discount 5% = 80.00, total = 1520.00
    assert order["discount_amount"] == "80.00"
    assert order["total_price"] == "1520.00"
    assert len(order["items"]) == 8


def test_builder_options_endpoint(client, builder_categories, make_builder_product):
    make_builder_product("CPU Option", builder_categories["cpu"], price="150.00")
    make_builder_product("GPU Option", builder_categories["gpu"], price="350.00")

    resp = client.get(f"{BUILDER_URL}/options")
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data
    assert "options" in data
    assert "cpu" in data["options"]
    assert len(data["options"]["cpu"]) >= 1
