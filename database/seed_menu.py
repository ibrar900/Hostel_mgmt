"""
Seed the weekly menu from the official HKBK Hostel Menu PDF.
Inserts for current week + next 3 weeks (4 weeks total).
Run: python database/seed_menu.py
"""
import sqlite3, sys, os
from datetime import date, timedelta

# Allow running from any directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'hostel.db')

# ── Weekly Menu Data (from official HKBK Hostel Menu PDF) ─────────────────────
# Keys: 0=Monday ... 6=Sunday
# meal_types: breakfast, lunch, snacks, dinner
# Each entry: (veg_items, non_veg_items)

WEEKLY_MENU = {
    0: {  # Monday
        'breakfast': (
            'Bisi belebath, Bread, Tea, Milk',
            'Egg / Omelette'
        ),
        'lunch': (
            'White Rice, Chapati (2), Mattar Paneer, Veg Sambar, Pickle',
            ''
        ),
        'snacks': (
            'Samosa & Tea',
            ''
        ),
        'dinner': (
            'White Rice, Chapati(2), Aalo Jeera, Daal Fry, Curd Rice, Pickle',
            ''
        ),
    },
    1: {  # Tuesday
        'breakfast': (
            'Idli & Vada, Banana (Big), Tea, Milk',
            ''
        ),
        'lunch': (
            'White Rice, Chapati(2), Pappu Daal, Mixed Veg/Beans, Papad, Butter Milk',
            ''
        ),
        'snacks': (
            'Sweet Bun & Tea',
            ''
        ),
        'dinner': (
            'Ghee Rice, Chapati, Paneer Masala, Pickle',
            'Ghee Rice, Chapati, Chicken Curry (2 pieces), Pickle'
        ),
    },
    2: {  # Wednesday
        'breakfast': (
            'Shavige Uppit, Tea, Milk',
            'Egg'
        ),
        'lunch': (
            'White Rice, Daal Fry, Chapathi(2), Aloo Ki Sabzi, Pickle',
            ''
        ),
        'snacks': (
            'Onion Pakoda & Tea/Coffee',
            ''
        ),
        'dinner': (
            'White Rice, Chapati, Veg Sambar, Green Peas Masala, Curd Rice, Pickle',
            ''
        ),
    },
    3: {  # Thursday
        'breakfast': (
            'Lemon Rice, Banana (Yalakki), Tea, Milk',
            ''
        ),
        'lunch': (
            'White Rice, Chapati(2), Sambar, Mixed Veg, Soya Beans 65, Papad, Butter Milk',
            ''
        ),
        'snacks': (
            'Bhailpuri & Tea',
            ''
        ),
        'dinner': (
            'Khushka, Mushroom Masala, Pickle',
            'Khushka, Egg Curry (1 egg), Pickle'
        ),
    },
    4: {  # Friday
        'breakfast': (
            'Khara & Kesari Bhaat, Tea, Milk',
            'Egg'
        ),
        'lunch': (
            'White Rice, Chapathi(2), Daal Fry, Aalo Matar, Pickle',
            ''
        ),
        'snacks': (
            'Bhajji & Tea/Coffee',
            ''
        ),
        'dinner': (
            'Veg Biryani, Gobi Manchurian, Raita, Pickle, Sweet',
            'Chicken Biryani (2 pieces), Raita, Pickle, Sweet'
        ),
    },
    5: {  # Saturday
        'breakfast': (
            'Puri Baji & Chattni, Bread, Banana (Big), Tea, Milk',
            'Omelette'
        ),
        'lunch': (
            'White Rice, Chapathi(2), Daal Makhni, Mushroom Manchurian, Papad, Butter Milk',
            ''
        ),
        'snacks': (
            'Samosa & Tea',
            ''
        ),
        'dinner': (
            'White Rice, Veg Sambar, Mixed Veg, Chapathi, Pickle',
            ''
        ),
    },
    6: {  # Sunday
        'breakfast': (
            'Mini Masala Dosa - 2 Pc, Tea, Milk',
            ''
        ),
        'lunch': (
            'Veg Fried Rice, Gobi Manchurian',
            ''
        ),
        'snacks': (
            'Veg Puff & Tea',
            'Egg Puff & Tea'
        ),
        'dinner': (
            'White Rice, Palak Paneer, Chapati(2), Pickle',
            'White Rice, Chicken Curry (2 pieces), Palak Paneer, Chapati(2), Pickle'
        ),
    },
}

def seed_menu(weeks=4):
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    db.row_factory = sqlite3.Row

    hostels = db.execute("SELECT id FROM hostels").fetchall()
    hostel_ids = [h['id'] for h in hostels]

    # find the Monday of current week
    today = date.today()
    monday = today - timedelta(days=today.weekday())

    inserted = 0
    for week_offset in range(weeks):
        week_start = monday + timedelta(weeks=week_offset)
        for day_offset, meals in WEEKLY_MENU.items():
            menu_date = (week_start + timedelta(days=day_offset)).isoformat()
            for meal_type, (veg, nv) in meals.items():
                for hid in hostel_ids:
                    db.execute("""
                        INSERT INTO weekly_menus
                            (hostel_id, menu_date, meal_type, veg_items, non_veg_items, uploaded_by)
                        VALUES (?, ?, ?, ?, ?, 1)
                        ON CONFLICT(hostel_id, menu_date, meal_type) DO UPDATE SET
                            veg_items     = excluded.veg_items,
                            non_veg_items = excluded.non_veg_items
                    """, (hid, menu_date, meal_type, veg, nv))
                    inserted += 1

    db.commit()
    db.close()
    print(f"Done. Inserted/updated {inserted} menu entries across {weeks} weeks "
          f"({monday.isoformat()} to {(monday + timedelta(weeks=weeks-1, days=6)).isoformat()})")

if __name__ == '__main__':
    weeks = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    seed_menu(weeks)
