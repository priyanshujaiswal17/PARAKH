"""Script to generate realistic test label images for evaluation."""

import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

golden_dir = Path(__file__).parent / "golden"
golden_dir.mkdir(parents=True, exist_ok=True)

# 1. Food Label: Digestive Biscuits
img_biscuit = Image.new("RGB", (900, 1100), color=(255, 250, 240))
draw = ImageDraw.Draw(img_biscuit)

# Header
draw.rectangle([(30, 30), (870, 120)], fill=(70, 130, 80))
draw.text((50, 50), "NUTRICRUNCH DIGESTIVE BISCUITS", fill=(255, 255, 255))

# Veg mark: Green square with circle
draw.rectangle([(800, 50), (840, 90)], outline=(0, 150, 0), width=3)
draw.ellipse([(810, 60), (830, 80)], fill=(0, 150, 0))

# Ingredients section
draw.text((50, 150), "INGREDIENTS:", fill=(0, 0, 0))
ing_text = (
    "Whole wheat flour (atta 60%), Palm oil, Sugar, Invert syrup,\n"
    "Edible salt, Raising agent (INS 500(ii)), Emulsifier (INS 322)."
)
draw.text((50, 190), ing_text, fill=(30, 30, 30))

# Allergens
draw.text((50, 280), "ALLERGEN ADVICE: Contains Wheat and Soy.", fill=(180, 0, 0))

# Nutrition table
draw.text((50, 340), "NUTRITION INFORMATION (Per 100 g):", fill=(0, 0, 0))
nut_lines = [
    "Energy: 450 kcal",
    "Protein: 7.5 g",
    "Carbohydrate: 68 g",
    "Total Sugar: 14 g",
    "Total Fat: 18 g",
    "Sodium: 320 mg",
]
y = 380
for line in nut_lines:
    draw.text((70, y), line, fill=(40, 40, 40))
    y += 35

# Date
draw.text((50, 620), "PKD 01/2026", fill=(0, 0, 0))
draw.text((50, 660), "Best before 6 months from manufacture", fill=(0, 0, 0))
draw.text((50, 720), "FSSAI Lic. No. 10012011000123", fill=(50, 50, 50))

biscuit_path = golden_dir / "sample_biscuit.jpg"
img_biscuit.save(biscuit_path, format="JPEG", quality=90)

biscuit_json = {
    "is_medicine": False,
    "product_name": "NutriCrunch Digestive Biscuits",
    "ingredients": [
        "Whole wheat flour",
        "Palm oil",
        "Sugar",
        "Invert syrup",
        "Edible salt",
        "Raising agent (INS 500(ii))",
        "Emulsifier (INS 322)"
    ],
    "allergen_statement": ["Contains Wheat and Soy"],
    "expiry_date": "2026-07-31"
}
with open(golden_dir / "sample_biscuit.json", "w", encoding="utf-8") as f:
    json.dump(biscuit_json, f, indent=2)

# 2. Medicine Strip Label
img_med = Image.new("RGB", (800, 600), color=(240, 240, 245))
draw_m = ImageDraw.Draw(img_med)
draw_m.rectangle([(20, 20), (780, 80)], fill=(200, 40, 40))
draw_m.text((40, 35), "Rx - SCHEDULE H PRESCRIPTION DRUG", fill=(255, 255, 255))

draw_m.text((40, 110), "Paracetamol and Ibuprofen Tablets I.P.", fill=(0, 0, 0))
draw_m.text((40, 160), "Each film coated tablet contains:", fill=(0, 0, 0))
draw_m.text((60, 200), "Paracetamol I.P. 325 mg", fill=(40, 40, 40))
draw_m.text((60, 240), "Ibuprofen I.P. 400 mg", fill=(40, 40, 40))
draw_m.text((40, 300), "Dosage: As directed by the physician.", fill=(150, 0, 0))
draw_m.text((40, 350), "Warning: To be sold by retail on the prescription of a Registered Medical Practitioner only.", fill=(150, 0, 0))
draw_m.text((40, 420), "Mfg. Lic. No. G/25/142", fill=(60, 60, 60))

med_path = golden_dir / "sample_medicine.jpg"
img_med.save(med_path, format="JPEG", quality=90)

med_json = {
    "is_medicine": True,
    "product_name": "Paracetamol and Ibuprofen Tablets I.P."
}
with open(golden_dir / "sample_medicine.json", "w", encoding="utf-8") as f:
    json.dump(med_json, f, indent=2)

print("Golden test samples created successfully in tests/golden!")
