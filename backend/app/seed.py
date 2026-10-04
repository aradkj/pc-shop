"""Development seed data.

    python -m app.seed

Creates 1 admin, 3 customers, 5 categories, 20 products and a few sample orders.
It is idempotent (existing records are left untouched) and refuses to run when
APP_ENV=production. Passwords come from SEED_ADMIN_PASSWORD / SEED_CUSTOMER_PASSWORD
(see .env.example) - they are for local development only.
"""

import logging
import os
import sys
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.logging_config import configure_logging
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.category import Category
from app.models.order import Order, OrderStatus
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User, UserRole
from app.services import order_service

logger = logging.getLogger("app.seed")

CATEGORIES = [
    ("Graphics Cards", "graphics-cards", "GPUs for smooth 1080p, 1440p and 4K gaming and creative work."),
    ("Processors", "processors", "Desktop CPUs from AMD and Intel for gaming and productivity."),
    ("Memory", "memory", "DDR4 and DDR5 RAM kits for every build."),
    ("Storage", "storage", "NVMe and SATA SSDs for fast boots and short load times."),
    ("Gaming Accessories", "gaming-accessories", "Mice, keyboards, headsets and desk gear."),
]

# (slug, name, category slug, brand, price, stock, description[, is_active])
PRODUCTS = [
    ("asus-dual-rtx-4070-super-12gb", "ASUS Dual GeForce RTX 4070 Super 12GB", "graphics-cards", "ASUS", "599.99", 14,
     "Compact 2.5-slot design with 12GB GDDR6X, DLSS 3 and ray tracing. A great fit for 1440p high-refresh gaming."),
    ("msi-rtx-4080-super-16gb-gaming-x-slim", "MSI GeForce RTX 4080 Super 16GB Gaming X Slim", "graphics-cards", "MSI", "1049.99", 6,
     "16GB GDDR6X, tri-fan cooling and a slim shroud. Built for 4K gaming and heavy creative workloads."),
    ("sapphire-pulse-rx-7800-xt-16gb", "Sapphire Pulse Radeon RX 7800 XT 16GB", "graphics-cards", "Sapphire", "489.99", 9,
     "16GB GDDR6 with RDNA 3 efficiency and quiet dual-fan cooling. Excellent 1440p value."),
    ("gigabyte-rtx-4060-eagle-oc-8gb", "Gigabyte GeForce RTX 4060 Eagle OC 8GB", "graphics-cards", "Gigabyte", "299.99", 0,
     "Efficient 8GB card with DLSS 3 and a factory overclock. Perfect for 1080p gaming."),
    ("amd-ryzen-7-7800x3d", "AMD Ryzen 7 7800X3D", "processors", "AMD", "399.00", 18,
     "8 cores, 16 threads and 3D V-Cache technology. One of the fastest gaming CPUs on the AM5 platform."),
    ("amd-ryzen-5-7600x", "AMD Ryzen 5 7600X", "processors", "AMD", "229.00", 25,
     "6 cores, 12 threads, up to 5.3GHz boost. A fast and affordable entry to AM5."),
    ("intel-core-i7-14700k", "Intel Core i7-14700K", "processors", "Intel", "389.99", 11,
     "20 cores (8P + 12E) and up to 5.6GHz. Strong all-rounder for gaming and content creation."),
    ("intel-core-i5-14600k", "Intel Core i5-14600K", "processors", "Intel", "279.99", 3,
     "14 cores (6P + 8E), unlocked for overclocking. Great mid-range gaming performance."),
    ("corsair-vengeance-rgb-32gb-ddr5-6000", "Corsair Vengeance RGB 32GB (2x16GB) DDR5-6000", "memory", "Corsair", "129.99", 40,
     "Dual-channel DDR5-6000 CL36 kit with dynamic RGB lighting and Intel XMP 3.0 / AMD EXPO profiles."),
    ("gskill-trident-z5-rgb-32gb-ddr5-6400", "G.SKILL Trident Z5 RGB 32GB (2x16GB) DDR5-6400", "memory", "G.SKILL", "149.99", 22,
     "High-speed DDR5-6400 CL32 kit with a brushed-aluminium heatspreader and addressable RGB."),
    ("kingston-fury-beast-16gb-ddr4-3200", "Kingston FURY Beast 16GB (2x8GB) DDR4-3200", "memory", "Kingston", "49.99", 60,
     "Reliable plug-and-play DDR4-3200 CL16 kit. The easy way to upgrade an existing system."),
    ("samsung-990-pro-2tb-nvme", "Samsung 990 PRO 2TB NVMe SSD", "storage", "Samsung", "169.99", 20,
     "PCIe 4.0 NVMe with up to 7,450MB/s reads. Top-tier performance for gaming and workstations."),
    ("wd-black-sn850x-1tb-nvme", "WD_BLACK SN850X 1TB NVMe SSD", "storage", "Western Digital", "89.99", 35,
     "PCIe 4.0 NVMe built for gaming, with up to 7,300MB/s reads and Game Mode 2.0."),
    ("crucial-mx500-1tb-sata", "Crucial MX500 1TB SATA SSD", "storage", "Crucial", "64.99", 48,
     "2.5-inch SATA SSD with dependable performance and a 5-year warranty. Ideal for older systems."),
    ("seagate-firecuda-530-2tb-nvme", "Seagate FireCuda 530 2TB NVMe SSD", "storage", "Seagate", "179.99", 8,
     "PCIe 4.0 NVMe with up to 7,300MB/s reads and very high endurance for sustained workloads."),
    ("logitech-g-pro-x-superlight-2", "Logitech G PRO X SUPERLIGHT 2 Wireless Mouse", "gaming-accessories", "Logitech", "159.99", 30,
     "Ultra-light 60g wireless esports mouse with the HERO 2 sensor (up to 32,000 DPI) and 95 hours of battery."),
    ("razer-blackwidow-v4-pro", "Razer BlackWidow V4 Pro Mechanical Keyboard", "gaming-accessories", "Razer", "229.99", 12,
     "Full-size mechanical keyboard with Green switches, magnetic wrist rest, dedicated macro keys and Chroma RGB."),
    ("steelseries-arctis-nova-7-wireless", "SteelSeries Arctis Nova 7 Wireless Headset", "gaming-accessories", "SteelSeries", "179.99", 16,
     "2.4GHz and Bluetooth multi-system headset with 38 hours of battery and a retractable noise-cancelling mic."),
    ("hyperx-quadcast-s-usb-microphone", "HyperX QuadCast S USB Microphone", "gaming-accessories", "HyperX", "139.99", 10,
     "Plug-and-play USB condenser microphone with four polar patterns, tap-to-mute and RGB lighting."),
    ("corsair-mm700-rgb-extended-mouse-pad", "Corsair MM700 RGB Extended Mouse Pad", "gaming-accessories", "Corsair", "59.99", 27,
     "Extended cloth mouse pad with tri-zone RGB lighting and USB pass-through. Discontinued.", False),
]

CUSTOMERS = [
    ("alice@example.com", "alice", "Alice", "Johnson"),
    ("bob@example.com", "bob", "Bob", "Smith"),
    ("carol@example.com", "carol", "Carol", "Davis"),
]

# (customer username, [(product slug, quantity), ...], final status)
SAMPLE_ORDERS = [
    ("alice", [("asus-dual-rtx-4070-super-12gb", 1), ("corsair-vengeance-rgb-32gb-ddr5-6000", 2)], OrderStatus.COMPLETED),
    ("alice", [("samsung-990-pro-2tb-nvme", 1), ("logitech-g-pro-x-superlight-2", 1)], OrderStatus.PENDING),
    ("bob", [("amd-ryzen-7-7800x3d", 1), ("wd-black-sn850x-1tb-nvme", 1)], OrderStatus.SHIPPED),
    ("carol", [("kingston-fury-beast-16gb-ddr4-3200", 2)], OrderStatus.PROCESSING),
]


def seed_categories(db: Session) -> dict[str, Category]:
    categories: dict[str, Category] = {}
    for name, slug, description in CATEGORIES:
        category = db.scalar(select(Category).where(Category.slug == slug))
        if category is None:
            category = Category(name=name, slug=slug, description=description)
            db.add(category)
            logger.info("Created category: %s", name)
        categories[slug] = category
    db.commit()
    return categories


def seed_products(db: Session, categories: dict[str, Category]) -> dict[str, Product]:
    products: dict[str, Product] = {}
    for slug, name, category_slug, brand, price, stock, description, *rest in PRODUCTS:
        product = db.scalar(select(Product).where(Product.slug == slug))
        if product is None:
            product = Product(
                slug=slug,
                name=name,
                description=description,
                price=Decimal(price),
                stock=stock,
                brand=brand,
                image_url=f"/img/products/{slug}.svg",
                category_id=categories[category_slug].id,
                is_active=rest[0] if rest else True,
            )
            db.add(product)
            logger.info("Created product: %s", name)
        products[slug] = product
    db.commit()
    return products


def seed_users(db: Session, admin_password: str, customer_password: str) -> dict[str, User]:
    wanted = [("admin@example.com", "admin", "Arad", "Admin", UserRole.ADMIN, admin_password)]
    wanted += [(email, username, first, last, UserRole.CUSTOMER, customer_password) for email, username, first, last in CUSTOMERS]

    users: dict[str, User] = {}
    for email, username, first_name, last_name, role, password in wanted:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                username=username,
                hashed_password=hash_password(password),
                first_name=first_name,
                last_name=last_name,
                role=role,
            )
            db.add(user)
            logger.info("Created %s: %s", role.value, email)
        users[username] = user
    db.commit()
    return users


def _advance_order_status(db: Session, order_id: int, target: OrderStatus) -> None:
    order = db.get(Order, order_id)
    if not order or order.status == target:
        return
    if order.status == OrderStatus.PENDING:
        if target == OrderStatus.CANCELLED:
            order_service.update_order_status(db, order_id, OrderStatus.CANCELLED)
            return
        order_service.update_order_status(db, order_id, OrderStatus.PROCESSING)
        order = db.get(Order, order_id)
    if order and order.status == OrderStatus.PROCESSING:
        if target == OrderStatus.CANCELLED:
            order_service.update_order_status(db, order_id, OrderStatus.CANCELLED)
            return
        if target in (OrderStatus.SHIPPED, OrderStatus.COMPLETED):
            order_service.update_order_status(db, order_id, OrderStatus.SHIPPED)
            order = db.get(Order, order_id)
    if order and order.status == OrderStatus.SHIPPED:
        if target == OrderStatus.COMPLETED:
            order_service.update_order_status(db, order_id, OrderStatus.COMPLETED)


def seed_orders(db: Session, users: dict[str, User], products: dict[str, Product]) -> None:
    """Create sample orders with deterministic identifiers.

    This function is idempotent and partial-failure safe:
    - Existing orders are left untouched (status and items repaired if needed).
    - Missing orders are recreated with deterministic markers in AuditLog tracking
      that inventory was deducted, preventing double-decrement of inventory.
    - Each order + its items + inventory mutation + deterministic marker happen in one transaction.
    """
    for idx, (username, lines, final_status) in enumerate(SAMPLE_ORDERS, start=1):
        order_num = f"SEED-ORD-{idx:04d}"

        # Check whether inventory decrement was already recorded/applied for this deterministic seed order
        marker = db.scalar(
            select(AuditLog).where(
                AuditLog.entity_type == "seed_order",
                AuditLog.entity_id == order_num,
                AuditLog.action == "seed_inventory_applied",
            )
        )
        already_applied = marker is not None

        existing_order = db.scalar(select(Order).where(Order.order_number == order_num))
        if existing_order is not None:
            # Repair any missing items if partial failure corrupted them
            existing_product_ids = {item.product_id for item in existing_order.items}
            items_repaired = False
            for slug, quantity in lines:
                product = products[slug]
                if product.id not in existing_product_ids:
                    subtotal = product.price * quantity
                    existing_order.items.append(
                        OrderItem(
                            product_id=product.id,
                            product_name=product.name,
                            unit_price=product.price,
                            quantity=quantity,
                            subtotal=subtotal,
                        )
                    )
                    items_repaired = True
            if items_repaired:
                existing_order.total_price = sum(item.subtotal for item in existing_order.items)
            if existing_order.status != final_status:
                _advance_order_status(db, existing_order.id, final_status)
            if not already_applied:
                db.add(
                    AuditLog(
                        entity_type="seed_order",
                        entity_id=order_num,
                        action="seed_inventory_applied",
                        new_value={"order_number": order_num, "status": existing_order.status.value},
                    )
                )
            db.commit()
            continue

        # Build the order directly within a single transaction
        try:
            user = users[username]
            total = Decimal("0.00")
            order_items: list[OrderItem] = []

            for slug, quantity in lines:
                product = products[slug]
                subtotal = product.price * quantity
                order_items.append(
                    OrderItem(
                        product_id=product.id,
                        product_name=product.name,
                        unit_price=product.price,
                        quantity=quantity,
                        subtotal=subtotal,
                    )
                )
                # Only decrement inventory if this seed order's inventory change has not yet been applied
                if not already_applied:
                    if product.stock < quantity:
                        raise ValueError(f"Insufficient stock to seed {product.name}")
                    product.stock -= quantity

                total += subtotal

            order = Order(
                user_id=user.id,
                order_number=order_num,
                status=OrderStatus.PENDING,
                total_price=total,
                items=order_items,
            )
            db.add(order)
            if not already_applied:
                db.add(
                    AuditLog(
                        entity_type="seed_order",
                        entity_id=order_num,
                        action="seed_inventory_applied",
                        new_value={"order_number": order_num, "status": final_status.value},
                    )
                )
            db.flush()
            _advance_order_status(db, order.id, final_status)
            db.commit()
        except Exception:
            db.rollback()
            raise
        logger.info("Created sample order %s (#%s) for %s (%s)", order_num, order.id, username, final_status.value)



def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)

    if settings.is_production:
        logger.error("Refusing to seed development data when APP_ENV=production")
        return 1
    admin_password = os.getenv("SEED_ADMIN_PASSWORD", "")
    customer_password = os.getenv("SEED_CUSTOMER_PASSWORD", "")
    if not admin_password or not customer_password:
        logger.error("Set SEED_ADMIN_PASSWORD and SEED_CUSTOMER_PASSWORD (see .env.example)")
        return 1

    with SessionLocal() as db:
        categories = seed_categories(db)
        products = seed_products(db, categories)
        users = seed_users(db, admin_password, customer_password)
        seed_orders(db, users, products)
    logger.info("Seed complete: admin@example.com + %d customers, %d categories, %d products", len(CUSTOMERS), len(CATEGORIES), len(PRODUCTS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
