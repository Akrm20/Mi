import sqlite3
import json
import os
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
import hashlib
import secrets

class POSBackend:
    def __init__(self, db_path="pos_database.db"):
        self.db_path = db_path
        self.initDatabase()
    
    def initDatabase(self):
        """تهيئة قاعدة البيانات وجميع الجداول"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # جدول المستخدمين
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول المنتجات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                barcode TEXT UNIQUE,
                category_id INTEGER,
                purchase_price REAL DEFAULT 0,
                sale_price REAL NOT NULL,
                stock_quantity REAL DEFAULT 0,
                min_stock REAL DEFAULT 0,
                unit TEXT DEFAULT 'قطعة',
                description TEXT,
                image_url TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول الفئات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول العملاء
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                address TEXT,
                balance REAL DEFAULT 0,
                tax_number TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول الموردين
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                address TEXT,
                balance REAL DEFAULT 0,
                tax_number TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول الفواتير
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                customer_id INTEGER,
                total_amount REAL NOT NULL,
                paid_amount REAL NOT NULL,
                remaining_amount REAL DEFAULT 0,
                type TEXT DEFAULT 'sale',
                status TEXT DEFAULT 'completed',
                notes TEXT,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (id),
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
        ''')
        
        # جدول عناصر الفواتير
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER,
                product_id INTEGER,
                product_name TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit_price REAL NOT NULL,
                total_price REAL NOT NULL,
                FOREIGN KEY (invoice_id) REFERENCES invoices (id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')
        
        # جدول الحسابات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                account_type TEXT NOT NULL,
                balance REAL DEFAULT 0,
                parent_id INTEGER,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول القيود اليومية
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS journal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date DATE NOT NULL,
                description TEXT,
                reference TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول بنود القيود
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS journal_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                journal_id INTEGER,
                account_id INTEGER,
                debit_amount REAL DEFAULT 0,
                credit_amount REAL DEFAULT 0,
                FOREIGN KEY (journal_id) REFERENCES journal_entries (id),
                FOREIGN KEY (account_id) REFERENCES accounts (id)
            )
        ''')
        
        # جدول حركات الخزنة
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cash_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                amount REAL NOT NULL,
                type TEXT NOT NULL,
                description TEXT,
                reference TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول الإعدادات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
        # إضافة البيانات الأساسية
        self.initializeDefaultData()
    
    def initializeDefaultData(self):
        """تهيئة البيانات الافتراضية"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # إضافة مستخدم افتراضي
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            default_password = hashlib.sha256('admin123'.encode()).hexdigest()
            cursor.execute('''
                INSERT INTO users (username, password_hash, full_name, role)
                VALUES (?, ?, ?, ?)
            ''', ('admin', default_password, 'مدير النظام', 'admin'))
        
        # تهيئة دليل الحسابات
        accounts = [
            {"name": "النقدية", "type": "asset", "parent_id": None},
            {"name": "البضاعة", "type": "asset", "parent_id": None},
            {"name": "العملاء", "type": "asset", "parent_id": None},
            {"name": "الموردين", "type": "liability", "parent_id": None},
            {"name": "رأس المال", "type": "equity", "parent_id": None},
            {"name": "مبيعات", "type": "revenue", "parent_id": None},
            {"name": "مشتريات", "type": "expense", "parent_id": None},
            {"name": "مصروفات تشغيل", "type": "expense", "parent_id": None}
        ]
        
        for account in accounts:
            cursor.execute('''
                INSERT OR IGNORE INTO accounts (name, account_type, parent_id)
                VALUES (?, ?, ?)
            ''', (account["name"], account["type"], account["parent_id"]))
        
        # إضافة فئات افتراضية
        categories = ["أجهزة إلكترونية", "ملابس", "أغذية", "أثاث", "مستلزمات مكتبية"]
        for category in categories:
            cursor.execute('''
                INSERT OR IGNORE INTO categories (name)
                VALUES (?)
            ''', (category,))
        
        conn.commit()
        conn.close()
    
    def hash_password(self, password):
        """تجزئة كلمة المرور"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_user(self, username, password):
        """التحقق من صحة بيانات المستخدم"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, username, full_name, role 
            FROM users 
            WHERE username = ? AND password_hash = ? AND is_active = 1
        ''', (username, self.hash_password(password)))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return {
                "id": user[0],
                "username": user[1],
                "full_name": user[2],
                "role": user[3]
            }
        return None
    
    # وظائف لوحة التحكم
    def loadDashboardData(self):
        """تحميل بيانات لوحة التحكم"""
        return {
            "today_sales": self.loadTodaySales(),
            "today_purchases": self.loadTodayPurchases(),
            "inventory_value": self.loadInventoryValues(),
            "customers_count": self.loadCustomersSuppliersCount()["customers"],
            "suppliers_count": self.loadCustomersSuppliersCount()["suppliers"],
            "capital_profit": self.loadCapitalAndProfit(),
            "credit_sales": self.loadCreditSales(),
            "credit_purchases": self.loadCreditPurchases(),
            "low_stock_products": self.loadLowStockProducts(),
            "recent_invoices": self.loadRecentInvoices()
        }
    
    def loadTodaySales(self):
        """تحميل مبيعات اليوم"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = date.today().isoformat()
        cursor.execute('''
            SELECT COALESCE(SUM(total_amount), 0) 
            FROM invoices 
            WHERE DATE(created_at) = ? AND type = 'sale' AND status = 'completed'
        ''', (today,))
        
        result = cursor.fetchone()[0]
        conn.close()
        return float(result)
    
    def loadTodayPurchases(self):
        """تحميل مشتريات اليوم"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = date.today().isoformat()
        cursor.execute('''
            SELECT COALESCE(SUM(total_amount), 0) 
            FROM invoices 
            WHERE DATE(created_at) = ? AND type = 'purchase' AND status = 'completed'
        ''', (today,))
        
        result = cursor.fetchone()[0]
        conn.close()
        return float(result)
    
    def loadInventoryValues(self):
        """تحميل قيمة المخزون"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COALESCE(SUM(stock_quantity * purchase_price), 0)
            FROM products
            WHERE is_active = 1
        ''')
        
        result = cursor.fetchone()[0]
        conn.close()
        return float(result)
    
    def loadCustomersSuppliersCount(self):
        """عدد العملاء والموردين"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM customers")
        customers_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM suppliers")
        suppliers_count = cursor.fetchone()[0]
        
        conn.close()
        return {"customers": customers_count, "suppliers": suppliers_count}
    
    def loadCapitalAndProfit(self):
        """رأس المال والأرباح"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COALESCE(SUM(balance), 0) FROM accounts WHERE account_type = 'asset'")
        assets = cursor.fetchone()[0]
        
        cursor.execute("SELECT COALESCE(SUM(balance), 0) FROM accounts WHERE account_type = 'liability'")
        liabilities = cursor.fetchone()[0]
        
        capital = assets - liabilities
        
        cursor.execute("SELECT COALESCE(SUM(balance), 0) FROM accounts WHERE account_type = 'revenue'")
        revenue = cursor.fetchone()[0]
        
        cursor.execute("SELECT COALESCE(SUM(balance), 0) FROM accounts WHERE account_type = 'expense'")
        expense = cursor.fetchone()[0]
        
        profit = revenue - expense
        
        conn.close()
        return {"capital": float(capital), "profit": float(profit)}
    
    def loadCreditSales(self):
        """المبيعات الآجلة"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COALESCE(SUM(remaining_amount), 0)
            FROM invoices 
            WHERE type = 'sale' AND remaining_amount > 0 AND status = 'completed'
        ''')
        
        result = cursor.fetchone()[0]
        conn.close()
        return float(result)
    
    def loadCreditPurchases(self):
        """المشتريات الآجلة"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COALESCE(SUM(remaining_amount), 0)
            FROM invoices 
            WHERE type = 'purchase' AND remaining_amount > 0 AND status = 'completed'
        ''')
        
        result = cursor.fetchone()[0]
        conn.close()
        return float(result)
    
    def loadLowStockProducts(self):
        """المنتجات منخفضة المخزون"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT name, stock_quantity, min_stock
            FROM products
            WHERE stock_quantity <= min_stock AND is_active = 1
            ORDER BY stock_quantity ASC
            LIMIT 10
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        return [{"name": row[0], "stock_quantity": row[1], "min_stock": row[2]} for row in results]
    
    def loadRecentInvoices(self):
        """آخر الفواتير"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT i.invoice_number, i.created_at, i.total_amount, i.type, i.status,
                   c.name as customer_name
            FROM invoices i
            LEFT JOIN customers c ON i.customer_id = c.id
            ORDER BY i.created_at DESC
            LIMIT 10
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        return [{
            "invoice_number": row[0],
            "created_at": row[1],
            "total_amount": float(row[2]),
            "type": row[3],
            "status": row[4],
            "customer_name": row[5]
        } for row in results]
    
    # وظائف التقارير
    def loadSalesReports(self, start_date=None, end_date=None):
        """تحميل تقارير المبيعات"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = '''
            SELECT i.*, c.name as customer_name
            FROM invoices i
            LEFT JOIN customers c ON i.customer_id = c.id
            WHERE i.type = 'sale'
        '''
        params = []
        
        if start_date and end_date:
            query += " AND DATE(i.created_at) BETWEEN ? AND ?"
            params.extend([start_date, end_date])
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        return [dict(zip([column[0] for column in cursor.description], row)) for row in results]
    
    def loadPurchasesReports(self, start_date=None, end_date=None):
        """تحميل تقارير المشتريات"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = '''
            SELECT i.*, s.name as supplier_name
            FROM invoices i
            LEFT JOIN suppliers s ON i.customer_id = s.id
            WHERE i.type = 'purchase'
        '''
        params = []
        
        if start_date and end_date:
            query += " AND DATE(i.created_at) BETWEEN ? AND ?"
            params.extend([start_date, end_date])
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        return [dict(zip([column[0] for column in cursor.description], row)) for row in results]
    
    # وظائف المنتجات
    def getAllProducts(self):
        """جلب جميع المنتجات"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT p.*, c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.is_active = 1
            ORDER BY p.name
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        return [dict(zip([column[0] for column in cursor.description], row)) for row in results]
    
    def loadCategories(self):
        """جلب جميع الفئات"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM categories ORDER BY name")
        results = cursor.fetchall()
        conn.close()
        
        return [dict(zip([column[0] for column in cursor.description], row)) for row in results]
    
    def loadSuppliers(self):
        """جلب جميع الموردين"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM suppliers ORDER BY name")
        results = cursor.fetchall()
        conn.close()
        
        return [dict(zip([column[0] for column in cursor.description], row)) for row in results]
    
    def saveProduct(self, product_data):
        """حفظ منتج"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if 'id' in product_data and product_data['id']:
                cursor.execute('''
                    UPDATE products 
                    SET name=?, barcode=?, category_id=?, purchase_price=?, 
                        sale_price=?, stock_quantity=?, min_stock=?, unit=?, 
                        description=?, image_url=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                ''', (
                    product_data['name'], product_data.get('barcode'), 
                    product_data.get('category_id'), product_data.get('purchase_price', 0),
                    product_data['sale_price'], product_data.get('stock_quantity', 0),
                    product_data.get('min_stock', 0), product_data.get('unit', 'قطعة'),
                    product_data.get('description'), product_data.get('image_url'), 
                    product_data['id']
                ))
            else:
                cursor.execute('''
                    INSERT INTO products 
                    (name, barcode, category_id, purchase_price, sale_price, 
                     stock_quantity, min_stock, unit, description, image_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    product_data['name'], product_data.get('barcode'), 
                    product_data.get('category_id'), product_data.get('purchase_price', 0),
                    product_data['sale_price'], product_data.get('stock_quantity', 0),
                    product_data.get('min_stock', 0), product_data.get('unit', 'قطعة'),
                    product_data.get('description'), product_data.get('image_url')
                ))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def deleteProduct(self, product_id):
        """حذف منتج (تنعيم - Soft Delete)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("UPDATE products SET is_active = 0 WHERE id = ?", (product_id,))
        conn.commit()
        conn.close()
        return True
    
    # وظائف العملاء
    def loadCustomers(self):
        """جلب جميع العملاء"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM customers ORDER BY name")
        results = cursor.fetchall()
        conn.close()
        
        return [dict(zip([column[0] for column in cursor.description], row)) for row in results]
    
    def saveCustomer(self, customer_data):
        """حفظ عميل"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if 'id' in customer_data and customer_data['id']:
                cursor.execute('''
                    UPDATE customers 
                    SET name=?, phone=?, email=?, address=?, balance=?, tax_number=?, notes=?
                    WHERE id=?
                ''', (
                    customer_data['name'], customer_data.get('phone'),
                    customer_data.get('email'), customer_data.get('address'),
                    customer_data.get('balance', 0), customer_data.get('tax_number'),
                    customer_data.get('notes'), customer_data['id']
                ))
            else:
                cursor.execute('''
                    INSERT INTO customers (name, phone, email, address, balance, tax_number, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    customer_data['name'], customer_data.get('phone'),
                    customer_data.get('email'), customer_data.get('address'),
                    customer_data.get('balance', 0), customer_data.get('tax_number'),
                    customer_data.get('notes')
                ))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    # وظائف الفواتير والمبيعات
    def getAllInvoices(self, invoice_type=None):
        """جلب جميع الفواتير"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = '''
            SELECT i.*, 
                   c.name as customer_name,
                   s.name as supplier_name
            FROM invoices i
            LEFT JOIN customers c ON i.customer_id = c.id AND i.type = 'sale'
            LEFT JOIN suppliers s ON i.customer_id = s.id AND i.type = 'purchase'
            WHERE 1=1
        '''
        params = []
        
        if invoice_type:
            query += " AND i.type = ?"
            params.append(invoice_type)
        
        query += " ORDER BY i.created_at DESC"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        return [dict(zip([column[0] for column in cursor.description], row)) for row in results]
    
    def generateInvoiceNumber(self, invoice_type='sale'):
        """إنشاء رقم فاتورة تلقائي"""
        prefix = 'S' if invoice_type == 'sale' else 'P'
        date_str = datetime.now().strftime('%Y%m%d')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) FROM invoices 
            WHERE invoice_number LIKE ? AND DATE(created_at) = DATE('now')
        ''', (f'{prefix}{date_str}%',))
        
        count = cursor.fetchone()[0] + 1
        conn.close()
        
        return f'{prefix}{date_str}{count:04d}'
    
    def saveInvoice(self, invoice_data):
        """حفظ فاتورة"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # إنشاء رقم فاتورة إذا لم يكن موجوداً
            if not invoice_data.get('invoice_number'):
                invoice_data['invoice_number'] = self.generateInvoiceNumber(invoice_data.get('type', 'sale'))
            
            # حفظ الفاتورة الرئيسية
            cursor.execute('''
                INSERT INTO invoices 
                (invoice_number, customer_id, total_amount, paid_amount, 
                 remaining_amount, type, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                invoice_data['invoice_number'],
                invoice_data.get('customer_id'),
                invoice_data['total_amount'],
                invoice_data.get('paid_amount', invoice_data['total_amount']),
                invoice_data.get('remaining_amount', 0),
                invoice_data['type'],
                invoice_data.get('status', 'completed'),
                invoice_data.get('notes', '')
            ))
            
            invoice_id = cursor.lastrowid
            
            # حفظ عناصر الفاتورة
            for item in invoice_data['items']:
                cursor.execute('''
                    INSERT INTO invoice_items 
                    (invoice_id, product_id, product_name, quantity, unit_price, total_price)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    invoice_id, item['product_id'], item.get('product_name', ''),
                    item['quantity'], item['unit_price'], item['total_price']
                ))
                
                # تحديث المخزون
                if invoice_data['type'] == 'sale':
                    cursor.execute('''
                        UPDATE products 
                        SET stock_quantity = stock_quantity - ?
                        WHERE id = ?
                    ''', (item['quantity'], item['product_id']))
                elif invoice_data['type'] == 'purchase':
                    cursor.execute('''
                        UPDATE products 
                        SET stock_quantity = stock_quantity + ?,
                            purchase_price = ?
                        WHERE id = ?
                    ''', (item['quantity'], item['unit_price'], item['product_id']))
            
            # تسجيل القيد المحاسبي
            self.createJournalEntry(invoice_data, invoice_id)
            
            conn.commit()
            return invoice_id
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def createJournalEntry(self, invoice_data, invoice_id):
        """إنشاء قيد محاسبي للفاتورة"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        entry_description = f"فاتورة {invoice_data['type']} رقم {invoice_data['invoice_number']}"
        
        cursor.execute('''
            INSERT INTO journal_entries (entry_date, description, reference)
            VALUES (CURRENT_DATE, ?, ?)
        ''', (entry_description, invoice_data['invoice_number']))
        
        journal_id = cursor.lastrowid
        
        if invoice_data['type'] == 'sale':
            # من ح/ النقدية (أو العملاء إذا كان بآجل)
            # إلى ح/ المبيعات
            cursor.execute("SELECT id FROM accounts WHERE name = 'النقدية'")
            cash_account = cursor.fetchone()[0]
            
            cursor.execute("SELECT id FROM accounts WHERE name = 'المبيعات'")
            sales_account = cursor.fetchone()[0]
            
            paid_amount = invoice_data.get('paid_amount', invoice_data['total_amount'])
            remaining_amount = invoice_data.get('remaining_amount', 0)
            
            if paid_amount > 0:
                cursor.execute('''
                    INSERT INTO journal_items (journal_id, account_id, debit_amount)
                    VALUES (?, ?, ?)
                ''', (journal_id, cash_account, paid_amount))
            
            if remaining_amount > 0:
                cursor.execute("SELECT id FROM accounts WHERE name = 'العملاء'")
                customers_account = cursor.fetchone()[0]
                cursor.execute('''
                    INSERT INTO journal_items (journal_id, account_id, debit_amount)
                    VALUES (?, ?, ?)
                ''', (journal_id, customers_account, remaining_amount))
            
            cursor.execute('''
                INSERT INTO journal_items (journal_id, account_id, credit_amount)
                VALUES (?, ?, ?)
            ''', (journal_id, sales_account, invoice_data['total_amount']))
        
        elif invoice_data['type'] == 'purchase':
            # من ح/ المشتريات
            # إلى ح/ النقدية (أو الموردين إذا كان بآجل)
            cursor.execute("SELECT id FROM accounts WHERE name = 'المشتريات'")
            purchases_account = cursor.fetchone()[0]
            
            cursor.execute("SELECT id FROM accounts WHERE name = 'النقدية'")
            cash_account = cursor.fetchone()[0]
            
            paid_amount = invoice_data.get('paid_amount', invoice_data['total_amount'])
            remaining_amount = invoice_data.get('remaining_amount', 0)
            
            cursor.execute('''
                INSERT INTO journal_items (journal_id, account_id, debit_amount)
                VALUES (?, ?, ?)
            ''', (journal_id, purchases_account, invoice_data['total_amount']))
            
            if paid_amount > 0:
                cursor.execute('''
                    INSERT INTO journal_items (journal_id, account_id, credit_amount)
                    VALUES (?, ?, ?)
                ''', (journal_id, cash_account, paid_amount))
            
            if remaining_amount > 0:
                cursor.execute("SELECT id FROM accounts WHERE name = 'الموردين'")
                suppliers_account = cursor.fetchone()[0]
                cursor.execute('''
                    INSERT INTO journal_items (journal_id, account_id, credit_amount)
                    VALUES (?, ?, ?)
                ''', (journal_id, suppliers_account, remaining_amount))
        
        conn.commit()
        conn.close()
    
    # وظائف نقاط البيع
    def loadProductsForPOS(self):
        """تحميل المنتجات لنقاط البيع"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT p.id, p.name, p.sale_price, p.stock_quantity, 
                   p.barcode, c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.stock_quantity > 0 AND p.is_active = 1
            ORDER BY p.name
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        return [dict(zip([column[0] for column in cursor.description], row)) for row in results]
    
    def getProductById(self, product_id):
        """جلب منتج بالرقم"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT p.*, c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.id = ? AND p.is_active = 1
        ''', (product_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return dict(zip([column[0] for column in cursor.description], result))
        return None
    
    def getCustomerById(self, customer_id):
        """جلب عميل بالرقم"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return dict(zip([column[0] for column in cursor.description], result))
        return None
    
    # وظائف الإعدادات
    def saveSettings(self, settings_data):
        """حفظ الإعدادات"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for key, value in settings_data.items():
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value)
                VALUES (?, ?)
            ''', (key, json.dumps(value) if isinstance(value, (dict, list)) else str(value)))
        
        conn.commit()
        conn.close()
        return True
    
    def loadSettings(self):
        """تحميل الإعدادات"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT key, value FROM settings")
        results = cursor.fetchall()
        conn.close()
        
        settings = {}
        for key, value in results:
            try:
                settings[key] = json.loads(value)
            except:
                settings[key] = value
        
        return settings
    
    # وظائف النسخ الاحتياطي
    def backupData(self, backup_path):
        """نسخ قاعدة البيانات احتياطياً"""
        import shutil
        shutil.copy2(self.db_path, backup_path)
        return True
    
    def restoreData(self, backup_path):
        """استعادة البيانات من نسخة احتياطية"""
        import shutil
        shutil.copy2(backup_path, self.db_path)
        return True

# إنشاء كائن النظام
pos_system = POSBackend()

if __name__ == "__main__":
    print("نظام نقطة البيع جاهز للعمل!")
    print("بيانات الدخول الافتراضية:")
    print("اسم المستخدم: admin")
    print("كلمة المرور: admin123")