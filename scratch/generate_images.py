import os
import sys

# Ensure backend is on sys.path to read seed.PRODUCTS
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.seed import PRODUCTS

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

CATEGORY_ART = {
    "cpu": """
        <rect x="110" y="35" width="180" height="180" rx="14" fill="#151a24" stroke="#2a354c" stroke-width="3"/>
        <rect x="135" y="60" width="130" height="130" rx="8" fill="#1c2333" stroke="#19e3c0" stroke-width="2"/>
        <path d="M110 55 L130 35" stroke="#19e3c0" stroke-width="2"/>
        <rect x="160" y="85" width="80" height="80" rx="4" fill="#10131a" stroke="#2a354c"/>
    """,
    "gpu": """
        <rect x="60" y="65" width="280" height="120" rx="12" fill="#151a24" stroke="#2a354c" stroke-width="3"/>
        <rect x="42" y="75" width="18" height="100" rx="3" fill="#1c2333" stroke="#9aa5bb" stroke-width="2"/>
        <circle cx="130" cy="125" r="42" fill="#1c2333" stroke="#19e3c0" stroke-width="2.5"/>
        <circle cx="130" cy="125" r="10" fill="#19e3c0"/>
        <circle cx="250" cy="125" r="42" fill="#1c2333" stroke="#19e3c0" stroke-width="2.5"/>
        <circle cx="250" cy="125" r="10" fill="#19e3c0"/>
        <path d="M80 185 L320 185" stroke="#19e3c0" stroke-width="3" stroke-dasharray="8 4"/>
    """,
    "ram": """
        <rect x="70" y="80" width="260" height="65" rx="6" fill="#151a24" stroke="#2a354c" stroke-width="2.5"/>
        <path d="M70 80 h260 v8 h-260 z" fill="#19e3c0"/>
        <rect x="70" y="145" width="260" height="15" rx="2" fill="#1c2333" stroke="#2a354c"/>
        <path d="M85 145 v15 M105 145 v15 M125 145 v15 M145 145 v15 M165 145 v15 M195 145 v15 M215 145 v15 M235 145 v15 M255 145 v15 M275 145 v15 M295 145 v15" stroke="#eab308" stroke-width="3"/>
    """,
    "motherboard": """
        <rect x="85" y="30" width="230" height="210" rx="10" fill="#151a24" stroke="#2a354c" stroke-width="3"/>
        <rect x="130" y="55" width="70" height="70" rx="6" fill="#1c2333" stroke="#19e3c0" stroke-width="2"/>
        <rect x="225" y="55" width="14" height="90" rx="2" fill="#1c2333" stroke="#2a354c"/>
        <rect x="245" y="55" width="14" height="90" rx="2" fill="#1c2333" stroke="#2a354c"/>
        <rect x="110" y="155" width="160" height="18" rx="3" fill="#1c2333" stroke="#19e3c0" stroke-width="1.5"/>
        <rect x="110" y="185" width="120" height="14" rx="2" fill="#1c2333" stroke="#2a354c"/>
    """,
    "storage": """
        <rect x="80" y="90" width="240" height="70" rx="6" fill="#151a24" stroke="#2a354c" stroke-width="2.5"/>
        <rect x="290" y="98" width="30" height="54" rx="2" fill="#1c2333" stroke="#eab308" stroke-width="2"/>
        <rect x="110" y="102" width="45" height="45" rx="4" fill="#1c2333" stroke="#19e3c0" stroke-width="1.5"/>
        <rect x="175" y="102" width="45" height="45" rx="4" fill="#1c2333" stroke="#2a354c"/>
        <rect x="235" y="102" width="45" height="45" rx="4" fill="#1c2333" stroke="#2a354c"/>
    """,
    "psu": """
        <rect x="80" y="45" width="240" height="170" rx="10" fill="#151a24" stroke="#2a354c" stroke-width="3"/>
        <circle cx="200" cy="120" r="55" fill="#1c2333" stroke="#2a354c" stroke-width="2"/>
        <circle cx="200" cy="120" r="45" fill="none" stroke="#19e3c0" stroke-width="2" stroke-dasharray="6 3"/>
        <circle cx="200" cy="120" r="14" fill="#19e3c0"/>
        <rect x="95" y="180" width="35" height="20" rx="2" fill="#1c2333" stroke="#9aa5bb"/>
        <rect x="140" y="180" width="20" height="20" rx="2" fill="#dc2626"/>
    """,
    "pc-case": """
        <rect x="110" y="30" width="180" height="215" rx="12" fill="#151a24" stroke="#2a354c" stroke-width="3"/>
        <rect x="125" y="45" width="125" height="180" rx="4" fill="#10131a" stroke="#19e3c0" stroke-width="1.5" opacity=".7"/>
        <path d="M265 45 v180" stroke="#2a354c" stroke-width="4" stroke-dasharray="8 6"/>
        <circle cx="265" cy="40" r="4" fill="#19e3c0"/>
    """,
    "cooler": """
        <rect x="115" y="60" width="170" height="140" rx="10" fill="#151a24" stroke="#2a354c" stroke-width="2.5"/>
        <path d="M125 60 v140 M145 60 v140 M165 60 v140 M185 60 v140 M205 60 v140 M225 60 v140 M245 60 v140 M265 60 v140 M275 60 v140" stroke="#2a354c" stroke-width="1.5"/>
        <circle cx="200" cy="130" r="46" fill="#1c2333" stroke="#19e3c0" stroke-width="2.5"/>
        <circle cx="200" cy="130" r="12" fill="#19e3c0"/>
        <path d="M160 200 C 160 230, 240 230, 240 200" fill="none" stroke="#9aa5bb" stroke-width="4"/>
    """,
}

def escape_xml(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def generate_svg(product):
    slug, name, category_slug, brand = product[0], product[1], product[2], product[3]
    art = CATEGORY_ART.get(category_slug, CATEGORY_ART["cpu"])
    safe_name = escape_xml(name)
    safe_brand = escape_xml(brand)
    safe_cat = category_slug.upper()

    # Short display title if name is very long
    display_name = safe_name
    if len(display_name) > 36:
        display_name = display_name[:34] + "…"

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" role="img" aria-labelledby="t">
  <title id="t">{safe_name}</title>
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#121620"/>
      <stop offset="100%" stop-color="#0a0c11"/>
    </linearGradient>
  </defs>
  <rect width="400" height="300" fill="url(#bg)"/>
  <rect x="8" y="8" width="384" height="284" rx="16" fill="none" stroke="#1f2637" stroke-width="2"/>

  <!-- Category Artwork -->
  <g>
    {art}
  </g>

  <!-- Product Labels -->
  <g font-family="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" text-anchor="middle">
    <rect x="24" y="24" width="70" height="22" rx="4" fill="#1c2333" stroke="#2a354c"/>
    <text x="59" y="39" font-size="11" font-weight="700" fill="#19e3c0" letter-spacing="1.5">{safe_cat}</text>

    <text x="200" y="248" font-size="13" font-weight="700" fill="#19e3c0" letter-spacing="2">{safe_brand.upper()}</text>
    <text x="200" y="272" font-size="15" font-weight="600" fill="#eceff6">{display_name}</text>
  </g>
</svg>
"""

count = 0
for p in PRODUCTS:
    slug = p[0]
    category_slug = p[2]
    cat_dir = os.path.join(FRONTEND_DIR, "images", "products", category_slug)
    os.makedirs(cat_dir, exist_ok=True)
    img_path = os.path.join(cat_dir, f"{slug}.svg")

    svg_content = generate_svg(p)
    with open(img_path, "w", encoding="utf-8") as f:
        f.write(svg_content)
    count += 1

print(f"Generated {count} product images.")
