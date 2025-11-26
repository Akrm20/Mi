from flask import Flask, render_template, request, jsonify, send_from_directory, session
from flask_cors import CORS
from pos_backend import POSBackend
import os
import json
from datetime import datetime

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
        data = pos_system.loadDashboardData()
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
        products = pos_system.loadProductsForPOS()
        return jsonify({"success": True, "data": products})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/products', methods=['POST'])
def save_product():
    try:
        data = request.json
        result = pos_system.saveProduct(data)
        return jsonify({"success": True, "message": "تم حفظ المنتج بنجاح"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        result = pos_system.deleteProduct(product_id)
        return jsonify({"success": True, "message": "تم حذف المنتج بنجاح"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/invoices')
def get_invoices():
    try:
        invoice_type = request.args.get('type')
        invoices = pos_system.getAllInvoices(invoice_type)
        return jsonify({"success": True, "data": invoices})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/invoices', methods=['POST'])
def create_invoice():
    try:
        data = request.json
        invoice_id = pos_system.saveInvoice(data)
        return jsonify({"success": True, "invoice_id": invoice_id, "message": "تم حفظ الفاتورة بنجاح"})
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

@app.route('/api/suppliers')
def get_suppliers():
    try:
        suppliers = pos_system.loadSuppliers()
        return jsonify({"success": True, "data": suppliers})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/categories')
def get_categories():
    try:
        categories = pos_system.loadCategories()
        return jsonify({"success": True, "data": categories})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/reports/sales')
def get_sales_reports():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        reports = pos_system.loadSalesReports(start_date, end_date)
        return jsonify({"success": True, "data": reports})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/reports/purchases')
def get_purchases_reports():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        reports = pos_system.loadPurchasesReports(start_date, end_date)
        return jsonify({"success": True, "data": reports})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/backup', methods=['POST'])
def create_backup():
    try:
        backup_path = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        pos_system.backupData(backup_path)
        return jsonify({"success": True, "message": "تم إنشاء نسخة احتياطية", "file": backup_path})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)