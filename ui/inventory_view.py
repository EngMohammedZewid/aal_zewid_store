import tkinter as tk
from tkinter import ttk, messagebox
from core.db import get_all_products, get_low_stock_products, get_all_categories, get_all_suppliers, add_product, update_product, delete_product, adjust_stock, add_category, get_product_units, ensure_product_unit

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


class InventoryView(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f1f5f9")
        self.controller = controller

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self.products_list = []
        self.categories_list = []
        self.suppliers_list = []

        self._build_header()
        self._build_search_filter()
        self._build_table_section()

        self.refresh_data()

    def _build_header(self):
        header_frame = tk.Frame(self, bg="#f1f5f9")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))

        title_label = tk.Label(header_frame, text="📦 المخزون وكتالوج المنتجات", font=("Helvetica", 22, "bold"), fg="#0f172a", bg="#f1f5f9")
        title_label.pack(side="right")

        actions_frame = tk.Frame(header_frame, bg="#f1f5f9")
        actions_frame.pack(side="left")

        btn_add = tk.Button(actions_frame, text="+ إضافة منتج جديد", font=("Helvetica", 11, "bold"), bg="#2563eb", fg="white",
                            padx=15, pady=6, bd=0, cursor="hand2", command=self._show_add_product_modal)
        btn_add.pack(side="right", padx=5)

        btn_cats = tk.Button(actions_frame, text="🏷️ إدارة التصنيفات", font=("Helvetica", 11, "bold"), bg="#475569", fg="white",
                             padx=15, pady=6, bd=0, cursor="hand2", command=self._show_manage_categories_modal)
        btn_cats.pack(side="right", padx=5)

        btn_low = tk.Button(actions_frame, text="⚠️ نواقص المخزون", font=("Helvetica", 11, "bold"), bg="#d97706", fg="white",
                            padx=15, pady=6, bd=0, cursor="hand2", command=self._filter_low_stock)
        btn_low.pack(side="right", padx=5)

    def _build_search_filter(self):
        filter_frame = tk.Frame(self, bg="white", padx=15, pady=10, bd=1, relief="solid")
        filter_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)

        tk.Label(filter_frame, text="بحث:", font=("Helvetica", 11, "bold"), bg="white", fg="#0f172a").pack(side="right", padx=5)
        self.ent_search = tk.Entry(filter_frame, font=("Helvetica", 12), width=25, justify="right")
        self.ent_search.pack(side="right", padx=5)
        self.ent_search.bind("<KeyRelease>", self._apply_filters)

        tk.Label(filter_frame, text="تصفية بالتصنيف:", font=("Helvetica", 11, "bold"), bg="white", fg="#0f172a").pack(side="right", padx=(20, 5))
        self.cb_cat_filter = ttk.Combobox(filter_frame, state="readonly", font=("Helvetica", 11), width=20, justify="right")
        self.cb_cat_filter.pack(side="right", padx=5)
        self.cb_cat_filter.bind("<<ComboboxSelected>>", self._apply_filters)

        btn_reset = tk.Button(filter_frame, text="🔄 إعادة ضبط التصفية", font=("Helvetica", 10, "bold"), bg="#f1f5f9", fg="#0f172a",
                              padx=12, pady=4, bd=0, cursor="hand2", command=self.refresh_data)
        btn_reset.pack(side="left", padx=5)

    def _build_table_section(self):
        table_frame = tk.Frame(self, bg="white", padx=15, pady=15)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        cols = ("reorder", "stock", "price", "cost", "supplier", "category", "name", "sku", "id")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=15)
        
        self.tree.heading("id", text="الرقم")
        self.tree.heading("sku", text="كود المنتج")
        self.tree.heading("name", text="اسم المنتج")
        self.tree.heading("category", text="التصنيف")
        self.tree.heading("supplier", text="المورّد")
        self.tree.heading("cost", text="سعر التكلفة")
        self.tree.heading("price", text="سعر البيع")
        self.tree.heading("stock", text="الكمية المتوفرة")
        self.tree.heading("reorder", text="حد التنبيه")

        self.tree.column("id", width=50, anchor="center")
        self.tree.column("sku", width=100, anchor="center")
        self.tree.column("name", width=220, anchor="e")
        self.tree.column("category", width=130, anchor="e")
        self.tree.column("supplier", width=150, anchor="e")
        self.tree.column("cost", width=90, anchor="center")
        self.tree.column("price", width=90, anchor="center")
        self.tree.column("stock", width=90, anchor="center")
        self.tree.column("reorder", width=90, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Bottom Actions
        bot_actions = tk.Frame(table_frame, bg="white")
        bot_actions.grid(row=1, column=0, sticky="ew", pady=(15, 0))

        btn_edit = tk.Button(bot_actions, text="✏️ تعديل المحدد", font=("Helvetica", 11, "bold"), bg="#e2e8f0", fg="#0f172a",
                             padx=15, pady=6, bd=0, cursor="hand2", command=self._show_edit_product_modal)
        btn_edit.pack(side="right", padx=5)

        btn_adj = tk.Button(bot_actions, text="📦 تعديل المخزون السريع", font=("Helvetica", 11, "bold"), bg="#16a34a", fg="white",
                            padx=15, pady=6, bd=0, cursor="hand2", command=self._show_adjust_stock_modal)
        btn_adj.pack(side="right", padx=5)

        btn_del = tk.Button(bot_actions, text="🗑️ حذف المحدد", font=("Helvetica", 11, "bold"), bg="#fee2e2", fg="#dc2626",
                            padx=15, pady=6, bd=0, cursor="hand2", command=self._delete_selected_product)
        btn_del.pack(side="left", padx=5)

    def refresh_data(self):
        self.ent_search.delete(0, "end")
        
        self.categories_list = get_all_categories()
        cat_names = ["جميع التصنيفات"] + [c['name'] for c in self.categories_list]
        self.cb_cat_filter.config(values=cat_names)
        self.cb_cat_filter.set("جميع التصنيفات")

        self.suppliers_list = get_all_suppliers()
        self.products_list = get_all_products()
        self._populate_tree(self.products_list)

    def _populate_tree(self, products):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for p in products:
            cost_str = f"{p['cost_price']:,.2f}"
            price_str = f"{p['selling_price']:,.2f}"
            stock = p['stock_quantity']
            
            tag = "low_stock" if stock <= p['reorder_level'] else "normal"

            self.tree.insert("", "end", values=(
                p['reorder_level'], stock, price_str, cost_str, p['supplier_name'] or "N/A",
                p['category_name'] or "N/A", p['name'], p['sku'], p['id']
            ), tags=(tag,))

        self.tree.tag_configure("low_stock", background="#fef3c7", foreground="#b45309")

    def _apply_filters(self, event=None):
        query = self.ent_search.get().lower()
        selected_cat = self.cb_cat_filter.get()

        filtered = self.products_list

        if query:
            filtered = [p for p in filtered if query in p['name'].lower() or query in p['sku'].lower() or (p['supplier_name'] and query in p['supplier_name'].lower())]
        
        if selected_cat and selected_cat != "جميع التصنيفات":
            filtered = [p for p in filtered if p['category_name'] == selected_cat]

        self._populate_tree(filtered)

    def _filter_low_stock(self):
        low_stock = get_low_stock_products()
        self.cb_cat_filter.set("جميع التصنيفات")
        self.ent_search.delete(0, "end")
        self._populate_tree(low_stock)

    def _show_add_product_modal(self):
        self._show_product_form_modal()

    def _show_edit_product_modal(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("تحديد منتج", "يرجى تحديد منتج من الجدول لتعديل بياناته.")
            return
        
        values = self.tree.item(selected[0], "values")
        prod_id = int(values[8])
        prod_obj = next((p for p in self.products_list if p['id'] == prod_id), None)
        if prod_obj:
            self._show_product_form_modal(prod_obj)

    def _show_product_form_modal(self, prod_obj=None):
        modal = tk.Toplevel(self)
        mode = "تعديل بيانات المنتج" if prod_obj else "إضافة منتج جديد"
        modal.title(mode)
        modal.geometry("620x760")
        modal.config(bg="white", padx=25, pady=25)
        modal.grab_set()

        modal.columnconfigure(0, weight=1)

        tk.Label(modal, text=mode, font=("Helvetica", 18, "bold"), bg="white", fg="#0f172a").pack(pady=(0, 20))

        form = tk.Frame(modal, bg="white")
        form.pack(fill="both", expand=True)
        form.columnconfigure(0, weight=1)

        fields = [
            ("كود المنتج (SKU) *", "sku"),
            ("اسم المنتج *", "name"),
            ("التصنيف", "category_id"),
            ("المورّد", "supplier_id"),
            ("سعر التكلفة *", "cost_price"),
            ("سعر البيع *", "selling_price"),
            ("الكمية المتوفرة *", "stock_quantity"),
            ("حد تنبيه النواقص *", "reorder_level")
        ]

        entries = {}

        for i, (label_text, field_name) in enumerate(fields):
            tk.Label(form, text=label_text, font=("Helvetica", 11, "bold"), bg="white", fg="#334155").grid(row=i, column=1, sticky="e", pady=8, padx=10)
            
            if field_name == "category_id":
                cb = ttk.Combobox(form, state="readonly", font=("Helvetica", 11), width=23, justify="right")
                cat_names = [c['name'] for c in self.categories_list]
                cb.config(values=cat_names)
                if prod_obj and prod_obj['category_name']:
                    cb.set(prod_obj['category_name'])
                elif cat_names:
                    cb.set(cat_names[0])
                cb.grid(row=i, column=0, pady=8, padx=5)
                entries[field_name] = cb

            elif field_name == "supplier_id":
                cb = ttk.Combobox(form, state="readonly", font=("Helvetica", 11), width=23, justify="right")
                sup_names = [s['name'] for s in self.suppliers_list]
                cb.config(values=sup_names)
                if prod_obj and prod_obj['supplier_name']:
                    cb.set(prod_obj['supplier_name'])
                elif sup_names:
                    cb.set(sup_names[0])
                cb.grid(row=i, column=0, pady=8, padx=5)
                entries[field_name] = cb

            else:
                ent = tk.Entry(form, font=("Helvetica", 12), width=24, justify="right")
                if prod_obj:
                    val = prod_obj[field_name]
                    ent.insert(0, str(val))
                elif field_name in ["stock_quantity", "reorder_level", "cost_price", "selling_price"]:
                    default_val = "0" if field_name == "stock_quantity" else ("5" if field_name == "reorder_level" else "0.00")
                    ent.insert(0, default_val)
                
                if prod_obj and field_name == "sku":
                    ent.config(state="disabled")

                ent.grid(row=i, column=0, pady=8, padx=5)
                entries[field_name] = ent

        unit_section = tk.LabelFrame(modal, text="", font=("Helvetica", 12, "bold"), bg="white", fg="#0f172a")
        unit_section.pack(fill="both", expand=True, pady=(15, 10))
        unit_title = tk.Label(unit_section, text="الوحدات والتسعير", font=("Helvetica", 12, "bold"), bg="white", fg="#0f172a", justify="right", anchor="e")
        unit_title.pack(anchor="e", padx=10, pady=(8, 0))
        unit_rows = []

        def add_unit_row(unit_name="", pieces="", cost="", selling="", default=False):
            row = tk.Frame(unit_section, bg="white")
            row.pack(fill="x", padx=10, pady=5)
            display_values = [get_display_unit_name(v) for v in ["Piece", "Pack", "Dozen", "Box", "Carton"]]
            cb = ttk.Combobox(row, state="readonly", values=display_values, width=12, justify="right")
            cb.set(get_display_unit_name(unit_name or "Piece"))
            cb.pack(side="right", padx=3)

            e_pieces = tk.Entry(row, width=10, justify="center")
            e_pieces.insert(0, pieces if pieces != "" else "1")
            e_pieces.pack(side="right", padx=3)

            e_cost = tk.Entry(row, width=10, justify="center")
            e_cost.insert(0, cost if cost != "" else "0.00")
            e_cost.pack(side="right", padx=3)

            e_sell = tk.Entry(row, width=10, justify="center")
            e_sell.insert(0, selling if selling != "" else "0.00")
            e_sell.pack(side="right", padx=3)

            default_var = tk.BooleanVar(value=default)
            chk = tk.Checkbutton(row, text="افتراضي", bg="white", variable=default_var)
            chk.pack(side="right", padx=8)
            row_widgets = {"frame": row, "unit": cb, "pieces": e_pieces, "cost": e_cost, "sell": e_sell, "default": default_var}
            unit_rows.append(row_widgets)
            return row_widgets

        existing_units = get_product_units(prod_obj['id']) if prod_obj else []
        if existing_units:
            for unit in existing_units:
                add_unit_row(unit['unit_name'], str(unit['pieces_per_unit']), str(unit['cost_price']), str(unit['selling_price']), bool(unit['is_default']))
        else:
            add_unit_row("Piece", "1", entries['cost_price'].get() or "0.00", entries['selling_price'].get() or "0.00", True)

        def add_new_unit_row():
            add_unit_row()

        row_actions = tk.Frame(modal, bg="white")
        row_actions.pack(fill="x", pady=(0, 15))
        tk.Button(row_actions, text="+ إضافة وحدة", font=("Helvetica", 11, "bold"), bg="#e2e8f0", fg="#0f172a", bd=0, padx=12, pady=6, cursor="hand2", command=add_new_unit_row).pack(side="right")

        def save_product():
            try:
                sku = entries['sku'].get().strip()
                name = entries['name'].get().strip()
                cost = float(entries['cost_price'].get())
                price = float(entries['selling_price'].get())
                stock = int(entries['stock_quantity'].get())
                reorder = int(entries['reorder_level'].get())

                if not sku or not name:
                    messagebox.showwarning("بيانات غير مكتملة", "يرجى إدخال كود المنتج واسمه.")
                    return

                cat_name = entries['category_id'].get()
                cat_obj = next((c for c in self.categories_list if c['name'] == cat_name), None)
                cat_id = cat_obj['id'] if cat_obj else None

                sup_name = entries['supplier_id'].get()
                sup_obj = next((s for s in self.suppliers_list if s['name'] == sup_name), None)
                sup_id = sup_obj['id'] if sup_obj else None

                if prod_obj:
                    success, msg = update_product(prod_obj['id'], sku, name, cat_id, cost, price, stock, reorder, sup_id)
                    product_id = prod_obj['id']
                else:
                    success, msg = add_product(sku, name, cat_id, cost, price, stock, reorder, sup_id)
                    if success:
                        products = get_all_products()
                        product_obj = next((p for p in products if p['sku'] == sku), None)
                        product_id = product_obj['id'] if product_obj else None
                    else:
                        product_id = None

                if not success:
                    messagebox.showerror("خطأ", msg)
                    return

                if product_id is not None:
                    seen_units = set()
                    default_set = False
                    for row in unit_rows:
                        unit_name = row['unit'].get().strip()
                        if not unit_name:
                            continue
                        normalized_name = get_internal_unit_name(unit_name)
                        if normalized_name.lower() in seen_units:
                            messagebox.showwarning("وحدة مكررة", f"الوحدة '{unit_name}' مكررة لهذا المنتج. يرجى حذف التكرار.")
                            return
                        seen_units.add(normalized_name.lower())
                        try:
                            pieces = float(row['pieces'].get())
                        except ValueError:
                            messagebox.showerror("إدخال غير صحيح", f"قيمة 'عدد القطع داخل الوحدة' غير صحيحة لوحدة '{unit_name}'.")
                            return
                        if pieces <= 0:
                            messagebox.showerror("إدخال غير صحيح", f"يجب أن يكون عدد القطع داخل الوحدة أكبر من صفر لوحدة '{unit_name}'.")
                            return
                        try:
                            unit_cost = float(row['cost'].get())
                            unit_sell = float(row['sell'].get())
                        except ValueError:
                            messagebox.showerror("إدخال غير صحيح", f"أسعار الوحدة '{unit_name}' غير صحيحة.")
                            return
                        if unit_cost < 0 or unit_sell < 0:
                            messagebox.showerror("إدخال غير صحيح", f"لا يمكن أن تكون أسعار الوحدة '{unit_name}' سالبة.")
                            return
                        is_default = bool(row['default'].get())
                        if is_default:
                            default_set = True
                        success_unit, msg_unit = ensure_product_unit(product_id, normalized_name, pieces, unit_cost, unit_sell, is_default=is_default, is_active=True)
                        if not success_unit:
                            messagebox.showerror("خطأ", msg_unit)
                            return
                    if not default_set:
                        default_unit = get_product_units(product_id)
                        if default_unit:
                            ensure_product_unit(product_id, default_unit[0]['unit_name'], default_unit[0]['pieces_per_unit'], default_unit[0]['cost_price'], default_unit[0]['selling_price'], is_default=True, is_active=True)

                messagebox.showinfo("نجاح", msg)
                self.refresh_data()
                self.controller.refresh_all_views()
                modal.destroy()

            except ValueError:
                messagebox.showerror("إدخال غير صحيح", "يرجى التأكد من إدخال أرقام صحيحة للأسعار والكميات.")

        btn_save = tk.Button(modal, text="💾 حفظ بيانات المنتج", font=("Helvetica", 13, "bold"), bg="#2563eb", fg="white",
                             pady=10, bd=0, cursor="hand2", command=save_product)
        btn_save.pack(fill="x", pady=(20, 0))

    def _show_adjust_stock_modal(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("تحديد منتج", "يرجى تحديد منتج من الجدول لتعديل كميته.")
            return

        values = self.tree.item(selected[0], "values")
        prod_id = int(values[8])
        name = values[6]
        curr_stock = values[1]

        modal = tk.Toplevel(self)
        modal.title(f"تعديل المخزون - {name}")
        modal.geometry("380x250")
        modal.config(bg="white", padx=20, pady=20)
        modal.grab_set()

        modal.columnconfigure(0, weight=1)

        tk.Label(modal, text="تعديل كمية المخزون الفعلي", font=("Helvetica", 16, "bold"), bg="white", fg="#0f172a").pack(pady=(0, 10))
        tk.Label(modal, text=f"المنتج: {name}", font=("Helvetica", 12), bg="white", fg="#64748b").pack(pady=(0, 15))

        f_inp = tk.Frame(modal, bg="white")
        f_inp.pack()

        tk.Label(f_inp, text="إجمالي الكمية المتوفرة:", font=("Helvetica", 12, "bold"), bg="white").pack(side="right", padx=5)
        ent_stock = tk.Entry(f_inp, font=("Helvetica", 13, "bold"), width=10, justify="center")
        ent_stock.insert(0, str(curr_stock))
        ent_stock.pack(side="right", padx=5)

        def save_adj():
            try:
                new_qty = int(ent_stock.get())
                if new_qty < 0: raise ValueError
            except ValueError:
                messagebox.showerror("كمية غير صحيحة", "يرجى إدخال رقم صحيح غير سالب لكمية المخزون.")
                return

            s, m = adjust_stock(prod_id, new_qty)
            if s:
                messagebox.showinfo("نجاح", m)
                self.refresh_data()
                self.controller.refresh_all_views()
                modal.destroy()
            else:
                messagebox.showerror("خطأ", m)

        btn_save = tk.Button(modal, text="💾 اعتماد التعديل", font=("Helvetica", 12, "bold"), bg="#16a34a", fg="white",
                             pady=10, bd=0, cursor="hand2", command=save_adj)
        btn_save.pack(fill="x", pady=(25, 0))

    def _delete_selected_product(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("تحديد منتج", "يرجى تحديد منتج من الجدول لحذفه.")
            return

        values = self.tree.item(selected[0], "values")
        prod_id = int(values[8])
        name = values[6]

        if messagebox.askyesno("تأكيد الحذف", f"هل أنت متأكد من رغبتك في حذف المنتج '{name}' نهائياً؟\nهذا الإجراء لا يمكن التراجع عنه."):
            s, m = delete_product(prod_id)
            if s:
                messagebox.showinfo("تم الحذف", m)
                self.refresh_data()
                self.controller.refresh_all_views()
            else:
                messagebox.showerror("خطأ في الحذف", m)

    def _show_manage_categories_modal(self):
        modal = tk.Toplevel(self)
        modal.title("إدارة تصنيفات المنتجات")
        modal.geometry("500x480")
        modal.config(bg="white", padx=20, pady=20)
        modal.grab_set()

        tk.Label(modal, text="تصنيفات المنتجات", font=("Helvetica", 18, "bold"), bg="white", fg="#0f172a").pack(pady=(0, 15))

        f_list = tk.Frame(modal, bg="white")
        f_list.pack(fill="both", expand=True, pady=(0, 15))

        cols = ("desc", "name", "code")
        tree = ttk.Treeview(f_list, columns=cols, show="headings", height=8)
        tree.heading("code", text="الرمز")
        tree.heading("name", text="اسم التصنيف")
        tree.heading("desc", text="الوصف")

        tree.column("code", width=80, anchor="center")
        tree.column("name", width=160, anchor="e")
        tree.column("desc", width=220, anchor="e")
        tree.pack(fill="both", expand=True)

        def fill_categories():
            for item in tree.get_children():
                tree.delete(item)
            for c in self.categories_list:
                tree.insert("", "end", values=(c['description'], c['name'], c['code'] or ""))

        fill_categories()

        tk.Label(modal, text="إضافة تصنيف جديد", font=("Helvetica", 13, "bold"), bg="white", fg="#0f172a").pack(anchor="e", pady=(5, 5))

        f_form = tk.Frame(modal, bg="white")
        f_form.pack(fill="x")
        f_form.columnconfigure(0, weight=1)

        tk.Label(f_form, text="رمز التصنيف:", font=("Helvetica", 11, "bold"), bg="white").grid(row=0, column=1, sticky="e", pady=5, padx=5)
        ent_code = tk.Entry(f_form, font=("Helvetica", 11), width=12, justify="right")
        ent_code.grid(row=0, column=0, pady=5, padx=5, sticky="e")

        tk.Label(f_form, text="اسم التصنيف:", font=("Helvetica", 11, "bold"), bg="white").grid(row=1, column=1, sticky="e", pady=5, padx=5)
        ent_name = tk.Entry(f_form, font=("Helvetica", 11), width=28, justify="right")
        ent_name.grid(row=1, column=0, pady=5, padx=5)

        tk.Label(f_form, text="الوصف:", font=("Helvetica", 11, "bold"), bg="white").grid(row=2, column=1, sticky="e", pady=5, padx=5)
        ent_desc = tk.Entry(f_form, font=("Helvetica", 11), width=38, justify="right")
        ent_desc.grid(row=2, column=0, pady=5, padx=5)

        def save_cat():
            code = ent_code.get().strip()
            name = ent_name.get().strip()
            desc = ent_desc.get().strip()
            s, m = add_category(code, name, desc)
            if s:
                messagebox.showinfo("نجاح", "تمت إضافة التصنيف بنجاح!")
                self.refresh_data()
                fill_categories()
                ent_code.delete(0, "end")
                ent_name.delete(0, "end")
                ent_desc.delete(0, "end")
            else:
                messagebox.showerror("خطأ", m)

        btn_add = tk.Button(modal, text="➕ إضافة التصنيف", font=("Helvetica", 11, "bold"), bg="#2563eb", fg="white",
                            pady=8, bd=0, cursor="hand2", command=save_cat)
        btn_add.pack(fill="x", pady=(15, 0))
