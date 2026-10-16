"""
Food by Soni - Food ordering web app
Backend : Python (Flask) + SQLite
Frontend: HTML (Jinja templates) + CSS + vanilla JS
Run     : python app.py   ->  http://127.0.0.1:5000
"""
import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (Flask, g, render_template, request, redirect, url_for,
                   session, flash, jsonify, abort)
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = "/tmp/foodbysoni.db" if os.environ.get("VERCEL") else os.path.join(BASE_DIR, "foodbysoni.db")

app = Flask(__name__)
app.secret_key = "food-by-soni-change-this-secret-key"

# ----------------------------------------------------------------- constants
COUPONS = {
    "WELCOME50": {"type": "percent", "value": 50, "max": 100, "min": 199,
                  "desc": "50% OFF up to ₹100 on orders above ₹199"},
    "SONI20": {"type": "percent", "value": 20, "max": 80, "min": 149,
               "desc": "20% OFF up to ₹80 on orders above ₹149"},
    "FREEDEL": {"type": "freedel", "value": 0, "max": 0, "min": 249,
                "desc": "Free delivery on orders above ₹249"},
}
STAGES = ["Placed", "Preparing", "Out for Delivery", "Delivered"]
PARTNERS = ["Rahul K.", "Amit S.", "Sanjay P.", "Vikram D.", "Imran S.", "Pooja R."]
CUISINES = [("Biryani", "🍛"), ("Pizza", "🍕"), ("Burgers", "🍔"),
            ("South Indian", "🥞"), ("Chinese", "🥡"), ("North Indian", "🍲"),
            ("Chaat", "🥟"), ("Desserts", "🍰"), ("Healthy", "🥗")]
PAYMENTS = {"cod": "Cash on Delivery", "upi": "UPI (pay on delivery)",
            "card": "Card on delivery"}

# ------------------------------------------------------------------ database
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, phone TEXT,
  password TEXT NOT NULL, is_admin INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS restaurants(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, cuisines TEXT, emoji TEXT, color TEXT,
  rating REAL, delivery_time INTEGER, cost_for_two INTEGER, offer TEXT,
  is_veg INTEGER DEFAULT 0, is_open INTEGER DEFAULT 1, address TEXT);
CREATE TABLE IF NOT EXISTS menu_items(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  restaurant_id INTEGER NOT NULL, category TEXT, name TEXT NOT NULL,
  description TEXT, price INTEGER NOT NULL, is_veg INTEGER DEFAULT 1,
  emoji TEXT, bestseller INTEGER DEFAULT 0,
  FOREIGN KEY(restaurant_id) REFERENCES restaurants(id));
CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL, restaurant_id INTEGER NOT NULL,
  subtotal REAL, delivery_fee REAL, platform_fee REAL, tax REAL,
  discount REAL, total REAL, coupon TEXT, address TEXT, phone TEXT,
  payment TEXT, note TEXT, status TEXT DEFAULT 'Placed',
  manual INTEGER DEFAULT 0, created_at TEXT);
CREATE TABLE IF NOT EXISTS order_items(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL, item_id INTEGER, name TEXT, price INTEGER, qty INTEGER);
"""

# (category, name, description, price, is_veg, emoji, bestseller)
SEED = [
    {"name": "Soni's Biryani House", "cuisines": "Biryani, Mughlai, North Indian",
     "emoji": "🍛", "color": "#ff8a00,#b3001b", "rating": 4.6, "time": 32, "cost": 450,
     "offer": "50% OFF up to ₹100", "veg": 0, "addr": "Civil Lines",
     "items": [
         ("Biryani", "Chicken Dum Biryani", "Slow-cooked basmati rice with tender chicken and saffron", 249, 0, "🍛", 1),
         ("Biryani", "Mutton Biryani", "Hearty mutton pieces layered with fragrant rice", 349, 0, "🍖", 0),
         ("Biryani", "Paneer Tikka Biryani", "Smoky paneer tikka in dum-cooked rice", 229, 1, "🧀", 0),
         ("Biryani", "Veg Dum Biryani", "Seasonal vegetables and whole spices", 199, 1, "🍚", 0),
         ("Starters", "Chicken 65", "Spicy, crispy South-Indian style fried chicken", 179, 0, "🍗", 1),
         ("Starters", "Paneer Tikka", "Char-grilled cottage cheese cubes", 189, 1, "🧆", 0),
         ("Sides & Drinks", "Boondi Raita", "Cool curd with crunchy boondi", 49, 1, "🥣", 0),
         ("Sides & Drinks", "Sweet Lassi", "Thick chilled Punjabi lassi", 69, 1, "🥛", 0)]},
    {"name": "Pizza Palace", "cuisines": "Pizza, Italian, Fast Food",
     "emoji": "🍕", "color": "#ff512f,#dd2476", "rating": 4.3, "time": 28, "cost": 400,
     "offer": "Buy 1 Get 1 on Medium", "veg": 0, "addr": "Dharampeth",
     "items": [
         ("Pizzas", "Margherita Pizza", "Classic tomato, mozzarella and basil", 199, 1, "🍕", 1),
         ("Pizzas", "Farmhouse Pizza", "Capsicum, onion, tomato, mushroom", 299, 1, "🍕", 0),
         ("Pizzas", "Pepperoni Pizza", "Loaded with spicy pepperoni", 349, 0, "🍕", 1),
         ("Pizzas", "Paneer Makhani Pizza", "Desi-style makhani sauce with paneer", 319, 1, "🧀", 0),
         ("Pasta & Sides", "White Sauce Pasta", "Creamy penne with herbs", 189, 1, "🍝", 0),
         ("Pasta & Sides", "Garlic Bread with Cheese", "Toasted and loaded", 129, 1, "🥖", 0),
         ("Drinks", "Cold Coffee", "Thick café-style cold coffee", 99, 1, "☕", 0),
         ("Drinks", "Coke (300 ml)", "Chilled", 40, 1, "🥤", 0)]},
    {"name": "Burger Barn", "cuisines": "Burgers, Fast Food, Shakes",
     "emoji": "🍔", "color": "#f7971e,#ffd200", "rating": 4.2, "time": 22, "cost": 300,
     "offer": "Flat ₹75 OFF", "veg": 0, "addr": "Sitabuldi",
     "items": [
         ("Burgers", "Aloo Tikki Burger", "Crispy potato patty with mint mayo", 89, 1, "🍔", 1),
         ("Burgers", "Crispy Chicken Burger", "Juicy fried chicken fillet", 149, 0, "🍔", 1),
         ("Burgers", "Double Cheese Veg Burger", "Two cheese slices, double the joy", 129, 1, "🍔", 0),
         ("Fries & Snacks", "Peri Peri Fries", "Spicy seasoned fries", 99, 1, "🍟", 0),
         ("Fries & Snacks", "Chicken Nuggets (6 pcs)", "Golden and crunchy", 139, 0, "🍗", 0),
         ("Shakes", "Oreo Shake", "Thick cookies & cream shake", 129, 1, "🥤", 0),
         ("Shakes", "Chocolate Shake", "Rich and creamy", 119, 1, "🍫", 0)]},
    {"name": "Dosa Darbar", "cuisines": "South Indian, Breakfast",
     "emoji": "🥞", "color": "#11998e,#38ef7d", "rating": 4.5, "time": 25, "cost": 250,
     "offer": "20% OFF up to ₹80", "veg": 1, "addr": "Ramdaspeth",
     "items": [
         ("Dosa", "Masala Dosa", "Crisp dosa with spiced potato filling", 99, 1, "🥞", 1),
         ("Dosa", "Mysore Masala Dosa", "Red chutney smeared, extra spicy", 119, 1, "🥞", 0),
         ("Dosa", "Paneer Dosa", "Stuffed with spiced paneer bhurji", 139, 1, "🥞", 0),
         ("Idli & Vada", "Idli Sambar (3 pcs)", "Soft idlis with sambar and chutney", 79, 1, "🍚", 1),
         ("Idli & Vada", "Medu Vada (2 pcs)", "Crispy outside, fluffy inside", 89, 1, "🍩", 0),
         ("Idli & Vada", "Onion Uttapam", "Thick pancake with onion topping", 109, 1, "🥞", 0),
         ("Beverages", "Filter Coffee", "Strong South-Indian filter coffee", 49, 1, "☕", 0)]},
    {"name": "Chai & Chaat Corner", "cuisines": "Chaat, Snacks, Tea",
     "emoji": "🥟", "color": "#f2994a,#f2c94c", "rating": 4.4, "time": 18, "cost": 150,
     "offer": "Free delivery", "veg": 1, "addr": "Gandhibagh",
     "items": [
         ("Chaat", "Pani Puri (6 pcs)", "Crisp puris with spicy pani", 59, 1, "🥟", 1),
         ("Chaat", "Sev Puri", "Tangy, crunchy and sweet", 69, 1, "🥟", 0),
         ("Chaat", "Dahi Puri", "Puris topped with chilled curd", 79, 1, "🥟", 0),
         ("Snacks", "Vada Pav", "Mumbai-style street classic", 39, 1, "🥪", 1),
         ("Snacks", "Samosa (2 pcs)", "Hot, flaky and spiced", 40, 1, "🥟", 0),
         ("Snacks", "Pyaaz Kachori", "Crispy kachori with chutney", 45, 1, "🥟", 0),
         ("Chai", "Masala Chai", "Ginger-cardamom kulhad chai", 25, 1, "☕", 1),
         ("Chai", "Cutting Chai", "Half-glass strong tea", 20, 1, "☕", 0)]},
    {"name": "Dragon Wok", "cuisines": "Chinese, Asian, Noodles",
     "emoji": "🥡", "color": "#cb2d3e,#ef473a", "rating": 4.1, "time": 35, "cost": 500,
     "offer": "30% OFF up to ₹75", "veg": 0, "addr": "Trimurti Nagar",
     "items": [
         ("Starters", "Veg Manchurian", "Crispy veg balls in tangy gravy", 169, 1, "🥡", 1),
         ("Starters", "Chicken Lollipop (6 pcs)", "Fried drumettes with schezwan dip", 219, 0, "🍗", 0),
         ("Noodles & Rice", "Veg Hakka Noodles", "Wok-tossed with crunchy veggies", 159, 1, "🍜", 1),
         ("Noodles & Rice", "Chicken Schezwan Noodles", "Fiery and satisfying", 189, 0, "🍜", 0),
         ("Noodles & Rice", "Veg Fried Rice", "Classic street-style fried rice", 149, 1, "🍚", 0),
         ("Noodles & Rice", "Chicken Fried Rice", "With egg and chicken shreds", 179, 0, "🍚", 0),
         ("Soups", "Hot & Sour Soup", "Peppery and comforting", 99, 1, "🍲", 0)]},
    {"name": "Sweet Tooth", "cuisines": "Desserts, Ice Cream, Bakery",
     "emoji": "🍰", "color": "#ee9ca7,#ffdde1", "rating": 4.7, "time": 20, "cost": 300,
     "offer": "Free dessert on ₹399+", "veg": 1, "addr": "Laxmi Nagar",
     "items": [
         ("Cakes & Pastries", "Choco Lava Cake", "Molten chocolate centre", 99, 1, "🍰", 1),
         ("Cakes & Pastries", "Black Forest Pastry", "Cherry, cream and chocolate", 89, 1, "🍰", 0),
         ("Ice Cream", "Butterscotch Sundae", "Loaded with nuts and caramel", 129, 1, "🍨", 0),
         ("Ice Cream", "Brownie with Ice Cream", "Warm brownie, cold scoop", 149, 1, "🍫", 1),
         ("Indian Sweets", "Gulab Jamun (2 pcs)", "Hot, soft and syrupy", 69, 1, "🍡", 0),
         ("Indian Sweets", "Rasmalai (2 pcs)", "Saffron milk-soaked cheese dumplings", 99, 1, "🍮", 0),
         ("Waffles", "Nutella Waffle", "Crisp waffle with Nutella", 139, 1, "🧇", 0)]},
    {"name": "Tandoori Tadka", "cuisines": "North Indian, Tandoor, Mughlai",
     "emoji": "🍗", "color": "#e65c00,#f9d423", "rating": 4.4, "time": 38, "cost": 550,
     "offer": "Flat ₹100 OFF above ₹499", "veg": 0, "addr": "Wardha Road",
     "items": [
         ("Tandoori", "Tandoori Chicken (Half)", "Charred and juicy, with mint chutney", 259, 0, "🍗", 1),
         ("Tandoori", "Chicken Tikka", "Marinated overnight, grilled to perfection", 229, 0, "🍢", 0),
         ("Tandoori", "Paneer Tikka", "Soft paneer in hung-curd marinade", 209, 1, "🧆", 0),
         ("Curries", "Butter Chicken", "Creamy tomato gravy with tender chicken", 289, 0, "🍛", 1),
         ("Curries", "Dal Makhani", "Overnight-simmered black lentils", 189, 1, "🍲", 0),
         ("Curries", "Paneer Butter Masala", "Rich, mildly sweet gravy", 239, 1, "🧈", 0),
         ("Breads", "Butter Naan", "Soft and buttery", 45, 1, "🫓", 0),
         ("Breads", "Tandoori Roti", "Whole wheat, clay-oven baked", 15, 1, "🫓", 0)]},
    {"name": "Healthy Bowl", "cuisines": "Healthy, Salads, Juices",
     "emoji": "🥗", "color": "#56ab2f,#a8e063", "rating": 4.3, "time": 24, "cost": 350,
     "offer": "15% OFF", "veg": 1, "addr": "Bajaj Nagar",
     "items": [
         ("Bowls & Salads", "Quinoa Power Bowl", "Quinoa, chickpeas, veggies and tahini", 229, 1, "🥗", 1),
         ("Bowls & Salads", "Greek Salad", "Feta, olives, cucumber and tomato", 199, 1, "🥗", 0),
         ("Bowls & Salads", "Paneer Protein Bowl", "Grilled paneer, brown rice, greens", 249, 1, "🥙", 0),
         ("Wraps", "Hummus Veggie Wrap", "Whole wheat wrap with hummus", 159, 1, "🌯", 0),
         ("Juices & Smoothies", "Fresh Orange Juice", "No sugar added", 99, 1, "🍊", 0),
         ("Juices & Smoothies", "Green Detox Juice", "Spinach, apple, cucumber", 119, 1, "🥤", 0),
         ("Juices & Smoothies", "Banana Almond Smoothie", "Thick and filling", 139, 1, "🍌", 1)]},
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def q(sql, args=(), one=False):
    rows = get_db().execute(sql, args).fetchall()
    if one:
        return rows[0] if rows else None
    return rows


def run(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    if db.execute("SELECT COUNT(*) FROM restaurants").fetchone()[0] == 0:
        for r in SEED:
            cur = db.execute(
                "INSERT INTO restaurants(name,cuisines,emoji,color,rating,delivery_time,"
                "cost_for_two,offer,is_veg,address) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (r["name"], r["cuisines"], r["emoji"], r["color"], r["rating"],
                 r["time"], r["cost"], r["offer"], r["veg"], r["addr"]))
            for it in r["items"]:
                db.execute(
                    "INSERT INTO menu_items(restaurant_id,category,name,description,"
                    "price,is_veg,emoji,bestseller) VALUES(?,?,?,?,?,?,?,?)",
                    (cur.lastrowid,) + it)
    if not db.execute("SELECT 1 FROM users WHERE is_admin=1").fetchone():
        db.execute("INSERT INTO users(name,email,phone,password,is_admin) VALUES(?,?,?,?,1)",
                   ("Soni Admin", "admin@foodbysoni.com", "9999999999",
                    generate_password_hash("admin123")))
    db.commit()
    db.close()


# ------------------------------------------------------------------- helpers
@app.before_request
def load_user():
    uid = session.get("uid")
    g.user = q("SELECT * FROM users WHERE id=?", (uid,), one=True) if uid else None


@app.context_processor
def inject_globals():
    cart = session.get("cart", {})
    return {"current_user": g.get("user"), "cart": cart,
            "cart_count": sum(cart.values())}


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not g.user:
            flash("Please log in to continue.", "info")
            return redirect(url_for("login", next=request.path))
        return fn(*a, **kw)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not g.user or not g.user["is_admin"]:
            abort(403)
        return fn(*a, **kw)
    return wrapper


def cart_details():
    cart = session.get("cart", {})
    rid = session.get("cart_restaurant")
    lines, subtotal = [], 0
    if cart:
        ids = [int(k) for k in cart]
        marks = ",".join("?" * len(ids))
        for r in q(f"SELECT * FROM menu_items WHERE id IN ({marks}) ORDER BY id", ids):
            qty = cart[str(r["id"])]
            lines.append({"item": r, "qty": qty, "line": r["price"] * qty})
            subtotal += r["price"] * qty
    restaurant = (q("SELECT * FROM restaurants WHERE id=?", (rid,), one=True)
                  if rid and lines else None)
    delivery = 0 if (subtotal == 0 or subtotal >= 399) else 35
    platform = 5 if subtotal else 0
    tax = round(subtotal * 0.05, 2)
    discount, code = 0, session.get("coupon")
    if code:
        c = COUPONS.get(code)
        if c and subtotal >= c["min"]:
            if c["type"] == "percent":
                discount = min(round(subtotal * c["value"] / 100), c["max"])
            else:
                discount = delivery
        else:
            session.pop("coupon", None)
            code = None
    total = round(subtotal + delivery + platform + tax - discount, 2)
    return {"lines": lines, "restaurant": restaurant, "subtotal": subtotal,
            "delivery": delivery, "platform": platform, "tax": tax,
            "discount": discount, "coupon": code, "total": total}


def effective_status(o):
    """Auto-progress an order over time (demo speed) unless admin set it manually."""
    if o["manual"] or o["status"] == "Cancelled":
        return o["status"]
    elapsed = (datetime.now() - datetime.strptime(o["created_at"], "%Y-%m-%d %H:%M:%S")).total_seconds()
    if elapsed < 30:
        return "Placed"
    if elapsed < 120:
        return "Preparing"
    if elapsed < 240:
        return "Out for Delivery"
    return "Delivered"


def order_view(o):
    d = dict(o)
    d["status"] = effective_status(o)
    d["stage"] = STAGES.index(d["status"]) if d["status"] in STAGES else -1
    d["code"] = f"FBS{1000 + o['id']}"
    d["partner"] = PARTNERS[o["id"] % len(PARTNERS)]
    return d


# -------------------------------------------------------------------- public
@app.route("/")
def index():
    search = request.args.get("q", "").strip()
    cuisine = request.args.get("cuisine", "").strip()
    veg = request.args.get("veg")
    sort = request.args.get("sort", "relevance")
    sql, args = "SELECT * FROM restaurants WHERE 1=1", []
    if search:
        like = f"%{search}%"
        sql += (" AND (name LIKE ? OR cuisines LIKE ? OR id IN "
                "(SELECT restaurant_id FROM menu_items WHERE name LIKE ?))")
        args += [like, like, like]
    if cuisine:
        sql += " AND cuisines LIKE ?"
        args.append(f"%{cuisine}%")
    if veg:
        sql += " AND is_veg=1"
    order = {"rating": "rating DESC", "time": "delivery_time ASC",
             "cost": "cost_for_two ASC"}.get(sort, "rating DESC")
    sql += f" ORDER BY is_open DESC, {order}"
    return render_template("index.html", restaurants=q(sql, args), search=search,
                           cuisine=cuisine, veg=veg, sort=sort, cuisines=CUISINES)


@app.route("/restaurant/<int:rid>")
def restaurant(rid):
    r = q("SELECT * FROM restaurants WHERE id=?", (rid,), one=True)
    if not r:
        abort(404)
    menu = {}
    for it in q("SELECT * FROM menu_items WHERE restaurant_id=? ORDER BY id", (rid,)):
        menu.setdefault(it["category"], []).append(it)
    return render_template("restaurant.html", r=r, menu=menu,
                           subtotal=cart_details()["subtotal"])


# ---------------------------------------------------------------------- cart
@app.route("/cart")
def cart_page():
    return render_template("cart.html", det=cart_details(), coupons=COUPONS)


@app.route("/cart/change", methods=["POST"])
def cart_change():
    d = request.get_json(force=True, silent=True) or {}
    item = q("SELECT * FROM menu_items WHERE id=?", (int(d.get("item_id", 0)),), one=True)
    if not item:
        return jsonify(error="Item not found"), 404
    delta = int(d.get("delta", 1))
    cart = session.get("cart", {})
    if delta > 0:
        rest = q("SELECT is_open FROM restaurants WHERE id=?", (item["restaurant_id"],), one=True)
        if not rest["is_open"]:
            return jsonify(error="This restaurant is closed right now"), 400
        if cart and session.get("cart_restaurant") != item["restaurant_id"]:
            if not d.get("replace"):
                return jsonify(conflict=True,
                               message="Your cart has items from another restaurant. "
                                       "Clear it and add this item?")
            cart = {}
    key = str(item["id"])
    qty = max(0, min(20, cart.get(key, 0) + delta))
    if qty:
        cart[key] = qty
    else:
        cart.pop(key, None)
    session["cart"] = cart
    session["cart_restaurant"] = item["restaurant_id"] if cart else None
    session.modified = True
    return jsonify(ok=True, qty=qty, count=sum(cart.values()),
                   subtotal=cart_details()["subtotal"])


@app.route("/cart/clear", methods=["POST"])
def cart_clear():
    session.pop("cart", None)
    session.pop("cart_restaurant", None)
    session.pop("coupon", None)
    return redirect(url_for("cart_page"))


@app.route("/cart/coupon", methods=["POST"])
def cart_coupon():
    if request.form.get("remove"):
        session.pop("coupon", None)
        flash("Coupon removed.", "info")
        return redirect(url_for("cart_page"))
    code = request.form.get("code", "").strip().upper()
    c = COUPONS.get(code)
    sub = cart_details()["subtotal"]
    if not c:
        flash("Invalid coupon code.", "error")
    elif sub < c["min"]:
        flash(f"Add items worth ₹{c['min'] - sub} more to use {code}.", "error")
    else:
        session["coupon"] = code
        flash(f"Coupon {code} applied!", "success")
    return redirect(url_for("cart_page"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    det = cart_details()
    if not det["lines"]:
        flash("Your cart is empty.", "info")
        return redirect(url_for("index"))
    if request.method == "POST":
        address = request.form.get("address", "").strip()
        phone = request.form.get("phone", "").strip()
        payment = request.form.get("payment", "cod")
        note = request.form.get("note", "").strip()
        if len(address) < 10:
            flash("Please enter a complete delivery address.", "error")
        elif not (phone.isdigit() and len(phone) == 10):
            flash("Enter a valid 10-digit phone number.", "error")
        elif payment not in PAYMENTS:
            flash("Choose a payment method.", "error")
        else:
            oid = run(
                "INSERT INTO orders(user_id,restaurant_id,subtotal,delivery_fee,platform_fee,"
                "tax,discount,total,coupon,address,phone,payment,note,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (g.user["id"], det["restaurant"]["id"], det["subtotal"], det["delivery"],
                 det["platform"], det["tax"], det["discount"], det["total"], det["coupon"],
                 address, phone, PAYMENTS[payment], note,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            for l in det["lines"]:
                run("INSERT INTO order_items(order_id,item_id,name,price,qty) VALUES(?,?,?,?,?)",
                    (oid, l["item"]["id"], l["item"]["name"], l["item"]["price"], l["qty"]))
            for k in ("cart", "cart_restaurant", "coupon"):
                session.pop(k, None)
            flash("Order placed successfully! 🎉", "success")
            return redirect(url_for("track", oid=oid))
    return render_template("checkout.html", det=det, payments=PAYMENTS)


# -------------------------------------------------------------------- orders
def own_order(oid):
    o = q("SELECT * FROM orders WHERE id=?", (oid,), one=True)
    if not o or (o["user_id"] != g.user["id"] and not g.user["is_admin"]):
        abort(404)
    return o


@app.route("/orders")
@login_required
def orders():
    rows = q("SELECT o.*, r.name AS rname, r.emoji AS remoji FROM orders o "
             "JOIN restaurants r ON r.id=o.restaurant_id WHERE o.user_id=? "
             "ORDER BY o.id DESC", (g.user["id"],))
    out = []
    for o in rows:
        d = order_view(o)
        d["rname"], d["remoji"] = o["rname"], o["remoji"]
        its = q("SELECT * FROM order_items WHERE order_id=?", (o["id"],))
        d["summary"] = ", ".join(f"{i['qty']} x {i['name']}" for i in its)
        out.append(d)
    return render_template("orders.html", orders=out)


@app.route("/track/<int:oid>")
@login_required
def track(oid):
    o = own_order(oid)
    rest = q("SELECT * FROM restaurants WHERE id=?", (o["restaurant_id"],), one=True)
    its = q("SELECT * FROM order_items WHERE order_id=?", (oid,))
    return render_template("track.html", o=order_view(o), r=rest, items=its, stages=STAGES)


@app.route("/api/order/<int:oid>/status")
@login_required
def order_status(oid):
    d = order_view(own_order(oid))
    return jsonify(status=d["status"], stage=d["stage"])


@app.route("/reorder/<int:oid>", methods=["POST"])
@login_required
def reorder(oid):
    o = own_order(oid)
    cart = {}
    for i in q("SELECT * FROM order_items WHERE order_id=?", (oid,)):
        if i["item_id"] and q("SELECT 1 FROM menu_items WHERE id=?", (i["item_id"],), one=True):
            cart[str(i["item_id"])] = i["qty"]
    session["cart"], session["cart_restaurant"] = cart, o["restaurant_id"]
    flash("Items added to your cart.", "success")
    return redirect(url_for("cart_page"))


# ---------------------------------------------------------------------- auth
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        pw = request.form.get("password", "")
        if not name or "@" not in email or len(pw) < 6:
            flash("Enter your name, a valid email and a password of 6+ characters.", "error")
        elif q("SELECT 1 FROM users WHERE email=?", (email,), one=True):
            flash("This email is already registered. Please log in.", "error")
        else:
            uid = run("INSERT INTO users(name,email,phone,password) VALUES(?,?,?,?)",
                      (name, email, phone, generate_password_hash(pw)))
            session["uid"] = uid
            flash(f"Welcome to Food by Soni, {name.split()[0]}! Try code WELCOME50.", "success")
            return redirect(url_for("index"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        u = q("SELECT * FROM users WHERE email=?", (email,), one=True)
        if u and check_password_hash(u["password"], request.form.get("password", "")):
            session["uid"] = u["id"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("index"))
        flash("Wrong email or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# --------------------------------------------------------------------- admin
@app.route("/admin")
@login_required
@admin_required
def admin():
    rows = q("SELECT o.*, r.name AS rname, u.name AS uname FROM orders o "
             "JOIN restaurants r ON r.id=o.restaurant_id JOIN users u ON u.id=o.user_id "
             "ORDER BY o.id DESC LIMIT 50")
    orders_ = []
    for o in rows:
        d = order_view(o)
        d["rname"], d["uname"] = o["rname"], o["uname"]
        orders_.append(d)
    stats = {
        "orders": q("SELECT COUNT(*) c FROM orders", one=True)["c"],
        "revenue": q("SELECT COALESCE(SUM(total),0) s FROM orders WHERE status!='Cancelled'", one=True)["s"],
        "users": q("SELECT COUNT(*) c FROM users WHERE is_admin=0", one=True)["c"],
        "restaurants": q("SELECT COUNT(*) c FROM restaurants", one=True)["c"],
    }
    return render_template("admin.html", orders=orders_, stats=stats,
                           restaurants=q("SELECT * FROM restaurants ORDER BY id"),
                           statuses=STAGES + ["Cancelled"])


@app.route("/admin/order/<int:oid>", methods=["POST"])
@login_required
@admin_required
def admin_order(oid):
    s = request.form.get("status")
    if s == "Auto":
        run("UPDATE orders SET manual=0, status='Placed' WHERE id=?", (oid,))
    elif s in STAGES + ["Cancelled"]:
        run("UPDATE orders SET manual=1, status=? WHERE id=?", (s, oid))
    flash(f"Order FBS{1000 + oid} updated.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/restaurant/<int:rid>/toggle", methods=["POST"])
@login_required
@admin_required
def admin_toggle(rid):
    run("UPDATE restaurants SET is_open = 1 - is_open WHERE id=?", (rid,))
    return redirect(url_for("admin"))


@app.route("/admin/menu", methods=["POST"])
@login_required
@admin_required
def admin_menu():
    f = request.form
    try:
        run("INSERT INTO menu_items(restaurant_id,category,name,description,price,is_veg,emoji) "
            "VALUES(?,?,?,?,?,?,?)",
            (int(f["restaurant_id"]), f["category"].strip() or "Specials", f["name"].strip(),
             f.get("description", "").strip(), int(f["price"]),
             1 if f.get("is_veg") else 0, f.get("emoji", "🍽️").strip() or "🍽️"))
        flash("Menu item added.", "success")
    except (KeyError, ValueError):
        flash("Fill all required fields correctly.", "error")
    return redirect(url_for("admin"))


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
