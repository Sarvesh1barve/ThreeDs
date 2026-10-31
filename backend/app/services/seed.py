from sqlalchemy.orm import Session
from ..models import Base, Category, Product, SchemaVersion, SiteSetting
from ..db import engine

CATEGORIES = ["Decor", "Lamps", "Planters & Vases", "Custom Gifts", "Toys & Figures", "Custom 3D Printing"]
PRODUCTS = [
    ("Ripple Glow Lamp", "ripple-glow-lamp", "lamps", "lamp", 149900, "For evenings that deserve a softer glow. A sculptural lamp with warmth and personality."),
    ("Petal Wave Vase", "petal-wave-vase", "decor", "vase", 89900, "A wavy little vase for stems, sunshine and shelves that need something beautiful."),
    ("Little Green Home", "little-green-home", "planters-vases", "planter", 74900, "A happy home for your favourite plant, with playful texture for any desk."),
    ("Just For You Plaque", "just-for-you-plaque", "custom-gifts", "gift", 69900, "A personalised nameplate, because some messages are better held onto."),
    ("Pocket Buddy Figure", "pocket-buddy-figure", "toys-figures", "figure", 59900, "A tiny collectible companion with a seriously big personality."),
    ("Moonlight Mood Lamp", "moonlight-mood-lamp", "lamps", "moon", 129900, "A little moon of your own for slow, cosy nights."),
]


def bootstrap(db: Session):
    Base.metadata.create_all(bind=engine)
    if not db.get(SchemaVersion, 1):
        db.add(SchemaVersion(version=1))
    if not db.get(SiteSetting, 1):
        db.add(SiteSetting(id=1))
    if not db.query(Category).count():
        for i, name in enumerate(CATEGORIES):
            slug = name.lower().replace(" & ", "-").replace(" ", "-")
            db.add(Category(name=name, slug=slug, sort_order=i))
        db.flush()
    categories = {c.slug: c for c in db.query(Category).all()}
    if not db.query(Product).count():
        for i, (name, slug, cat, art, price, desc) in enumerate(PRODUCTS):
            db.add(Product(name=name, slug=slug, sku=f"3DS-{i+1:03d}", category_id=categories[cat].id, short_description=desc, description=desc, price_paise=price, price_verified=False, allow_checkout=False, active=True, featured=i < 3, customization_enabled=art == "gift", illustration_key=art, sort_order=i))
    db.commit()

