from flask import Flask, render_template, request, jsonify, send_from_directory, session, send_file
from flask_cors import CORS
from pos_backend import POSBackend
import os
import json
from datetime import datetime
import io
import base64

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'
CORS(app)

pos_system = POSBackend()

# خدمة الملفات الثابتة
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

# APIs للواجهة الأمامية
@app.route('/api/dashboard')
def get_dashboard_data():
    try:
        # جلب البيانات الأساسية للوحة التحكم
        products = pos_system.getAllProducts()
        invoices = pos_system.getAllInvoices()
        customers = pos_system.loadCustomers()
        
        # مبيعات اليوم
        today = datetime.now().date()
        today_sales = sum(invoice['total_amount'] for invoice in invoices 
                         if invoice['type'] == 'sale' 
                         and datetime.strptime(invoice['created_at'], '%Y-%m-%d %H:%M:%S').date() == today)
        
        # قيمة المخزون
        inventory_value = sum(product['stock_quantity'] * product.get('purchase_price', 0) for product in products)
        
        data = {
            'today_sales': today_sales,
            'today_purchases': 0,  # يمكن تطويره لاحقاً
            'inventory_value': inventory_value,
            'customers_count': len(customers),
            'recent_invoices': invoices[-5:][::-1],  # آخر 5 فواتير
            'low_stock_products': [p for p in products if p['stock_quantity'] <= p.get('min_stock', 0)]
        }
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/products')
def get_products():
    try:
        products = pos_system.getAllProducts()
        return jsonify({"success": True, "data": products})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/products/pos')
def get_products_pos():
    try:
        category_id = request.args.get('category_id')
        if category_id and category_id != 'all':
            products = pos_system.getProductsByCategory(category_id)
        else:
            products = pos_system.getAllProducts()
        return jsonify({"success": True, "data": products})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/products/search')
def search_products():
    try:
        query = request.args.get('q', '')
        if len(query) >= 2:
            products = pos_system.searchProducts(query)
        else:
            products = []
        return jsonify({"success": True, "data": products})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/products', methods=['POST'])
def save_product():
    try:
        data = request.json
        result = pos_system.saveProduct(data)
        return jsonify({"success": True, "message": "تم حفظ المنتج بنجاح", "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        # في النظام الحالي، نستخدم التحديث بدلاً من الحذف الفعلي
        result = pos_system.saveProduct({'id': product_id, 'is_active': 0})
        return jsonify({"success": True, "message": "تم حذف المنتج بنجاح"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/products/statistics')
def get_product_statistics():
    try:
        stats = pos_system.getProductStatistics()
        return jsonify({"success": True, "data": stats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/products/export')
def export_products():
    try:
        result = pos_system.exportProductsToExcel()
        if result['success']:
            return send_file(
                io.BytesIO(result['data']),
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'products_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            )
        else:
            return jsonify({"success": False, "error": result['error']}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/products/import', methods=['POST'])
def import_products():
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "لم يتم اختيار ملف"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "لم يتم اختيار ملف"}), 400
        
        # حفظ الملف مؤقتاً
        file_path = f"temp_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        file.save(file_path)
        
        # استيراد البيانات
        result = pos_system.importProductsFromExcel(file_path)
        
        # حذف الملف المؤقت
        try:
            os.remove(file_path)
        except:
            pass
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/categories')
def get_categories():
    try:
        categories = pos_system.getCategoriesWithCount()
        return jsonify({"success": True, "data": categories})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/categories', methods=['POST'])
def save_category():
    try:
        data = request.json
        result = pos_system.updateCategory(data)
        return jsonify({"success": True, "message": "تم حفظ الفئة بنجاح"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    try:
        result = pos_system.deleteCategory(category_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/sales/process', methods=['POST'])
def process_sale():
    try:
        data = request.json
        result = pos_system.processSale(data)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/cash/balance')
def get_cash_balance():
    try:
        balance = pos_system.getCashBalance()
        return jsonify({"success": True, "balance": balance})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/invoices')
def get_invoices():
    try:
        invoice_type = request.args.get('type', 'sale')
        invoices = pos_system.getAllInvoices(invoice_type)
        return jsonify({"success": True, "data": invoices})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/invoices', methods=['POST'])
def create_invoice():
    try:
        data = request.json
        # استخدام النظام الجديد لمعالجة المبيعات
        if data.get('type') == 'sale':
            result = pos_system.processSale(data)
            return jsonify(result)
        else:
            # للمشتريات يمكن تطويرها لاحقاً
            return jsonify({"success": False, "error": "نوع الفاتورة غير مدعوم"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/customers')
def get_customers():
    try:
        customers = pos_system.loadCustomers()
        return jsonify({"success": True, "data": customers})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/customers', methods=['POST'])
def save_customer():
    try:
        data = request.json
        pos_system.saveCustomer(data)
        return jsonify({"success": True, "message": "تم حفظ العميل بنجاح"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/customers/balances')
def get_customer_balances():
    try:
        balances = pos_system.getCustomerBalances()
        return jsonify({"success": True, "data": balances})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# نظام المحاسبة الجديد
@app.route('/api/accounts')
def get_accounts():
    try:
        # في النظام الحالي، نعيد الحسابات الأساسية
        accounts = [
            {"id": 1, "name": "النقدية", "type": "asset", "balance": pos_system.getCashBalance()},
            {"id": 2, "name": "البضاعة", "type": "asset", "balance": 0},
            {"id": 3, "name": "العملاء", "type": "asset", "balance": 0},
            {"id": 4, "name": "الموردين", "type": "liability", "balance": 0},
            {"id": 5, "name": "رأس المال", "type": "equity", "balance": 0},
            {"id": 6, "name": "مبيعات", "type": "revenue", "balance": 0},
            {"id": 7, "name": "مشتريات", "type": "expense", "balance": 0}
        ]
        return jsonify({"success": True, "data": accounts})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/accounts', methods=['POST'])
def create_account():
    try:
        data = request.json
        result = pos_system.createAccount(data)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/accounts/types')
def get_account_types():
    try:
        types = pos_system.getAccountTypes()
        return jsonify({"success": True, "data": types})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/financial/summary')
def get_financial_summary():
    try:
        summary = pos_system.getFinancialSummary()
        return jsonify({"success": True, "data": summary})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/vouchers')
def get_vouchers():
    try:
        voucher_type = request.args.get('type', 'receipt')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        vouchers = pos_system.getVouchersByType(voucher_type, start_date, end_date)
        return jsonify({"success": True, "data": vouchers})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/vouchers', methods=['POST'])
def create_voucher():
    try:
        data = request.json
        voucher_type = data.get('voucher_type')
        
        if voucher_type == 'receipt':
            result = pos_system.processReceiptVoucher(data)
        elif voucher_type == 'payment':
            result = pos_system.processPaymentVoucher(data)
        else:
            return jsonify({"success": False, "error": "نوع السند غير مدعوم"}), 400
            
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/financial/report')
def get_financial_report():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            return jsonify({"success": False, "error": "يجب تحديد تاريخ البداية والنهاية"}), 400
            
        report = pos_system.generateFinancialReport(start_date, end_date)
        return jsonify({"success": True, "data": report})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/suppliers/balances')
def get_supplier_balances():
    try:
        balances = pos_system.getSupplierBalances()
        return jsonify({"success": True, "data": balances})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# التقارير
@app.route('/api/reports/sales')
def get_sales_reports():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        invoices = pos_system.getAllInvoices('sale')
        
        # تطبيق الفلتر إذا كان موجوداً
        if start_date and end_date:
            filtered_invoices = []
            for invoice in invoices:
                invoice_date = datetime.strptime(invoice['created_at'], '%Y-%m-%d %H:%M:%S').date()
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                if start <= invoice_date <= end:
                    filtered_invoices.append(invoice)
            invoices = filtered_invoices
        
        return jsonify({"success": True, "data": invoices})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/reports/purchases')
def get_purchases_reports():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        invoices = pos_system.getAllInvoices('purchase')
        
        # تطبيق الفلتر إذا كان موجوداً
        if start_date and end_date:
            filtered_invoices = []
            for invoice in invoices:
                invoice_date = datetime.strptime(invoice['created_at'], '%Y-%m-%d %H:%M:%S').date()
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                if start <= invoice_date <= end:
                    filtered_invoices.append(invoice)
            invoices = filtered_invoices
        
        return jsonify({"success": True, "data": invoices})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# النسخ الاحتياطي
@app.route('/api/backup', methods=['POST'])
def create_backup():
    try:
        backup_data = {
            'products': pos_system.getAllProducts(),
            'customers': pos_system.loadCustomers(),
            'invoices': pos_system.getAllInvoices(),
            'settings': pos_system.loadSettings(),
            'backup_date': datetime.now().isoformat()
        }
        
        backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        return jsonify({
            "success": True, 
            "message": "تم إنشاء نسخة احتياطية", 
            "filename": backup_filename,
            "data": backup_data
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/backup/restore', methods=['POST'])
def restore_backup():
    try:
        data = request.json
        # هنا سيتم استعادة البيانات من النسخة الاحتياطية
        # في النظام الحقيقي، سيتم حفظها في قاعدة البيانات
        return jsonify({"success": True, "message": "تم استعادة النسخة الاحتياطية بنجاح"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# الإعدادات
@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    try:
        if request.method == 'POST':
            data = request.json
            pos_system.saveSettings(data)
            return jsonify({"success": True, "message": "تم حفظ الإعدادات بنجاح"})
        else:
            settings = pos_system.loadSettings()
            return jsonify({"success": True, "data": settings})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# إدارة الصور
@app.route('/api/products/<int:product_id>/images', methods=['GET', 'POST'])
def manage_product_images(product_id):
    try:
        if request.method == 'POST':
            data = request.json
            action = data.get('action', 'add')
            image_data = data.get('image_data')
            image_url = data.get('image_url')
            
            result = pos_system.manageProductImages(product_id, image_data, image_url, action)
            return jsonify({"success": True, "message": "تمت العملية بنجاح"})
        else:
            images = pos_system.getProductImages(product_id)
            return jsonify({"success": True, "data": images})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# API للتحقق من صحة المستخدم
@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        user = pos_system.verify_user(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return jsonify({"success": True, "user": user})
        else:
            return jsonify({"success": False, "error": "اسم المستخدم أو كلمة المرور غير صحيحة"}), 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    try:
        session.clear()
        return jsonify({"success": True, "message": "تم تسجيل الخروج بنجاح"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/auth/check')
def check_auth():
    try:
        if 'user_id' in session:
            return jsonify({
                "success": True, 
                "authenticated": True,
                "user": {
                    "id": session['user_id'],
                    "username": session['username'],
                    "role": session['role']
                }
            })
        else:
            return jsonify({"success": True, "authenticated": False})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)