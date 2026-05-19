"""
BarMGR Cafe Warehouse Inventory
Stock items organized by category with quantities.
"""

WAREHOUSE_CAFE = {
    "Coffee": [
        {"name": "Greek coffee", "quantity": 0},
        {"name": "Espresso", "quantity": 0},
        {"name": "Frappe", "quantity": 0},
        {"name": "Decaf", "quantity": 0},
        {"name": "Chocolate", "quantity": 0},
        {"name": "Brown sugar", "quantity": 0},
        {"name": "White sugar", "quantity": 0},
    ],
    "Juices & Refreshments": [
        {"name": "Cherry juice (βύσσινο)", "quantity": 0},
        {"name": "Orange juice", "quantity": 0},
        {"name": "Mixed juice", "quantity": 0},
        {"name": "Lemon juice", "quantity": 0},
        {"name": "Peach juice", "quantity": 0},
        {"name": "Peach ice tea", "quantity": 0},
        {"name": "Lemon ice tea", "quantity": 0},
    ],
    "Soft Drinks": [
        {"name": "Water 500ml", "quantity": 0},
        {"name": "Water 1lt (personal)", "quantity": 0},
        {"name": "Water 1lt (table)", "quantity": 0},
        {"name": "Coca Cola glass", "quantity": 0},
        {"name": "Coca Cola can", "quantity": 0},
        {"name": "Coca Cola bar", "quantity": 0},
        {"name": "Coca Cola Zero glass", "quantity": 0},
        {"name": "Coca Cola Zero can", "quantity": 0},
        {"name": "Soda glass", "quantity": 0},
        {"name": "Soda can", "quantity": 0},
        {"name": "Soda bar", "quantity": 0},
        {"name": "Tonic glass", "quantity": 0},
        {"name": "Tonic can", "quantity": 0},
        {"name": "Tonic bar", "quantity": 0},
        {"name": "Sprite glass", "quantity": 0},
        {"name": "Sprite can", "quantity": 0},
        {"name": "Sprite bar", "quantity": 0},
        {"name": "Xino Nero Florinas 250ml", "quantity": 0},
        {"name": "San Pellegrino 750ml", "quantity": 0},
        {"name": "3Cents Pink Grapefruit 250ml", "quantity": 0},
        {"name": "3Cents Ginger Beer 250ml", "quantity": 0},
        {"name": "3Cents Aegean Tonic 250ml", "quantity": 0},
    ],
}


def get_warehouse_items():
    """Return all warehouse items organized by category."""
    return WAREHOUSE_CAFE


def get_category_items(category):
    """Get items for a specific category."""
    return WAREHOUSE_CAFE.get(category, [])


def get_all_categories():
    """Return all available categories."""
    return list(WAREHOUSE_CAFE.keys())
