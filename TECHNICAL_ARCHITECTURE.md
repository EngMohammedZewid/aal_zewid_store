# 🏬 StoreManagerPro - Technical Architecture & Deep Dive

**Version:** 1.0.0  
**Last Updated:** 2026-08-02  
**Language:** Python 3.x with Tkinter & SQLite3

---

## 📋 Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Technology Stack](#technology-stack)
4. [Database Layer](#database-layer)
5. [Application Layer](#application-layer)
6. [User Interface Structure](#user-interface-structure)
7. [Data Flow & State Management](#data-flow--state-management)
8. [Core Modules & Responsibilities](#core-modules--responsibilities)
9. [Business Logic & Algorithms](#business-logic--algorithms)
10. [Integration Points](#integration-points)

---

## Executive Summary

**StoreManagerPro** is a comprehensive **desktop Point-of-Sale (POS) and Inventory Management System** designed for retail store operators in Arabic-speaking markets. The application implements a **three-tier architecture** consisting of:

- **Presentation Layer:** Native desktop GUI built with Python's Tkinter framework with full RTL (Right-to-Left) Arabic support
- **Business Logic Layer:** Core database operations, calculations, and state management
- **Data Persistence Layer:** SQLite3 embedded database with relational schema supporting ACID transactions

The application is **standalone**, requires **no internet connectivity**, and operates entirely on the local machine with data stored in a single SQLite database file (`store.db`), ensuring 100% data privacy and security.

---

## System Architecture

### 3-Tier Architecture Diagram

```
┌────────────────────────────────────────────────────────────┐
│                   PRESENTATION LAYER                       │
│              (Tkinter Desktop GUI - RTL/LTR)              │
│  ┌──────────────┬──────────────┬──────────────────────┐   │
│  │ Dashboard    │ POS/Checkout │ Inventory Manager    │   │
│  │ Analytics    │ Customer Mgr  │ Suppliers Manager    │   │
│  └──────────────┴──────────────┴──────────────────────┘   │
└────────────────────────────────────────────────────────────┘
                            ↕
┌────────────────────────────────────────────────────────────┐
│                BUSINESS LOGIC LAYER                         │
│         (Core DB Operations, Calculations, Validation)     │
│  ┌──────────────┬──────────────┬──────────────────────┐   │
│  │ Sales Engine │ Inventory Ops│ Report Generation    │   │
│  │ Cart Manager │ Stock Adjust │ Analytics Compute    │   │
│  └──────────────┴──────────────┴──────────────────────┘   │
└────────────────────────────────────────────────────────────┘
                            ↕
┌────────────────────────────────────────────────────────────┐
│              DATA PERSISTENCE LAYER                         │
│     (SQLite3 Database with Relational Schema)             │
│  store.db → 8 Tables | Foreign Keys | Constraints         │
└────────────────────────────────────────────────────────────┘
```

### Application Flow

1. **Initialization (`main.py`):**
   - Tkinter root window is created
   - Database initialization via `core.db.init_db()` occurs
   - Views are instantiated and cached in memory
   - Navigation between views happens via controller callback

2. **User Interaction:**
   - User clicks navigation button in sidebar
   - Controller calls `show_view(view_name)` 
   - Corresponding view frame is raised to top, old one is hidden
   - View calls `refresh_data()` to fetch latest data from database

3. **Data Modification:**
   - User performs action (add product, process sale, etc.)
   - Validation occurs client-side
   - Database operation is called from `core.db`
   - Success/error message returned to UI
   - View is refreshed to reflect changes

---

## Technology Stack

### Core Technologies

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **GUI Framework** | Python Tkinter | Built-in | Native desktop interface with TTK styling |
| **Database Engine** | SQLite3 | 3.x | Embedded relational database |
| **Data Visualization** | Matplotlib | ≥3.7.1 | Charts & graphs for analytics |
| **Packaging** | PyInstaller | ≥6.0.0 | Convert to standalone executable |
| **Language** | Python | 3.8+ | Core language |

### Key Features by Technology

**Tkinter:**
- Grid-based layout system with weight-based responsive design
- TTK (themed widgets) for modern styling
- Custom styles via `ttk.Style()` with color themes
- Treeview widget for tabular data
- Modal dialogs for user input
- Bindings for event handling (double-click, key press, etc.)

**SQLite3:**
- `sqlite3.Row` factory for dict-like column access
- Foreign key constraints enforced via `PRAGMA foreign_keys = ON`
- Transaction management with commit/rollback
- Connection pooling via `get_connection()` helper
- Query results cached in memory when needed

**Matplotlib:**
- Embedded in Tkinter via `FigureCanvasTkAgg`
- Bar charts for daily sales trends (7-day rolling)
- Horizontal bar charts for top 5 selling products
- Interactive figures with zoom/pan capabilities

---

## Database Layer

### SQLite3 Schema Overview

The database consists of **8 interconnected tables** with proper normalization and referential integrity:

```
┌─────────────────────────────────────────────────────┐
│                  DATABASE SCHEMA                     │
├─────────────────────────────────────────────────────┤
│                                                       │
│  MASTER TABLES (No FK)                              │
│  ├── categories (id, name, description)             │
│  ├── suppliers (id, name, contact, phone, email)    │
│  └── customers (id, name, phone, email, loyalty_pt) │
│                                                       │
│  PRODUCT INVENTORY                                  │
│  └── products (id, sku, name, category_id→,         │
│      cost_price, selling_price, stock_quantity,     │
│      reorder_level, supplier_id→)                   │
│                                                       │
│  SALES TRANSACTION TABLES (Time-Series)             │
│  ├── sales (id, sale_date, customer_id→,            │
│  │   total_amount, discount, tax_amount,            │
│  │   payment_method)                                 │
│  └── sale_items (id, sale_id→, product_id→,         │
│      quantity, unit_price, subtotal)                │
│                                                       │
│  PURCHASE ORDER TABLES (Supply Chain)               │
│  ├── purchase_orders (id, po_date, supplier_id→,    │
│  │   total_cost, status)                            │
│  └── purchase_order_items (id, po_id→,              │
│      product_id→, quantity, unit_cost)              │
│                                                       │
│  → indicates Foreign Key relationship               │
└─────────────────────────────────────────────────────┘
```

### Detailed Table Schemas

#### 1. **categories** - Product Classification
```sql
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,           -- Enforces unique category names
    description TEXT
);
```
**Purpose:** Organize products into logical groups (e.g., "ملابس وأزياء", "إلكترونيات")  
**Constraints:** Unique name prevents duplicate categories  
**Relationships:** Referenced by `products.category_id`

---

#### 2. **suppliers** - Vendor Information
```sql
CREATE TABLE suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_person TEXT,
    phone TEXT,
    email TEXT,
    address TEXT
);
```
**Purpose:** Maintain vendor directory for purchase orders and contact  
**Constraints:** No uniqueness constraints (allows multiple contact persons)  
**Relationships:** Referenced by `products.supplier_id` and `purchase_orders.supplier_id`

---

#### 3. **products** - Master Inventory Catalog
```sql
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT UNIQUE NOT NULL,            -- Stock Keeping Unit, unique barcode
    name TEXT NOT NULL,
    category_id INTEGER,
    cost_price REAL NOT NULL,            -- Wholesale/landed cost per unit
    selling_price REAL NOT NULL,         -- Retail price per unit
    stock_quantity INTEGER NOT NULL DEFAULT 0,  -- Current on-hand quantity
    reorder_level INTEGER NOT NULL DEFAULT 5,   -- Alert threshold
    supplier_id INTEGER,
    FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE SET NULL,
    FOREIGN KEY (supplier_id) REFERENCES suppliers (id) ON DELETE SET NULL
);
```
**Purpose:** Core product master data  
**Key Attributes:**
- `sku`: Barcode/product code for POS lookup
- `cost_price`: Used in COGS calculations for profitability
- `selling_price`: Price shown at checkout
- `stock_quantity`: Real-time inventory level (decremented on sale, incremented on PO receipt)
- `reorder_level`: Triggers low-stock alert in UI (orange highlight in Inventory View)

**Relationships:**
- `category_id` → `categories.id` (many-to-one)
- `supplier_id` → `suppliers.id` (many-to-one)

---

#### 4. **customers** - Loyalty Program & Contact Registry
```sql
CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT UNIQUE,                   -- Unique phone enforces no duplicates
    email TEXT,
    loyalty_points INTEGER DEFAULT 0     -- Points earned from purchases
);
```
**Purpose:** Customer profiles for loyalty rewards and contact  
**Key Attributes:**
- `loyalty_points`: Accumulated points (1 point per $10 spent, calculated in POS)
- `phone`: Used for searching customers and deduplication

**Special Record:** Default "عميل عام (نقدي)" (Generic Cash Customer) for anonymous transactions

---

#### 5. **sales** - Transaction Header (Transaction Master)
```sql
CREATE TABLE sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_date TEXT NOT NULL,             -- ISO format timestamp for queries
    customer_id INTEGER,                 -- NULL for anonymous/cash transactions
    total_amount REAL NOT NULL,          -- = SUM(sale_items.subtotal) + tax - discount
    discount REAL DEFAULT 0,             -- Additional discount ($) applied
    tax_amount REAL DEFAULT 0,           -- 8% VAT pre-calculated
    payment_method TEXT NOT NULL,        -- "كاش", "بطاقة ائتمان", "دفع إلكتروني", etc.
    FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE SET NULL
);
```
**Purpose:** Header record for each transaction  
**Key Attributes:**
- `sale_date`: Timestamp for daily aggregation in analytics
- `customer_id`: Links to loyalty program (can be NULL for walk-in customers)
- `total_amount`: Final invoice amount including tax and discount
- `payment_method`: Used for payment reconciliation and reporting

**Relationships:**
- `customer_id` → `customers.id` (many-to-one, optional)
- Referenced by `sale_items.sale_id` (one-to-many)

---

#### 6. **sale_items** - Transaction Line Items
```sql
CREATE TABLE sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,            -- Links to parent transaction
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,           -- Units sold
    unit_price REAL NOT NULL,            -- Price at time of sale
    subtotal REAL NOT NULL,              -- = quantity * unit_price
    FOREIGN KEY (sale_id) REFERENCES sales (id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE RESTRICT
);
```
**Purpose:** Line-item details for each product in a transaction  
**Key Attributes:**
- `unit_price`: Historical price (allows price changes without altering history)
- `subtotal`: Pre-calculated for query performance
- `quantity`: Units decremented from `products.stock_quantity`

**Cascade Rules:**
- `ON DELETE CASCADE` for `sale_id`: Deleting a sale removes all its line items
- `ON DELETE RESTRICT` for `product_id`: Prevents deletion of products with sales history

---

#### 7. **purchase_orders** - Supply Chain Orders
```sql
CREATE TABLE purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_date TEXT NOT NULL,               -- Order creation timestamp
    supplier_id INTEGER NOT NULL,
    total_cost REAL NOT NULL,            -- SUM of po_items cost
    status TEXT NOT NULL,                -- 'Pending', 'Received', 'Cancelled'
    FOREIGN KEY (supplier_id) REFERENCES suppliers (id) ON DELETE RESTRICT
);
```
**Purpose:** Track inbound inventory from suppliers  
**Key Attributes:**
- `status`: Workflow state ("معلق" → "تم الاستلام" → or "ملغى")
- `total_cost`: Budget tracking for procurement

**Relationships:**
- `supplier_id` → `suppliers.id` (many-to-one)
- Referenced by `purchase_order_items.po_id`

---

#### 8. **purchase_order_items** - Purchase Line Items
```sql
CREATE TABLE purchase_order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id INTEGER NOT NULL,              -- Links to parent PO
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,           -- Units ordered
    unit_cost REAL NOT NULL,             -- Cost per unit from supplier
    FOREIGN KEY (po_id) REFERENCES purchase_orders (id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE RESTRICT
);
```
**Purpose:** Individual product lines in purchase orders  
**Key Attributes:**
- `unit_cost`: Supplier price (may differ from current `products.cost_price`)
- `quantity`: Added to `products.stock_quantity` when PO status → "Received"

**Cascade Rules:**
- `ON DELETE CASCADE` for `po_id`: Deleting PO removes line items
- `ON DELETE RESTRICT` for `product_id`: Prevents orphaning ordered items

---

### Database Constraints & Integrity

| Constraint | Table | Type | Purpose |
|-----------|-------|------|---------|
| UNIQUE | categories.name | Column | No duplicate category names |
| UNIQUE | products.sku | Column | SKU is primary identifier for barcode scanning |
| UNIQUE | customers.phone | Column | Prevents duplicate customer registrations |
| FK + RESTRICT | products.category_id | Referential | Can't delete category with products |
| FK + RESTRICT | products.supplier_id | Referential | Can't delete supplier with products |
| FK + SET NULL | sales.customer_id | Referential | Anonymous sales allowed, customer delete nullifies link |
| FK + CASCADE | sale_items.sale_id | Referential | Delete sale deletes all items |
| FK + RESTRICT | sale_items.product_id | Referential | Preserve sales history integrity |
| FK + RESTRICT | purchase_orders.supplier_id | Referential | Can't delete supplier with POs |
| FK + CASCADE | purchase_order_items.po_id | Referential | Delete PO deletes line items |

---

### Database Initialization & Seeding

**File:** `core/db.py`

**Key Functions:**

```python
def init_db(db_path=DEFAULT_DB_PATH, seed_sample_data=True):
    # Creates schema if DB doesn't exist
    # Optionally loads sample/demo data on first run
```

**Sample Data Included:**
- 4 categories (ملابس, إلكترونيات, أدوات منزلية, مشروبات)
- 4 suppliers with contact details
- 9 sample products with varying stock levels (1 marked as low stock)
- 4 customers including generic cash customer
- 4 historical sales transactions
- 1 sample purchase order

**Database Reset Function:**
```python
def reset_db(db_path=DEFAULT_DB_PATH):
    # Drops all tables and recreates empty schema
    # Used for clean testing or data wipe
```

---

## Application Layer

### Core Database Operations (`core/db.py`)

The core module provides a **data abstraction layer** with helper functions for all common operations:

#### Connection Management
```python
def get_connection(db_path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row       # Dict-like access to columns
    conn.execute("PRAGMA foreign_keys = ON")  # Enable referential integrity
    return conn
```

**Pattern:** Each function opens connection, executes query, closes connection
**Design:** Prevents connection leaks via context cleanup

#### Query Functions (Selection)

| Function | SQL Operation | Returns |
|----------|--------------|---------|
| `get_all_products()` | SELECT with JOINs | List of product dicts |
| `get_low_stock_products()` | WHERE stock ≤ reorder_level | List of low-stock items |
| `search_products(query)` | LIKE on name/sku/category | Search results |
| `get_all_customers()` | SELECT * FROM customers | All customer records |
| `get_all_suppliers()` | SELECT * FROM suppliers | All supplier records |
| `get_all_categories()` | SELECT * FROM categories | All categories |
| `get_recent_sales(limit=10)` | ORDER BY sale_date DESC | Recent transactions |
| `get_sale_details(sale_id)` | JOIN with sale_items | Line items of sale |
| `get_dashboard_summary()` | Multiple aggregate queries | KPI metrics |
| `get_sales_chart_data()` | GROUP BY DATE(sale_date) | Daily revenue (7 days) |
| `get_top_selling_products_data()` | GROUP BY product_id | Top 5 products |

#### Mutation Functions (Create/Update/Delete)

| Function | Operation | Returns |
|----------|-----------|---------|
| `add_product(...)` | INSERT INTO products | (bool success, str message) |
| `update_product(product_id, ...)` | UPDATE products | (bool success, str message) |
| `delete_product(product_id)` | DELETE FROM products | (bool success, str message) |
| `adjust_stock(product_id, delta)` | UPDATE stock_quantity | (bool, message) |
| `add_customer(name, phone, email)` | INSERT INTO customers | (bool, message) |
| `add_category(name, description)` | INSERT INTO categories | (bool, message) |
| `record_sale(customer_id, items[], discount, payment)` | Transaction INSERT | (bool, message, sale_id) |
| `add_purchase_order(supplier_id, items[])` | INSERT PO + PO items | (bool, message, po_id) |
| `receive_purchase_order(po_id)` | UPDATE PO status + stock | (bool, message) |

#### Transaction-Based Operations

**Key Example: `record_sale()` - Atomic Sales Recording**

```python
def record_sale(customer_id, sale_items_list, discount, tax, payment_method):
    """
    Atomic transaction:
    1. INSERT into sales (header)
    2. INSERT into sale_items (line items)
    3. UPDATE products.stock_quantity (decrement inventory)
    4. UPDATE customers.loyalty_points (if customer exists)
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Get sale_id from INSERT
        cursor.execute("INSERT INTO sales (...) VALUES (...)")
        sale_id = cursor.lastrowid
        
        # Insert each line item
        for item in sale_items_list:
            cursor.execute("INSERT INTO sale_items (...)")
            # Decrement stock
            cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ?
                          WHERE id = ?", (item['qty'], item['product_id']))
        
        # Award loyalty points if customer exists
        if customer_id and customer_id != 1:  # Skip generic customer
            points_earned = int(total_amount / 10)
            cursor.execute("UPDATE customers SET loyalty_points = 
                          loyalty_points + ? WHERE id = ?", (points_earned, customer_id))
        
        conn.commit()
        return True, "تمت العملية بنجاح", sale_id
    except Exception as e:
        conn.rollback()
        return False, f"خطأ: {str(e)}", None
    finally:
        conn.close()
```

**Guarantees:**
- All-or-nothing atomicity (commit or rollback)
- Stock never becomes inconsistent with sales
- Loyalty points only awarded for named customers
- Error messages returned to UI for user feedback

---

## User Interface Structure

### Main Application Window (`main.py`)

**Class:** `StoreManagerApp(tk.Tk)`

**Responsibilities:**
- Root window configuration (1280x800, resizable)
- Theme styling via `ttk.Style()` configuration
- Sidebar navigation with button callbacks
- View management (instantiation, caching, display toggling)

**Layout Grid:**
```
┌───────────────────────────────────┬──────────┐
│                                   │ SIDEBAR  │
│         CONTENT CONTAINER         │ (Col 1)  │
│         (Col 0, weight=1)         │ width=230│
│                                   │          │
│   ┌─ DashboardView (visible)     │ BTN: 📊  │
│   ├─ POSView       (hidden)       │ BTN: 🛒  │
│   ├─ InventoryView (hidden)       │ BTN: 📦  │
│   ├─ SuppliersView (hidden)       │ BTN: 🚚  │
│   ├─ CustomersView (hidden)       │ BTN: 👥  │
│   └─ AnalyticsView (hidden)       │ BTN: 📈  │
│                                   │          │
└───────────────────────────────────┴──────────┘
```

**Navigation Mechanism:**
- Sidebar buttons trigger `controller.show_view(view_name)`
- Selected view frame raised to top via `.tkraise()`
- All views pre-loaded in memory for instant switching
- Current view receives `refresh_data()` call on activation

**Styling Theme:**
- Background: `#1e293b` (dark slate)
- Text: `#0f172a` (near-black)
- Accent: `#2563eb` (blue), `#16a34a` (green), `#dc2626` (red)
- Treeview selected row: `#eff6ff` (light blue)

---

### View Architecture

Each view is a subclass of `tk.Frame` with lifecycle:

```python
class ViewName(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f1f5f9")
        self.controller = controller  # Reference to root for navigation
        self._build_ui()              # Construct all widgets
        self.refresh_data()           # Load initial data
    
    def refresh_data(self):
        # Called on view activation
        # Fetch fresh data from database
        # Populate tables/widgets
```

---

### Dashboard View (`ui/dashboard_view.py`)

**Purpose:** Executive summary and quick actions

**Components:**

1. **Header with Quick Actions**
   - Button: "📦 إضافة منتج جديد" → Navigates to InventoryView
   - Button: "🛒 بدء عملية بيع" → Navigates to POSView

2. **KPI Metric Cards (4 columns)**
   - 📊 Sales Today (aggregated from today's transactions)
   - 📦 Total Products (product count)
   - ⚠️ Low Stock Alerts (count of stock_quantity ≤ reorder_level)
   - 💰 Inventory Value (Σ stock_quantity × selling_price)

3. **Recent Sales Table (Treeview)**
   - Columns: Transaction ID, Date/Time, Customer Name, Amount, Payment Method
   - Double-click to open receipt modal showing line items
   - Automatically sorted by date descending
   - Scrollbar for large datasets

**Data Flow:**
```python
refresh_data() 
  → get_dashboard_summary() 
  → get_recent_sales(limit=10)
  → Update metric labels
  → Populate treeview
```

---

### POS (Point of Sale) View (`ui/pos_view.py`)

**Purpose:** Fast checkout and invoice generation

**Layout (RTL):** 2-column grid
- **Right Panel (Col 1, weight 6):** Product Catalog
- **Left Panel (Col 0, weight 4):** Shopping Cart & Checkout

**Right Panel - Product Catalog:**
- Search bar (Real-time filtering via `<KeyRelease>` event)
- Treeview: SKU | Product Name | Selling Price
- Double-click or Enter to add to cart
- Live search on SKU, name, category

**Left Panel - Shopping Cart:**
1. Customer selector (Combobox + "Add New" button)
2. Active cart Treeview: Product Name | Quantity | Unit Price | Subtotal
3. Cart action buttons:
   - ➕ Increment quantity
   - ➖ Decrement quantity
   - 🗑️ Remove item
   - Clear all

4. Checkout Section (Blue summary box):
   - Subtotal (Σ line items)
   - Tax (8% auto-calculated: subtotal × 0.08)
   - Additional discount (manual entry field)
   - **Final Total** = subtotal + tax - discount
   - Payment method selector (Combobox: Cash, Credit, E-payment)
   - **PROCESS SALE** button (Green, large)

**State Management:**
```python
self.cart = [
    {
        'product_id': int,
        'sku': str,
        'name': str,
        'quantity': int,
        'unit_price': float,
        'subtotal': float
    },
    ...
]
```

**Key Methods:**
- `_add_selected_to_cart()`: Extract selection, find product, add to cart list, update UI
- `_adjust_cart_qty(delta)`: Modify quantity of selected cart item
- `_update_totals()`: Recalculate subtotal, tax, final total in real-time
- `_process_sale()`: Validate cart, call `record_sale()`, print receipt, clear cart

**Business Logic:**
- Inventory decremented on sale confirmation (not during browse)
- Loyalty points awarded if non-generic customer selected
- Tax hardcoded at 8% (VAT rate)
- Discount applied as flat amount (not percentage)

---

### Inventory View (`ui/inventory_view.py`)

**Purpose:** Master product catalog management

**Components:**

1. **Header with Actions**
   - Button: "+ إضافة منتج جديد" → Add product modal
   - Button: "🏷️ إدارة التصنيفات" → Category management modal
   - Button: "⚠️ نواقص المخزون" → Filter to low-stock items only

2. **Search & Filter Bar**
   - Text search (live, searches name/SKU/category)
   - Category dropdown filter (multi-select logic: "All" or single)
   - Reset button

3. **Products Table (Treeview - 9 columns)**
   ```
   ID | SKU | Name | Category | Supplier | Cost Price | Selling Price | Stock | Reorder Level
   ```
   - Conditional coloring: If `stock ≤ reorder_level` → Orange background (#fef3c7)
   - Numeric formatting: Prices with 2 decimals and thousands separator

4. **Bottom Action Buttons**
   - ✏️ Edit Selected Product
   - 📦 Quick Stock Adjustment
   - 🗑️ Delete Selected

**Modal Dialogs:**

**Add Product Modal:**
```
Form Fields:
├─ SKU (Text) - UNIQUE constraint validated
├─ Product Name (Text)
├─ Category (Dropdown) - Existing categories
├─ Cost Price (Float)
├─ Selling Price (Float)
├─ Initial Stock Quantity (Int)
├─ Reorder Level (Int) - Threshold for alerts
└─ Supplier (Dropdown)

Buttons: [Save] [Cancel]
```

**Edit Product Modal:**
```
Same form, pre-populated with current values
On save: UPDATE products WHERE id = ?
```

**Quick Stock Adjustment Modal:**
```
Simple dialog:
├─ Product Name (Display only)
├─ Current Stock (Display only)
├─ New Stock Quantity (Input)
└─ [Apply] [Cancel]

On apply: UPDATE products.stock_quantity directly
```

**Category Management Modal:**
```
List of existing categories (Treeview):
├─ Add new category
├─ Delete selected
└─ [OK] [Cancel]
```

**Data Flow:**
```
refresh_data()
  → get_all_categories()
  → get_all_suppliers()
  → get_all_products()  (with JOINs for names)
  → _populate_tree()
```

---

### Suppliers View (`ui/suppliers_view.py`)

**Purpose:** Manage vendors and procurement

**Components:**

1. **Suppliers List (Treeview)**
   - Columns: ID | Name | Contact Person | Phone | Email | Address
   - Select supplier to view/edit details

2. **Action Buttons**
   - Add new supplier
   - Edit selected
   - Delete selected

3. **Purchase Orders Section**
   - New PO button (links to supplier selection)
   - Active POs table: PO ID | Supplier | Date | Amount | Status
   - PO detail view: Line items with products/quantities/costs
   - Receive PO button: Mark as received (triggers stock increment)

**Business Logic:**
- When PO status changes to "Received":
  - For each `purchase_order_items` entry:
    - `UPDATE products.stock_quantity += item.quantity`
  - Mark PO.status = "Received"
  - Record timestamp

**New PO Form:**
```
├─ Supplier (Dropdown)
├─ PO Date (Auto-timestamp)
├─ Add Line Items (Table):
│  └─ Product | Quantity | Unit Cost
├─ Calculate Total Cost (Σ quantity × unit_cost)
└─ [Create PO] [Cancel]
```

---

### Customers View (`ui/customers_view.py`)

**Purpose:** Loyalty program management and customer history

**Components:**

1. **Customers List (Treeview)**
   - Columns: ID | Name | Phone | Email | Loyalty Points
   - Double-click for customer detail/transaction history

2. **Action Buttons**
   - Add new customer
   - Edit selected
   - Delete selected

3. **Customer Detail Modal**
   - Display all fields
   - Show order history (sales linked to this customer)
   - Display total spent, loyalty points earned
   - Allow point adjustments (manual corrections)

**Data Flow:**
```
Double-click customer
  → get_customer_sales(customer_id)
  → Display transaction history
  → Calculate total spent, points
  → Show detail modal
```

---

### Analytics View (`ui/analytics_view.py`)

**Purpose:** Financial reporting and business intelligence

**Components:**

1. **Financial Summary Cards (4 columns)**
   - 💰 Total Revenue (Σ sales.total_amount)
   - 📊 COGS - Cost of Goods Sold (Σ quantity × cost_price for all sold items)
   - 🟢 Gross Profit (Revenue - COGS)
   - 📈 Profit Margin % (Gross Profit / Revenue × 100)

2. **Charts Section (2-column layout)**

   **Left: Daily Sales Chart (Bar Chart)**
   - X-axis: Last 7 days (dates)
   - Y-axis: Revenue ($)
   - Bar height: SUM of daily sales
   - Query: `GROUP BY DATE(sale_date) ORDER BY date DESC LIMIT 7`

   **Right: Top Selling Products (Horizontal Bar Chart)**
   - Y-axis: Top 5 product names
   - X-axis: Units sold
   - Query: `GROUP BY product_id, SUM(quantity) LIMIT 5`

3. **Export Button**
   - "📥 Export Report (CSV)"
   - Generates file: `sales_report_{timestamp}.csv`
   - Encoding: UTF-8-SIG (for Arabic text in Excel)
   - Columns: Invoice# | Date | Customer | Amount | Tax | Discount | Payment Method

**Chart Implementation:**
```python
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

figure = Figure(figsize=(5, 4), dpi=100)
axis = figure.add_subplot(111)
axis.bar(dates, revenues)
axis.set_title("إيرادات أخر 7 أيام")

canvas = FigureCanvasTkAgg(figure, master=chart_frame)
canvas.draw()
canvas.get_tk_widget().pack(fill="both", expand=True)
```

**Profit Calculation Logic:**
```
Total Revenue = SUM(sales.total_amount)
COGS = SUM(sale_items.quantity × products.cost_price) for all line items
Gross Profit = Revenue - COGS
Profit Margin = (Gross Profit / Revenue) × 100%
```

---

## Data Flow & State Management

### Typical User Journey: Processing a Sale

```
1. USER INITIATES SALE
   └─ Click "🛒 بدء عملية بيع" button
      → Controller calls show_view("POSView")
      → POSView.refresh_data() executes
         └─ get_all_products() → populate product catalog
         └─ get_all_customers() → populate customer dropdown

2. USER SEARCHES & SELECTS PRODUCTS
   └─ Type in search box (KeyRelease event)
      → _filter_products() filters catalog live
   └─ Double-click product row
      → _add_selected_to_cart()
         └─ Find product in self.products_list
         └─ Append to self.cart list
         └─ Insert into cart Treeview
         └─ _update_totals() recalculates running sum

3. USER ADJUSTS CART
   └─ Click ➕➖🗑️ buttons
      → _adjust_cart_qty(delta) modifies self.cart
      → _update_totals() recalculates
      → Cart Treeview refreshed

4. USER APPLIES DISCOUNT & SELECTS PAYMENT
   └─ Type discount amount in field
      → _update_totals() invoked on KeyRelease
         └─ Final Total = subtotal + tax - discount
   └─ Select payment method from dropdown

5. USER COMPLETES SALE
   └─ Click "تأكيد العملية" button
      → Validation checks:
         ├─ Cart not empty?
         ├─ Discount not negative?
         └─ Payment method selected?
      → Call record_sale(customer_id, self.cart, discount, tax, payment)
         └─ Transaction in DB:
            ├─ INSERT sales record
            ├─ INSERT sale_items (one per product)
            ├─ UPDATE products.stock_quantity for each item (decrement)
            └─ UPDATE customers.loyalty_points if applicable
      → Receive sale_id and success message
      → Show receipt modal with invoice details
      → Clear cart for next transaction
      → Optionally print receipt (if printer configured)

6. DASHBOARD REFLECTS CHANGES
   └─ User navigates to Dashboard
      → refresh_data() executes
      → get_dashboard_summary() now includes new sale
      → KPI metrics updated
      → Recent sales table shows new transaction
```

### State Management Pattern

**No Global State:**
- Each view maintains its own local state (`self.cart`, `self.products_list`, etc.)
- Database is single source of truth
- On view activation, `refresh_data()` fetches latest from DB

**Singleton Pattern - Database Connection:**
- `get_connection()` opens new connection each time
- No persistent connection pool
- Avoids concurrency issues in single-threaded Tkinter app

**Event-Driven Updates:**
- Treeview update: Manual via `tree.insert()`, `tree.delete()`, `tree.tag_configure()`
- Label update: Direct via `.config(text=new_value)`
- Combobox: Rebuilt via `.config(values=new_list)`

---

## Core Modules & Responsibilities

### Module Dependency Graph

```
main.py (StoreManagerApp)
│
├─→ core/db.py
│   ├─ get_connection()
│   ├─ init_db()
│   ├─ All query/mutation functions
│   └─ SQLite3 schema & triggers
│
├─→ ui/dashboard_view.py
│   └─ Imports: core.db functions
│
├─→ ui/pos_view.py
│   └─ Imports: core.db.get_all_products, get_all_customers, record_sale, add_customer
│
├─→ ui/inventory_view.py
│   └─ Imports: core.db.get_all_products, get_all_categories, add/update/delete_product, adjust_stock
│
├─→ ui/suppliers_view.py
│   └─ Imports: core.db.get_all_suppliers, get_all_products, add_purchase_order, receive_purchase_order
│
├─→ ui/customers_view.py
│   └─ Imports: core.db.get_all_customers, get_customer_sales, add_customer, update_customer
│
└─→ ui/analytics_view.py
    └─ Imports: core.db.get_sales_chart_data, get_top_selling_products_data, get_connection (raw SQL)
```

### `core/db.py` - Database Abstraction Layer

**Exports:**
- Connection: `get_connection()`
- Initialization: `init_db()`, `reset_db()`
- Products: `get_all_products()`, `search_products()`, `add_product()`, `update_product()`, `delete_product()`, `adjust_stock()`, `get_low_stock_products()`
- Customers: `get_all_customers()`, `add_customer()`, `update_customer()`, `delete_customer()`, `get_customer_sales()`
- Sales: `get_recent_sales()`, `get_sale_details()`, `record_sale()`
- Suppliers: `get_all_suppliers()`, `add_supplier()`, `update_supplier()`, `delete_supplier()`
- Purchase Orders: `add_purchase_order()`, `get_all_purchase_orders()`, `receive_purchase_order()`
- Categories: `get_all_categories()`, `add_category()`, `delete_category()`
- Analytics: `get_dashboard_summary()`, `get_sales_chart_data()`, `get_top_selling_products_data()`

**Error Handling:**
- Returns tuples: `(bool success, str message)` for mutations
- Raises exceptions for critical errors (caught by caller)
- Validates foreign key constraints
- Detects duplicate SKUs, phone numbers, etc.

---

## Business Logic & Algorithms

### 1. Inventory Management

**Stock Decrement on Sale:**
```python
# In record_sale() transaction
for item in sale_items_list:
    cursor.execute("""
        UPDATE products 
        SET stock_quantity = stock_quantity - ? 
        WHERE id = ?
    """, (item['quantity'], item['product_id']))
```
- Prevents overselling via atomic update
- If product becomes negative, transaction rolls back (error)

**Low Stock Alert:**
```python
# In inventory_view.py
WHERE stock_quantity <= reorder_level
```
- Compared at query time, not precomputed
- Efficient because reorder_level typically small (5-20 units)
- Orange highlight in Treeview triggers manual action

**Stock Increment on PO Receive:**
```python
def receive_purchase_order(po_id):
    # Get all line items for this PO
    cursor.execute("SELECT * FROM purchase_order_items WHERE po_id = ?", (po_id,))
    items = cursor.fetchall()
    
    # Increment stock for each product
    for item in items:
        cursor.execute("""
            UPDATE products 
            SET stock_quantity = stock_quantity + ? 
            WHERE id = ?
        """, (item['quantity'], item['product_id']))
    
    # Mark PO as received
    cursor.execute("UPDATE purchase_orders SET status = ? WHERE id = ?", 
                  ("Received", po_id))
    conn.commit()
```

---

### 2. Sales & Revenue Calculation

**Invoice Total Calculation:**
```
Subtotal = Σ (quantity × unit_price) for all line items
Tax Amount = Subtotal × 0.08  (8% VAT)
Final Total = Subtotal + Tax Amount - Discount
```

**Implemented in POS View:**
```python
def _update_totals(self):
    subtotal = sum(item['subtotal'] for item in self.cart)
    tax = subtotal * 0.08
    discount = float(self.ent_discount.get() or 0)
    final_total = subtotal + tax - discount
    
    self.lbl_subtotal.config(text=f"{subtotal:,.2f}")
    self.lbl_tax.config(text=f"{tax:,.2f}")
    self.lbl_final.config(text=f"{final_total:,.2f}")
```

**COGS (Cost of Goods Sold) Calculation:**
```sql
SELECT SUM(sale_items.quantity * products.cost_price)
FROM sale_items
JOIN products ON sale_items.product_id = products.id
WHERE sales.id IN (selected transactions)
```

**Profit Analysis:**
```
Gross Profit = Total Revenue - COGS
Profit Margin % = (Gross Profit / Total Revenue) × 100

Example:
Revenue: $1,000
COGS: $600
Gross Profit: $400
Margin: 40%
```

---

### 3. Loyalty Points System

**Points Earning:**
- 1 point per $10 spent
- Formula: `points_earned = int(total_amount / 10)`

**Only Named Customers:**
```python
if customer_id and customer_id != 1:  # Skip generic customer (id=1)
    points = int(total_amount / 10)
    cursor.execute("""
        UPDATE customers 
        SET loyalty_points = loyalty_points + ? 
        WHERE id = ?
    """, (points, customer_id))
```

**Generic Cash Customer Handling:**
- Prevents loyalty point inflation from anonymous cash sales
- Sales recorded with `customer_id = 1` (generic "عميل عام (نقدي)")
- Still tracked for analytics, but no loyalty rewards

---

### 4. Search & Filtering

**Product Search (Treeview Filter):**
```python
def _filter_products(self, event):
    query = self.ent_search.get().lower()
    filtered = [
        p for p in self.products_list
        if query in p['name'].lower() 
        or query in p['sku'].lower()
        or query in (p['category_name'] or '').lower()
    ]
    self._populate_tree(filtered)
```
- Real-time on KeyRelease event
- Case-insensitive matching
- Searches name, SKU, category simultaneously

**Database-Level Search:**
```python
def search_products(query):
    cursor.execute("""
        SELECT ... FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        WHERE p.name LIKE ? OR p.sku LIKE ? OR c.name LIKE ?
    """, (f"%{query}%", f"%{query}%", f"%{query}%"))
```
- Used for comprehensive searches
- Returns enriched results with joins

---

## Integration Points

### External Dependencies

1. **Matplotlib** - Chart Rendering
   - Embedded in Tkinter via `FigureCanvasTkAgg`
   - Used for: Daily sales trends, top products chart
   - No external data sources, purely client-side calculation

2. **PyInstaller** - Executable Packaging
   - Bundles Python interpreter + dependencies into .exe
   - File: `StoreManagerPro.spec` configures build
   - Output: `build/StoreManagerPro/` contains packaged app

### File I/O Operations

**Database File:**
- Path: `store.db` (project root by default)
- Created automatically on first run
- SQLite format (binary, not human-readable)

**CSV Export:**
- Path: `sales_report_{YYYY-MM-DD}_{HH-MM-SS}.csv`
- Encoding: UTF-8-SIG (Excel compatibility for Arabic)
- Delimiter: Comma
- Columns: Invoice#, Date, Customer, Amount, Tax, Discount, Payment Method

**Sample Data:**
- Loaded automatically on `init_db()` if database doesn't exist
- Allows testing without manual data entry

### Locale & Internationalization (i18n)

**RTL Support (Right-to-Left):**
- Hardcoded in Tkinter layout (anchor="e", side="right")
- Arabic text labels throughout UI
- No translation layer; Arabic is primary language

**Formatting:**
- Numbers: Thousands separator, 2 decimal places
- Dates: ISO format in DB (`YYYY-MM-DD HH:MM:SS`), display format flexible
- Currency: Always `$` (USD-assumed), can modify to `ر.س` (SAR)

---

## Performance Considerations

### Query Optimization

| Query | Optimization |
|-------|---------------|
| `get_all_products()` with JOINs | LEFT JOIN avoids duplicate rows |
| `get_low_stock_products()` | WHERE clause filters before result set |
| `get_sales_chart_data()` | GROUP BY date aggregates before returning |
| `record_sale()` | Single transaction, all-or-nothing |
| Product search | In-memory filtering (faster than DB for small catalogs <10k) |

### Data Load Strategy

**Eager Loading (Current Approach):**
- Load all products on view activation
- Filter in memory via Python list comprehension
- Pros: Instant filtering, no DB round-trips
- Cons: Doesn't scale to 100k+ products

**Lazy Loading (Future Optimization):**
- Load only visible rows (pagination)
- Fetch on scroll
- Filter at DB level with LIMIT/OFFSET

### Memory Usage

- **Typical Small Store:** <1MB RAM (100 products, 1000 sales)
- **Large Store:** 50MB RAM (10k products, 100k sales)
- No memory leaks (connections properly closed)
- Views cached in memory (not recreated on each navigation)

---

## Error Handling & Validation

### Database Errors

| Error | Cause | Response |
|-------|-------|----------|
| Unique constraint violation | Duplicate SKU/phone | User error message: "كود المنتج مسجل مسبقاً" |
| Foreign key violation | Deleting product with sales | RESTRICT prevents; user sees "لا يمكن حذف المنتج" |
| Overflow/arithmetic | Negative stock attempted | Rollback; user sees "خطأ في المخزون" |

### Input Validation

**Client-Side (UI):**
- Required fields marked (not empty)
- Numeric fields validated before save
- Price fields must be positive
- Quantity must be integer

**Database-Side:**
- PRIMARY KEY prevents duplicate IDs
- UNIQUE constraints on SKU, phone
- FOREIGN KEY constraints enforce referential integrity
- DEFAULT values ensure no NULL issues

---

## Deployment & Distribution

### Standalone Executable

**Build Command:**
```bash
pyinstaller StoreManagerPro.spec
```

**Output Structure:**
```
build/StoreManagerPro/
├─ StoreManagerPro.exe     # Main executable
├─ python*.dll             # Python runtime
├─ tcl/tk                  # Tkinter libraries
├─ matplotlib/             # Chart rendering libs
└─ store.db               # Database (embedded)
```

**Distribution:**
- Single-click installation (no dependencies)
- Runs on Windows 7+ (Python 3.8+)
- No admin rights required
- Portable; can run from USB drive

### Data Portability

- SQLite database is standard format
- Can be opened by any SQLite tool (DBeaver, SQLiteStudio)
- Backup: Simply copy `store.db` file
- Migration: Copy `store.db` to new machine

---

## Security Considerations

### Data Protection

1. **No Network Transmission**
   - All data stored locally
   - No cloud dependencies
   - 100% offline operation

2. **Hardcoded Credentials**
   - Database has no password
   - Assumes single-user, trusted environment
   - Could add SQLite encryption for sensitive deployments

3. **SQL Injection Prevention**
   - Parameterized queries used throughout
   - No string concatenation in SQL
   - SQLite3 `?` placeholders enforce type safety

### Access Control

- No user authentication system
- Assumes single-user desktop environment
- Could extend with login, role-based access, audit logs

---

## Future Enhancement Opportunities

### Phase 2 Enhancements

1. **Multi-Store Support**
   - Database schema: Add `store_id` foreign key to transactions
   - Support multiple retail locations
   - Consolidated reporting across stores

2. **Advanced Analytics**
   - Customer segmentation (high-value, inactive)
   - Inventory forecasting (reorder predictions)
   - Seasonal trend analysis
   - Profitability by category/supplier

3. **Payment Integration**
   - Link to payment processors (Stripe, Arab Bank APIs)
   - Digital receipt delivery (email/SMS)
   - Recurring customer billing

4. **Mobile/Cloud Extension**
   - REST API backend (FastAPI, Django)
   - Mobile app for inventory scanning
   - Cloud sync for multi-location reporting
   - Real-time dashboard

5. **User Management**
   - Role-based access control (Manager, Cashier, Inventory)
   - Audit logs for transactions
   - Password protection

6. **Localization**
   - Support multiple languages (English, French, Urdu)
   - Currency selector (SAR, AED, EGP)
   - Regional date/number formatting

---

## Testing Strategy

### Unit Tests (Recommended)

```python
# tests/test_db.py
def test_add_product():
    db_path = ":memory:"
    init_db(db_path, seed_sample_data=False)
    success, msg = add_product(db_path, "SKU001", "Test", 1, 10.0, 20.0, 50, 5, 1)
    assert success == True
    
def test_duplicate_sku_fails():
    success, msg = add_product(..., "SKU001", ...)
    assert success == False
    assert "مسجل مسبقاً" in msg
```

### Integration Tests

- Test full POS workflow: Add customer → Add products to cart → Process sale → Verify stock decremented
- Test PO receive: Create PO → Receive → Verify stock incremented
- Test analytics: Create sales → Check COGS calculation → Export CSV

### Manual Testing Checklist

- [ ] Product CRUD operations
- [ ] POS checkout with discounts
- [ ] Loyalty points accumulation
- [ ] Low stock alerts
- [ ] CSV export with Arabic text
- [ ] Charts render correctly
- [ ] Database integrity after crashes

---

## Conclusion

**StoreManagerPro** implements a complete, production-ready retail management system with:

- **Robust Database:** Normalized SQLite schema with referential integrity
- **Responsive UI:** Tkinter with native RTL support and modern styling
- **Business Logic:** Transactional sales, inventory tracking, loyalty rewards
- **Analytics:** Real-time KPIs, charts, and CSV reporting
- **Reliability:** Atomic transactions, error handling, data validation
- **Portability:** Standalone executable, no dependencies

The architecture supports future scaling (multi-store, cloud sync, mobile) while maintaining simplicity for current single-location deployments.

---

## Changelog - 2026-08-03

### Added Financial Workflow Extensions

This version extends the original architecture with three new production features while preserving the same Tkinter + SQLite + `core/db.py` design:

1. **POS Cashier Sessions (`جلسة الكاشير`)**
   - New `pos_sessions` table.
   - One open session allowed at a time via a partial unique index.
   - All new POS sales are associated with the active session.
   - Session closing stores expected balance, actual balance, and reconciliation difference.

2. **Sales Return Invoices**
   - New `sale_returns` header table.
   - New `sale_return_items` line-items table.
   - Original sales remain immutable.
   - Partial and repeated returns are supported as long as the cumulative returned quantity does not exceed the originally sold quantity.

3. **Daily Session Expenses**
   - New `expenses` table linked to `pos_sessions`.
   - Only cash expenses reduce the drawer balance.
   - Non-cash expenses remain visible in analytics and exports.

### Schema Updates

#### New Tables

```sql
pos_sessions
expenses
sale_returns
sale_return_items
schema_migrations
```

#### Updated Existing Table

```sql
sales.session_id INTEGER NULL REFERENCES pos_sessions(id) ON DELETE RESTRICT
```

### Migration Strategy

The initialization path in `core/db.py` now performs safe repeatable upgrades:

1. Detect missing tables and columns.
2. Create a backup only when a real schema upgrade is needed.
3. Preserve historical `sales` rows with `session_id = NULL`.
4. Avoid destructive resets or reseeding for existing databases.
5. Recreate new indexes with `CREATE INDEX IF NOT EXISTS`.

### New Public Database Functions

The database layer now exposes these additional public APIs:

```python
open_pos_session()
get_active_pos_session()
get_pos_session()
get_pos_sessions()
calculate_session_summary()
close_pos_session()

add_expense()
get_session_expenses()
get_expense()
get_expenses_summary()
delete_expense()

get_sale_for_return()
get_returnable_sale_items()
get_previously_returned_quantity()
preview_sale_return()
record_sale_return()
get_sale_returns()
get_return_details()

get_financial_overview()
get_combined_report_rows()
get_generic_customer_id()
```

### Cash Drawer Formula

The expected cash balance per open session is computed as:

```text
Expected Cash Balance =
Opening Balance
+ Cash Sales
- Cash Returns
- Cash Expenses
```

Card and electronic operations are intentionally excluded from the physical drawer total.

### Return Allocation Model

Because the original sales schema stores tax and discount at the sale header level, return lines use proportional allocation:

```text
Original Line Share = Original Line Subtotal / Original Sale Subtotal
Allocated Line Tax = Sale Tax * Original Line Share
Allocated Line Discount = Sale Discount * Original Line Share

Return Ratio = Returned Quantity / Original Sold Quantity
Return Tax = Allocated Line Tax * Return Ratio
Return Discount = Allocated Line Discount * Return Ratio
Return Total = Return Subtotal + Return Tax - Return Discount
```

The implementation also caps repeated partial returns so the cumulative refunded tax, discount, and total do not exceed the original sale.

### UI Changes

#### POS View
- Added a cashier-session status bar above the existing catalog/cart layout.
- Added modal workflows for:
  - opening a session
  - closing a session
  - recording expenses
  - creating return invoices
  - browsing session history
  - viewing session closing reports

#### Dashboard
- Added operational metrics for:
  - current session status
  - expected cash
  - today sales
  - today returns
  - today expenses
  - today net sales

#### Analytics
- Added return-aware profit metrics.
- Added session history access.
- Updated CSV export to include sales, returns, and expenses in one report.

### Reporting Notes

Returned COGS currently uses the same costing model as the original application: `products.cost_price` at report time. The code intentionally preserves this historical limitation rather than silently redesigning costing behavior in this release.

### Test Coverage Added

Automated tests now cover:

- session opening validation
- single-open-session enforcement
- balanced / shortage / increase closing scenarios
- cash vs non-cash sales
- cash vs non-cash expenses
- full and partial returns
- repeated partial returns
- stock restoration
- loyalty point reversal with non-negative floor
- migration of a legacy schema with historical null session sales
- end-to-end cash reconciliation workflow

---

**End of Technical Documentation**
