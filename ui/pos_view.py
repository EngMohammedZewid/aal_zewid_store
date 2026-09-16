import tkinter as tk
from tkinter import ttk, messagebox

UNIT_DISPLAY_NAMES = {
    "Piece": "قطعة",
    "Pack": "باكو",
    "Dozen": "دستة",
    "Box": "علبة",
    "Carton": "كرتونة",
}
UNIT_INTERNAL_NAMES = {value: key for key, value in UNIT_DISPLAY_NAMES.items()}


def get_display_unit_name(unit_name):
    return UNIT_DISPLAY_NAMES.get(unit_name, unit_name or "قطعة")


def get_internal_unit_name(unit_name):
    return UNIT_INTERNAL_NAMES.get(unit_name, unit_name or "Piece")


from core.db import (
    add_customer,
    add_expense,
    calculate_session_summary,
    calculate_tax,
    close_pos_session,
    delete_expense,
    get_active_pos_session,
    get_all_customers,
    get_all_products,
    get_expense,
    get_pos_sessions,
    get_product_units,
    get_return_details,
    get_returnable_sale_items,
    get_sale_for_return,
    get_session_expenses,
    open_pos_session,
    preview_sale_return,
    record_sale,
    record_sale_return,
)


EXPENSE_CATEGORIES = [
    "نقل وشحن",
    "أدوات نظافة",
    "صيانة",
    "كهرباء ومياه",
    "ضيافة",
    "مصروف عامل",
    "مشتريات عاجلة",
    "مصروفات أخرى",
]

EXPENSE_PAYMENT_METHODS = ["كاش", "بطاقة", "تحويل", "دفع إلكتروني"]
RETURN_REFUND_METHODS = ["كاش", "بطاقة ائتمان", "دفع إلكتروني", "نفس طريقة الدفع الأصلية"]
RETURN_REASONS = ["منتج تالف", "منتج غير مناسب", "خطأ في الفاتورة", "استبدال منتج", "طلب العميل", "أخرى"]


class POSView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f1f5f9")
        self.controller = controller

        self.columnconfigure(0, weight=4)
        self.columnconfigure(1, weight=6)
        self.rowconfigure(1, weight=1)

        self.cart = []
        self.customers_list = []
        self.products_list = []
        self.active_session = None
        self.session_summary = None
        self.selected_product = None
        self.selected_product_unit = None

        self.lbl_session_title = None
        self.lbl_session_opening = None
        self.lbl_session_expected = None
        self.btn_open_session = None
        self.btn_return = None
        self.btn_expense = None
        self.btn_close_session = None
        self.btn_session_history = None
        self.btn_checkout = None
        self.cb_customer = None
        self.cb_payment = None
        self.cb_unit = None
        self.lbl_unit_info = None
        self.ent_discount = None
        self.prod_tree = None
        self.cart_tree = None
        self.lbl_subtotal = None
        self.lbl_tax = None
        self.lbl_total = None
        self.ent_search = None

        self._build_session_header()
        self._build_product_catalog_pane()
        self._build_shopping_cart_pane()

        self.refresh_data()

    def _build_session_header(self):
        header = tk.Frame(self, bg="white", padx=15, pady=12, bd=1, relief="solid")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(20, 10))
        header.columnconfigure(0, weight=1)

        actions = tk.Frame(header, bg="white")
        actions.pack(side="left")

        self.btn_close_session = tk.Button(
            actions,
            text="إغلاق الجلسة",
            font=("Helvetica", 11, "bold"),
            bg="#dc2626",
            fg="white",
            padx=12,
            pady=6,
            bd=0,
            cursor="hand2",
            command=self._show_close_session_modal,
        )
        self.btn_close_session.pack(side="left", padx=4)

        self.btn_expense = tk.Button(
            actions,
            text="إضافة مصروف",
            font=("Helvetica", 11, "bold"),
            bg="#d97706",
            fg="white",
            padx=12,
            pady=6,
            bd=0,
            cursor="hand2",
            command=self._show_expense_modal,
        )
        self.btn_expense.pack(side="left", padx=4)

        self.btn_return = tk.Button(
            actions,
            text="فاتورة استرجاع",
            font=("Helvetica", 11, "bold"),
            bg="#475569",
            fg="white",
            padx=12,
            pady=6,
            bd=0,
            cursor="hand2",
            command=self._show_return_modal,
        )
        self.btn_return.pack(side="left", padx=4)

        self.btn_session_history = tk.Button(
            actions,
            text="سجل الجلسات",
            font=("Helvetica", 11, "bold"),
            bg="#e2e8f0",
            fg="#0f172a",
            padx=12,
            pady=6,
            bd=0,
            cursor="hand2",
            command=self._show_session_history_modal,
        )
        self.btn_session_history.pack(side="left", padx=4)

        self.btn_open_session = tk.Button(
            actions,
            text="فتح جلسة جديدة",
            font=("Helvetica", 11, "bold"),
            bg="#16a34a",
            fg="white",
            padx=12,
            pady=6,
            bd=0,
            cursor="hand2",
            command=self._show_open_session_modal,
        )
        self.btn_open_session.pack(side="left", padx=4)

        info = tk.Frame(header, bg="white")
        info.pack(side="right", fill="x", expand=True)

        self.lbl_session_title = tk.Label(info, text="لا توجد جلسة كاشير مفتوحة", font=("Helvetica", 16, "bold"), fg="#0f172a", bg="white")
        self.lbl_session_title.pack(anchor="e")
        self.lbl_session_opening = tk.Label(info, text="", font=("Helvetica", 11), fg="#64748b", bg="white")
        self.lbl_session_opening.pack(anchor="e", pady=(4, 0))
        self.lbl_session_expected = tk.Label(info, text="", font=("Helvetica", 11, "bold"), fg="#2563eb", bg="white")
        self.lbl_session_expected.pack(anchor="e", pady=(4, 0))

    def _build_product_catalog_pane(self):
        left_frame = tk.Frame(self, bg="white", padx=15, pady=15)
        left_frame.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=(0, 20))
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(2, weight=1)

        top_bar = tk.Frame(left_frame, bg="white")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 15))

        tk.Label(top_bar, text="🛒 نقطة البيع (POS)", font=("Helvetica", 20, "bold"), fg="#0f172a", bg="white").pack(side="right")

        search_frame = tk.Frame(top_bar, bg="white")
        search_frame.pack(side="left")

        tk.Label(search_frame, text="بحث عن منتج:", font=("Helvetica", 11, "bold"), bg="white").pack(side="right", padx=5)
        self.ent_search = tk.Entry(search_frame, font=("Helvetica", 12), width=25, justify="right")
        self.ent_search.pack(side="right", padx=5)
        self.ent_search.bind("<KeyRelease>", self._filter_products)

        unit_frame = tk.Frame(left_frame, bg="#f8fafc", padx=12, pady=12, bd=1, relief="solid")
        unit_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        tk.Label(unit_frame, text="الوحدة:", font=("Helvetica", 11, "bold"), bg="#f8fafc", fg="#0f172a").pack(side="right", padx=(5, 0))
        self.cb_unit = ttk.Combobox(unit_frame, state="readonly", font=("Helvetica", 11), width=18, justify="right")
        self.cb_unit.pack(side="right", padx=8)
        self.cb_unit.bind("<<ComboboxSelected>>", self._on_unit_selected)

        self.lbl_unit_info = tk.Label(unit_frame, text="اختر منتجاً لعرض الوحدات المتاحة", font=("Helvetica", 10), bg="#f8fafc", fg="#64748b")
        self.lbl_unit_info.pack(side="left")

        tk.Label(
            left_frame,
            text="انقر مزدوجاً أو اضغط Enter على أي منتج أدناه لإضافته إلى سلة المشتريات:",
            font=("Helvetica", 11, "italic"),
            fg="#64748b",
            bg="white",
        ).grid(row=2, column=0, sticky="e", pady=(0, 5))

        cols = ("price", "name", "sku")
        self.prod_tree = ttk.Treeview(left_frame, columns=cols, show="headings", height=20)
        self.prod_tree.heading("sku", text="كود المنتج (SKU)")
        self.prod_tree.heading("name", text="اسم المنتج")
        self.prod_tree.heading("price", text="سعر البيع")

        self.prod_tree.column("sku", width=110, anchor="e")
        self.prod_tree.column("name", width=250, anchor="e")
        self.prod_tree.column("price", width=100, anchor="e")

        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.prod_tree.yview)
        self.prod_tree.configure(yscrollcommand=scrollbar.set)
        self.prod_tree.grid(row=3, column=0, sticky="nsew")
        scrollbar.grid(row=3, column=1, sticky="ns")

        self.prod_tree.bind("<<TreeviewSelect>>", self._on_product_selected)
        self.prod_tree.bind("<Double-1>", lambda event: self._add_selected_to_cart())
        self.prod_tree.bind("<Return>", lambda event: self._add_selected_to_cart())

    def _build_shopping_cart_pane(self):
        right_frame = tk.Frame(self, bg="white", padx=15, pady=15)
        right_frame.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=(0, 20))
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(2, weight=1)

        cust_frame = tk.Frame(right_frame, bg="white")
        cust_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        tk.Label(cust_frame, text="العميل:", font=("Helvetica", 12, "bold"), bg="white", fg="#0f172a").pack(anchor="e")

        c_sub = tk.Frame(cust_frame, bg="white")
        c_sub.pack(fill="x", pady=5)

        self.cb_customer = ttk.Combobox(c_sub, state="readonly", font=("Helvetica", 12), justify="right")
        self.cb_customer.pack(side="right", fill="x", expand=True, padx=(10, 0))

        tk.Button(
            c_sub,
            text="+ إضافة عميل",
            font=("Helvetica", 11, "bold"),
            bg="#16a34a",
            fg="white",
            padx=12,
            pady=4,
            bd=0,
            cursor="hand2",
            command=self._show_add_customer_modal,
        ).pack(side="left")

        tk.Label(right_frame, text="سلة المشتريات الحالية", font=("Helvetica", 14, "bold"), bg="white", fg="#0f172a").grid(row=1, column=0, sticky="e", pady=(0, 5))

        cart_cols = ("sub", "price", "qty", "unit", "name")
        self.cart_tree = ttk.Treeview(right_frame, columns=cart_cols, show="headings", height=12)
        self.cart_tree.heading("sub", text="المجموع")
        self.cart_tree.heading("price", text="السعر")
        self.cart_tree.heading("qty", text="الكمية")
        self.cart_tree.heading("unit", text="الوحدة")
        self.cart_tree.heading("name", text="المنتج")

        self.cart_tree.column("sub", width=90, anchor="center")
        self.cart_tree.column("price", width=90, anchor="center")
        self.cart_tree.column("qty", width=55, anchor="center")
        self.cart_tree.column("unit", width=90, anchor="center")
        self.cart_tree.column("name", width=180, anchor="center")

        cart_scroll = ttk.Scrollbar(right_frame, orient="vertical", command=self.cart_tree.yview)
        self.cart_tree.configure(yscrollcommand=cart_scroll.set)
        self.cart_tree.grid(row=2, column=0, sticky="nsew")
        cart_scroll.grid(row=2, column=1, sticky="ns")

        cart_btns = tk.Frame(right_frame, bg="white")
        cart_btns.grid(row=3, column=0, sticky="ew", pady=10)

        tk.Button(cart_btns, text="➕ زيادة 1", font=("Helvetica", 10, "bold"), bg="#e2e8f0", fg="#0f172a", padx=10, pady=4, bd=0, cursor="hand2", command=lambda: self._adjust_cart_qty(1)).pack(side="right", padx=3)
        tk.Button(cart_btns, text="➖ تقليل 1", font=("Helvetica", 10, "bold"), bg="#e2e8f0", fg="#0f172a", padx=10, pady=4, bd=0, cursor="hand2", command=lambda: self._adjust_cart_qty(-1)).pack(side="right", padx=3)
        tk.Button(cart_btns, text="🗑️ حذف العنصر", font=("Helvetica", 10, "bold"), bg="#fee2e2", fg="#dc2626", padx=10, pady=4, bd=0, cursor="hand2", command=self._remove_cart_item).pack(side="right", padx=3)
        tk.Button(cart_btns, text="إفراغ السلة", font=("Helvetica", 10, "bold"), bg="#f1f5f9", fg="#64748b", padx=10, pady=4, bd=0, cursor="hand2", command=self.clear_cart).pack(side="left", padx=3)

        totals_frame = tk.Frame(right_frame, bg="#f8fafc", padx=15, pady=15, bd=1, relief="solid")
        totals_frame.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        totals_frame.columnconfigure(0, weight=1)

        tk.Label(totals_frame, text="المجموع الفرعي:", font=("Helvetica", 12), bg="#f8fafc", fg="#64748b").grid(row=0, column=1, sticky="e", pady=2)
        self.lbl_subtotal = tk.Label(totals_frame, text="0.00", font=("Helvetica", 12, "bold"), bg="#f8fafc", fg="#0f172a")
        self.lbl_subtotal.grid(row=0, column=0, sticky="w", pady=2)

        tk.Label(totals_frame, text="الضريبة المضافة (8%):", font=("Helvetica", 12), bg="#f8fafc", fg="#64748b").grid(row=1, column=1, sticky="e", pady=2)
        self.lbl_tax = tk.Label(totals_frame, text="0.00", font=("Helvetica", 12, "bold"), bg="#f8fafc", fg="#0f172a")
        self.lbl_tax.grid(row=1, column=0, sticky="w", pady=2)

        tk.Label(totals_frame, text="الخصم الإضافي:", font=("Helvetica", 12), bg="#f8fafc", fg="#64748b").grid(row=2, column=1, sticky="e", pady=2)
        self.ent_discount = tk.Entry(totals_frame, font=("Helvetica", 11), width=10, justify="center")
        self.ent_discount.insert(0, "0.00")
        self.ent_discount.grid(row=2, column=0, sticky="w", pady=2)
        self.ent_discount.bind("<KeyRelease>", lambda event: self._update_totals())

        tk.Label(totals_frame, text="طريقة الدفع:", font=("Helvetica", 12, "bold"), bg="#f8fafc", fg="#0f172a").grid(row=3, column=1, sticky="e", pady=(10, 5))
        self.cb_payment = ttk.Combobox(totals_frame, values=["كاش (نقدي)", "بطاقة ائتمان", "دفع إلكتروني (مدى/فوري)", "شبكة (مدى)"], state="readonly", font=("Helvetica", 11), width=15, justify="right")
        self.cb_payment.set("كاش (نقدي)")
        self.cb_payment.grid(row=3, column=0, sticky="w", pady=(10, 5))

        tk.Label(totals_frame, text="المبلغ الإجمالي المطلوب:", font=("Helvetica", 15, "bold"), bg="#f8fafc", fg="#2563eb").grid(row=4, column=1, sticky="e", pady=(10, 0))
        self.lbl_total = tk.Label(totals_frame, text="0.00", font=("Helvetica", 20, "bold"), bg="#f8fafc", fg="#2563eb")
        self.lbl_total.grid(row=4, column=0, sticky="w", pady=(10, 0))

        self.btn_checkout = tk.Button(
            totals_frame,
            text="💳 إتمام عملية الدفع وفتح الفاتورة",
            font=("Helvetica", 14, "bold"),
            bg="#2563eb",
            fg="white",
            pady=12,
            bd=0,
            cursor="hand2",
            command=self._complete_checkout,
        )
        self.btn_checkout.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(15, 0))

    def refresh_data(self):
        self.active_session = get_active_pos_session()
        self.session_summary = calculate_session_summary(self.active_session["id"]) if self.active_session else None

        self.products_list = get_all_products()
        self._populate_products_tree(self.products_list)

        self.customers_list = get_all_customers()
        customer_names = [f"{customer['name']} ({customer['phone']})" for customer in self.customers_list]
        self.cb_customer.config(values=customer_names)
        if customer_names and not self.cb_customer.get():
            self.cb_customer.set(customer_names[0])
        elif not customer_names:
            self.cb_customer.set("")

        self._update_session_header()
        self._update_financial_controls()
        self._update_totals()

    def _update_session_header(self):
        if self.active_session and self.session_summary:
            self.lbl_session_title.config(text=f"الجلسة الحالية: #{self.active_session['id']}", fg="#0f172a")
            self.lbl_session_opening.config(
                text=f"وقت الفتح: {self.active_session['opened_at']}    |    الرصيد الافتتاحي: {self.active_session['opening_balance']:,.2f}"
            )
            self.lbl_session_expected.config(text=f"الرصيد النقدي المتوقع: {self.session_summary['expected_cash_balance']:,.2f}")
        else:
            self.lbl_session_title.config(text="لا توجد جلسة كاشير مفتوحة", fg="#dc2626")
            self.lbl_session_opening.config(text="افتح جلسة جديدة قبل تنفيذ أي عملية مالية.")
            self.lbl_session_expected.config(text="")

    def _update_financial_controls(self):
        has_session = self.active_session is not None
        self.btn_checkout.config(state="normal" if has_session else "disabled")
        self.btn_return.config(state="normal" if has_session else "disabled")
        self.btn_expense.config(state="normal" if has_session else "disabled")
        self.btn_close_session.config(state="normal" if has_session else "disabled")
        self.btn_open_session.config(state="disabled" if has_session else "normal")

    def _on_product_selected(self, event=None):
        selected = self.prod_tree.selection()
        if not selected:
            self.selected_product = None
            self.selected_product_unit = None
            self.cb_unit.config(values=[])
            self.cb_unit.set("")
            self.lbl_unit_info.config(text="اختر منتجاً لعرض الوحدات المتاحة")
            return

        sku = self.prod_tree.item(selected[0], "values")[2]
        product = next((item for item in self.products_list if item["sku"] == sku), None)
        self.selected_product = product
        self.selected_product_unit = None
        self.cb_unit.config(values=[])
        self.cb_unit.set("")
        if product is None:
            self.lbl_unit_info.config(text="المنتج غير موجود")
            return

        units = get_product_units(product["id"])
        if not units:
            self.lbl_unit_info.config(text="لا توجد وحدات مضافة لهذا المنتج")
            return
        unit_names = [get_display_unit_name(unit["unit_name"]) for unit in units]
        self.cb_unit.config(values=unit_names)
        default_unit = next((unit for unit in units if unit["is_default"]), units[0])
        self.selected_product_unit = default_unit
        self.cb_unit.set(get_display_unit_name(default_unit["unit_name"]))
        self.lbl_unit_info.config(text=f"عدد القطع داخل الوحدة: {default_unit['pieces_per_unit']}")

    def _on_unit_selected(self, event=None):
        if not self.selected_product:
            return
        selected_name = self.cb_unit.get().strip()
        units = get_product_units(self.selected_product["id"])
        internal_name = get_internal_unit_name(selected_name)
        unit = next((item for item in units if item["unit_name"] == internal_name), None)
        self.selected_product_unit = unit
        if unit:
            self.lbl_unit_info.config(text=f"الوحدة: {get_display_unit_name(unit['unit_name'])} | عدد القطع: {unit['pieces_per_unit']} | السعر: {unit['selling_price']:,.2f}")

    def _populate_products_tree(self, products):
        for item in self.prod_tree.get_children():
            self.prod_tree.delete(item)
        for product in products:
            self.prod_tree.insert("", "end", values=(f"{product['selling_price']:,.2f}", product["name"], product["sku"]))

    def _filter_products(self, event=None):
        query = self.ent_search.get().lower().strip()
        if not query:
            self._populate_products_tree(self.products_list)
            return
        filtered = [
            product for product in self.products_list
            if query in product["name"].lower()
            or query in product["sku"].lower()
            or (product["category_name"] and query in product["category_name"].lower())
        ]
        self._populate_products_tree(filtered)

    def _show_add_to_cart_unit_modal(self, product):
        if not product:
            return

        product_units = get_product_units(product["id"])
        if not product_units:
            messagebox.showwarning("وحدة غير موجودة", f"لا توجد وحدة مسجلة للمنتج '{product['name']}'.")
            return

        default_unit = self.selected_product_unit if self.selected_product and self.selected_product["id"] == product["id"] else next((unit for unit in product_units if unit["is_default"]), product_units[0])
        modal = tk.Toplevel(self)
        modal.title("اختيار الوحدة")
        modal.geometry("380x230")
        modal.config(bg="white", padx=18, pady=18)
        modal.grab_set()

        tk.Label(modal, text=f"إضافة: {product['name']}", font=("Helvetica", 15, "bold"), bg="white", fg="#0f172a").pack(anchor="e", pady=(0, 12))

        form = tk.Frame(modal, bg="white")
        form.pack(fill="both", expand=True)

        tk.Label(form, text="الوحدة:", font=("Helvetica", 11, "bold"), bg="white").grid(row=0, column=1, sticky="e", padx=8, pady=6)
        unit_cb = ttk.Combobox(form, state="readonly", font=("Helvetica", 11), width=18, justify="right")
        unit_cb["values"] = [get_display_unit_name(unit["unit_name"]) for unit in product_units]
        unit_cb.set(get_display_unit_name(default_unit["unit_name"]))
        unit_cb.grid(row=0, column=0, sticky="ew", padx=8, pady=6)

        tk.Label(form, text="الكمية:", font=("Helvetica", 11, "bold"), bg="white").grid(row=1, column=1, sticky="e", padx=8, pady=6)
        qty_ent = tk.Entry(form, font=("Helvetica", 11), width=18, justify="center")
        qty_ent.insert(0, "1")
        qty_ent.grid(row=1, column=0, sticky="ew", padx=8, pady=6)

        price_var = tk.StringVar(value="0.00")
        tk.Label(form, text="السعر المختار:", font=("Helvetica", 10, "bold"), bg="white", fg="#64748b").grid(row=2, column=1, sticky="e", padx=8, pady=(10, 4))
        tk.Label(form, textvariable=price_var, font=("Helvetica", 13, "bold"), bg="white", fg="#2563eb").grid(row=2, column=0, sticky="w", padx=8, pady=(10, 4))

        def update_price_display():
            unit_name = unit_cb.get().strip()
            selected_unit = next((unit for unit in product_units if unit["unit_name"] == unit_name), default_unit)
            price_var.set(f"{selected_unit['selling_price']:,.2f}")

        unit_cb.bind("<<ComboboxSelected>>", lambda event: update_price_display())
        update_price_display()

        action_bar = tk.Frame(modal, bg="white")
        action_bar.pack(fill="x", pady=(20, 0))

        def add_item():
            unit_name = unit_cb.get().strip()
            internal_name = get_internal_unit_name(unit_name)
            selected_unit = next((unit for unit in product_units if unit["unit_name"] == internal_name), None)
            if not selected_unit:
                messagebox.showwarning("وحدة غير صحيحة", "يرجى اختيار وحدة صالحة.", parent=modal)
                return

            try:
                qty = int(qty_ent.get())
            except ValueError:
                messagebox.showwarning("كمية غير صحيحة", "يرجى إدخال عدد صحيح للكمية.", parent=modal)
                return
            if qty <= 0:
                messagebox.showwarning("كمية غير صحيحة", "يجب أن تكون الكمية أكبر من صفر.", parent=modal)
                return

            required_base = qty * selected_unit["pieces_per_unit"]
            if required_base > product["stock_quantity"]:
                messagebox.showwarning("الحد الأقصى للمخزون", f"المتوفر في المخزون من '{product['name']}' هو {product['stock_quantity']} قطعة فقط، ولا يكفي لهذا الطلب في وحدة '{selected_unit['unit_name']}'.", parent=modal)
                return

            existing = next((line for line in self.cart if line["product"]["id"] == product["id"] and line.get("unit_name") == selected_unit["unit_name"]), None)
            if existing:
                new_qty = existing["quantity"] + qty
                if new_qty * selected_unit["pieces_per_unit"] > product["stock_quantity"]:
                    messagebox.showwarning("الحد الأقصى للمخزون", f"لا يمكن إضافة {qty} من '{product['name']}' في وحدة '{selected_unit['unit_name']}' لأن إجمالي الكمية المطلوبة يتجاوز المخزون المتوفر.", parent=modal)
                    return
                existing["quantity"] = new_qty
                existing["subtotal"] = existing["quantity"] * selected_unit["selling_price"]
                existing["unit_price"] = selected_unit["selling_price"]
                existing["pieces_per_unit"] = selected_unit["pieces_per_unit"]
                existing["base_quantity"] = existing["quantity"] * selected_unit["pieces_per_unit"]
            else:
                self.cart.append({
                    "product": product,
                    "product_unit_id": selected_unit["id"],
                    "unit_name": selected_unit["unit_name"],
                    "quantity": qty,
                    "unit_price": selected_unit["selling_price"],
                    "pieces_per_unit": selected_unit["pieces_per_unit"],
                    "base_quantity": qty * selected_unit["pieces_per_unit"],
                    "subtotal": qty * selected_unit["selling_price"],
                })

            self._render_cart()
            modal.destroy()

        tk.Button(action_bar, text="إضافة إلى السلة", font=("Helvetica", 11, "bold"), bg="#2563eb", fg="white", padx=14, pady=8, bd=0, cursor="hand2", command=add_item).pack(side="right")
        tk.Button(action_bar, text="إلغاء", font=("Helvetica", 11, "bold"), bg="#e2e8f0", fg="#0f172a", padx=14, pady=8, bd=0, cursor="hand2", command=modal.destroy).pack(side="left")

    def _add_selected_to_cart(self):
        selected = self.prod_tree.selection()
        if not selected:
            return
        sku = self.prod_tree.item(selected[0], "values")[2]
        product = next((item for item in self.products_list if item["sku"] == sku), None)
        if not product:
            messagebox.showwarning("خطأ", "تعذر العثور على المنتج المحدد. يرجى إعادة المحاولة.")
            return
        self._show_add_to_cart_unit_modal(product)

    def _adjust_cart_qty(self, delta):
        selected = self.cart_tree.selection()
        if not selected:
            messagebox.showinfo("تحديد عنصر", "يرجى تحديد عنصر من سلة المشتريات لتعديل كميته.")
            return
        idx = self.cart_tree.index(selected[0])
        cart_item = self.cart[idx]
        product = cart_item["product"]
        pieces_per_unit = cart_item.get("pieces_per_unit", 1)
        new_qty = cart_item["quantity"] + delta
        if new_qty <= 0:
            self.cart.pop(idx)
        else:
            required_base = new_qty * pieces_per_unit
            if required_base > product["stock_quantity"]:
                messagebox.showwarning("الحد الأقصى للمخزون", f"المتوفر في المخزون من '{product['name']}' هو {product['stock_quantity']} قطعة فقط، ولا يكفي لهذا الطلب في وحدة '{cart_item.get('unit_name', 'الأساسية')}'.")
                return
            cart_item["quantity"] = new_qty
            cart_item["subtotal"] = new_qty * cart_item["unit_price"]
            cart_item["base_quantity"] = required_base
        self._render_cart()

    def _remove_cart_item(self):
        selected = self.cart_tree.selection()
        if not selected:
            messagebox.showinfo("تحديد عنصر", "يرجى تحديد عنصر من سلة المشتريات لحذفه.")
            return
        self.cart.pop(self.cart_tree.index(selected[0]))
        self._render_cart()

    def clear_cart(self):
        self.cart = []
        self._render_cart()

    def _render_cart(self):
        for item in self.cart_tree.get_children():
            self.cart_tree.delete(item)
        for line in self.cart:
            self.cart_tree.insert(
                "",
                "end",
                values=(
                    f"{line['subtotal']:,.2f}",
                    f"{line.get('unit_price', line['product']['selling_price']):,.2f}",
                    line["quantity"],
                    line.get("unit_name", "Piece"),
                    line["product"]["name"],
                ),
            )
        self._update_totals()

    def _get_discount_value(self):
        try:
            discount = float(self.ent_discount.get() or 0.0)
        except ValueError:
            return 0.0
        return max(0.0, discount)

    def _update_totals(self):
        subtotal = sum(line["subtotal"] for line in self.cart)
        tax = calculate_tax(subtotal)
        discount = self._get_discount_value()
        total = max(0.0, subtotal + tax - discount)
        self.lbl_subtotal.config(text=f"{subtotal:,.2f}")
        self.lbl_tax.config(text=f"{tax:,.2f}")
        self.lbl_total.config(text=f"{total:,.2f}")

    def _complete_checkout(self):
        if not self.active_session:
            messagebox.showwarning("جلسة الكاشير", "لا توجد جلسة كاشير مفتوحة")
            return
        if not self.cart:
            messagebox.showwarning("سلة فارغة", "سلة المشتريات فارغة. يرجى إضافة منتجات قبل إتمام عملية الدفع.")
            return

        subtotal = sum(line["subtotal"] for line in self.cart)
        tax = calculate_tax(subtotal)
        discount = self._get_discount_value()
        total = max(0.0, subtotal + tax - discount)
        payment_method = self.cb_payment.get().strip()

        customer_id = None
        customer_index = self.cb_customer.current()
        if customer_index >= 0:
            customer_id = self.customers_list[customer_index]["id"]

        sale_items = [
            {
                "product_id": line["product"]["id"],
                "product_unit_id": line.get("product_unit_id"),
                "unit_name": line.get("unit_name", "Piece"),
                "quantity": line["quantity"],
                "unit_price": line.get("unit_price", line["product"]["selling_price"]),
                "pieces_per_unit": line.get("pieces_per_unit", 1),
                "base_quantity": line.get("base_quantity", line["quantity"]),
                "subtotal": line["subtotal"],
            }
            for line in self.cart
        ]

        self.btn_checkout.config(state="disabled")
        success, result = record_sale(customer_id, sale_items, total, discount, tax, payment_method, session_id=self.active_session["id"])
        if success:
            sale_id = result
            messagebox.showinfo("تمت العملية بنجاح!", f"تم إصدار الفاتورة رقم #{sale_id} بنجاح!\nالمبلغ الإجمالي المدفوع: {total:,.2f} عبر {payment_method}")
            self.clear_cart()
            self.refresh_data()
            self.controller.refresh_all_views()
        else:
            messagebox.showerror("فشل إتمام العملية", result)
            self._update_financial_controls()

    def _show_open_session_modal(self):
        modal = tk.Toplevel(self)
        modal.title("فتح جلسة جديدة")
        modal.geometry("420x310")
        modal.config(bg="white", padx=25, pady=25)
        modal.grab_set()

        tk.Label(modal, text="فتح جلسة الكاشير", font=("Helvetica", 18, "bold"), bg="white", fg="#0f172a").pack(pady=(0, 20))

        form = tk.Frame(modal, bg="white")
        form.pack(fill="both", expand=True)

        tk.Label(form, text="الرصيد الافتتاحي", font=("Helvetica", 11, "bold"), bg="white").grid(row=0, column=1, sticky="e", pady=8, padx=10)
        ent_balance = tk.Entry(form, font=("Helvetica", 12), width=22, justify="right")
        ent_balance.grid(row=0, column=0, pady=8, padx=5)
        ent_balance.focus_set()

        tk.Label(form, text="ملاحظات الافتتاح", font=("Helvetica", 11, "bold"), bg="white").grid(row=1, column=1, sticky="ne", pady=8, padx=10)
        txt_notes = tk.Text(form, font=("Helvetica", 11), width=24, height=5)
        txt_notes.grid(row=1, column=0, pady=8, padx=5)

        buttons = tk.Frame(modal, bg="white")
        buttons.pack(fill="x", pady=(15, 0))

        btn_cancel = tk.Button(buttons, text="إلغاء", font=("Helvetica", 11, "bold"), bg="#e2e8f0", fg="#0f172a", padx=15, pady=8, bd=0, cursor="hand2", command=modal.destroy)
        btn_cancel.pack(side="left")

        btn_open = tk.Button(buttons, text="فتح الجلسة", font=("Helvetica", 11, "bold"), bg="#16a34a", fg="white", padx=15, pady=8, bd=0, cursor="hand2")
        btn_open.pack(side="right")

        def submit_open_session():
            balance_text = ent_balance.get().strip()
            notes = txt_notes.get("1.0", "end").strip()
            if not balance_text:
                messagebox.showwarning("جلسة الكاشير", "الرصيد الافتتاحي غير صحيح", parent=modal)
                return
            btn_open.config(state="disabled")
            success, result = open_pos_session(balance_text, notes)
            if success:
                messagebox.showinfo("جلسة الكاشير", "تم فتح الجلسة بنجاح", parent=modal)
                modal.destroy()
                self.refresh_data()
                self.controller.refresh_all_views()
            else:
                btn_open.config(state="normal")
                messagebox.showerror("جلسة الكاشير", result, parent=modal)

        btn_open.config(command=submit_open_session)

    def _show_close_session_modal(self):
        if not self.active_session or not self.session_summary:
            messagebox.showwarning("جلسة الكاشير", "لا توجد جلسة كاشير مفتوحة")
            return
        if self.cart and not messagebox.askyesno("إغلاق الجلسة", "توجد عناصر في سلة المشتريات الحالية. هل تريد متابعة إغلاق الجلسة ومسح السلة؟"):
            return

        summary = calculate_session_summary(self.active_session["id"])
        modal = tk.Toplevel(self)
        modal.title("إغلاق جلسة الكاشير")
        modal.geometry("520x620")
        modal.config(bg="white", padx=25, pady=25)
        modal.grab_set()

        tk.Label(modal, text="إغلاق جلسة الكاشير", font=("Helvetica", 18, "bold"), bg="white", fg="#0f172a").pack(pady=(0, 15))

        details = tk.Frame(modal, bg="white")
        details.pack(fill="x")

        rows = [
            ("الرصيد الافتتاحي", summary["opening_balance"]),
            ("المبيعات النقدية", summary["cash_sales"]),
            ("مبيعات البطاقات", summary["card_sales"]),
            ("المدفوعات الإلكترونية", summary["electronic_sales"]),
            ("المرتجعات النقدية", summary["cash_returns"]),
            ("المرتجعات غير النقدية", summary["total_returns"] - summary["cash_returns"]),
            ("المصروفات النقدية", summary["cash_expenses"]),
            ("المصروفات غير النقدية", summary["non_cash_expenses"]),
            ("الرصيد المتوقع", summary["expected_cash_balance"]),
        ]
        for idx, (label_text, value) in enumerate(rows):
            tk.Label(details, text=label_text, font=("Helvetica", 11, "bold"), bg="white", fg="#334155").grid(row=idx, column=1, sticky="e", pady=5, padx=10)
            tk.Label(details, text=f"{value:,.2f}", font=("Helvetica", 11), bg="white", fg="#0f172a").grid(row=idx, column=0, sticky="w", pady=5, padx=5)

        actual_frame = tk.Frame(modal, bg="white")
        actual_frame.pack(fill="x", pady=(15, 0))

        tk.Label(actual_frame, text="الرصيد الفعلي", font=("Helvetica", 11, "bold"), bg="white").grid(row=0, column=1, sticky="e", pady=8, padx=10)
        ent_actual = tk.Entry(actual_frame, font=("Helvetica", 12), width=18, justify="right")
        ent_actual.grid(row=0, column=0, pady=8, padx=5)

        lbl_difference = tk.Label(actual_frame, text="الفرق: 0.00 (متوازن)", font=("Helvetica", 12, "bold"), bg="white", fg="#16a34a")
        lbl_difference.grid(row=1, column=0, columnspan=2, sticky="e", pady=(5, 0))

        tk.Label(modal, text="ملاحظات الإغلاق", font=("Helvetica", 11, "bold"), bg="white").pack(anchor="e", pady=(15, 5))
        txt_notes = tk.Text(modal, font=("Helvetica", 11), height=5)
        txt_notes.pack(fill="x")

        def update_difference_label(event=None):
            try:
                actual_balance = float(ent_actual.get() or 0.0)
            except ValueError:
                lbl_difference.config(text="الفرق: --", fg="#dc2626")
                return
            difference = actual_balance - summary["expected_cash_balance"]
            if difference > 0:
                status = "زيادة"
                color = "#d97706"
            elif difference < 0:
                status = "عجز"
                color = "#dc2626"
            else:
                status = "متوازن"
                color = "#16a34a"
            lbl_difference.config(text=f"الفرق: {difference:,.2f} ({status})", fg=color)

        ent_actual.bind("<KeyRelease>", update_difference_label)

        footer = tk.Frame(modal, bg="white")
        footer.pack(fill="x", pady=(20, 0))

        btn_cancel = tk.Button(footer, text="إلغاء", font=("Helvetica", 11, "bold"), bg="#e2e8f0", fg="#0f172a", padx=15, pady=8, bd=0, cursor="hand2", command=modal.destroy)
        btn_cancel.pack(side="left")

        btn_confirm = tk.Button(footer, text="تأكيد إغلاق الجلسة", font=("Helvetica", 11, "bold"), bg="#dc2626", fg="white", padx=15, pady=8, bd=0, cursor="hand2")
        btn_confirm.pack(side="right")

        def submit_close_session():
            actual_value = ent_actual.get().strip()
            if not actual_value:
                messagebox.showwarning("جلسة الكاشير", "أدخل الرصيد الفعلي الموجود في الدرج", parent=modal)
                return
            btn_confirm.config(state="disabled")
            success, result = close_pos_session(self.active_session["id"], actual_value, txt_notes.get("1.0", "end").strip())
            if success:
                modal.destroy()
                self.clear_cart()
                self.refresh_data()
                self.controller.refresh_all_views()
                self._show_session_summary_report(result)
            else:
                btn_confirm.config(state="normal")
                messagebox.showerror("جلسة الكاشير", result, parent=modal)

        btn_confirm.config(command=submit_close_session)

    def _show_expense_modal(self):
        if not self.active_session:
            messagebox.showwarning("المصروفات", "لا توجد جلسة كاشير مفتوحة")
            return

        modal = tk.Toplevel(self)
        modal.title("إضافة مصروف")
        modal.geometry("820x620")
        modal.config(bg="white", padx=20, pady=20)
        modal.grab_set()
        modal.columnconfigure(0, weight=1)
        modal.rowconfigure(2, weight=1)

        tk.Label(modal, text="مصروفات الجلسة الحالية", font=("Helvetica", 18, "bold"), bg="white", fg="#0f172a").grid(row=0, column=0, sticky="e", pady=(0, 15))

        form = tk.Frame(modal, bg="#f8fafc", padx=15, pady=15, bd=1, relief="solid")
        form.grid(row=1, column=0, sticky="ew", pady=(0, 15))

        tk.Label(form, text="نوع المصروف", font=("Helvetica", 11, "bold"), bg="#f8fafc").grid(row=0, column=1, sticky="e", pady=6, padx=8)
        cb_category = ttk.Combobox(form, values=EXPENSE_CATEGORIES, state="readonly", font=("Helvetica", 11), width=22, justify="right")
        cb_category.set(EXPENSE_CATEGORIES[0])
        cb_category.grid(row=0, column=0, sticky="w", pady=6)

        tk.Label(form, text="الوصف", font=("Helvetica", 11, "bold"), bg="#f8fafc").grid(row=1, column=1, sticky="e", pady=6, padx=8)
        ent_description = tk.Entry(form, font=("Helvetica", 11), width=28, justify="right")
        ent_description.grid(row=1, column=0, sticky="w", pady=6)

        tk.Label(form, text="المبلغ", font=("Helvetica", 11, "bold"), bg="#f8fafc").grid(row=2, column=1, sticky="e", pady=6, padx=8)
        ent_amount = tk.Entry(form, font=("Helvetica", 11), width=20, justify="right")
        ent_amount.grid(row=2, column=0, sticky="w", pady=6)

        tk.Label(form, text="طريقة الدفع", font=("Helvetica", 11, "bold"), bg="#f8fafc").grid(row=0, column=3, sticky="e", pady=6, padx=8)
        cb_payment = ttk.Combobox(form, values=EXPENSE_PAYMENT_METHODS, state="readonly", font=("Helvetica", 11), width=20, justify="right")
        cb_payment.set(EXPENSE_PAYMENT_METHODS[0])
        cb_payment.grid(row=0, column=2, sticky="w", pady=6)

        tk.Label(form, text="رقم المرجع", font=("Helvetica", 11, "bold"), bg="#f8fafc").grid(row=1, column=3, sticky="e", pady=6, padx=8)
        ent_reference = tk.Entry(form, font=("Helvetica", 11), width=24, justify="right")
        ent_reference.grid(row=1, column=2, sticky="w", pady=6)

        tk.Label(form, text="ملاحظات", font=("Helvetica", 11, "bold"), bg="#f8fafc").grid(row=2, column=3, sticky="ne", pady=6, padx=8)
        txt_notes = tk.Text(form, font=("Helvetica", 11), width=24, height=4)
        txt_notes.grid(row=2, column=2, sticky="w", pady=6)

        tree_frame = tk.Frame(modal, bg="white")
        tree_frame.grid(row=2, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        columns = ("payment", "amount", "category", "date", "id")
        expense_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        expense_tree.heading("id", text="الرقم")
        expense_tree.heading("date", text="التاريخ")
        expense_tree.heading("category", text="نوع المصروف")
        expense_tree.heading("amount", text="المبلغ")
        expense_tree.heading("payment", text="طريقة الدفع")

        expense_tree.column("id", width=70, anchor="center")
        expense_tree.column("date", width=180, anchor="center")
        expense_tree.column("category", width=180, anchor="e")
        expense_tree.column("amount", width=110, anchor="center")
        expense_tree.column("payment", width=120, anchor="center")

        expense_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=expense_tree.yview)
        expense_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

        footer = tk.Frame(modal, bg="white")
        footer.grid(row=3, column=0, sticky="ew", pady=(15, 0))

        btn_delete = tk.Button(footer, text="حذف المصروف المحدد", font=("Helvetica", 11, "bold"), bg="#fee2e2", fg="#dc2626", padx=12, pady=6, bd=0, cursor="hand2")
        btn_delete.pack(side="left", padx=4)
        btn_details = tk.Button(footer, text="تفاصيل المصروف", font=("Helvetica", 11, "bold"), bg="#e2e8f0", fg="#0f172a", padx=12, pady=6, bd=0, cursor="hand2")
        btn_details.pack(side="left", padx=4)
        btn_close = tk.Button(footer, text="إغلاق", font=("Helvetica", 11, "bold"), bg="#e2e8f0", fg="#0f172a", padx=12, pady=6, bd=0, cursor="hand2", command=modal.destroy)
        btn_close.pack(side="right", padx=4)
        btn_save = tk.Button(footer, text="تسجيل المصروف", font=("Helvetica", 11, "bold"), bg="#d97706", fg="white", padx=12, pady=6, bd=0, cursor="hand2")
        btn_save.pack(side="right", padx=4)

        def refresh_expenses_tree():
            for item in expense_tree.get_children():
                expense_tree.delete(item)
            for expense in get_session_expenses(self.active_session["id"]):
                expense_tree.insert("", "end", iid=str(expense["id"]), values=(expense["payment_method"], f"{expense['amount']:,.2f}", expense["category"], expense["expense_date"], expense["id"]))
            self.refresh_data()
            self.controller.refresh_all_views()

        def save_expense():
            btn_save.config(state="disabled")
            success, result = add_expense(
                self.active_session["id"],
                cb_category.get().strip(),
                ent_description.get().strip(),
                ent_amount.get().strip(),
                cb_payment.get().strip(),
                ent_reference.get().strip(),
                txt_notes.get("1.0", "end").strip(),
            )
            if success:
                messagebox.showinfo("المصروفات", "تم تسجيل المصروف بنجاح", parent=modal)
                ent_description.delete(0, "end")
                ent_amount.delete(0, "end")
                ent_reference.delete(0, "end")
                txt_notes.delete("1.0", "end")
                btn_save.config(state="normal")
                refresh_expenses_tree()
            else:
                btn_save.config(state="normal")
                messagebox.showerror("المصروفات", result, parent=modal)

        def show_selected_expense_details():
            selected = expense_tree.selection()
            if not selected:
                messagebox.showinfo("المصروفات", "يرجى تحديد مصروف من الجدول.", parent=modal)
                return
            expense = get_expense(int(selected[0]))
            if not expense:
                messagebox.showerror("المصروفات", "المصروف غير موجود", parent=modal)
                refresh_expenses_tree()
                return

            detail = tk.Toplevel(modal)
            detail.title(f"تفاصيل المصروف #{expense['id']}")
            detail.geometry("420x320")
            detail.config(bg="white", padx=20, pady=20)
            detail.grab_set()

            tk.Label(detail, text=f"مصروف رقم #{expense['id']}", font=("Helvetica", 16, "bold"), bg="white", fg="#0f172a").pack(pady=(0, 15))
            lines = [
                f"التاريخ: {expense['expense_date']}",
                f"نوع المصروف: {expense['category']}",
                f"الوصف: {expense['description']}",
                f"المبلغ: {expense['amount']:,.2f}",
                f"طريقة الدفع: {expense['payment_method']}",
                f"رقم المرجع: {expense['reference_number'] or '—'}",
                f"ملاحظات: {expense['notes'] or '—'}",
            ]
            for text in lines:
                tk.Label(detail, text=text, font=("Helvetica", 11), bg="white", fg="#334155", anchor="e", justify="right").pack(fill="x", pady=4)
            tk.Button(detail, text="إغلاق", font=("Helvetica", 11, "bold"), bg="#e2e8f0", fg="#0f172a", padx=12, pady=6, bd=0, cursor="hand2", command=detail.destroy).pack(pady=(15, 0))

        def delete_selected_expense():
            selected = expense_tree.selection()
            if not selected:
                messagebox.showinfo("المصروفات", "يرجى تحديد مصروف من الجدول.", parent=modal)
                return
            if not messagebox.askyesno("حذف المصروف", "هل أنت متأكد من حذف المصروف المحدد؟", parent=modal):
                return
            success, result = delete_expense(int(selected[0]))
            if success:
                messagebox.showinfo("المصروفات", result, parent=modal)
                refresh_expenses_tree()
            else:
                messagebox.showerror("المصروفات", result, parent=modal)

        btn_save.config(command=save_expense)
        btn_details.config(command=show_selected_expense_details)
        btn_delete.config(command=delete_selected_expense)
        expense_tree.bind("<Double-1>", lambda event: show_selected_expense_details())
        refresh_expenses_tree()

    def _show_return_modal(self):
        if not self.active_session:
            messagebox.showwarning("الاسترجاع", "لا توجد جلسة كاشير مفتوحة")
            return

        modal = tk.Toplevel(self)
        modal.title("فاتورة استرجاع")
        modal.geometry("980x720")
        modal.config(bg="white", padx=20, pady=20)
        modal.grab_set()
        modal.columnconfigure(0, weight=1)
        modal.rowconfigure(2, weight=1)

        state = {"sale": None, "items": [], "selected_quantities": {}}

        search_bar = tk.Frame(modal, bg="white")
        search_bar.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        tk.Label(search_bar, text="رقم الفاتورة الأصلية:", font=("Helvetica", 11, "bold"), bg="white").pack(side="right", padx=5)
        ent_sale_id = tk.Entry(search_bar, font=("Helvetica", 12), width=18, justify="right")
        ent_sale_id.pack(side="right", padx=5)
        btn_search = tk.Button(search_bar, text="بحث", font=("Helvetica", 11, "bold"), bg="#2563eb", fg="white", padx=12, pady=6, bd=0, cursor="hand2")
        btn_search.pack(side="right", padx=5)

        info_frame = tk.Frame(modal, bg="#f8fafc", padx=15, pady=15, bd=1, relief="solid")
        info_frame.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        info_labels = {}
        info_fields = [
            "رقم الفاتورة",
            "تاريخ البيع",
            "العميل",
            "طريقة الدفع الأصلية",
            "المجموع الفرعي",
            "الضريبة",
            "الخصم",
            "الإجمالي الأصلي",
            "إجمالي المسترجع سابقًا",
            "المبلغ المتبقي للاسترجاع",
        ]
        for index, field in enumerate(info_fields):
            label = tk.Label(info_frame, text=f"{field}: —", font=("Helvetica", 10, "bold" if index < 4 else "normal"), bg="#f8fafc", fg="#334155", anchor="e")
            label.grid(row=index // 2, column=index % 2, sticky="ew", padx=8, pady=4)
            info_labels[field] = label

        body = tk.Frame(modal, bg="white")
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        columns = ("value", "return_qty", "price", "available", "returned", "sold", "sku", "product")
        return_tree = ttk.Treeview(body, columns=columns, show="headings", height=12)
        return_tree.heading("product", text="المنتج")
        return_tree.heading("sku", text="SKU")
        return_tree.heading("sold", text="الكمية المباعة")
        return_tree.heading("returned", text="المسترجع سابقًا")
        return_tree.heading("available", text="المتاح للاسترجاع")
        return_tree.heading("price", text="سعر الوحدة")
        return_tree.heading("return_qty", text="كمية الاسترجاع")
        return_tree.heading("value", text="قيمة الاسترجاع")

        return_tree.column("product", width=220, anchor="e")
        return_tree.column("sku", width=110, anchor="center")
        return_tree.column("sold", width=90, anchor="center")
        return_tree.column("returned", width=110, anchor="center")
        return_tree.column("available", width=110, anchor="center")
        return_tree.column("price", width=100, anchor="center")
        return_tree.column("return_qty", width=100, anchor="center")
        return_tree.column("value", width=110, anchor="center")
        return_tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(body, orient="vertical", command=return_tree.yview)
        return_tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")

        controls = tk.Frame(modal, bg="white")
        controls.grid(row=3, column=0, sticky="ew", pady=(15, 10))
        tk.Label(controls, text="كمية الاسترجاع للصنف المحدد:", font=("Helvetica", 11, "bold"), bg="white").pack(side="right", padx=5)
        ent_qty = tk.Entry(controls, font=("Helvetica", 11), width=8, justify="center")
        ent_qty.pack(side="right", padx=5)
        btn_apply_qty = tk.Button(controls, text="تحديث الكمية", font=("Helvetica", 11, "bold"), bg="#475569", fg="white", padx=12, pady=6, bd=0, cursor="hand2")
        btn_apply_qty.pack(side="right", padx=5)
        btn_clear_qty = tk.Button(controls, text="تصفير المحدد", font=("Helvetica", 11, "bold"), bg="#e2e8f0", fg="#0f172a", padx=12, pady=6, bd=0, cursor="hand2")
        btn_clear_qty.pack(side="right", padx=5)

        summary_frame = tk.Frame(modal, bg="#f8fafc", padx=15, pady=15, bd=1, relief="solid")
        summary_frame.grid(row=4, column=0, sticky="ew")

        tk.Label(summary_frame, text="طريقة الاسترجاع", font=("Helvetica", 11, "bold"), bg="#f8fafc").grid(row=0, column=3, sticky="e", pady=6, padx=8)
        cb_refund = ttk.Combobox(summary_frame, values=RETURN_REFUND_METHODS, state="readonly", font=("Helvetica", 11), width=22, justify="right")
        cb_refund.set(RETURN_REFUND_METHODS[0])
        cb_refund.grid(row=0, column=2, sticky="w", pady=6)

        tk.Label(summary_frame, text="سبب الاسترجاع", font=("Helvetica", 11, "bold"), bg="#f8fafc").grid(row=0, column=1, sticky="e", pady=6, padx=8)
        cb_reason = ttk.Combobox(summary_frame, values=RETURN_REASONS, state="readonly", font=("Helvetica", 11), width=20, justify="right")
        cb_reason.set(RETURN_REASONS[0])
        cb_reason.grid(row=0, column=0, sticky="w", pady=6)

        tk.Label(summary_frame, text="ملاحظات", font=("Helvetica", 11, "bold"), bg="#f8fafc").grid(row=1, column=3, sticky="ne", pady=6, padx=8)
        txt_notes = tk.Text(summary_frame, font=("Helvetica", 11), width=28, height=4)
        txt_notes.grid(row=1, column=2, sticky="w", pady=6)

        lbl_preview = tk.Label(summary_frame, text="إجمالي الاسترجاع المتوقع: 0.00", font=("Helvetica", 13, "bold"), bg="#f8fafc", fg="#2563eb")
        lbl_preview.grid(row=1, column=0, columnspan=2, sticky="e", pady=6)
        lbl_breakdown = tk.Label(summary_frame, text="", font=("Helvetica", 10), bg="#f8fafc", fg="#64748b")
        lbl_breakdown.grid(row=2, column=0, columnspan=4, sticky="e", pady=(4, 0))

        footer = tk.Frame(modal, bg="white")
        footer.grid(row=5, column=0, sticky="ew", pady=(15, 0))
        btn_close = tk.Button(footer, text="إغلاق", font=("Helvetica", 11, "bold"), bg="#e2e8f0", fg="#0f172a", padx=12, pady=6, bd=0, cursor="hand2", command=modal.destroy)
        btn_close.pack(side="left")
        btn_confirm = tk.Button(footer, text="تأكيد الاسترجاع", font=("Helvetica", 11, "bold"), bg="#dc2626", fg="white", padx=12, pady=6, bd=0, cursor="hand2")
        btn_confirm.pack(side="right")

        def selected_items_payload():
            return [
                {"original_sale_item_id": sale_item_id, "quantity": qty}
                for sale_item_id, qty in state["selected_quantities"].items() if qty > 0
            ]

        def refresh_return_tree():
            for item in return_tree.get_children():
                return_tree.delete(item)
            for item in state["items"]:
                selected_qty = state["selected_quantities"].get(item["id"], 0)
                return_value = selected_qty * item["unit_price"]
                return_tree.insert(
                    "",
                    "end",
                    iid=str(item["id"]),
                    values=(
                        f"{return_value:,.2f}",
                        selected_qty,
                        f"{item['unit_price']:,.2f}",
                        item["available_return_quantity"],
                        item["returned_quantity"],
                        item["quantity"],
                        item["sku"],
                        item["product_name"],
                    ),
                )
            update_preview()

        def update_preview():
            payload = selected_items_payload()
            if not state["sale"] or not payload:
                lbl_preview.config(text="إجمالي الاسترجاع المتوقع: 0.00")
                lbl_breakdown.config(text="")
                return
            success, result = preview_sale_return(state["sale"]["id"], payload, cb_refund.get().strip())
            if success:
                totals = result["totals"]
                lbl_preview.config(text=f"إجمالي الاسترجاع المتوقع: {totals['total_amount']:,.2f}")
                lbl_breakdown.config(text=f"المجموع الفرعي: {totals['subtotal']:,.2f} | الضريبة: {totals['tax_amount']:,.2f} | الخصم: {totals['discount_amount']:,.2f}")
            else:
                lbl_preview.config(text=f"إجمالي الاسترجاع المتوقع: --")
                lbl_breakdown.config(text=result)

        def load_sale():
            sale_id_text = ent_sale_id.get().strip()
            if not sale_id_text.isdigit():
                messagebox.showwarning("الاسترجاع", "رقم الفاتورة غير موجود", parent=modal)
                return
            sale = get_sale_for_return(int(sale_id_text))
            if not sale:
                messagebox.showwarning("الاسترجاع", "رقم الفاتورة غير موجود", parent=modal)
                return
            items = get_returnable_sale_items(sale["id"])
            if not any(item["available_return_quantity"] > 0 for item in items):
                messagebox.showwarning("الاسترجاع", "لا توجد كميات متاحة للاسترجاع", parent=modal)
                return
            state["sale"] = sale
            state["items"] = items
            state["selected_quantities"] = {}
            info_labels["رقم الفاتورة"].config(text=f"رقم الفاتورة: #{sale['id']}")
            info_labels["تاريخ البيع"].config(text=f"تاريخ البيع: {sale['sale_date']}")
            info_labels["العميل"].config(text=f"العميل: {sale['customer_name'] or 'عميل عام (نقدي)'}")
            info_labels["طريقة الدفع الأصلية"].config(text=f"طريقة الدفع الأصلية: {sale['payment_method']}")
            info_labels["المجموع الفرعي"].config(text=f"المجموع الفرعي: {sale['subtotal_amount']:,.2f}")
            info_labels["الضريبة"].config(text=f"الضريبة: {sale['tax_amount']:,.2f}")
            info_labels["الخصم"].config(text=f"الخصم: {sale['discount']:,.2f}")
            info_labels["الإجمالي الأصلي"].config(text=f"الإجمالي الأصلي: {sale['total_amount']:,.2f}")
            info_labels["إجمالي المسترجع سابقًا"].config(text=f"إجمالي المسترجع سابقًا: {sale['returned_total']:,.2f}")
            info_labels["المبلغ المتبقي للاسترجاع"].config(text=f"المبلغ المتبقي للاسترجاع: {sale['remaining_returnable_amount']:,.2f}")
            refresh_return_tree()

        def apply_selected_quantity(quantity_value=None):
            selected = return_tree.selection()
            if not selected:
                messagebox.showinfo("الاسترجاع", "يرجى تحديد صنف من الجدول.", parent=modal)
                return
            item = next((row for row in state["items"] if row["id"] == int(selected[0])), None)
            if not item:
                return
            try:
                qty = int(quantity_value if quantity_value is not None else ent_qty.get().strip())
            except ValueError:
                messagebox.showerror("الاسترجاع", "أدخل كمية صحيحة للاسترجاع", parent=modal)
                return
            if qty < 0:
                messagebox.showerror("الاسترجاع", "أدخل كمية صحيحة للاسترجاع", parent=modal)
                return
            if qty > item["available_return_quantity"]:
                messagebox.showerror("الاسترجاع", "الكمية المرتجعة أكبر من الكمية المتاحة", parent=modal)
                return
            if qty == 0:
                state["selected_quantities"].pop(item["id"], None)
            else:
                state["selected_quantities"][item["id"]] = qty
            refresh_return_tree()

        def clear_selected_quantity():
            selected = return_tree.selection()
            if not selected:
                return
            state["selected_quantities"].pop(int(selected[0]), None)
            refresh_return_tree()

        def confirm_return():
            if not state["sale"]:
                messagebox.showwarning("الاسترجاع", "ابحث عن الفاتورة الأصلية أولاً", parent=modal)
                return
            payload = selected_items_payload()
            if not payload:
                messagebox.showwarning("الاسترجاع", "اختر منتجًا واحدًا على الأقل للاسترجاع", parent=modal)
                return
            btn_confirm.config(state="disabled")
            success, result = record_sale_return(
                state["sale"]["id"],
                self.active_session["id"],
                payload,
                cb_refund.get().strip(),
                cb_reason.get().strip(),
                txt_notes.get("1.0", "end").strip(),
            )
            if success:
                return_id = result
                modal.destroy()
                self.refresh_data()
                self.controller.refresh_all_views()
                self._show_return_receipt(return_id)
            else:
                btn_confirm.config(state="normal")
                messagebox.showerror("الاسترجاع", result, parent=modal)

        btn_search.config(command=load_sale)
        btn_apply_qty.config(command=apply_selected_quantity)
        btn_clear_qty.config(command=clear_selected_quantity)
        btn_confirm.config(command=confirm_return)
        cb_refund.bind("<<ComboboxSelected>>", lambda event: update_preview())
        return_tree.bind("<Double-1>", lambda event: apply_selected_quantity(ent_qty.get().strip() or 0))

    def _show_return_receipt(self, return_id):
        data = get_return_details(return_id)
        if not data:
            messagebox.showerror("الاسترجاع", "تعذر تحميل تفاصيل فاتورة الاسترجاع")
            return
        header = data["header"]
        items = data["items"]

        modal = tk.Toplevel(self)
        modal.title(f"فاتورة استرجاع #{return_id}")
        modal.geometry("700x560")
        modal.config(bg="white", padx=20, pady=20)
        modal.grab_set()

        tk.Label(modal, text="فاتورة استرجاع", font=("Helvetica", 20, "bold"), bg="white", fg="#0f172a").pack(pady=(0, 8))
        tk.Label(modal, text=f"رقم فاتورة الاسترجاع: #{header['id']} | الفاتورة الأصلية: #{header['original_sale_id']}", font=("Helvetica", 11), bg="white", fg="#334155").pack()
        tk.Label(modal, text=f"التاريخ: {header['return_date']} | الجلسة: #{header['session_id']} | العميل: {header['customer_name'] or 'عميل عام (نقدي)'}", font=("Helvetica", 11), bg="white", fg="#334155").pack(pady=(4, 0))
        tk.Label(modal, text=f"طريقة الاسترجاع: {header['refund_method']} | السبب: {header['reason'] or '—'}", font=("Helvetica", 11), bg="white", fg="#334155").pack(pady=(4, 12))

        frame_items = tk.Frame(modal, bg="white")
        frame_items.pack(fill="both", expand=True)
        columns = ("total", "discount", "tax", "subtotal", "price", "qty", "item")
        tree = ttk.Treeview(frame_items, columns=columns, show="headings", height=12)
        tree.heading("item", text="المنتج")
        tree.heading("qty", text="الكمية")
        tree.heading("price", text="سعر الوحدة")
        tree.heading("subtotal", text="المجموع الفرعي")
        tree.heading("tax", text="الضريبة")
        tree.heading("discount", text="الخصم")
        tree.heading("total", text="الإجمالي")

        tree.column("item", width=250, anchor="e")
        tree.column("qty", width=70, anchor="center")
        tree.column("price", width=90, anchor="center")
        tree.column("subtotal", width=100, anchor="center")
        tree.column("tax", width=90, anchor="center")
        tree.column("discount", width=90, anchor="center")
        tree.column("total", width=100, anchor="center")
        tree.pack(fill="both", expand=True)

        subtotal = 0.0
        tax_amount = 0.0
        discount_amount = 0.0
        for item in items:
            subtotal += item["subtotal"]
            tax_amount += item["tax_amount"]
            discount_amount += item["discount_amount"]
            tree.insert(
                "",
                "end",
                values=(
                    f"{item['line_total']:,.2f}",
                    f"{item['discount_amount']:,.2f}",
                    f"{item['tax_amount']:,.2f}",
                    f"{item['subtotal']:,.2f}",
                    f"{item['unit_price']:,.2f}",
                    item["quantity"],
                    f"[{item['sku']}] {item['product_name']}",
                ),
            )

        tk.Label(modal, text=f"المجموع الفرعي: {subtotal:,.2f} | الضريبة المرتجعة: {tax_amount:,.2f} | الخصم المرتجع: {discount_amount:,.2f}", font=("Helvetica", 11), bg="white", fg="#334155").pack(pady=(12, 4))
        tk.Label(modal, text=f"إجمالي المبلغ المسترد: {header['total_amount']:,.2f}", font=("Helvetica", 18, "bold"), bg="white", fg="#dc2626").pack(pady=(0, 12))
        if header["notes"]:
            tk.Label(modal, text=f"ملاحظات: {header['notes']}", font=("Helvetica", 11), bg="white", fg="#64748b").pack(pady=(0, 8))
        tk.Button(modal, text="إغلاق", font=("Helvetica", 11, "bold"), bg="#e2e8f0", fg="#0f172a", padx=12, pady=6, bd=0, cursor="hand2", command=modal.destroy).pack()

    def _show_session_history_modal(self):
        modal = tk.Toplevel(self)
        modal.title("سجل جلسات الكاشير")
        modal.geometry("860x520")
        modal.config(bg="white", padx=20, pady=20)
        modal.grab_set()

        tk.Label(modal, text="سجل جلسات الكاشير", font=("Helvetica", 18, "bold"), bg="white", fg="#0f172a").pack(pady=(0, 15))

        frame = tk.Frame(modal, bg="white")
        frame.pack(fill="both", expand=True)
        columns = ("status", "difference", "actual", "expected", "opening", "closed", "opened", "id")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=14)
        tree.heading("id", text="الجلسة")
        tree.heading("opened", text="وقت الفتح")
        tree.heading("closed", text="وقت الإغلاق")
        tree.heading("opening", text="الرصيد الافتتاحي")
        tree.heading("expected", text="الرصيد المتوقع")
        tree.heading("actual", text="الرصيد الفعلي")
        tree.heading("difference", text="الفرق")
        tree.heading("status", text="الحالة")

        tree.column("id", width=70, anchor="center")
        tree.column("opened", width=160, anchor="center")
        tree.column("closed", width=160, anchor="center")
        tree.column("opening", width=110, anchor="center")
        tree.column("expected", width=110, anchor="center")
        tree.column("actual", width=110, anchor="center")
        tree.column("difference", width=90, anchor="center")
        tree.column("status", width=90, anchor="center")

        tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

        for session in get_pos_sessions(limit=100):
            summary = calculate_session_summary(session["id"])
            tree.insert(
                "",
                "end",
                iid=str(session["id"]),
                values=(
                    "مغلقة" if session["status"] == "CLOSED" else "مفتوحة",
                    f"{(summary['difference'] or 0.0):,.2f}" if summary else "—",
                    f"{summary['actual_closing_balance']:,.2f}" if summary and summary["actual_closing_balance"] is not None else "—",
                    f"{summary['expected_cash_balance']:,.2f}" if summary else "—",
                    f"{session['opening_balance']:,.2f}",
                    session["closed_at"] or "—",
                    session["opened_at"],
                    session["id"],
                ),
            )

        def open_selected_session(event=None):
            selected = tree.selection()
            if not selected:
                return
            self._show_session_summary_report(int(selected[0]))

        tree.bind("<Double-1>", open_selected_session)
        tk.Button(modal, text="عرض التقرير", font=("Helvetica", 11, "bold"), bg="#2563eb", fg="white", padx=12, pady=6, bd=0, cursor="hand2", command=open_selected_session).pack(side="right", pady=(15, 0))
        tk.Button(modal, text="إغلاق", font=("Helvetica", 11, "bold"), bg="#e2e8f0", fg="#0f172a", padx=12, pady=6, bd=0, cursor="hand2", command=modal.destroy).pack(side="left", pady=(15, 0))

    def _show_session_summary_report(self, session_id):
        summary = calculate_session_summary(session_id)
        if not summary:
            messagebox.showerror("الجلسات", "تعذر تحميل تقرير الجلسة")
            return

        difference = summary["difference"] or 0.0
        if difference > 0:
            diff_status = "زيادة"
            diff_color = "#d97706"
        elif difference < 0:
            diff_status = "عجز"
            diff_color = "#dc2626"
        else:
            diff_status = "متوازن"
            diff_color = "#16a34a"

        modal = tk.Toplevel(self)
        modal.title(f"تقرير جلسة الكاشير #{session_id}")
        modal.geometry("760x680")
        modal.config(bg="white", padx=20, pady=20)
        modal.grab_set()

        tk.Label(modal, text=f"تقرير جلسة الكاشير #{session_id}", font=("Helvetica", 20, "bold"), bg="white", fg="#0f172a").pack(pady=(0, 15))

        sections = [
            ("معلومات الجلسة", [
                f"وقت الفتح: {summary['opened_at']}",
                f"وقت الإغلاق: {summary['closed_at'] or '—'}",
                f"الرصيد الافتتاحي: {summary['opening_balance']:,.2f}",
                f"ملاحظات الافتتاح: {summary['opening_notes'] or '—'}",
                f"ملاحظات الإغلاق: {summary['closing_notes'] or '—'}",
                f"الحالة: {'مغلقة' if summary['status'] == 'CLOSED' else 'مفتوحة'}",
            ]),
            ("المبيعات", [
                f"عدد فواتير البيع: {summary['sales_count']}",
                f"إجمالي المبيعات: {summary['total_sales']:,.2f}",
                f"المبيعات النقدية: {summary['cash_sales']:,.2f}",
                f"مبيعات البطاقات: {summary['card_sales']:,.2f}",
                f"المدفوعات الإلكترونية: {summary['electronic_sales']:,.2f}",
                f"مبيعات أخرى: {summary['other_sales']:,.2f}",
            ]),
            ("المرتجعات", [
                f"عدد فواتير الاسترجاع: {summary['returns_count']}",
                f"إجمالي الاسترجاع: {summary['total_returns']:,.2f}",
                f"المرتجعات النقدية: {summary['cash_returns']:,.2f}",
                f"مرتجعات البطاقات: {summary['card_returns']:,.2f}",
                f"مرتجعات إلكترونية: {summary['electronic_returns']:,.2f}",
                f"مرتجعات أخرى: {summary['other_returns']:,.2f}",
            ]),
            ("المصروفات", [
                f"عدد المصروفات: {summary['expenses_count']}",
                f"إجمالي المصروفات: {summary['total_expenses']:,.2f}",
                f"المصروفات النقدية: {summary['cash_expenses']:,.2f}",
                f"المصروفات غير النقدية: {summary['non_cash_expenses']:,.2f}",
            ] + [f"{category}: {amount:,.2f}" for category, amount in summary['expenses_by_category'].items()]),
            ("مطابقة النقدية", [
                f"الرصيد الافتتاحي: {summary['opening_balance']:,.2f}",
                f"المبيعات النقدية: {summary['cash_sales']:,.2f}",
                f"المرتجعات النقدية: {summary['cash_returns']:,.2f}",
                f"المصروفات النقدية: {summary['cash_expenses']:,.2f}",
                f"الرصيد المتوقع: {summary['expected_cash_balance']:,.2f}",
                f"الرصيد الفعلي: {(summary['actual_closing_balance'] if summary['actual_closing_balance'] is not None else 0.0):,.2f}",
            ]),
        ]

        body = tk.Frame(modal, bg="white")
        body.pack(fill="both", expand=True)
        for title, lines in sections:
            card = tk.Frame(body, bg="#f8fafc", padx=15, pady=12, bd=1, relief="solid")
            card.pack(fill="x", pady=6)
            tk.Label(card, text=title, font=("Helvetica", 14, "bold"), bg="#f8fafc", fg="#0f172a").pack(anchor="e", pady=(0, 6))
            for line in lines:
                tk.Label(card, text=line, font=("Helvetica", 11), bg="#f8fafc", fg="#334155", anchor="e", justify="right").pack(fill="x", pady=2)

        tk.Label(modal, text=f"الفرق: {difference:,.2f} ({diff_status})", font=("Helvetica", 16, "bold"), bg="white", fg=diff_color).pack(pady=(15, 10))
        tk.Button(modal, text="إغلاق", font=("Helvetica", 11, "bold"), bg="#e2e8f0", fg="#0f172a", padx=12, pady=6, bd=0, cursor="hand2", command=modal.destroy).pack()

    def _show_add_customer_modal(self):
        modal = tk.Toplevel(self)
        modal.title("إضافة عميل جديد")
        modal.geometry("420x320")
        modal.config(bg="white", padx=25, pady=25)
        modal.grab_set()

        tk.Label(modal, text="إضافة عميل جديد", font=("Helvetica", 18, "bold"), bg="white", fg="#0f172a").pack(pady=(0, 20))
        form = tk.Frame(modal, bg="white")
        form.pack(fill="both", expand=True)

        tk.Label(form, text="الاسم الكامل *", font=("Helvetica", 11, "bold"), bg="white").grid(row=0, column=1, sticky="e", pady=8, padx=10)
        ent_name = tk.Entry(form, font=("Helvetica", 12), width=22, justify="right")
        ent_name.grid(row=0, column=0, pady=8, padx=5)

        tk.Label(form, text="رقم الهاتف *", font=("Helvetica", 11, "bold"), bg="white").grid(row=1, column=1, sticky="e", pady=8, padx=10)
        ent_phone = tk.Entry(form, font=("Helvetica", 12), width=22, justify="right")
        ent_phone.grid(row=1, column=0, pady=8, padx=5)

        tk.Label(form, text="البريد الإلكتروني", font=("Helvetica", 11, "bold"), bg="white").grid(row=2, column=1, sticky="e", pady=8, padx=10)
        ent_email = tk.Entry(form, font=("Helvetica", 12), width=22, justify="right")
        ent_email.grid(row=2, column=0, pady=8, padx=5)

        def save_customer():
            name = ent_name.get().strip()
            phone = ent_phone.get().strip()
            email = ent_email.get().strip()
            if not name or not phone:
                messagebox.showwarning("بيانات مطلوبة", "يرجى إدخال اسم العميل ورقم الهاتف.", parent=modal)
                return
            success, message = add_customer(name, phone, email)
            if success:
                self.customers_list = get_all_customers()
                customer_names = [f"{customer['name']} ({customer['phone']})" for customer in self.customers_list]
                self.cb_customer.config(values=customer_names)
                new_index = next((index for index, customer in enumerate(self.customers_list) if customer["phone"] == phone), 0)
                if customer_names:
                    self.cb_customer.current(new_index)
                modal.destroy()
                messagebox.showinfo("نجاح", "تم تسجيل العميل بنجاح!")
            else:
                messagebox.showerror("خطأ", message, parent=modal)

        tk.Button(modal, text="💾 حفظ بيانات العميل", font=("Helvetica", 12, "bold"), bg="#16a34a", fg="white", pady=10, bd=0, cursor="hand2", command=save_customer).pack(fill="x", pady=(15, 0))