"""Development seed data.

    python -m app.seed

Creates 1 admin, 3 customers, 8 categories, 80 products and sample orders.
It is idempotent (existing records are left untouched or updated) and refuses to run when
APP_ENV=production. Passwords come from SEED_ADMIN_PASSWORD / SEED_CUSTOMER_PASSWORD
(see .env.example) - they are for local development only.
"""

import logging
import os
import sys
from decimal import Decimal

from sqlalchemy import func, select
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
    ("CPU", "cpu", "Desktop processors from AMD and Intel for gaming, creation, and multitasking."),
    ("GPU", "gpu", "Graphics cards from NVIDIA, AMD, and Intel for high-framerate gaming and 3D rendering."),
    ("RAM", "ram", "High-performance DDR4 and DDR5 desktop memory kits with low latency."),
    ("Motherboard", "motherboard", "AMD AM4/AM5 and Intel LGA1700 motherboards with modern connectivity."),
    ("Storage", "storage", "High-speed PCIe 4.0/5.0 NVMe M.2 SSDs and reliable SATA solid state drives."),
    ("PSU", "psu", "Efficient ATX power supplies with 80 PLUS Gold and Platinum certifications."),
    ("PC Case", "pc-case", "Premium mid-tower and full-tower computer chassis with optimal airflow."),
    ("Cooler", "cooler", "High-efficiency air coolers and all-in-one (AIO) liquid coolers."),
]

# (slug, name, category slug, brand, price, stock, description, specifications[, is_active])
PRODUCTS = [
    # ------------------------------------------------------------------ CPU (10)
    (
        "amd-ryzen-5-5600x",
        "AMD Ryzen 5 5600X",
        "cpu",
        "AMD",
        "139.99",
        28,
        "6-core, 12-thread AM4 desktop processor with Zen 3 architecture, perfect for budget gaming builds.",
        {
            "manufacturer": "AMD",
            "model": "Ryzen 5 5600X",
            "socket": "AM4",
            "architecture": "Zen 3",
            "cores": 6,
            "threads": 12,
            "base_clock": "3.7 GHz",
            "boost_clock": "4.6 GHz",
            "tdp": "65W",
            "integrated_graphics": False,
            "memory_support": "DDR4-3200",
        },
    ),
    (
        "amd-ryzen-5-7600x",
        "AMD Ryzen 5 7600X",
        "cpu",
        "AMD",
        "219.99",
        25,
        "6-core, 12-thread AM5 processor offering high clock speeds and PCIe 5.0 support for modern gaming rigs.",
        {
            "manufacturer": "AMD",
            "model": "Ryzen 5 7600X",
            "socket": "AM5",
            "architecture": "Zen 4",
            "cores": 6,
            "threads": 12,
            "base_clock": "4.7 GHz",
            "boost_clock": "5.3 GHz",
            "tdp": "105W",
            "integrated_graphics": True,
            "memory_support": "DDR5-5200",
        },
    ),
    (
        "amd-ryzen-7-7700x",
        "AMD Ryzen 7 7700X",
        "cpu",
        "AMD",
        "299.99",
        18,
        "8-core, 16-thread desktop CPU balancing fast gaming responsiveness with powerful multitasking productivity.",
        {
            "manufacturer": "AMD",
            "model": "Ryzen 7 7700X",
            "socket": "AM5",
            "architecture": "Zen 4",
            "cores": 8,
            "threads": 16,
            "base_clock": "4.5 GHz",
            "boost_clock": "5.4 GHz",
            "tdp": "105W",
            "integrated_graphics": True,
            "memory_support": "DDR5-5200",
        },
    ),
    (
        "amd-ryzen-7-7800x3d",
        "AMD Ryzen 7 7800X3D",
        "cpu",
        "AMD",
        "399.00",
        18,
        "Premier 8-core gaming processor equipped with AMD 3D V-Cache technology for class-leading gaming performance.",
        {
            "manufacturer": "AMD",
            "model": "Ryzen 7 7800X3D",
            "socket": "AM5",
            "architecture": "Zen 4",
            "cores": 8,
            "threads": 16,
            "base_clock": "4.2 GHz",
            "boost_clock": "5.0 GHz",
            "tdp": "120W",
            "integrated_graphics": True,
            "memory_support": "DDR5-5200",
        },
    ),
    (
        "amd-ryzen-9-7950x",
        "AMD Ryzen 9 7950X",
        "cpu",
        "AMD",
        "549.99",
        10,
        "Flagship 16-core, 32-thread workstation-grade AM5 processor engineered for heavy video editing, 3D rendering, and compilation.",
        {
            "manufacturer": "AMD",
            "model": "Ryzen 9 7950X",
            "socket": "AM5",
            "architecture": "Zen 4",
            "cores": 16,
            "threads": 32,
            "base_clock": "4.5 GHz",
            "boost_clock": "5.7 GHz",
            "tdp": "170W",
            "integrated_graphics": True,
            "memory_support": "DDR5-5200",
        },
    ),
    (
        "intel-core-i3-13100f",
        "Intel Core i3-13100F",
        "cpu",
        "Intel",
        "89.99",
        35,
        "Entry-level 4-core, 8-thread LGA1700 desktop processor delivering great value for budget 1080p gaming systems.",
        {
            "manufacturer": "Intel",
            "model": "Core i3-13100F",
            "socket": "LGA1700",
            "architecture": "Raptor Lake",
            "cores": 4,
            "threads": 8,
            "base_clock": "3.4 GHz",
            "boost_clock": "4.5 GHz",
            "tdp": "58W",
            "integrated_graphics": False,
            "memory_support": "DDR4-3200 / DDR5-4800",
        },
    ),
    (
        "intel-core-i5-13400f",
        "Intel Core i5-13400F",
        "cpu",
        "Intel",
        "184.99",
        26,
        "10-core hybrid CPU (6 Performance + 4 Efficient cores) for smooth mainstream gaming and content creation.",
        {
            "manufacturer": "Intel",
            "model": "Core i5-13400F",
            "socket": "LGA1700",
            "architecture": "Raptor Lake",
            "cores": 10,
            "threads": 16,
            "base_clock": "2.5 GHz",
            "boost_clock": "4.6 GHz",
            "tdp": "65W",
            "integrated_graphics": False,
            "memory_support": "DDR4-3200 / DDR5-4800",
        },
    ),
    (
        "intel-core-i5-14600k",
        "Intel Core i5-14600K",
        "cpu",
        "Intel",
        "289.99",
        16,
        "14-core unlocked desktop processor featuring 6 P-cores and 8 E-cores with boost speeds up to 5.3 GHz.",
        {
            "manufacturer": "Intel",
            "model": "Core i5-14600K",
            "socket": "LGA1700",
            "architecture": "Raptor Lake Refresh",
            "cores": 14,
            "threads": 20,
            "base_clock": "3.5 GHz",
            "boost_clock": "5.3 GHz",
            "tdp": "125W",
            "integrated_graphics": True,
            "memory_support": "DDR4-3200 / DDR5-5600",
        },
    ),
    (
        "intel-core-i7-14700k",
        "Intel Core i7-14700K",
        "cpu",
        "Intel",
        "389.99",
        14,
        "20-core unlocked desktop CPU (8P + 12E cores) capable of 5.6 GHz boost, ideal for intensive gaming and professional workflows.",
        {
            "manufacturer": "Intel",
            "model": "Core i7-14700K",
            "socket": "LGA1700",
            "architecture": "Raptor Lake Refresh",
            "cores": 20,
            "threads": 28,
            "base_clock": "3.4 GHz",
            "boost_clock": "5.6 GHz",
            "tdp": "125W",
            "integrated_graphics": True,
            "memory_support": "DDR4-3200 / DDR5-5600",
        },
    ),
    (
        "intel-core-i9-14900k",
        "Intel Core i9-14900K",
        "cpu",
        "Intel",
        "549.00",
        8,
        "Top-tier 24-core unlocked desktop CPU with Intel Thermal Velocity Boost up to 6.0 GHz for enthusiast systems.",
        {
            "manufacturer": "Intel",
            "model": "Core i9-14900K",
            "socket": "LGA1700",
            "architecture": "Raptor Lake Refresh",
            "cores": 24,
            "threads": 32,
            "base_clock": "3.2 GHz",
            "boost_clock": "6.0 GHz",
            "tdp": "125W",
            "integrated_graphics": True,
            "memory_support": "DDR4-3200 / DDR5-5600",
        },
    ),
    # ------------------------------------------------------------------ GPU (10)
    (
        "asrock-challenger-arc-a580-8gb",
        "ASRock Challenger Intel Arc A580 8GB",
        "gpu",
        "ASRock",
        "199.99",
        20,
        "Affordable 8GB graphics card with hardware-accelerated ray tracing and AV1 encoding for 1080p gaming.",
        {
            "gpu_model": "Intel Arc A580",
            "vram": "8GB",
            "memory_type": "GDDR6",
            "memory_bus": "256-bit",
            "boost_clock": "2000 MHz",
            "power_consumption": "185W",
            "recommended_psu": "550W",
            "interface": "PCIe 4.0 x16",
        },
    ),
    (
        "powercolor-fighter-rx-6600-8gb",
        "PowerColor Fighter Radeon RX 6600 8GB",
        "gpu",
        "PowerColor",
        "219.99",
        28,
        "High-efficiency 8GB graphics card offering reliable 1080p performance on high settings with low power draw.",
        {
            "gpu_model": "AMD Radeon RX 6600",
            "vram": "8GB",
            "memory_type": "GDDR6",
            "memory_bus": "128-bit",
            "boost_clock": "2491 MHz",
            "power_consumption": "132W",
            "recommended_psu": "450W",
            "interface": "PCIe 4.0 x8",
        },
    ),
    (
        "gigabyte-geforce-rtx-4060-windforce-oc-8gb",
        "Gigabyte GeForce RTX 4060 Windforce OC 8GB",
        "gpu",
        "Gigabyte",
        "299.99",
        25,
        "Compact dual-fan graphics card featuring DLSS 3 frame generation and 3rd gen ray tracing for smooth 1080p gaming.",
        {
            "gpu_model": "NVIDIA GeForce RTX 4060",
            "vram": "8GB",
            "memory_type": "GDDR6",
            "memory_bus": "128-bit",
            "boost_clock": "2475 MHz",
            "power_consumption": "115W",
            "recommended_psu": "450W",
            "interface": "PCIe 4.0 x8",
        },
    ),
    (
        "sapphire-pulse-rx-7600-xt-16gb",
        "Sapphire Pulse Radeon RX 7600 XT 16GB",
        "gpu",
        "Sapphire",
        "329.99",
        18,
        "Generous 16GB VRAM buffer on RDNA 3 architecture, handling high texture settings and video creation smoothly.",
        {
            "gpu_model": "AMD Radeon RX 7600 XT",
            "vram": "16GB",
            "memory_type": "GDDR6",
            "memory_bus": "128-bit",
            "boost_clock": "2755 MHz",
            "power_consumption": "190W",
            "recommended_psu": "600W",
            "interface": "PCIe 4.0 x8",
        },
    ),
    (
        "xfx-speedster-qick-319-rx-7800-xt-16gb",
        "XFX Speedster QICK 319 Radeon RX 7800 XT 16GB",
        "gpu",
        "XFX",
        "499.99",
        15,
        "Triple-fan cooled 16GB graphics card engineered for ultra-smooth 1440p high-refresh rate gaming.",
        {
            "gpu_model": "AMD Radeon RX 7800 XT",
            "vram": "16GB",
            "memory_type": "GDDR6",
            "memory_bus": "256-bit",
            "boost_clock": "2430 MHz",
            "power_consumption": "263W",
            "recommended_psu": "700W",
            "interface": "PCIe 4.0 x16",
        },
    ),
    (
        "asus-dual-geforce-rtx-4070-super-12gb",
        "ASUS Dual GeForce RTX 4070 Super 12GB",
        "gpu",
        "ASUS",
        "599.99",
        14,
        "Compact 2.56-slot card with 12GB GDDR6X, DLSS 3.5, and dual axial-tech fans for excellent 1440p gaming.",
        {
            "gpu_model": "NVIDIA GeForce RTX 4070 Super",
            "vram": "12GB",
            "memory_type": "GDDR6X",
            "memory_bus": "192-bit",
            "boost_clock": "2505 MHz",
            "power_consumption": "220W",
            "recommended_psu": "650W",
            "interface": "PCIe 4.0 x16",
        },
    ),
    (
        "sapphire-nitro-plus-rx-7900-gre-16gb",
        "Sapphire NITRO+ Radeon RX 7900 GRE 16GB",
        "gpu",
        "Sapphire",
        "579.99",
        12,
        "Premium overclocked 16GB RDNA 3 card with vapor chamber cooling for 1440p and entry 4K gaming.",
        {
            "gpu_model": "AMD Radeon RX 7900 GRE",
            "vram": "16GB",
            "memory_type": "GDDR6",
            "memory_bus": "256-bit",
            "boost_clock": "2391 MHz",
            "power_consumption": "260W",
            "recommended_psu": "700W",
            "interface": "PCIe 4.0 x16",
        },
    ),
    (
        "msi-geforce-rtx-4070-ti-super-16gb-ventus-3x",
        "MSI GeForce RTX 4070 Ti Super 16GB Ventus 3X",
        "gpu",
        "MSI",
        "799.99",
        11,
        "High-performance 16GB GDDR6X GPU on a 256-bit bus, excelling in 1440p ultra and 4K DLSS gaming.",
        {
            "gpu_model": "NVIDIA GeForce RTX 4070 Ti Super",
            "vram": "16GB",
            "memory_type": "GDDR6X",
            "memory_bus": "256-bit",
            "boost_clock": "2655 MHz",
            "power_consumption": "285W",
            "recommended_psu": "700W",
            "interface": "PCIe 4.0 x16",
        },
    ),
    (
        "asus-tuf-geforce-rtx-4080-super-16gb",
        "ASUS TUF Gaming GeForce RTX 4080 Super 16GB",
        "gpu",
        "ASUS",
        "999.99",
        7,
        "Heavy-duty 16GB GDDR6X graphics card with all-metal shroud, military-grade capacitors, and 4K dominance.",
        {
            "gpu_model": "NVIDIA GeForce RTX 4080 Super",
            "vram": "16GB",
            "memory_type": "GDDR6X",
            "memory_bus": "256-bit",
            "boost_clock": "2580 MHz",
            "power_consumption": "320W",
            "recommended_psu": "750W",
            "interface": "PCIe 4.0 x16",
        },
    ),
    (
        "msi-geforce-rtx-4090-gaming-x-trio-24gb",
        "MSI GeForce RTX 4090 Gaming X Trio 24GB",
        "gpu",
        "MSI",
        "1749.99",
        5,
        "Ultimate consumer GPU with 24GB GDDR6X VRAM, delivering uncompromised 4K ray tracing and generative AI compute.",
        {
            "gpu_model": "NVIDIA GeForce RTX 4090",
            "vram": "24GB",
            "memory_type": "GDDR6X",
            "memory_bus": "384-bit",
            "boost_clock": "2595 MHz",
            "power_consumption": "450W",
            "recommended_psu": "850W",
            "interface": "PCIe 4.0 x16",
        },
    ),
    # ------------------------------------------------------------------ RAM (10)
    (
        "kingston-fury-beast-16gb-ddr4-3200",
        "Kingston FURY Beast 16GB (2x8GB) DDR4-3200",
        "ram",
        "Kingston",
        "42.99",
        45,
        "Reliable plug-and-play DDR4 memory kit with low-profile heatspreader for mainstream gaming PCs.",
        {
            "memory_type": "DDR4",
            "capacity": "16GB",
            "module_configuration": "2x8GB",
            "speed": "DDR4-3200",
            "latency": "CL16-20-20",
            "voltage": "1.35V",
            "form_factor": "288-pin DIMM",
        },
    ),
    (
        "teamgroup-t-force-vulcan-z-32gb-ddr4-3200",
        "TeamGroup T-Force Vulcan Z 32GB (2x16GB) DDR4-3200",
        "ram",
        "TeamGroup",
        "59.99",
        36,
        "Reinforced aluminum heatspreader DDR4-3200 CL16 dual-channel kit optimized for stability and gaming.",
        {
            "memory_type": "DDR4",
            "capacity": "32GB",
            "module_configuration": "2x16GB",
            "speed": "DDR4-3200",
            "latency": "CL16-20-20",
            "voltage": "1.35V",
            "form_factor": "288-pin DIMM",
        },
    ),
    (
        "corsair-vengeance-lpx-32gb-ddr4-3600",
        "Corsair Vengeance LPX 32GB (2x16GB) DDR4-3600",
        "ram",
        "Corsair",
        "74.99",
        32,
        "Pure aluminum heat spreader designed for high-performance overclocking and broad motherboard compatibility.",
        {
            "memory_type": "DDR4",
            "capacity": "32GB",
            "module_configuration": "2x16GB",
            "speed": "DDR4-3600",
            "latency": "CL18-22-22",
            "voltage": "1.35V",
            "form_factor": "288-pin DIMM",
        },
    ),
    (
        "crucial-pro-32gb-ddr5-5600",
        "Crucial Pro 32GB (2x16GB) DDR5-5600",
        "ram",
        "Crucial",
        "89.99",
        38,
        "Standard-voltage DDR5 desktop kit supporting both Intel XMP 3.0 and AMD EXPO without bios hassle.",
        {
            "memory_type": "DDR5",
            "capacity": "32GB",
            "module_configuration": "2x16GB",
            "speed": "DDR5-5600",
            "latency": "CL46-45-45",
            "voltage": "1.1V",
            "form_factor": "288-pin DIMM",
        },
    ),
    (
        "gskill-ripjaws-s5-32gb-ddr5-6000",
        "G.Skill Ripjaws S5 32GB (2x16GB) DDR5-6000",
        "ram",
        "G.Skill",
        "104.99",
        26,
        "Low-profile matte black DDR5-6000 CL30 memory kit tailor-made for tight CPU cooler clearances.",
        {
            "memory_type": "DDR5",
            "capacity": "32GB",
            "module_configuration": "2x16GB",
            "speed": "DDR5-6000",
            "latency": "CL30-40-40",
            "voltage": "1.35V",
            "form_factor": "288-pin DIMM",
        },
    ),
    (
        "corsair-vengeance-rgb-32gb-ddr5-6000",
        "Corsair Vengeance RGB 32GB (2x16GB) DDR5-6000",
        "ram",
        "Corsair",
        "119.99",
        40,
        "Dynamic ten-zone RGB DDR5 kit with tight timings and integrated voltage regulation for easy tuning.",
        {
            "memory_type": "DDR5",
            "capacity": "32GB",
            "module_configuration": "2x16GB",
            "speed": "DDR5-6000",
            "latency": "CL36-36-36",
            "voltage": "1.35V",
            "form_factor": "288-pin DIMM",
        },
    ),
    (
        "gskill-trident-z5-neo-rgb-32gb-ddr5-6000",
        "G.Skill Trident Z5 Neo RGB 32GB (2x16GB) DDR5-6000",
        "ram",
        "G.Skill",
        "114.99",
        22,
        "Optimized for AMD AM5 platforms with AMD EXPO certification and ultra-fast CL30 response times.",
        {
            "memory_type": "DDR5",
            "capacity": "32GB",
            "module_configuration": "2x16GB",
            "speed": "DDR5-6000",
            "latency": "CL30-38-38",
            "voltage": "1.35V",
            "form_factor": "288-pin DIMM",
        },
    ),
    (
        "corsair-dominator-titanium-rgb-32gb-ddr5-7200",
        "Corsair Dominator Titanium RGB 32GB (2x16GB) DDR5-7200",
        "ram",
        "Corsair",
        "189.99",
        15,
        "Enthusiast-grade DDR5-7200 kit with swappable top bars, patented DHX cooling and premium aluminum styling.",
        {
            "memory_type": "DDR5",
            "capacity": "32GB",
            "module_configuration": "2x16GB",
            "speed": "DDR5-7200",
            "latency": "CL34-44-44",
            "voltage": "1.45V",
            "form_factor": "288-pin DIMM",
        },
    ),
    (
        "gskill-trident-z5-rgb-64gb-ddr5-6400",
        "G.Skill Trident Z5 RGB 64GB (2x32GB) DDR5-6400",
        "ram",
        "G.Skill",
        "219.99",
        14,
        "Massive 64GB high-frequency DDR5 kit engineered for 4K video editing, large datasets, and simultaneous streaming.",
        {
            "memory_type": "DDR5",
            "capacity": "64GB",
            "module_configuration": "2x32GB",
            "speed": "DDR5-6400",
            "latency": "CL32-39-39",
            "voltage": "1.40V",
            "form_factor": "288-pin DIMM",
        },
    ),
    (
        "corsair-vengeance-rgb-96gb-ddr5-5600",
        "Corsair Vengeance RGB 96GB (2x48GB) DDR5-5600",
        "ram",
        "Corsair",
        "319.99",
        8,
        "High-density non-binary 96GB DDR5 memory kit built for heavy virtualization and creative professional workloads.",
        {
            "memory_type": "DDR5",
            "capacity": "96GB",
            "module_configuration": "2x48GB",
            "speed": "DDR5-5600",
            "latency": "CL40-40-40",
            "voltage": "1.25V",
            "form_factor": "288-pin DIMM",
        },
    ),
    # ------------------------------------------------------------------ Motherboard (10)
    (
        "asrock-b550m-pro4",
        "ASRock B550M Pro4",
        "motherboard",
        "ASRock",
        "99.99",
        24,
        "Budget-friendly Micro-ATX motherboard for AMD AM4 with dual M.2 slots and robust power delivery.",
        {
            "socket": "AM4",
            "chipset": "AMD B550",
            "form_factor": "Micro-ATX",
            "memory_type": "DDR4",
            "maximum_memory": "128GB",
            "memory_slots": 4,
            "pcie_support": "PCIe 4.0 x16",
            "m2_slots": 2,
            "sata_ports": 6,
            "wifi": False,
            "lan_speed": "1 Gbps",
        },
    ),
    (
        "msi-b550-gaming-gen3",
        "MSI B550 Gaming GEN3",
        "motherboard",
        "MSI",
        "109.99",
        20,
        "Full-size ATX AM4 motherboard featuring Core Boost, Turbo M.2, and audio boost for budget gamers.",
        {
            "socket": "AM4",
            "chipset": "AMD B550",
            "form_factor": "ATX",
            "memory_type": "DDR4",
            "maximum_memory": "128GB",
            "memory_slots": 4,
            "pcie_support": "PCIe 3.0 x16",
            "m2_slots": 2,
            "sata_ports": 6,
            "wifi": False,
            "lan_speed": "1 Gbps",
        },
    ),
    (
        "asrock-b650m-hdv-m2",
        "ASRock B650M-HDV/M.2",
        "motherboard",
        "ASRock",
        "119.99",
        30,
        "Best-value entry AM5 motherboard featuring 8+2+1 power phases, PCIe 5.0 M.2, and 2.5G LAN.",
        {
            "socket": "AM5",
            "chipset": "AMD B650",
            "form_factor": "Micro-ATX",
            "memory_type": "DDR5",
            "maximum_memory": "96GB",
            "memory_slots": 2,
            "pcie_support": "PCIe 4.0 x16",
            "m2_slots": 2,
            "sata_ports": 4,
            "wifi": False,
            "lan_speed": "2.5 Gbps",
        },
    ),
    (
        "msi-b650-gaming-plus-wifi",
        "MSI B650 GAMING PLUS WIFI",
        "motherboard",
        "MSI",
        "169.99",
        22,
        "Feature-rich ATX AM5 board with Wi-Fi 6E, dual M.2 shield frozr, and extended heatsink design.",
        {
            "socket": "AM5",
            "chipset": "AMD B650",
            "form_factor": "ATX",
            "memory_type": "DDR5",
            "maximum_memory": "192GB",
            "memory_slots": 4,
            "pcie_support": "PCIe 4.0 x16",
            "m2_slots": 2,
            "sata_ports": 4,
            "wifi": True,
            "lan_speed": "2.5 Gbps",
        },
    ),
    (
        "gigabyte-b760-aorus-elite-ax",
        "Gigabyte B760 AORUS ELITE AX",
        "motherboard",
        "Gigabyte",
        "179.99",
        20,
        "Solid Intel LGA1700 ATX board with twin 12+1+1 phases, PCIe 4.0 x16, and on-board Wi-Fi 6E.",
        {
            "socket": "LGA1700",
            "chipset": "Intel B760",
            "form_factor": "ATX",
            "memory_type": "DDR5",
            "maximum_memory": "192GB",
            "memory_slots": 4,
            "pcie_support": "PCIe 4.0 x16",
            "m2_slots": 3,
            "sata_ports": 4,
            "wifi": True,
            "lan_speed": "2.5 Gbps",
        },
    ),
    (
        "asus-tuf-gaming-b650-plus-wifi",
        "ASUS TUF Gaming B650-PLUS WIFI",
        "motherboard",
        "ASUS",
        "199.99",
        18,
        "Durable military-grade AM5 gaming motherboard with PCIe 5.0 M.2, USB 3.2 Gen 2x2 Type-C, and Aura Sync.",
        {
            "socket": "AM5",
            "chipset": "AMD B650",
            "form_factor": "ATX",
            "memory_type": "DDR5",
            "maximum_memory": "192GB",
            "memory_slots": 4,
            "pcie_support": "PCIe 5.0 M.2 / PCIe 4.0 x16",
            "m2_slots": 3,
            "sata_ports": 4,
            "wifi": True,
            "lan_speed": "2.5 Gbps",
        },
    ),
    (
        "msi-mag-z790-tomahawk-max-wifi",
        "MSI MAG Z790 TOMAHAWK MAX WIFI",
        "motherboard",
        "MSI",
        "259.99",
        15,
        "Enthusiast Intel Z790 board supporting CPU overclocking, 16+1+1 power design, and Wi-Fi 7 connectivity.",
        {
            "socket": "LGA1700",
            "chipset": "Intel Z790",
            "form_factor": "ATX",
            "memory_type": "DDR5",
            "maximum_memory": "192GB",
            "memory_slots": 4,
            "pcie_support": "PCIe 5.0 x16",
            "m2_slots": 4,
            "sata_ports": 6,
            "wifi": True,
            "lan_speed": "2.5 Gbps",
        },
    ),
    (
        "asus-rog-strix-b650e-f-gaming-wifi",
        "ASUS ROG Strix B650E-F Gaming WIFI",
        "motherboard",
        "ASUS",
        "279.99",
        14,
        "Premium gaming AM5 board boasting native PCIe 5.0 x16 GPU slot, SupremeFX audio, and ROG styling.",
        {
            "socket": "AM5",
            "chipset": "AMD B650E",
            "form_factor": "ATX",
            "memory_type": "DDR5",
            "maximum_memory": "192GB",
            "memory_slots": 4,
            "pcie_support": "PCIe 5.0 x16",
            "m2_slots": 3,
            "sata_ports": 4,
            "wifi": True,
            "lan_speed": "2.5 Gbps",
        },
    ),
    (
        "gigabyte-x670e-aorus-pro-x",
        "Gigabyte X670E AORUS PRO X",
        "motherboard",
        "Gigabyte",
        "329.99",
        9,
        "All-white enthusiast AM5 motherboard with dual PCIe 5.0 slots, EZ-Latch Click M.2, and Wi-Fi 7.",
        {
            "socket": "AM5",
            "chipset": "AMD X670E",
            "form_factor": "ATX",
            "memory_type": "DDR5",
            "maximum_memory": "192GB",
            "memory_slots": 4,
            "pcie_support": "PCIe 5.0 x16",
            "m2_slots": 4,
            "sata_ports": 4,
            "wifi": True,
            "lan_speed": "2.5 Gbps",
        },
    ),
    (
        "asus-rog-maximus-z790-dark-hero",
        "ASUS ROG Maximus Z790 Dark Hero",
        "motherboard",
        "ASUS",
        "629.99",
        6,
        "Flagship Intel Z790 motherboard with 20+1+2 power stages, dual Thunderbolt 4 ports, and PCIe 5.0 M.2.",
        {
            "socket": "LGA1700",
            "chipset": "Intel Z790",
            "form_factor": "ATX",
            "memory_type": "DDR5",
            "maximum_memory": "192GB",
            "memory_slots": 4,
            "pcie_support": "PCIe 5.0 x16 (dual slots)",
            "m2_slots": 5,
            "sata_ports": 4,
            "wifi": True,
            "lan_speed": "2.5 Gbps / Wi-Fi 7",
        },
    ),
    # ------------------------------------------------------------------ Storage (10)
    (
        "kingston-nv2-1tb-nvme",
        "Kingston NV2 1TB NVMe SSD",
        "storage",
        "Kingston",
        "61.99",
        40,
        "Cost-effective Gen 4x4 NVMe SSD with up to 3,500MB/s speeds for budget desktop and laptop builds.",
        {
            "type": "NVMe SSD",
            "interface": "PCIe 4.0 x4",
            "form_factor": "M.2 2280",
            "capacity": "1TB",
            "sequential_read": "3500 MB/s",
            "sequential_write": "2100 MB/s",
            "nand_type": "3D QLC",
        },
    ),
    (
        "crucial-mx500-1tb-sata",
        "Crucial MX500 1TB SATA SSD",
        "storage",
        "Crucial",
        "74.99",
        35,
        "Dependable 2.5-inch SATA III SSD with integrated power loss immunity and 560MB/s read speeds.",
        {
            "type": "SATA SSD",
            "interface": "SATA III 6Gb/s",
            "form_factor": "2.5-inch",
            "capacity": "1TB",
            "sequential_read": "560 MB/s",
            "sequential_write": "510 MB/s",
            "nand_type": "3D TLC",
        },
    ),
    (
        "crucial-p3-plus-1tb-nvme",
        "Crucial P3 Plus 1TB NVMe SSD",
        "storage",
        "Crucial",
        "69.99",
        38,
        "Gen4 NVMe drive delivering flexible backward compatibility and up to 5,000MB/s sequential reads.",
        {
            "type": "NVMe SSD",
            "interface": "PCIe 4.0 x4",
            "form_factor": "M.2 2280",
            "capacity": "1TB",
            "sequential_read": "5000 MB/s",
            "sequential_write": "4200 MB/s",
            "nand_type": "3D QLC",
        },
    ),
    (
        "wd-blue-sn580-1tb-nvme",
        "WD Blue SN580 1TB NVMe SSD",
        "storage",
        "Western Digital",
        "71.99",
        32,
        "DRAM-less PCIe Gen 4.0 SSD with nCache 4.0 technology, ideal for productivity and light gaming.",
        {
            "type": "NVMe SSD",
            "interface": "PCIe 4.0 x4",
            "form_factor": "M.2 2280",
            "capacity": "1TB",
            "sequential_read": "4150 MB/s",
            "sequential_write": "4150 MB/s",
            "nand_type": "3D TLC",
        },
    ),
    (
        "samsung-990-evo-1tb-nvme",
        "Samsung 990 EVO 1TB NVMe SSD",
        "storage",
        "Samsung",
        "79.99",
        26,
        "Hybrid PCIe 4.0 x4 / 5.0 x2 SSD offering power efficiency and speeds up to 5,000MB/s.",
        {
            "type": "NVMe SSD",
            "interface": "PCIe 4.0 x4 / PCIe 5.0 x2",
            "form_factor": "M.2 2280",
            "capacity": "1TB",
            "sequential_read": "5000 MB/s",
            "sequential_write": "4200 MB/s",
            "nand_type": "Samsung V-NAND TLC",
        },
    ),
    (
        "wd-black-sn850x-1tb-nvme",
        "WD_BLACK SN850X 1TB NVMe SSD",
        "storage",
        "Western Digital",
        "94.99",
        30,
        "Gaming NVMe drive with custom controller, Game Mode 2.0, and blistering 7,300MB/s read speeds.",
        {
            "type": "NVMe SSD",
            "interface": "PCIe 4.0 x4",
            "form_factor": "M.2 2280",
            "capacity": "1TB",
            "sequential_read": "7300 MB/s",
            "sequential_write": "6300 MB/s",
            "nand_type": "BiCS5 3D TLC",
        },
    ),
    (
        "samsung-990-pro-2tb-nvme",
        "Samsung 990 PRO 2TB NVMe SSD",
        "storage",
        "Samsung",
        "169.99",
        20,
        "Flagship PCIe 4.0 NVMe with in-house Pascal controller and 7,450MB/s speeds for peak gaming and workflows.",
        {
            "type": "NVMe SSD",
            "interface": "PCIe 4.0 x4",
            "form_factor": "M.2 2280",
            "capacity": "2TB",
            "sequential_read": "7450 MB/s",
            "sequential_write": "6900 MB/s",
            "nand_type": "Samsung V-NAND TLC",
        },
    ),
    (
        "seagate-firecuda-530-2tb-nvme",
        "Seagate FireCuda 530 2TB NVMe SSD",
        "storage",
        "Seagate",
        "179.99",
        16,
        "High-endurance PCIe 4.0 drive boasting 2,550 TBW endurance and 7,300MB/s sustained transfers.",
        {
            "type": "NVMe SSD",
            "interface": "PCIe 4.0 x4",
            "form_factor": "M.2 2280",
            "capacity": "2TB",
            "sequential_read": "7300 MB/s",
            "sequential_write": "6900 MB/s",
            "nand_type": "3D TLC",
        },
    ),
    (
        "crucial-t700-2tb-gen5-nvme",
        "Crucial T700 2TB PCIe 5.0 NVMe SSD",
        "storage",
        "Crucial",
        "269.99",
        12,
        "Extreme next-gen PCIe 5.0 SSD with speeds up to 12,400MB/s, designed for DirectStorage and high-end rigs.",
        {
            "type": "NVMe SSD",
            "interface": "PCIe 5.0 x4",
            "form_factor": "M.2 2280",
            "capacity": "2TB",
            "sequential_read": "12400 MB/s",
            "sequential_write": "11800 MB/s",
            "nand_type": "Micron 232-Layer 3D TLC",
        },
    ),
    (
        "samsung-990-pro-4tb-nvme",
        "Samsung 990 PRO 4TB NVMe SSD",
        "storage",
        "Samsung",
        "329.99",
        8,
        "High-capacity 4TB single-sided NVMe SSD combining huge storage with 7,450MB/s speeds.",
        {
            "type": "NVMe SSD",
            "interface": "PCIe 4.0 x4",
            "form_factor": "M.2 2280",
            "capacity": "4TB",
            "sequential_read": "7450 MB/s",
            "sequential_write": "6900 MB/s",
            "nand_type": "Samsung V-NAND TLC",
        },
    ),
    # ------------------------------------------------------------------ PSU (10)
    (
        "evga-600-w1-600w-80-plus",
        "EVGA 600 W1 600W 80 PLUS Power Supply",
        "psu",
        "EVGA",
        "59.99",
        35,
        "Budget 600W power supply offering continuous power and standard safety protections for entry rigs.",
        {
            "wattage": "600W",
            "efficiency_certification": "80 PLUS White",
            "form_factor": "ATX",
            "modularity": "Non-Modular",
            "atx_version": "ATX 12V v2.31",
            "pcie_connectors": "2x 8-pin (6+2)",
        },
    ),
    (
        "corsair-cx650m-650w-80-plus-bronze",
        "Corsair CX650M 650W 80 PLUS Bronze",
        "psu",
        "Corsair",
        "79.99",
        28,
        "Semi-modular 650W PSU with low-noise rifle bearing fan and reliable 80 PLUS Bronze efficiency.",
        {
            "wattage": "650W",
            "efficiency_certification": "80 PLUS Bronze",
            "form_factor": "ATX",
            "modularity": "Semi-Modular",
            "atx_version": "ATX 12V v2.4",
            "pcie_connectors": "2x 8-pin (6+2)",
        },
    ),
    (
        "cooler-master-mwe-gold-750-v2",
        "Cooler Master MWE Gold 750 V2 750W",
        "psu",
        "Cooler Master",
        "99.99",
        25,
        "Fully modular 750W 80 PLUS Gold power supply with flat black cables and 120mm HDB fan.",
        {
            "wattage": "750W",
            "efficiency_certification": "80 PLUS Gold",
            "form_factor": "ATX",
            "modularity": "Fully Modular",
            "atx_version": "ATX 12V v2.52",
            "pcie_connectors": "4x 8-pin (6+2)",
        },
    ),
    (
        "be-quiet-pure-power-12-m-750w-atx-30",
        "be quiet! Pure Power 12 M 750W ATX 3.0",
        "psu",
        "be quiet!",
        "119.99",
        22,
        "ATX 3.0 certified 80 PLUS Gold power supply featuring 12VHPWR connector and whisper-quiet operation.",
        {
            "wattage": "750W",
            "efficiency_certification": "80 PLUS Gold",
            "form_factor": "ATX",
            "modularity": "Fully Modular",
            "atx_version": "ATX 3.0 (PCIe 5.0)",
            "pcie_connectors": "1x 12VHPWR (450W), 2x PCIe 6+2",
        },
    ),
    (
        "msi-mag-a850gl-pcie5-850w-atx-30",
        "MSI MAG A850GL PCIE5 850W ATX 3.0",
        "psu",
        "MSI",
        "129.99",
        24,
        "Compact ATX 3.0 850W unit equipped with dual-color yellow 12VHPWR connector for verified secure seating.",
        {
            "wattage": "850W",
            "efficiency_certification": "80 PLUS Gold",
            "form_factor": "ATX",
            "modularity": "Fully Modular",
            "atx_version": "ATX 3.0 (PCIe 5.0)",
            "pcie_connectors": "1x 12VHPWR (600W), 4x PCIe 6+2",
        },
    ),
    (
        "corsair-rm850x-shift-850w-atx-30",
        "Corsair RM850x SHIFT 850W 80 PLUS Gold",
        "psu",
        "Corsair",
        "149.99",
        18,
        "Innovative side-mounted modular cable interface for effortless cable access and ATX 3.0 compliance.",
        {
            "wattage": "850W",
            "efficiency_certification": "80 PLUS Gold",
            "form_factor": "ATX",
            "modularity": "Fully Modular (Side Interface)",
            "atx_version": "ATX 3.0",
            "pcie_connectors": "1x 12VHPWR, 4x PCIe 6+2",
        },
    ),
    (
        "seasonic-focus-gx-850-atx-30",
        "Seasonic FOCUS GX-850 ATX 3.0 850W",
        "psu",
        "Seasonic",
        "159.99",
        16,
        "Japanese capacitor equipped 850W PSU with hybrid silent fan control and 10-year manufacturer warranty.",
        {
            "wattage": "850W",
            "efficiency_certification": "80 PLUS Gold",
            "form_factor": "ATX",
            "modularity": "Fully Modular",
            "atx_version": "ATX 3.0",
            "pcie_connectors": "1x 12VHPWR, 3x PCIe 6+2",
        },
    ),
    (
        "corsair-rm1000e-1000w-atx-30",
        "Corsair RM1000e 1000W 80 PLUS Gold",
        "psu",
        "Corsair",
        "179.99",
        15,
        "High-wattage compact 1000W power supply ready for high-end GPUs with native PCIe 5.0 12VHPWR cable.",
        {
            "wattage": "1000W",
            "efficiency_certification": "80 PLUS Gold",
            "form_factor": "ATX",
            "modularity": "Fully Modular",
            "atx_version": "ATX 3.0",
            "pcie_connectors": "1x 12VHPWR (450W), 4x PCIe 6+2",
        },
    ),
    (
        "seasonic-vertex-gx-1000-1000w",
        "Seasonic Vertex GX-1000 1000W ATX 3.0",
        "psu",
        "Seasonic",
        "219.99",
        10,
        "Premium 1000W Gold PSU engineered for high transient loads and silent fluid dynamic bearing cooling.",
        {
            "wattage": "1000W",
            "efficiency_certification": "80 PLUS Gold",
            "form_factor": "ATX",
            "modularity": "Fully Modular",
            "atx_version": "ATX 3.0",
            "pcie_connectors": "1x 12VHPWR (600W), 3x PCIe 6+2",
        },
    ),
    (
        "be-quiet-dark-power-pro-13-1300w-titanium",
        "be quiet! Dark Power Pro 13 1300W Titanium",
        "psu",
        "be quiet!",
        "399.99",
        6,
        "Ultra-efficient 80 PLUS Titanium rated 1300W monster with frameless Silent Wings fan and dual 12VHPWR.",
        {
            "wattage": "1300W",
            "efficiency_certification": "80 PLUS Titanium",
            "form_factor": "ATX",
            "modularity": "Fully Modular",
            "atx_version": "ATX 3.0",
            "pcie_connectors": "2x 12VHPWR (600W), 6x PCIe 6+2",
        },
    ),
    # ------------------------------------------------------------------ PC Case (10)
    (
        "montech-air-903-base-black",
        "Montech AIR 903 BASE Black",
        "pc-case",
        "Montech",
        "65.99",
        30,
        "High-airflow mid-tower case featuring an ultra-fine mesh front and three included 140mm PWM fans.",
        {
            "form_factor": "Mid-Tower",
            "motherboard_support": "E-ATX, ATX, Micro-ATX, Mini-ITX",
            "gpu_max_length": "400mm",
            "cpu_cooler_max_height": "180mm",
            "radiator_support": "Up to 360mm front/top",
            "included_fans": "3x 140mm PWM fans",
            "airflow_characteristics": "High airflow mesh front panel",
        },
    ),
    (
        "deepcool-cc560-v2-mid-tower",
        "DeepCool CC560 V2 Mid-Tower",
        "pc-case",
        "DeepCool",
        "59.99",
        26,
        "Budget ATX chassis with four pre-installed LED fans, clean cable routing, and tempered glass side panel.",
        {
            "form_factor": "Mid-Tower",
            "motherboard_support": "ATX, Micro-ATX, Mini-ITX",
            "gpu_max_length": "370mm",
            "cpu_cooler_max_height": "163mm",
            "radiator_support": "Up to 360mm front",
            "included_fans": "4x 120mm LED fans",
            "airflow_characteristics": "Front airflow channels with tempered glass side",
        },
    ),
    (
        "fractal-design-pop-air-black",
        "Fractal Design Pop Air Black",
        "pc-case",
        "Fractal Design",
        "79.99",
        24,
        "Stylish mesh chassis with clean Scandinavian design, 3 included Aspect fans, and hidden storage drawer.",
        {
            "form_factor": "Mid-Tower",
            "motherboard_support": "ATX, Micro-ATX, Mini-ITX",
            "gpu_max_length": "405mm",
            "cpu_cooler_max_height": "170mm",
            "radiator_support": "Up to 280mm front, 240mm top",
            "included_fans": "3x Aspect 12 120mm fans",
            "airflow_characteristics": "Honeycomb mesh front with hidden 5.25 drawer",
        },
    ),
    (
        "corsair-4000d-airflow-black",
        "Corsair 4000D Airflow Tempered Glass Black",
        "pc-case",
        "Corsair",
        "89.99",
        35,
        "Iconic mid-tower case with dedicated steel ventilation channels and RapidRoute cable management.",
        {
            "form_factor": "Mid-Tower",
            "motherboard_support": "ATX, Micro-ATX, Mini-ITX",
            "gpu_max_length": "360mm",
            "cpu_cooler_max_height": "170mm",
            "radiator_support": "Up to 360mm front, 280mm top",
            "included_fans": "2x 120mm AirGuide fans",
            "airflow_characteristics": "Optimized steel front panel ventilation",
        },
    ),
    (
        "nzxt-h5-flow-black-compact-atx",
        "NZXT H5 Flow Compact ATX Mid-Tower",
        "pc-case",
        "NZXT",
        "94.99",
        28,
        "Compact mid-tower with dedicated angled intake fan aimed directly at the graphics card for lower GPU temps.",
        {
            "form_factor": "Mid-Tower",
            "motherboard_support": "ATX, Micro-ATX, Mini-ITX",
            "gpu_max_length": "365mm",
            "cpu_cooler_max_height": "165mm",
            "radiator_support": "Up to 280mm front, 240mm top",
            "included_fans": "2x 120mm fans (including dedicated GPU floor fan)",
            "airflow_characteristics": "Perforated front and bottom intake",
        },
    ),
    (
        "lian-li-lancool-216-rgb-black",
        "Lian Li LANCOOL 216 RGB Black",
        "pc-case",
        "Lian Li",
        "104.99",
        22,
        "Airflow-focused mid-tower with two massive 160mm front ARGB fans and modular rear fan bracket.",
        {
            "form_factor": "Mid-Tower",
            "motherboard_support": "E-ATX, ATX, Micro-ATX, Mini-ITX",
            "gpu_max_length": "392mm",
            "cpu_cooler_max_height": "180mm",
            "radiator_support": "Up to 360mm top/front",
            "included_fans": "2x 160mm ARGB front fans, 1x 140mm rear fan",
            "airflow_characteristics": "Full mesh design with rear external PCIe fan mount",
        },
    ),
    (
        "fractal-design-north-charcoal-black",
        "Fractal Design North Charcoal Black",
        "pc-case",
        "Fractal Design",
        "139.99",
        18,
        "Award-winning PC chassis featuring real FSC-certified walnut wood front slats and sleek brass details.",
        {
            "form_factor": "Mid-Tower",
            "motherboard_support": "ATX, Micro-ATX, Mini-ITX",
            "gpu_max_length": "355mm",
            "cpu_cooler_max_height": "170mm",
            "radiator_support": "Up to 360mm front, 240mm top",
            "included_fans": "2x Aspect 140mm PWM fans",
            "airflow_characteristics": "Natural walnut wood slat front with open mesh",
        },
    ),
    (
        "be-quiet-shadow-base-800-dx-black",
        "be quiet! Shadow Base 800 DX Black",
        "pc-case",
        "be quiet!",
        "169.99",
        14,
        "Spacious mid-tower supporting huge 420mm radiators, three Pure Wings 3 fans, and subtle ARGB accents.",
        {
            "form_factor": "Mid-Tower",
            "motherboard_support": "E-ATX, ATX, Micro-ATX, Mini-ITX",
            "gpu_max_length": "430mm",
            "cpu_cooler_max_height": "180mm",
            "radiator_support": "Up to 420mm front and top",
            "included_fans": "3x Pure Wings 3 140mm PWM fans",
            "airflow_characteristics": "Massive mesh intake with ARGB front illumination",
        },
    ),
    (
        "lian-li-o11-dynamic-evo-rgb-black",
        "Lian Li O11 Dynamic EVO RGB Black",
        "pc-case",
        "Lian Li",
        "159.99",
        16,
        "Iconic dual-chamber showcase chassis with reversible design, diffuse RGB light strips, and multi-radiator support.",
        {
            "form_factor": "Mid-Tower Dual Chamber",
            "motherboard_support": "E-ATX, ATX, Micro-ATX, Mini-ITX",
            "gpu_max_length": "455mm",
            "cpu_cooler_max_height": "167mm",
            "radiator_support": "Up to 3x 360mm radiators (top, side, bottom)",
            "included_fans": "None (chassis only)",
            "airflow_characteristics": "Panoramic seamless glass with dual-chamber cable management",
        },
    ),
    (
        "fractal-design-torrent-black-rgb",
        "Fractal Design Torrent Black RGB Tint",
        "pc-case",
        "Fractal Design",
        "229.99",
        10,
        "High-performance full-tower chassis with two 180mm front fans and bottom intake for top air cooling performance.",
        {
            "form_factor": "Full-Tower",
            "motherboard_support": "E-ATX, ATX, Micro-ATX, Mini-ITX, SSI-EEB",
            "gpu_max_length": "461mm",
            "cpu_cooler_max_height": "188mm",
            "radiator_support": "Up to 420mm front/bottom",
            "included_fans": "2x 180mm Prisma AL PWM fans, 3x 140mm Prisma AL PWM fans",
            "airflow_characteristics": "Unrestricted open front grille with bottom-to-top component cooling",
        },
    ),
    # ------------------------------------------------------------------ Cooler (10)
    (
        "thermalright-peerless-assassin-120-se",
        "Thermalright Peerless Assassin 120 SE",
        "cooler",
        "Thermalright",
        "34.99",
        50,
        "Dual-tower air cooler with 6 heatpipes and two 120mm PWM fans offering unbeatable thermal performance per dollar.",
        {
            "cooler_type": "Air Cooler",
            "socket_support": "AM4, AM5, LGA1700, LGA1200, LGA115x",
            "radiator_size": None,
            "fan_size": "120mm",
            "fan_count": 2,
            "cooling_capacity_tdp": "245W",
        },
    ),
    (
        "deepcool-ak400-zero-dark",
        "DeepCool AK400 ZERO DARK Air Cooler",
        "cooler",
        "DeepCool",
        "39.99",
        35,
        "All-black single-tower CPU cooler with matrix fin design, direct-touch heat pipes, and FDB fan.",
        {
            "cooler_type": "Air Cooler",
            "socket_support": "AM4, AM5, LGA1700, LGA1200, LGA115x",
            "radiator_size": None,
            "fan_size": "120mm",
            "fan_count": 1,
            "cooling_capacity_tdp": "220W",
        },
    ),
    (
        "be-quiet-pure-rock-2-black",
        "be quiet! Pure Rock 2 Black",
        "cooler",
        "be quiet!",
        "44.99",
        30,
        "Quiet 150W TDP air cooler with asymmetrical construction for unhindered memory slot clearance.",
        {
            "cooler_type": "Air Cooler",
            "socket_support": "AM4, AM5, LGA1700, LGA1200, LGA115x",
            "radiator_size": None,
            "fan_size": "120mm",
            "fan_count": 1,
            "cooling_capacity_tdp": "150W",
        },
    ),
    (
        "scythe-fuma-3",
        "Scythe Fuma 3 Dual Tower CPU Cooler",
        "cooler",
        "Scythe",
        "49.99",
        22,
        "Asymmetric dual-tower cooler engineered with Reverse Jet Flow technology for maximum static pressure.",
        {
            "cooler_type": "Air Cooler",
            "socket_support": "AM4, AM5, LGA1700, LGA1200, LGA115x",
            "radiator_size": None,
            "fan_size": "120mm",
            "fan_count": 2,
            "cooling_capacity_tdp": "250W",
        },
    ),
    (
        "arctic-liquid-freezer-iii-240-black",
        "Arctic Liquid Freezer III 240 Black",
        "cooler",
        "Arctic",
        "76.99",
        25,
        "All-in-one liquid cooler with thick 38mm radiator, integrated VRM cooling fan, and high-pressure P12 PWM fans.",
        {
            "cooler_type": "AIO Liquid Cooler",
            "socket_support": "AM4, AM5, LGA1700, LGA1851",
            "radiator_size": "240mm (38mm thick)",
            "fan_size": "120mm",
            "fan_count": 2,
            "cooling_capacity_tdp": "280W",
        },
    ),
    (
        "noctua-nh-d15-chromax-black",
        "Noctua NH-D15 chromax.black",
        "cooler",
        "Noctua",
        "119.99",
        18,
        "Flagship dual-tower stealth black air cooler equipped with two quiet NF-A15 140mm PWM fans.",
        {
            "cooler_type": "Air Cooler",
            "socket_support": "AM4, AM5, LGA1700, LGA1200, LGA115x",
            "radiator_size": None,
            "fan_size": "140mm",
            "fan_count": 2,
            "cooling_capacity_tdp": "250W+",
        },
    ),
    (
        "arctic-liquid-freezer-iii-360-black",
        "Arctic Liquid Freezer III 360 Black",
        "cooler",
        "Arctic",
        "99.99",
        24,
        "High-capacity 360mm AIO liquid cooler with offset contact frame for AMD AM5 and dedicated VRM fan.",
        {
            "cooler_type": "AIO Liquid Cooler",
            "socket_support": "AM4, AM5, LGA1700, LGA1851",
            "radiator_size": "360mm (38mm thick)",
            "fan_size": "120mm",
            "fan_count": 3,
            "cooling_capacity_tdp": "320W",
        },
    ),
    (
        "corsair-icue-link-h100i-rgb-240mm",
        "Corsair iCUE LINK H100i RGB 240mm AIO",
        "cooler",
        "Corsair",
        "139.99",
        15,
        "Single-cable iCUE LINK ecosystem AIO with brilliant RGB pump cap and QX120 magnetic dome fans.",
        {
            "cooler_type": "AIO Liquid Cooler",
            "socket_support": "AM4, AM5, LGA1700, LGA1200, LGA115x",
            "radiator_size": "240mm",
            "fan_size": "120mm",
            "fan_count": 2,
            "cooling_capacity_tdp": "260W",
        },
    ),
    (
        "deepcool-lt720-360mm-liquid-cooler",
        "DeepCool LT720 360mm High-Performance AIO",
        "cooler",
        "DeepCool",
        "124.99",
        16,
        "High-performance 360mm liquid cooler with 4th generation water pump and multidimensional infinity mirror block.",
        {
            "cooler_type": "AIO Liquid Cooler",
            "socket_support": "AM4, AM5, LGA1700, LGA1200, LGA115x, sTRX4",
            "radiator_size": "360mm",
            "fan_size": "120mm",
            "fan_count": 3,
            "cooling_capacity_tdp": "300W",
        },
    ),
    (
        "nzxt-kraken-elite-360-rgb-black",
        "NZXT Kraken Elite 360 RGB Black",
        "cooler",
        "NZXT",
        "279.99",
        9,
        "Enthusiast 360mm AIO cooler with wide-angle 2.36 inch customizable LCD display for real-time temps and GIFs.",
        {
            "cooler_type": "AIO Liquid Cooler",
            "socket_support": "AM4, AM5, LGA1700, LGA1200, LGA115x",
            "radiator_size": "360mm",
            "fan_size": "120mm",
            "fan_count": 3,
            "cooling_capacity_tdp": "300W",
        },
    ),
]

CUSTOMERS = [
    ("alice@example.com", "alice", "Alice", "Johnson"),
    ("bob@example.com", "bob", "Bob", "Smith"),
    ("carol@example.com", "carol", "Carol", "Davis"),
]

# (customer username, [(product slug, quantity), ...], final status)
SAMPLE_ORDERS = [
    (
        "alice",
        [("asus-dual-geforce-rtx-4070-super-12gb", 1), ("corsair-vengeance-rgb-32gb-ddr5-6000", 2)],
        OrderStatus.COMPLETED,
    ),
    ("alice", [("samsung-990-pro-2tb-nvme", 1), ("montech-air-903-base-black", 1)], OrderStatus.PENDING),
    ("bob", [("amd-ryzen-7-7800x3d", 1), ("wd-black-sn850x-1tb-nvme", 1)], OrderStatus.SHIPPED),
    ("carol", [("kingston-fury-beast-16gb-ddr4-3200", 2)], OrderStatus.PROCESSING),
]


def seed_categories(db: Session) -> dict[str, Category]:
    # Remap legacy categories if present
    legacy_map = {
        "processors": ("CPU", "cpu", "Desktop processors from AMD and Intel for gaming, creation, and multitasking."),
        "graphics-cards": ("GPU", "gpu", "Graphics cards from NVIDIA, AMD, and Intel for high-framerate gaming and 3D rendering."),
        "memory": ("RAM", "ram", "High-performance DDR4 and DDR5 desktop memory kits with low latency."),
    }
    for old_slug, (new_name, new_slug, new_desc) in legacy_map.items():
        existing_old = db.scalar(select(Category).where(Category.slug == old_slug))
        target = db.scalar(select(Category).where(Category.slug == new_slug))
        if existing_old and not target:
            existing_old.name = new_name
            existing_old.slug = new_slug
            existing_old.description = new_desc
            db.commit()

    categories: dict[str, Category] = {}
    for name, slug, description in CATEGORIES:
        category = db.scalar(select(Category).where(Category.slug == slug))
        if category is None:
            category = Category(name=name, slug=slug, description=description)
            db.add(category)
            logger.info("Created category: %s", name)
        else:
            category.name = name
            category.description = description
        categories[slug] = category
    db.commit()

    # Clean up empty legacy categories if any (e.g. gaming-accessories with 0 products)
    active_category_ids = {c.id for c in categories.values()}
    all_categories = db.scalars(select(Category)).all()
    for cat in all_categories:
        if cat.id not in active_category_ids:
            prod_count = db.scalar(select(func.count()).select_from(Product).where(Product.category_id == cat.id))
            if prod_count == 0:
                db.delete(cat)
                logger.info("Removed legacy empty category: %s", cat.name)
    db.commit()
    return categories


def seed_products(db: Session, categories: dict[str, Category]) -> dict[str, Product]:
    products: dict[str, Product] = {}
    for row in PRODUCTS:
        slug = row[0]
        name = row[1]
        category_slug = row[2]
        brand = row[3]
        price = row[4]
        stock = row[5]
        description = row[6]
        specifications = row[7] if len(row) > 7 else None
        is_active = row[8] if len(row) > 8 else True
        image_url = f"/images/products/{category_slug}/{slug}.svg"

        product = db.scalar(select(Product).where(Product.slug == slug))
        if product is None:
            product = Product(
                slug=slug,
                name=name,
                description=description,
                specifications=specifications,
                price=Decimal(price),
                stock=stock,
                brand=brand,
                image_url=image_url,
                category_id=categories[category_slug].id,
                is_active=is_active,
            )
            db.add(product)
            logger.info("Created product: %s", name)
        else:
            product.name = name
            product.description = description
            product.specifications = specifications
            product.price = Decimal(price)
            product.brand = brand
            product.image_url = image_url
            product.category_id = categories[category_slug].id
            product.is_active = is_active
        products[slug] = product
    db.commit()

    # Clean up any leftover products that are not in the current 80 catalog and have no orders
    current_slugs = set(products.keys())
    extra_products = db.scalars(select(Product).where(Product.slug.notin_(current_slugs))).all()
    for extra in extra_products:
        ordered_count = db.scalar(select(func.count()).select_from(OrderItem).where(OrderItem.product_id == extra.id))
        if ordered_count == 0:
            db.delete(extra)
            logger.info("Removed outdated seed product: %s", extra.slug)
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
    logger.info(
        "Seed complete: admin@example.com + %d customers, %d categories, %d products",
        len(CUSTOMERS),
        len(CATEGORIES),
        len(PRODUCTS),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
