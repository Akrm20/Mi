import sqlite3
import json
import os
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
import hashlib
import secrets
import base64
import io
from PIL import Image
import openpyxl

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
        
        # جدول جديد: صور المنتجات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                image_data BLOB,
                image_url TEXT,
                is_primary INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')
        
        # جدول جديد: السندات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vouchers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voucher_number TEXT UNIQUE NOT NULL,
                voucher_type TEXT NOT NULL,
                account_id INTEGER,
                amount REAL NOT NULL,
                description TEXT,
                reference TEXT,
                status TEXT DEFAULT 'completed',
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts (id),
                FOREIGN KEY (created_by) REFERENCES users (id)
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
    
    # =========================================================================
    # وظائف نظام نقاط البيع المحسن
    # =========================================================================
    
    def getCashBalance(self):
        """جلب رصيد الصندوق الحالي"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COALESCE(SUM(balance), 0) 
            FROM accounts 
            WHERE name = 'النقدية' AND is_active = 1
        ''')
        
        result = cursor.fetchone()[0]
        conn.close()
        return float(result)
    
    def processSale(self, sale_data):
        """معالجة عملية بيع مع دعم الدفع النقدي والآجل"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # إنشاء رقم فاتورة
            invoice_number = self.generateInvoiceNumber('sale')
            
            # تحديد حالة الفاتورة بناءً على نوع الدفع
            payment_type = sale_data.get('payment_type', 'cash')
            status = 'completed' if payment_type == 'cash' else 'pending'
            remaining_amount = sale_data['total_amount'] - sale_data.get('paid_amount', 0)
            
            # حفظ الفاتورة
            cursor.execute('''
                INSERT INTO invoices 
                (invoice_number, customer_id, total_amount, paid_amount, 
                 remaining_amount, type, status, notes)
                VALUES (?, ?, ?, ?, ?, 'sale', ?, ?)
            ''', (
                invoice_number,
                sale_data.get('customer_id'),
                sale_data['total_amount'],
                sale_data.get('paid_amount', sale_data['total_amount']),
                remaining_amount,
                status,
                sale_data.get('notes', '')
            ))
            
            invoice_id = cursor.lastrowid
            
            # حفظ عناصر الفاتورة
            for item in sale_data['items']:
                cursor.execute('''
                    INSERT INTO invoice_items 
                    (invoice_id, product_id, product_name, quantity, unit_price, total_price)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    invoice_id, item['product_id'], item.get('product_name', ''),
                    item['quantity'], item['unit_price'], item['total_price']
                ))
                
                # تحديث المخزون
                cursor.execute('''
                    UPDATE products 
                    SET stock_quantity = stock_quantity - ?
                    WHERE id = ?
                ''', (item['quantity'], item['product_id']))
            
            # إذا كان البيع نقدياً، تحديث رصيد الصندوق
            if payment_type == 'cash':
                self.updateCashBalance(sale_data['total_amount'], 'income', f'بيع نقدي - فاتورة {invoice_number}')
            
            # إذا كان البيع آجلاً، تحديث رصيد العميل
            if payment_type == 'credit' and sale_data.get('customer_id'):
                cursor.execute('''
                    UPDATE customers 
                    SET balance = balance + ?
                    WHERE id = ?
                ''', (remaining_amount, sale_data['customer_id']))
            
            # إنشاء القيد المحاسبي
            self.createJournalEntry({
                'type': 'sale',
                'invoice_number': invoice_number,
                'total_amount': sale_data['total_amount'],
                'paid_amount': sale_data.get('paid_amount', sale_data['total_amount']),
                'remaining_amount': remaining_amount
            }, invoice_id)
            
            conn.commit()
            return {
                'success': True,
                'invoice_id': invoice_id,
                'invoice_number': invoice_number,
                'message': 'تمت عملية البيع بنجاح'
            }
            
        except Exception as e:
            conn.rollback()
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            conn.close()
    
    def getProductsByCategory(self, category_id=None):
        """جلب المنتجات حسب الفئة"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if category_id:
            cursor.execute('''
                SELECT p.*, c.name as category_name,
                       CASE 
                           WHEN p.stock_quantity <= p.min_stock THEN 'low'
                           WHEN p.stock_quantity = 0 THEN 'out'
                           ELSE 'good'
                       END as stock_status
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.category_id = ? AND p.is_active = 1
                ORDER BY p.name
            ''', (category_id,))
        else:
            cursor.execute('''
                SELECT p.*, c.name as category_name,
                       CASE 
                           WHEN p.stock_quantity <= p.min_stock THEN 'low'
                           WHEN p.stock_quantity = 0 THEN 'out'
                           ELSE 'good'
                       END as stock_status
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.is_active = 1
                ORDER BY p.name
            ''')
        
        results = cursor.fetchall()
        conn.close()
        
        products = []
        for row in results:
            product = dict(zip([column[0] for column in cursor.description], row))
            # تحويل القيم العشرية
            product['sale_price'] = float(product['sale_price'])
            product['purchase_price'] = float(product['purchase_price'])
            product['stock_quantity'] = float(product['stock_quantity'])
            products.append(product)
        
        return products
    
    def searchProducts(self, query):
        """بحث فوري في المنتجات"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        search_term = f'%{query}%'
        cursor.execute('''
            SELECT p.*, c.name as category_name,
                   CASE 
                       WHEN p.stock_quantity <= p.min_stock THEN 'low'
                       WHEN p.stock_quantity = 0 THEN 'out'
                       ELSE 'good'
                   END as stock_status
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE (p.name LIKE ? OR p.barcode LIKE ?) AND p.is_active = 1
            ORDER BY p.name
            LIMIT 20
        ''', (search_term, search_term))
        
        results = cursor.fetchall()
        conn.close()
        
        products = []
        for row in results:
            product = dict(zip([column[0] for column in cursor.description], row))
            product['sale_price'] = float(product['sale_price'])
            product['purchase_price'] = float(product['purchase_price'])
            product['stock_quantity'] = float(product['stock_quantity'])
            products.append(product)
        
        return products
    
    def updateCashBalance(self, amount, transaction_type, description):
        """تحديث رصيد الصندوق"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # تحديث حساب النقدية
            if transaction_type == 'income':
                cursor.execute('''
                    UPDATE accounts SET balance = balance + ? WHERE name = 'النقدية'
                ''', (amount,))
            else:
                cursor.execute('''
                    UPDATE accounts SET balance = balance - ? WHERE name = 'النقدية'
                ''', (amount,))
            
            # تسجيل الحركة
            cursor.execute('''
                INSERT INTO cash_transactions (amount, type, description)
                VALUES (?, ?, ?)
            ''', (amount, transaction_type, description))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    # =========================================================================
    # وظائف إدارة المنتجات المتقدمة
    # =========================================================================
    
    def getProductStatistics(self):
        """جلب إحصائيات المنتجات"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # إجمالي المنتجات
        cursor.execute('SELECT COUNT(*) FROM products WHERE is_active = 1')
        total_products = cursor.fetchone()[0]
        
        # المنتجات منخفضة المخزون
        cursor.execute('''
            SELECT COUNT(*) FROM products 
            WHERE stock_quantity <= min_stock AND is_active = 1
        ''')
        low_stock_count = cursor.fetchone()[0]
        
        # المنتجات التي نفذت من المخزون
        cursor.execute('''
            SELECT COUNT(*) FROM products 
            WHERE stock_quantity = 0 AND is_active = 1
        ''')
        out_of_stock_count = cursor.fetchone()[0]
        
        # قيمة المخزون الإجمالية
        cursor.execute('''
            SELECT COALESCE(SUM(stock_quantity * purchase_price), 0)
            FROM products WHERE is_active = 1
        ''')
        inventory_value = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_products': total_products,
            'low_stock_count': low_stock_count,
            'out_of_stock_count': out_of_stock_count,
            'inventory_value': float(inventory_value),
            'categories_count': self.getCategoriesCount()
        }
    
    def getCategoriesCount(self):
        """عدد الفئات والمنتجات في كل فئة"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT c.id, c.name, COUNT(p.id) as product_count
            FROM categories c
            LEFT JOIN products p ON c.id = p.category_id AND p.is_active = 1
            GROUP BY c.id, c.name
            ORDER BY c.name
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        categories = []
        for row in results:
            categories.append({
                'id': row[0],
                'name': row[1],
                'product_count': row[2]
            })
        
        return categories
    
    def exportProductsToExcel(self, file_path=None):
        """تصدير المنتجات إلى Excel"""
        try:
            products = self.getAllProducts()
            
            # إنشاء DataFrame
            df_data = []
            for product in products:
                df_data.append({
                    'الاسم': product['name'],
                    'البarcode': product.get('barcode', ''),
                    'الفئة': product.get('category_name', ''),
                    'سعر الشراء': product.get('purchase_price', 0),
                    'سعر البيع': product['sale_price'],
                    'المخزون': product.get('stock_quantity', 0),
                    'الحد الأدنى': product.get('min_stock', 0),
                    'الوحدة': product.get('unit', 'قطعة'),
                    'الوصف': product.get('description', '')
                })
            
            df = pd.DataFrame(df_data)
            
            if file_path:
                df.to_excel(file_path, index=False, engine='openpyxl')
                return {'success': True, 'file_path': file_path}
            else:
                # إرجاع البيانات كـ Bytes
                output = io.BytesIO()
                df.to_excel(output, index=False, engine='openpyxl')
                output.seek(0)
                return {'success': True, 'data': output.getvalue()}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def importProductsFromExcel(self, file_path):
        """استيراد المنتجات من Excel"""
        try:
            df = pd.read_excel(file_path)
            imported_count = 0
            updated_count = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    product_data = {
                        'name': row['الاسم'],
                        'barcode': str(row['البarcode']) if pd.notna(row['البarcode']) else None,
                        'sale_price': float(row['سعر البيع']),
                        'purchase_price': float(row['سعر الشراء']) if pd.notna(row['سعر الشراء']) else 0,
                        'stock_quantity': float(row['المخزون']) if pd.notna(row['المخزون']) else 0,
                        'min_stock': float(row['الحد الأدنى']) if pd.notna(row['الحد الأدنى']) else 0,
                        'unit': row['الوحدة'] if pd.notna(row['الوحدة']) else 'قطعة',
                        'description': row['الوصف'] if pd.notna(row['الوصف']) else ''
                    }
                    
                    # البحث عن الفئة
                    if pd.notna(row['الفئة']):
                        category_id = self.getOrCreateCategory(row['الفئة'])
                        if category_id:
                            product_data['category_id'] = category_id
                    
                    # التحقق إذا كان المنتج موجوداً مسبقاً
                    existing_product = self.getProductByBarcode(product_data.get('barcode'))
                    if existing_product:
                        product_data['id'] = existing_product['id']
                        self.saveProduct(product_data)
                        updated_count += 1
                    else:
                        self.saveProduct(product_data)
                        imported_count += 1
                        
                except Exception as e:
                    errors.append(f"صف {index + 2}: {str(e)}")
            
            return {
                'success': True,
                'imported_count': imported_count,
                'updated_count': updated_count,
                'errors': errors
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def getOrCreateCategory(self, category_name):
        """الحصول على فئة أو إنشاؤها إذا لم تكن موجودة"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM categories WHERE name = ?', (category_name,))
        result = cursor.fetchone()
        
        if result:
            conn.close()
            return result[0]
        else:
            cursor.execute('INSERT INTO categories (name) VALUES (?)', (category_name,))
            category_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return category_id
    
    def getProductByBarcode(self, barcode):
        """جلب منتج بواسطة الباركود"""
        if not barcode:
            return None
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM products WHERE barcode = ? AND is_active = 1', (barcode,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return dict(zip([column[0] for column in cursor.description], result))
        return None
    
    def manageProductImages(self, product_id, image_data=None, image_url=None, action='add'):
        """إدارة صور المنتجات"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if action == 'add':
                # تحديد إذا كانت هناك صورة أساسية موجودة
                cursor.execute('SELECT COUNT(*) FROM product_images WHERE product_id = ? AND is_primary = 1', (product_id,))
                has_primary = cursor.fetchone()[0] > 0
                
                is_primary = 0 if has_primary else 1
                
                cursor.execute('''
                    INSERT INTO product_images (product_id, image_data, image_url, is_primary)
                    VALUES (?, ?, ?, ?)
                ''', (product_id, image_data, image_url, is_primary))
                
            elif action == 'set_primary':
                # إلغاء جميع الصور الأساسية
                cursor.execute('''
                    UPDATE product_images SET is_primary = 0 
                    WHERE product_id = ?
                ''', (product_id,))
                
                # تعيين الصورة كأساسية
                cursor.execute('''
                    UPDATE product_images SET is_primary = 1 
                    WHERE id = ? AND product_id = ?
                ''', (image_data, product_id))
                
            elif action == 'delete':
                cursor.execute('DELETE FROM product_images WHERE id = ? AND product_id = ?', (image_data, product_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def getProductImages(self, product_id):
        """جلب صور المنتج"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, image_data, image_url, is_primary, created_at
            FROM product_images 
            WHERE product_id = ?
            ORDER BY is_primary DESC, created_at DESC
        ''', (product_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        images = []
        for row in results:
            image_data = None
            if row[1]:  # image_data
                # تحويل BLOB إلى base64 للعرض في الواجهة
                image_data = base64.b64encode(row[1]).decode('utf-8')
            
            images.append({
                'id': row[0],
                'image_data': image_data,
                'image_url': row[2],
                'is_primary': bool(row[3]),
                'created_at': row[4]
            })
        
        return images
    
    # =========================================================================
    # وظائف إدارة الفئات المتقدمة
    # =========================================================================
    
    def getCategoriesWithCount(self):
        """جلب الفئات مع عدد المنتجات"""
        return self.getCategoriesCount()
    
    def updateCategory(self, category_data):
        """تحديث الفئة"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if 'id' in category_data and category_data['id']:
                cursor.execute('''
                    UPDATE categories 
                    SET name = ?, description = ?
                    WHERE id = ?
                ''', (category_data['name'], category_data.get('description'), category_data['id']))
            else:
                cursor.execute('''
                    INSERT INTO categories (name, description)
                    VALUES (?, ?)
                ''', (category_data['name'], category_data.get('description')))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def deleteCategory(self, category_id):
        """حذف الفئة"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # التحقق إذا كانت الفئة مستخدمة في منتجات
            cursor.execute('SELECT COUNT(*) FROM products WHERE category_id = ? AND is_active = 1', (category_id,))
            product_count = cursor.fetchone()[0]
            
            if product_count > 0:
                return {
                    'success': False,
                    'error': f'لا يمكن حذف الفئة لأنها تحتوي على {product_count} منتج'
                }
            
            cursor.execute('DELETE FROM categories WHERE id = ?', (category_id,))
            conn.commit()
            
            return {'success': True, 'message': 'تم حذف الفئة بنجاح'}
            
        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    # =========================================================================
    # نظام المحاسبة المتقدم
    # =========================================================================
    
    def getAccountBalance(self, account_id):
        """جلب رصيد الحساب"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT balance FROM accounts WHERE id = ?', (account_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return float(result[0])
        return 0.0
    
    def createAccount(self, account_data):
        """إنشاء حساب جديد"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO accounts (name, account_type, balance, parent_id)
                VALUES (?, ?, ?, ?)
            ''', (
                account_data['name'],
                account_data['account_type'],
                account_data.get('balance', 0),
                account_data.get('parent_id')
            ))
            
            account_id = cursor.lastrowid
            conn.commit()
            
            return {'success': True, 'account_id': account_id}
            
        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    def getAccountTypes(self):
        """جلب أنواع الحسابات"""
        return [
            {'value': 'asset', 'label': 'أصول'},
            {'value': 'liability', 'label': 'خصوم'},
            {'value': 'equity', 'label': 'حقوق ملكية'},
            {'value': 'revenue', 'label': 'إيرادات'},
            {'value': 'expense', 'label': 'مصروفات'}
        ]
    
    def getFinancialSummary(self):
        """جلب الملخص المالي"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # إجمالي الأصول
        cursor.execute("SELECT COALESCE(SUM(balance), 0) FROM accounts WHERE account_type = 'asset' AND is_active = 1")
        total_assets = cursor.fetchone()[0]
        
        # إجمالي الخصوم
        cursor.execute("SELECT COALESCE(SUM(balance), 0) FROM accounts WHERE account_type = 'liability' AND is_active = 1")
        total_liabilities = cursor.fetchone()[0]
        
        # إجمالي حقوق الملكية
        cursor.execute("SELECT COALESCE(SUM(balance), 0) FROM accounts WHERE account_type = 'equity' AND is_active = 1")
        total_equity = cursor.fetchone()[0]
        
        # صافي الدخل (الإيرادات - المصروفات)
        cursor.execute("SELECT COALESCE(SUM(balance), 0) FROM accounts WHERE account_type = 'revenue' AND is_active = 1")
        total_revenue = cursor.fetchone()[0]
        
        cursor.execute("SELECT COALESCE(SUM(balance), 0) FROM accounts WHERE account_type = 'expense' AND is_active = 1")
        total_expense = cursor.fetchone()[0]
        net_income = total_revenue - total_expense
        
        # رصيد الصندوق
        cash_balance = self.getCashBalance()
        
        conn.close()
        
        return {
            'total_assets': float(total_assets),
            'total_liabilities': float(total_liabilities),
            'total_equity': float(total_equity),
            'net_income': float(net_income),
            'cash_balance': cash_balance,
            'financial_health': 'جيد' if total_assets >= total_liabilities else 'يتطلب الاهتمام'
        }
    
    def createVoucher(self, voucher_data):
        """إنشاء سند قبض/صرف"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # إنشاء رقم سند
            voucher_number = self.generateVoucherNumber(voucher_data['voucher_type'])
            
            cursor.execute('''
                INSERT INTO vouchers (voucher_number, voucher_type, account_id, amount, description, reference)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                voucher_number,
                voucher_data['voucher_type'],
                voucher_data['account_id'],
                voucher_data['amount'],
                voucher_data.get('description', ''),
                voucher_data.get('reference', '')
            ))
            
            voucher_id = cursor.lastrowid
            
            # تحديث رصيد الحساب
            if voucher_data['voucher_type'] == 'receipt':
                # سند قبض - زيادة رصيد الحساب
                cursor.execute('''
                    UPDATE accounts SET balance = balance + ? WHERE id = ?
                ''', (voucher_data['amount'], voucher_data['account_id']))
            else:
                # سند صرف - نقصان رصيد الحساب
                cursor.execute('''
                    UPDATE accounts SET balance = balance - ? WHERE id = ?
                ''', (voucher_data['amount'], voucher_data['account_id']))
            
            # تسجيل الحركة النقدية إذا كان الحساب نقدياً
            cursor.execute('SELECT name FROM accounts WHERE id = ?', (voucher_data['account_id'],))
            account_name = cursor.fetchone()[0]
            
            if 'نقد' in account_name or 'صندوق' in account_name:
                transaction_type = 'income' if voucher_data['voucher_type'] == 'receipt' else 'expense'
                self.updateCashBalance(voucher_data['amount'], transaction_type, voucher_data.get('description', ''))
            
            conn.commit()
            
            return {
                'success': True,
                'voucher_id': voucher_id,
                'voucher_number': voucher_number
            }
            
        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    def generateVoucherNumber(self, voucher_type):
        """إنشاء رقم سند تلقائي"""
        prefix = 'RCV' if voucher_type == 'receipt' else 'PAY'
        date_str = datetime.now().strftime('%Y%m%d')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) FROM vouchers 
            WHERE voucher_number LIKE ? AND DATE(created_at) = DATE('now')
        ''', (f'{prefix}{date_str}%',))
        
        count = cursor.fetchone()[0] + 1
        conn.close()
        
        return f'{prefix}{date_str}{count:04d}'
    
    def getVouchersByType(self, voucher_type, start_date=None, end_date=None):
        """جلب السندات حسب النوع"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = '''
            SELECT v.*, a.name as account_name
            FROM vouchers v
            LEFT JOIN accounts a ON v.account_id = a.id
            WHERE v.voucher_type = ?
        '''
        params = [voucher_type]
        
        if start_date and end_date:
            query += " AND DATE(v.created_at) BETWEEN ? AND ?"
            params.extend([start_date, end_date])
        
        query += " ORDER BY v.created_at DESC"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        vouchers = []
        for row in results:
            voucher = dict(zip([column[0] for column in cursor.description], row))
            voucher['amount'] = float(voucher['amount'])
            vouchers.append(voucher)
        
        return vouchers
    
    def processReceiptVoucher(self, voucher_data):
        """معالجة سند قبض"""
        voucher_data['voucher_type'] = 'receipt'
        return self.createVoucher(voucher_data)
    
    def processPaymentVoucher(self, voucher_data):
        """معالجة سند صرف"""
        voucher_data['voucher_type'] = 'payment'
        return self.createVoucher(voucher_data)
    
    def generateFinancialReport(self, start_date, end_date):
        """تقرير مالي شامل"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # الإيرادات
        cursor.execute('''
            SELECT COALESCE(SUM(total_amount), 0)
            FROM invoices 
            WHERE type = 'sale' AND status = 'completed'
            AND DATE(created_at) BETWEEN ? AND ?
        ''', (start_date, end_date))
        total_revenue = cursor.fetchone()[0]
        
        # المصروفات
        cursor.execute('''
            SELECT COALESCE(SUM(amount), 0)
            FROM vouchers 
            WHERE voucher_type = 'payment'
            AND DATE(created_at) BETWEEN ? AND ?
        ''', (start_date, end_date))
        total_expenses = cursor.fetchone()[0]
        
        # المبيعات النقدية
        cursor.execute('''
            SELECT COALESCE(SUM(paid_amount), 0)
            FROM invoices 
            WHERE type = 'sale' AND status = 'completed'
            AND remaining_amount = 0
            AND DATE(created_at) BETWEEN ? AND ?
        ''', (start_date, end_date))
        cash_sales = cursor.fetchone()[0]
        
        # المبيعات الآجلة
        cursor.execute('''
            SELECT COALESCE(SUM(remaining_amount), 0)
            FROM invoices 
            WHERE type = 'sale' AND status = 'completed'
            AND remaining_amount > 0
            AND DATE(created_at) BETWEEN ? AND ?
        ''', (start_date, end_date))
        credit_sales = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'period': f'{start_date} إلى {end_date}',
            'total_revenue': float(total_revenue),
            'total_expenses': float(total_expenses),
            'net_profit': float(total_revenue - total_expenses),
            'cash_sales': float(cash_sales),
            'credit_sales': float(credit_sales),
            'cash_balance': self.getCashBalance(),
            'report_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def getCustomerBalances(self):
        """أرصدة العملاء"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, phone, balance
            FROM customers
            WHERE balance != 0
            ORDER BY balance DESC
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        customers = []
        for row in results:
            customers.append({
                'id': row[0],
                'name': row[1],
                'phone': row[2],
                'balance': float(row[3])
            })
        
        return customers
    
    def getSupplierBalances(self):
        """أرصدة الموردين"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, phone, balance
            FROM suppliers
            WHERE balance != 0
            ORDER BY balance DESC
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        suppliers = []
        for row in results:
            suppliers.append({
                'id': row[0],
                'name': row[1],
                'phone': row[2],
                'balance': float(row[3])
            })
        
        return suppliers
    
    # =========================================================================
    # الوظائف الحالية (للحفاظ على التوافق)
    # =========================================================================
    
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
    
    def createJournalEntry(self, invoice_data, invoice_id):
        """إنشاء قيد محاسبي للفاتورة"""
        # التنفيذ الحالي - يمكن تحديثه ليتناسب مع النظام الجديد
        pass

# إنشاء كائن النظام
pos_system = POSBackend()

if __name__ == "__main__":
    print("نظام نقطة البيع المحسن جاهز للعمل!")
    print("بيانات الدخول الافتراضية:")
    print("اسم المستخدم: admin")
    print("كلمة المرور: admin123")
    print("\nالميزات الجديدة:")
    print("- نظام نقاط البيع المحسن مع دفع نقدي وآجل")
    print("- إدارة متقدمة للمنتجات والفئات")
    print("- نظام محاسبة متكامل مع السندات")
    print("- تقارير مالية شاملة")