import csv
import chardet
from typing import List, Dict, Any, Optional

class HuaweiBillAdapter:
    PRODUCT_MAPPING = {
        '弹性云服务器': 'ECS',
        '云服务器': 'ECS',
        'ECS': 'ECS',
        '弹性公网IP': 'EIP',
        '公网IP': 'EIP',
        'EIP': 'EIP',
        '弹性块存储': 'EVS',
        '云硬盘': 'EVS',
        'EVS': 'EVS',
        '虚拟私有云': 'VPC',
        'VPC': 'VPC',
        '云数据库RDS': 'RDS',
        'RDS': 'RDS',
        '对象存储服务': 'OBS',
        'OBS': 'OBS',
        '负载均衡': 'ELB',
        'ELB': 'ELB',
    }
    
    def __init__(self):
        self.detected_encoding = 'utf-8'
    
    def detect_encoding(self, file_path: str) -> str:
        """检测文件编码，支持UTF-8和GBK"""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(1024)
                result = chardet.detect(raw_data)
                encoding = result.get('encoding', 'utf-8')
                if encoding is None:
                    encoding = 'utf-8'
                return encoding.lower()
        except Exception as e:
            return 'utf-8'
    
    def normalize_product_type(self, product_name: str) -> str:
        """将华为云产品名称映射为标准类型"""
        if not product_name:
            return '其他'
        
        product_name = product_name.strip()
        
        for key, value in self.PRODUCT_MAPPING.items():
            if key in product_name or product_name in key:
                return value
        
        return '其他'
    
    def extract_fields(self, row: Dict[str, str], headers: List[str], row_num: int = 0) -> Optional[Dict[str, Any]]:
        """从单行数据中提取需要的字段"""
        result = {}
        
        resource_id = self._find_field_value(row, headers, ['资源ID', '实例ID', 'ID', 'resource_id', 'instance_id'])
        
        if not resource_id:
            product = self._find_field_value(row, headers, ['产品', '产品类型', '产品名称', '服务类型'])
            if product:
                resource_id = f"product_{product[:20]}_{row_num}"
            else:
                order_id = self._find_field_value(row, headers, ['订单号', '订单ID', 'order_id', 'order_no'])
                if order_id:
                    resource_id = f"order_{order_id[:20]}"
                else:
                    resource_id = f"row_{row_num}"
        
        result['resource_id'] = resource_id
        
        product_name = self._find_field_value(row, headers, ['产品类型', '产品名称', '服务类型', 'resource_type', 'product_name'])
        result['product_name'] = product_name if product_name else '未知'
        result['product_type'] = self.normalize_product_type(product_name)
        
        spec = self._find_field_value(row, headers, ['规格', '实例规格', '配置', 'spec', 'instance_spec'])
        result['spec'] = spec if spec else None
        
        cost_str = self._find_field_value(row, headers, ['应付金额', '费用', '金额', '实际费用', 'cost', 'amount'])
        if not cost_str:
            result['cost'] = 0.0
        else:
            result['cost'] = self._parse_cost(cost_str)
        
        official_price_str = self._find_field_value(row, headers, ['官网价', '官方价', '标价', 'list_price', 'official_price'])
        if official_price_str:
            result['official_price'] = self._parse_cost(official_price_str)
        else:
            result['official_price'] = None
        
        usage_str = self._find_field_value(row, headers, ['使用量', '用量', '使用时长', 'usage', 'quantity'])
        if usage_str:
            result['usage'] = self._parse_numeric(usage_str)
        else:
            result['usage'] = 0.0
        
        usage_unit = self._find_field_value(row, headers, ['用量单位', '单位', '使用量单位', 'usage_unit', 'unit'])
        result['usage_unit'] = usage_unit if usage_unit else None
        
        region = self._find_field_value(row, headers, ['区域', '可用区', 'region', 'zone'])
        result['region'] = region if region else None
        
        billing_mode = self._find_field_value(row, headers, ['计费模式', '付费方式', 'billing_mode'])
        result['billing_mode'] = self._parse_billing_mode(billing_mode)
        
        return result
    
    def _find_field_value(self, row: Dict[str, str], headers: List[str], possible_names: List[str]) -> Optional[str]:
        """在多个可能的字段名中查找值"""
        for possible_name in possible_names:
            for header in headers:
                if header.strip() == possible_name or possible_name.lower() in header.lower():
                    value = row.get(header, row.get(header.strip()))
                    if value:
                        return str(value).strip()
        return None
    
    def _parse_cost(self, cost_str: str) -> float:
        """解析费用字段，处理带'折扣'等字样的情况"""
        try:
            cost_str = str(cost_str).strip()
            if '折扣' in cost_str or '折后' in cost_str or '优惠' in cost_str:
                parts = cost_str.split()
                for part in parts:
                    try:
                        return float(part.replace(',', '').replace('元', '').replace('¥', ''))
                    except ValueError:
                        continue
                return 0.0
            return float(cost_str.replace(',', '').replace('元', '').replace('¥', ''))
        except (ValueError, TypeError):
            return 0.0
    
    def _parse_numeric(self, value_str: str) -> float:
        """解析数值字段"""
        try:
            return float(str(value_str).strip().replace(',', ''))
        except (ValueError, TypeError):
            return 0.0
    
    def _parse_billing_mode(self, mode_str: Optional[str]) -> Optional[str]:
        """解析计费模式"""
        if not mode_str:
            return None
        
        mode_str = mode_str.strip().lower()
        
        if '包年包月' in mode_str or '年付' in mode_str or 'yearly' in mode_str:
            return 'yearly'
        elif '月付' in mode_str or 'monthly' in mode_str or '包月' in mode_str:
            return 'monthly'
        elif '按需' in mode_str or '按量' in mode_str or 'on_demand' in mode_str:
            return 'on_demand'
        
        return None
    
    def validate_file(self, file_path: str) -> Dict[str, Any]:
        """验证文件格式是否正确"""
        if not file_path or not file_path.endswith('.csv'):
            return {"code": 400, "message": "文件格式错误，仅支持CSV文件"}
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                if len(content) == 0:
                    return {"code": 400, "message": "文件为空"}
                
                self.detected_encoding = self.detect_encoding(file_path)
                
                with open(file_path, 'r', encoding=self.detected_encoding, errors='replace') as f:
                    reader = csv.reader(f)
                    headers = next(reader, None)
                    
                    if not headers:
                        return {"code": 400, "message": "CSV文件没有表头"}
                    
                    headers = [h.strip() for h in headers]
                    
                    has_product_type = any('产品类型' in h or '产品名称' in h or '服务类型' in h or 'product_type' in h.lower() for h in headers)
                    has_cost = any('应付金额' in h or '费用' in h or '金额' in h or 'cost' in h.lower() or 'amount' in h.lower() for h in headers)
                    
                    if not has_product_type:
                        return {"code": 400, "message": "缺少必要的列：产品类型"}
                    if not has_cost:
                        return {"code": 400, "message": "缺少必要的列：应付金额"}
                
                return {"code": 0, "message": "验证通过"}
        
        except Exception as e:
            return {"code": 400, "message": f"文件读取失败：{str(e)}"}
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """解析华为云账单CSV文件"""
        validation = self.validate_file(file_path)
        if validation['code'] != 0:
            return validation
        
        try:
            resources = []
            
            with open(file_path, 'r', encoding=self.detected_encoding, errors='replace') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                
                if not headers:
                    return {"code": 400, "message": "无法读取CSV表头"}
                
                headers = [h.strip() for h in headers]
                
                for row_num, row in enumerate(reader, start=1):
                    normalized_row = {h: row.get(h, '').strip() for h in headers}
                    
                    if not any(normalized_row.values()):
                        continue
                    
                    extracted = self.extract_fields(normalized_row, headers, row_num)
                    if extracted:
                        resources.append(extracted)
            
            if len(resources) == 0:
                return {"code": 400, "message": "CSV文件中没有有效的资源记录"}
            
            return {
                "code": 0,
                "message": "解析成功",
                "data": resources,
                "count": len(resources)
            }
        
        except Exception as e:
            return {"code": 400, "message": f"解析CSV失败：{str(e)}"}