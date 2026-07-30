from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import uuid
from datetime import datetime
import tempfile

from models import init_db, Bill, Resource, AnalysisResult, get_db
from adapter import HuaweiBillAdapter
from analyzer import BillAnalyzer

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

init_db()

@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('../frontend', path)

@app.route('/api/v1/bills/upload', methods=['POST'])
def upload_bill():
    if 'file' not in request.files:
        return jsonify({"code": 400, "message": "请选择要上传的文件"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"code": 400, "message": "文件名不能为空"}), 400
    
    if not file.filename.lower().endswith('.csv'):
        return jsonify({"code": 400, "message": "仅支持CSV格式的账单文件"}), 400
    
    try:
        temp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex[:8]}_{file.filename}")
        file.save(temp_path)
        
        adapter = HuaweiBillAdapter()
        parse_result = adapter.parse(temp_path)
        
        if parse_result['code'] != 0:
            os.remove(temp_path)
            return jsonify(parse_result), 400
        
        bill_id = f"bill-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
        
        db = next(get_db())
        
        bill = Bill(
            bill_id=bill_id,
            file_name=file.filename,
            record_count=parse_result['count'],
            total_amount=float(sum(r['cost'] for r in parse_result['data'])),
            status='completed'
        )
        db.add(bill)
        
        for resource_data in parse_result['data']:
            resource = Resource(
                bill_id=bill_id,
                resource_id=resource_data['resource_id'],
                product_type=resource_data['product_type'],
                product_name=resource_data['product_name'],
                spec=resource_data['spec'],
                region=resource_data['region'],
                cost=resource_data['cost'],
                usage=resource_data['usage'],
                usage_unit=resource_data['usage_unit'],
                billing_mode=resource_data.get('billing_mode', 'on_demand')
            )
            db.add(resource)
        
        db.commit()
        
        analyzer = BillAnalyzer()
        recommendations = analyzer.generate_recommendations(parse_result['data'])
        
        if recommendations['code'] == 0:
            for rec in recommendations['data']['recommendations']:
                analysis_result = AnalysisResult(
                    bill_id=bill_id,
                    resource_id=rec['resource_id'],
                    product_type=rec['product_type'],
                    issue_description=rec['issue_description'],
                    recommendation=rec['recommendation'],
                    estimated_savings=rec['estimated_savings'],
                    billing_mode=rec['billing_mode'],
                    risk_level=rec['risk_level'],
                    risk_warning=rec['risk_warning'],
                    category=rec['category']
                )
                db.add(analysis_result)
        
        db.commit()
        os.remove(temp_path)
        
        return jsonify({
            "code": 0,
            "message": "上传成功",
            "data": {
                "bill_id": bill_id,
                "file_name": file.filename,
                "upload_time": datetime.now().isoformat(),
                "record_count": parse_result['count'],
                "total_amount": round(float(sum(r['cost'] for r in parse_result['data'])), 2)
            }
        })
    
    except Exception as e:
        return jsonify({"code": 400, "message": f"上传失败：{str(e)}"}), 400

@app.route('/api/v1/bills/list', methods=['GET'])
def list_bills():
    try:
        db = next(get_db())
        bills = db.query(Bill).order_by(Bill.upload_time.desc()).all()
        return jsonify({
            "code": 0,
            "message": "success",
            "data": [bill.to_dict() for bill in bills]
        })
    except Exception as e:
        return jsonify({"code": 400, "message": f"查询失败：{str(e)}"}), 400

@app.route('/api/v1/bills/<bill_id>', methods=['GET'])
def get_bill(bill_id):
    try:
        db = next(get_db())
        bill = db.query(Bill).filter(Bill.bill_id == bill_id).first()
        if not bill:
            return jsonify({"code": 404, "message": "账单不存在"}), 404
        return jsonify({
            "code": 0,
            "message": "success",
            "data": bill.to_dict()
        })
    except Exception as e:
        return jsonify({"code": 400, "message": f"查询失败：{str(e)}"}), 400

@app.route('/api/v1/bills/<bill_id>', methods=['DELETE'])
def delete_bill(bill_id):
    try:
        db = next(get_db())
        bill = db.query(Bill).filter(Bill.bill_id == bill_id).first()
        if not bill:
            return jsonify({"code": 404, "message": "账单不存在"}), 404
        
        db.query(Resource).filter(Resource.bill_id == bill_id).delete()
        db.query(AnalysisResult).filter(AnalysisResult.bill_id == bill_id).delete()
        db.delete(bill)
        db.commit()
        
        return jsonify({"code": 0, "message": "删除成功"})
    except Exception as e:
        return jsonify({"code": 400, "message": f"删除失败：{str(e)}"}), 400

@app.route('/api/v1/analysis/overview', methods=['GET'])
def get_analysis_overview():
    bill_id = request.args.get('bill_id')
    if not bill_id:
        return jsonify({"code": 400, "message": "缺少bill_id参数"}), 400
    
    try:
        db = next(get_db())
        resources = db.query(Resource).filter(Resource.bill_id == bill_id).all()
        
        if not resources:
            return jsonify({"code": 404, "message": "没有找到资源数据"}), 404
        
        resources_list = [r.to_dict() for r in resources]
        
        total_cost = float(sum(r['cost'] for r in resources_list))
        resource_count = len(resources_list)
        product_types = {}
        
        for r in resources_list:
            pt = r['product_type']
            if pt not in product_types:
                product_types[pt] = {'count': 0, 'cost': 0.0}
            product_types[pt]['count'] += 1
            product_types[pt]['cost'] += float(r['cost'])
        
        return jsonify({
            "code": 0,
            "message": "success",
            "data": {
                "bill_id": bill_id,
                "total_cost": round(total_cost, 2),
                "resource_count": resource_count,
                "product_types": product_types
            }
        })
    except Exception as e:
        return jsonify({"code": 400, "message": f"分析失败：{str(e)}"}), 400

@app.route('/api/v1/analysis/category', methods=['GET'])
def get_analysis_category():
    bill_id = request.args.get('bill_id')
    if not bill_id:
        return jsonify({"code": 400, "message": "缺少bill_id参数"}), 400
    
    try:
        db = next(get_db())
        resources = db.query(Resource).filter(Resource.bill_id == bill_id).all()
        
        if not resources:
            return jsonify({"code": 404, "message": "没有找到资源数据"}), 404
        
        resources_list = [r.to_dict() for r in resources]
        total_cost = float(sum(r['cost'] for r in resources_list))
        
        category_data = {}
        for r in resources_list:
            pt = r['product_type']
            if pt not in category_data:
                category_data[pt] = 0.0
            category_data[pt] += float(r['cost'])
        
        categories = []
        for name, cost in category_data.items():
            categories.append({
                "name": name,
                "amount": round(cost, 2),
                "percentage": round((cost / total_cost) * 100, 1) if total_cost > 0 else 0.0
            })
        
        return jsonify({
            "code": 0,
            "message": "success",
            "data": {
                "bill_id": bill_id,
                "categories": categories
            }
        })
    except Exception as e:
        return jsonify({"code": 400, "message": f"分析失败：{str(e)}"}), 400

@app.route('/api/v1/diagnosis/idle', methods=['GET'])
def get_diagnosis_idle():
    bill_id = request.args.get('bill_id')
    if not bill_id:
        return jsonify({"code": 400, "message": "缺少bill_id参数"}), 400
    
    try:
        db = next(get_db())
        resources = db.query(Resource).filter(Resource.bill_id == bill_id).all()
        
        if not resources:
            return jsonify({"code": 404, "message": "没有找到资源数据"}), 404
        
        resources_list = [r.to_dict() for r in resources]
        
        idle_eips = []
        low_load_ecss = []
        idle_evs = []
        
        for r in resources_list:
            if r['product_type'] == 'EIP' and r['usage'] == 0:
                idle_eips.append(r)
            elif r['product_type'] == 'ECS' and r['usage'] < 10:
                low_load_ecss.append(r)
            elif r['product_type'] == 'EVS' and r['usage'] == 0:
                idle_evs.append(r)
        
        return jsonify({
            "code": 0,
            "message": "success",
            "data": {
                "bill_id": bill_id,
                "idle_eips": idle_eips,
                "low_load_ecss": low_load_ecss,
                "idle_evs": idle_evs,
                "summary": {
                    "idle_eip_count": len(idle_eips),
                    "low_load_ecs_count": len(low_load_ecss),
                    "idle_evs_count": len(idle_evs)
                }
            }
        })
    except Exception as e:
        return jsonify({"code": 400, "message": f"诊断失败：{str(e)}"}), 400

@app.route('/api/v1/recommendations', methods=['GET'])
def get_recommendations():
    bill_id = request.args.get('bill_id')
    if not bill_id:
        return jsonify({"code": 400, "message": "缺少bill_id参数"}), 400
    
    try:
        db = next(get_db())
        results = db.query(AnalysisResult).filter(AnalysisResult.bill_id == bill_id).all()
        
        if not results:
            return jsonify({"code": 404, "message": "没有找到建议数据"}), 404
        
        recommendations = []
        total_savings = 0.0
        
        for result in results:
            rec = result.to_dict()
            total_savings += rec['estimated_savings']
            recommendations.append({
                "id": rec['id'],
                "resource_id": rec['resource_id'],
                "product_type": rec['product_type'],
                "issue_description": rec['issue_description'],
                "recommendation": rec['recommendation'],
                "estimated_savings": rec['estimated_savings'],
                "billing_mode": rec['billing_mode'],
                "risk_level": rec['risk_level'],
                "risk_warning": rec['risk_warning'],
                "category": rec['category']
            })
        
        return jsonify({
            "code": 0,
            "message": "success",
            "data": {
                "bill_id": bill_id,
                "total_savings": round(total_savings, 2),
                "recommendations": recommendations
            }
        })
    except Exception as e:
        return jsonify({"code": 400, "message": f"查询失败：{str(e)}"}), 400

@app.route('/api/v1/analysis/complete', methods=['GET'])
def get_complete_analysis():
    bill_id = request.args.get('bill_id')
    if not bill_id:
        return jsonify({"code": 400, "message": "缺少bill_id参数"}), 400
    
    try:
        db = next(get_db())
        resources = db.query(Resource).filter(Resource.bill_id == bill_id).all()
        
        if not resources:
            return jsonify({"code": 404, "message": "没有找到资源数据"}), 404
        
        resources_list = [r.to_dict() for r in resources]
        
        analyzer = BillAnalyzer()
        complete_result = analyzer.get_complete_analysis(resources_list)
        
        return jsonify(complete_result)
    except Exception as e:
        return jsonify({"code": 400, "message": f"分析失败：{str(e)}"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)