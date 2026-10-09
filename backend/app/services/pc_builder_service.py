import logging
import re
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.cart import Cart, CartItem
from app.models.category import Category
from app.models.product import Product
from app.models.user import User
from app.schemas.pc_builder import (
    BuilderOptionsResponse,
    BuilderProductBrief,
    BuildValidationResponse,
    CompatibilityIssue,
    GPURecommendation,
    RecommendationItem,
)
from app.services import cart_service

logger = logging.getLogger(__name__)

CORE_BUILD_CATEGORIES: set[str] = {
    "cpu",
    "gpu",
    "ram",
    "motherboard",
    "storage",
    "psu",
    "pc-case",
    "cooler",
}

CATEGORY_ALIASES: dict[str, str] = {
    "cpu": "cpu",
    "processor": "cpu",
    "processors": "cpu",
    "gpu": "gpu",
    "graphics-card": "gpu",
    "graphics-cards": "gpu",
    "video-card": "gpu",
    "ram": "ram",
    "memory": "ram",
    "motherboard": "motherboard",
    "mobo": "motherboard",
    "storage": "storage",
    "ssd": "storage",
    "hdd": "storage",
    "psu": "psu",
    "power-supply": "psu",
    "pc-case": "pc-case",
    "case": "pc-case",
    "pc_case": "pc-case",
    "chassis": "pc-case",
    "cooler": "cooler",
    "cpu-cooler": "cooler",
}


def normalize_category_slug(slug: str) -> str:
    cleaned = slug.strip().lower()
    return CATEGORY_ALIASES.get(cleaned, cleaned)


def _extract_number(val: Any) -> int | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    match = re.search(r"\d+", str(val))
    return int(match.group()) if match else None


# ---------------------------------------------------------------------------
# Individual Compatibility Check Functions
# ---------------------------------------------------------------------------


def check_cpu_motherboard_compatibility(
    cpu: Product, mobo: Product
) -> tuple[list[CompatibilityIssue], list[CompatibilityIssue]]:
    """A) CPU <-> Motherboard: The CPU socket must match the motherboard socket."""
    issues: list[CompatibilityIssue] = []
    warnings: list[CompatibilityIssue] = []

    cpu_specs = cpu.specifications or {}
    mobo_specs = mobo.specifications or {}

    cpu_socket = cpu_specs.get("socket")
    mobo_socket = mobo_specs.get("socket")

    if not cpu_socket or not mobo_socket:
        warnings.append(
            CompatibilityIssue(
                type="missing_socket_data",
                severity="warning",
                components=["cpu", "motherboard"],
                message="Unknown / needs verification: Socket specification missing for CPU or Motherboard.",
            )
        )
        return issues, warnings

    if str(cpu_socket).strip().upper() != str(mobo_socket).strip().upper():
        issues.append(
            CompatibilityIssue(
                type="socket_mismatch",
                severity="error",
                components=["cpu", "motherboard"],
                message=(
                    f"CPU socket ({cpu_socket}) does not match Motherboard socket ({mobo_socket}). "
                    "The processor cannot be physically mounted on this motherboard."
                ),
            )
        )

    return issues, warnings


def check_motherboard_ram_compatibility(
    mobo: Product, ram: Product
) -> tuple[list[CompatibilityIssue], list[CompatibilityIssue]]:
    """B) Motherboard <-> RAM: RAM memory type must match motherboard memory type."""
    issues: list[CompatibilityIssue] = []
    warnings: list[CompatibilityIssue] = []

    mobo_specs = mobo.specifications or {}
    ram_specs = ram.specifications or {}

    mobo_mem = mobo_specs.get("memory_type")
    ram_mem = ram_specs.get("memory_type")

    if not mobo_mem or not ram_mem:
        warnings.append(
            CompatibilityIssue(
                type="missing_memory_type_data",
                severity="warning",
                components=["motherboard", "ram"],
                message="Unknown / needs verification: Memory type missing for Motherboard or RAM.",
            )
        )
        return issues, warnings

    if str(mobo_mem).strip().upper() != str(ram_mem).strip().upper():
        issues.append(
            CompatibilityIssue(
                type="ram_motherboard_mismatch",
                severity="error",
                components=["motherboard", "ram"],
                message=f"Motherboard requires {mobo_mem} memory, but selected RAM is {ram_mem}.",
            )
        )

    return issues, warnings


def check_cpu_ram_compatibility(
    cpu: Product, ram: Product
) -> tuple[list[CompatibilityIssue], list[CompatibilityIssue]]:
    """C) CPU <-> RAM: CPU memory support must be compatible with selected RAM."""
    issues: list[CompatibilityIssue] = []
    warnings: list[CompatibilityIssue] = []

    cpu_specs = cpu.specifications or {}
    ram_specs = ram.specifications or {}

    cpu_mem_support = cpu_specs.get("memory_support")
    ram_mem = ram_specs.get("memory_type")

    if not cpu_mem_support or not ram_mem:
        warnings.append(
            CompatibilityIssue(
                type="missing_cpu_memory_support",
                severity="warning",
                components=["cpu", "ram"],
                message="Unknown / needs verification: Memory support specification missing for CPU or RAM.",
            )
        )
        return issues, warnings

    ram_type = str(ram_mem).strip().upper()
    cpu_support = str(cpu_mem_support).strip().upper()

    if ram_type not in cpu_support:
        issues.append(
            CompatibilityIssue(
                type="cpu_ram_mismatch",
                severity="error",
                components=["cpu", "ram"],
                message=f"CPU memory controller does not support {ram_mem} (supported: {cpu_mem_support}).",
            )
        )

    return issues, warnings


def check_cooler_compatibility(
    cpu: Product, cooler: Product
) -> tuple[list[CompatibilityIssue], list[CompatibilityIssue]]:
    """G) Cooler <-> CPU: Socket compatibility and thermal requirements/TDP."""
    issues: list[CompatibilityIssue] = []
    warnings: list[CompatibilityIssue] = []

    cpu_specs = cpu.specifications or {}
    cooler_specs = cooler.specifications or {}

    cpu_socket = cpu_specs.get("socket")
    socket_support = cooler_specs.get("socket_support")

    if cpu_socket and socket_support:
        supported = [s.strip().upper() for s in str(socket_support).split(",")]
        if str(cpu_socket).strip().upper() not in supported:
            issues.append(
                CompatibilityIssue(
                    type="cooler_socket_incompatible",
                    severity="error",
                    components=["cpu", "cooler"],
                    message=f"Cooler does not support CPU socket {cpu_socket} (supported sockets: {socket_support}).",
                )
            )
    elif not socket_support:
        warnings.append(
            CompatibilityIssue(
                type="missing_cooler_socket_data",
                severity="warning",
                components=["cpu", "cooler"],
                message="Unknown / needs verification: Cooler socket support specifications are not available.",
            )
        )

    # Thermal / TDP capability
    cpu_tdp = _extract_number(cpu_specs.get("tdp"))
    cooler_tdp = _extract_number(cooler_specs.get("cooling_capacity_tdp"))

    if cpu_tdp and cooler_tdp and cooler_tdp < cpu_tdp:
        warnings.append(
            CompatibilityIssue(
                type="cooler_tdp_insufficient",
                severity="warning",
                components=["cpu", "cooler"],
                message=(
                    f"Cooler cooling capacity ({cooler_tdp}W) is lower than CPU TDP ({cpu_tdp}W). "
                    "The processor may experience elevated temperatures or thermal throttling under heavy loads."
                ),
            )
        )

    return issues, warnings


def check_psu_requirement(
    gpu: Product | None, cpu: Product | None, psu: Product
) -> tuple[list[CompatibilityIssue], list[CompatibilityIssue]]:
    """E) GPU <-> PSU: Recommended wattage with safety margin and CPU TDP consideration."""
    issues: list[CompatibilityIssue] = []
    warnings: list[CompatibilityIssue] = []

    psu_specs = psu.specifications or {}
    gpu_specs = (gpu.specifications or {}) if gpu else {}
    cpu_specs = (cpu.specifications or {}) if cpu else {}

    psu_wattage = _extract_number(psu_specs.get("wattage"))
    gpu_rec_psu = _extract_number(gpu_specs.get("recommended_psu"))
    gpu_pwr = _extract_number(gpu_specs.get("power_consumption")) or 0
    cpu_tdp = _extract_number(cpu_specs.get("tdp")) or 65

    if not psu_wattage:
        warnings.append(
            CompatibilityIssue(
                type="missing_psu_wattage",
                severity="warning",
                components=["psu"],
                message="Unknown / needs verification: PSU wattage specification is missing.",
            )
        )
        return issues, warnings

    # Estimate minimum system requirement
    estimated_system_draw = gpu_pwr + cpu_tdp + 100
    minimum_required = max(gpu_rec_psu or 0, estimated_system_draw)

    components = ["psu"]
    if gpu:
        components.append("gpu")

    if minimum_required > 0 and psu_wattage < minimum_required:
        issues.append(
            CompatibilityIssue(
                type="insufficient_psu_wattage",
                severity="error",
                components=components,
                message=(
                    f"Selected PSU ({psu_wattage}W) is insufficient. Minimum recommended wattage "
                    f"for this configuration is {minimum_required}W."
                ),
            )
        )
    elif minimum_required > 0 and psu_wattage < minimum_required + 50:
        recommended_target = minimum_required + 100
        warnings.append(
            CompatibilityIssue(
                type="psu_headroom_warning",
                severity="warning",
                components=components,
                message=(
                    f"Selected PSU ({psu_wattage}W) meets the base requirement ({minimum_required}W), "
                    f"but a {recommended_target}W+ unit is recommended for safety margin and transient spikes."
                ),
            )
        )

    return issues, warnings


def check_case_compatibility(
    mobo: Product | None,
    case: Product,
    gpu: Product | None = None,
    cooler: Product | None = None,
) -> tuple[list[CompatibilityIssue], list[CompatibilityIssue]]:
    """F) Motherboard <-> Case: Form factor compatibility without rejecting smaller boards."""
    issues: list[CompatibilityIssue] = []
    warnings: list[CompatibilityIssue] = []

    case_specs = case.specifications or {}

    if mobo:
        mobo_specs = mobo.specifications or {}
        mobo_ff = mobo_specs.get("form_factor")
        case_mobo_support = case_specs.get("motherboard_support")

        if mobo_ff and case_mobo_support:
            supported = [s.strip().upper() for s in str(case_mobo_support).split(",")]
            m_norm = str(mobo_ff).strip().upper()

            # Check direct or hierarchical fit
            is_fit = False
            if m_norm in supported:
                is_fit = True
            elif m_norm in ["MICRO-ATX", "MINI-ITX"] and ("ATX" in supported or "E-ATX" in supported):
                is_fit = True
            elif m_norm == "MINI-ITX" and "MICRO-ATX" in supported:
                is_fit = True
            elif m_norm == "ATX" and "E-ATX" in supported:
                is_fit = True

            if not is_fit:
                issues.append(
                    CompatibilityIssue(
                        type="case_form_factor_incompatible",
                        severity="error",
                        components=["motherboard", "pc-case"],
                        message=(
                            f"Case does not support {mobo_ff} motherboards "
                            f"(supported sizes: {case_mobo_support})."
                        ),
                    )
                )
        elif not case_mobo_support:
            warnings.append(
                CompatibilityIssue(
                    type="missing_case_support_data",
                    severity="warning",
                    components=["motherboard", "pc-case"],
                    message="Unknown / needs verification: Case motherboard support specifications missing.",
                )
            )

    return issues, warnings


def check_storage_compatibility(
    mobo: Product, storage: Product
) -> tuple[list[CompatibilityIssue], list[CompatibilityIssue]]:
    """H) Storage <-> Motherboard: M.2 and SATA interface checks."""
    issues: list[CompatibilityIssue] = []
    warnings: list[CompatibilityIssue] = []

    mobo_specs = mobo.specifications or {}
    storage_specs = storage.specifications or {}

    storage_type = str(storage_specs.get("type", "")).upper()
    storage_ff = str(storage_specs.get("form_factor", "")).upper()

    m2_slots = mobo_specs.get("m2_slots")
    sata_ports = mobo_specs.get("sata_ports")

    if "NVME" in storage_type or "M.2" in storage_ff:
        if m2_slots is not None and int(m2_slots) <= 0:
            issues.append(
                CompatibilityIssue(
                    type="no_m2_slots",
                    severity="error",
                    components=["storage", "motherboard"],
                    message="Motherboard has no M.2 slots available for the selected NVMe SSD.",
                )
            )
    elif "SATA" in storage_type or "2.5" in storage_ff:
        if sata_ports is not None and int(sata_ports) <= 0:
            issues.append(
                CompatibilityIssue(
                    type="no_sata_ports",
                    severity="error",
                    components=["storage", "motherboard"],
                    message="Motherboard has no SATA ports available for the selected SATA storage drive.",
                )
            )

    return issues, warnings


# ---------------------------------------------------------------------------
# CPU <-> GPU Recommendation & Scoring
# ---------------------------------------------------------------------------


def _calculate_cpu_tier(cpu: Product) -> int:
    specs = cpu.specifications or {}
    cores = _extract_number(specs.get("cores")) or 6
    name = cpu.name.upper()
    price = cpu.price

    if "7950X" in name or "14900K" in name or cores >= 16:
        return 5
    if "7800X3D" in name or "14700K" in name or (cores >= 8 and price >= Decimal("350")):
        return 4
    if "7700X" in name or "14600K" in name or cores >= 8 or price >= Decimal("250"):
        return 3
    if "7600X" in name or "5600X" in name or "13400F" in name or (cores == 6 and price >= Decimal("150")):
        return 2
    return 1


def _calculate_gpu_tier(gpu: Product) -> int:
    price = gpu.price
    name = gpu.name.upper()

    if "4090" in name or "4080" in name or price >= Decimal("1000"):
        return 5
    if "7900" in name or "4070 TI" in name or price >= Decimal("750"):
        return 4
    if "7800 XT" in name or "4070" in name or price >= Decimal("450"):
        return 3
    if "7600 XT" in name or "4060" in name or price >= Decimal("280"):
        return 2
    return 1


def check_gpu_cpu_recommendation(cpu: Product, gpu: Product) -> RecommendationItem:
    """D) CPU <-> GPU: Non-restrictive recommendation / pairing assessment."""
    cpu_tier = _calculate_cpu_tier(cpu)
    gpu_tier = _calculate_gpu_tier(gpu)
    tier_diff = gpu_tier - cpu_tier

    if abs(tier_diff) <= 1:
        match_level = "recommended"
        message = "Recommended match: well-balanced CPU and GPU pairing for gaming and general workloads."
    elif tier_diff == 2:
        match_level = "good match"
        message = "Good match: high-tier GPU; may experience slight CPU-limiting in some high-FPS 1080p workloads."
    elif tier_diff >= 3:
        match_level = "not ideal"
        message = "Not ideal: GPU significantly outpaces CPU and may be CPU-limited in CPU-intensive tasks."
    elif tier_diff == -2:
        match_level = "good match"
        message = "Good match: strong CPU with budget/mainstream GPU; ideal for CPU-heavy productivity."
    else:
        match_level = "not ideal"
        message = "Not ideal: entry-level GPU will limit gaming potential compared to high-end CPU capabilities."

    return RecommendationItem(
        type="cpu_gpu_pairing",
        category="gpu",
        match_level=match_level,
        message=message,
    )


# ---------------------------------------------------------------------------
# Price & Discount Calculation (authoritative server-side Decimal)
# ---------------------------------------------------------------------------


def calculate_build_price(
    products: list[Product],
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Calculate subtotal, discount_percent, discount_amount, and total.

    Returns: (subtotal, discount_percent, discount_amount, total)
    """
    subtotal = sum((p.price for p in products), Decimal("0.00"))

    # Check if all 8 core categories are present
    categories_present = {
        normalize_category_slug(p.category.slug)
        for p in products
        if p.category is not None
    }
    is_complete = CORE_BUILD_CATEGORIES.issubset(categories_present)

    if is_complete and products:
        discount_percent = Decimal("5")
        # 5% discount on the build subtotal
        discount_amount = (subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
        total = max(Decimal("0.00"), subtotal - discount_amount)
    else:
        discount_percent = Decimal("0")
        discount_amount = Decimal("0.00")
        total = subtotal

    return subtotal, discount_percent, discount_amount, total


def calculate_build_discount(
    products: list[Product],
) -> tuple[Decimal, Decimal, Decimal]:
    """Helper returning (subtotal, discount_amount, total)."""
    subtotal, _, discount_amount, total = calculate_build_price(products)
    return subtotal, discount_amount, total


# ---------------------------------------------------------------------------
# Validation & Options Service Functions
# ---------------------------------------------------------------------------


def _resolve_build_products(
    db: Session,
    components_map: dict[str, int] | None,
    product_ids: list[int] | None,
) -> tuple[dict[str, Product], list[CompatibilityIssue]]:
    """Load products from PostgreSQL and map them by normalized category slug."""
    issues: list[CompatibilityIssue] = []
    id_to_slot: dict[int, str] = {}
    requested_ids: set[int] = set()

    if components_map:
        for cat_raw, pid in components_map.items():
            cat = normalize_category_slug(cat_raw)
            if pid in id_to_slot.values():
                pass
            id_to_slot[pid] = cat
            requested_ids.add(pid)

    if product_ids:
        requested_ids.update(product_ids)

    if not requested_ids:
        return {}, issues

    stmt = (
        select(Product)
        .where(Product.id.in_(requested_ids))
        .options(joinedload(Product.category))
    )
    loaded_products = {p.id: p for p in db.scalars(stmt)}

    # Check for nonexistent product IDs
    missing_ids = requested_ids - set(loaded_products.keys())
    if missing_ids:
        issues.append(
            CompatibilityIssue(
                type="nonexistent_product",
                severity="error",
                components=[],
                message=f"Product IDs do not exist: {sorted(missing_ids)}",
            )
        )

    resolved_by_category: dict[str, Product] = {}
    duplicate_categories: set[str] = set()

    for pid in requested_ids:
        product = loaded_products.get(pid)
        if not product:
            continue
        category_slug = (
            id_to_slot.get(pid)
            or (normalize_category_slug(product.category.slug) if product.category else "unknown")
        )

        if category_slug in resolved_by_category and resolved_by_category[category_slug].id != product.id:
            duplicate_categories.add(category_slug)
        else:
            resolved_by_category[category_slug] = product

    if duplicate_categories:
        issues.append(
            CompatibilityIssue(
                type="duplicate_category",
                severity="error",
                components=list(duplicate_categories),
                message=f"Multiple conflicting products selected for category: {', '.join(sorted(duplicate_categories))}",
            )
        )

    return resolved_by_category, issues


def validate_build(
    db: Session,
    components_map: dict[str, int] | None = None,
    product_ids: list[int] | None = None,
) -> BuildValidationResponse:
    """Validate a build authoritatively against PostgreSQL data."""
    selected_products, resolution_issues = _resolve_build_products(
        db, components_map, product_ids
    )

    all_issues: list[CompatibilityIssue] = list(resolution_issues)
    all_warnings: list[CompatibilityIssue] = []
    recommendations: list[RecommendationItem] = []

    # Check active status & stock availability for each product
    for cat_slug, prod in selected_products.items():
        if not prod.is_active:
            all_issues.append(
                CompatibilityIssue(
                    type="inactive_product",
                    severity="error",
                    components=[cat_slug],
                    message=f"Product '{prod.name}' is inactive and cannot be included in a build.",
                )
            )
        if prod.stock <= 0:
            all_issues.append(
                CompatibilityIssue(
                    type="out_of_stock",
                    severity="error",
                    components=[cat_slug],
                    message=f"Product '{prod.name}' is out of stock.",
                )
            )

    cpu = selected_products.get("cpu")
    mobo = selected_products.get("motherboard")
    ram = selected_products.get("ram")
    gpu = selected_products.get("gpu")
    psu = selected_products.get("psu")
    case = selected_products.get("pc-case")
    cooler = selected_products.get("cooler")
    storage = selected_products.get("storage")

    # A) CPU <-> Motherboard
    if cpu and mobo:
        iss, wrn = check_cpu_motherboard_compatibility(cpu, mobo)
        all_issues.extend(iss)
        all_warnings.extend(wrn)

    # B) Motherboard <-> RAM
    if mobo and ram:
        iss, wrn = check_motherboard_ram_compatibility(mobo, ram)
        all_issues.extend(iss)
        all_warnings.extend(wrn)

    # C) CPU <-> RAM
    if cpu and ram:
        iss, wrn = check_cpu_ram_compatibility(cpu, ram)
        all_issues.extend(iss)
        all_warnings.extend(wrn)

    # D) CPU <-> GPU recommendation
    if cpu and gpu:
        rec = check_gpu_cpu_recommendation(cpu, gpu)
        recommendations.append(rec)

    # E) GPU/CPU <-> PSU
    if psu:
        iss, wrn = check_psu_requirement(gpu, cpu, psu)
        all_issues.extend(iss)
        all_warnings.extend(wrn)

    # F) Motherboard <-> Case
    if case:
        iss, wrn = check_case_compatibility(mobo, case, gpu, cooler)
        all_issues.extend(iss)
        all_warnings.extend(wrn)

    # G) Cooler <-> CPU
    if cpu and cooler:
        iss, wrn = check_cooler_compatibility(cpu, cooler)
        all_issues.extend(iss)
        all_warnings.extend(wrn)

    # H) Storage <-> Motherboard
    if mobo and storage:
        iss, wrn = check_storage_compatibility(mobo, storage)
        all_issues.extend(iss)
        all_warnings.extend(wrn)

    # Completeness check: all 8 core categories present
    categories_present = set(selected_products.keys())
    complete = CORE_BUILD_CATEGORIES.issubset(categories_present)
    compatible = len(all_issues) == 0

    product_list = list(selected_products.values())
    subtotal, discount_percent, discount_amount, total = calculate_build_price(product_list)

    # Build brief representations
    brief_map = {
        cat: BuilderProductBrief(
            id=p.id,
            name=p.name,
            slug=p.slug,
            brand=p.brand,
            price=p.price,
            stock=p.stock,
            category_slug=cat,
            image_url=p.image_url,
            specifications=p.specifications,
        )
        for cat, p in selected_products.items()
    }

    return BuildValidationResponse(
        compatible=compatible,
        complete=complete,
        issues=all_issues,
        warnings=all_warnings,
        recommendations=recommendations,
        selected_products=brief_map,
        subtotal=subtotal,
        discount_percent=discount_percent,
        discount_amount=discount_amount,
        total=total,
    )


def get_gpu_recommendations(db: Session, cpu_id: int) -> list[GPURecommendation]:
    """Rank and recommend available GPUs for a given CPU."""
    cpu = db.get(Product, cpu_id)
    if not cpu or not cpu.is_active:
        raise NotFoundError("CPU product not found")

    # Fetch active GPUs
    gpu_cat = db.scalar(select(Category).where(Category.slug == "gpu"))
    if not gpu_cat:
        return []

    stmt = (
        select(Product)
        .where(Product.category_id == gpu_cat.id, Product.is_active.is_(True))
        .order_by(Product.price.asc())
    )
    gpus = list(db.scalars(stmt))

    cpu_tier = _calculate_cpu_tier(cpu)
    recommendations: list[GPURecommendation] = []

    for gpu in gpus:
        gpu_tier = _calculate_gpu_tier(gpu)
        tier_diff = gpu_tier - cpu_tier
        rec_item = check_gpu_cpu_recommendation(cpu, gpu)

        # Score calculation: 100 base minus tier delta penalty
        score = 100 - abs(tier_diff) * 20
        if gpu.stock <= 0:
            score -= 30
        score = max(10, min(100, score))

        recommendations.append(
            GPURecommendation(
                product_id=gpu.id,
                name=gpu.name,
                brand=gpu.brand,
                price=gpu.price,
                stock=gpu.stock,
                score=score,
                match_level=rec_item.match_level,
                reason=rec_item.message,
                specifications=gpu.specifications,
            )
        )

    # Sort descending by score, then price
    recommendations.sort(key=lambda r: (-r.score, r.price))
    return recommendations


def get_builder_options(
    db: Session, category_slug: str | None = None
) -> BuilderOptionsResponse:
    """Return active, stocked/all active products organized by build category."""
    categories_query = select(Category)
    if category_slug:
        norm_slug = normalize_category_slug(category_slug)
        categories_query = categories_query.where(Category.slug == norm_slug)

    categories = list(db.scalars(categories_query))
    cat_ids = [c.id for c in categories]

    stmt = (
        select(Product)
        .where(Product.category_id.in_(cat_ids), Product.is_active.is_(True))
        .options(joinedload(Product.category))
        .order_by(Product.price.asc())
    )
    products = list(db.scalars(stmt))

    options: dict[str, list[BuilderProductBrief]] = {}
    for c in categories:
        norm_cat = normalize_category_slug(c.slug)
        options[norm_cat] = []

    for p in products:
        if not p.category:
            continue
        norm_cat = normalize_category_slug(p.category.slug)
        if norm_cat not in options:
            options[norm_cat] = []
        options[norm_cat].append(
            BuilderProductBrief(
                id=p.id,
                name=p.name,
                slug=p.slug,
                brand=p.brand,
                price=p.price,
                stock=p.stock,
                category_slug=norm_cat,
                image_url=p.image_url,
                specifications=p.specifications,
            )
        )

    return BuilderOptionsResponse(
        categories=sorted(options.keys()),
        options=options,
    )


def add_build_to_cart(
    db: Session,
    user: User,
    components_map: dict[str, int] | None = None,
    product_ids: list[int] | None = None,
    clear_existing: bool = False,
) -> Cart:
    """Validate build and add components to the user's cart under transaction locks."""
    validation = validate_build(db, components_map, product_ids)
    if not validation.compatible:
        err_msgs = "; ".join(issue.message for issue in validation.issues)
        raise BadRequestError(f"Cannot add incompatible build to cart: {err_msgs}")

    if clear_existing:
        cart_service.clear_cart(db, user)

    # Add each component to cart safely via cart_service.add_item
    for brief in validation.selected_products.values():
        cart_service.add_item(db, user, product_id=brief.id, quantity=1)

    return cart_service.get_cart(db, user)
