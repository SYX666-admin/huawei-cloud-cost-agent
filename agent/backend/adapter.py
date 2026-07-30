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
        '弹性负载均衡': 'ELB',
        '虚拟专用网络': 'VPN',
        'VPN': 'VPN',
        '高性能弹性文件服务': 'SFS Turbo',
        'SFS Turbo': 'SFS Turbo',
        '云商店': '云商店',
        '云备份': 'CBR',
        'CBR': 'CBR',
        '云监控服务': '云监控',
        '云监控': '云监控',
        '弹性伸缩': 'AS',
        'AS': 'AS',
        '自动伸缩': 'AS',
    }
    
    def __init__(self):
        self.detected_encoding = 'utf-8'
    
    def detect_encoding(self, file_path: str) -> str:
        """检测文件编码，支持UTF-8(含BOM)和GBK"""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(1024)
                
                # 检查 UTF-8 BOM (EF BB BF)
                if raw_data.startswith(b'\xef\xbb\xbf'):
                    return 'utf-8-sig'
                
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
            order_id = self._find_field_value(row, headers, ['订单号', '订单ID', 'order_id', 'order_no'])
            if order_id:
                resource_id = f"order_{order_id[:20]}"
            else:
                product_name = self._find_field_value(row, headers, ['产品类型', '产品名称', '服务类型', 'resource_type', 'product_name'])
                if product_name:
                    resource_id = f"product_{product_name[:20]}_{row_num}"
                else:
                    resource_id = f"row_{row_num}"
            result['is_aggregate'] = True
        else:
            result['is_aggregate'] = False
        
        result['resource_id'] = resource_id
        
        product_name = self._find_field_value(row, headers, ['产品类型', '产品名称', '服务类型', 'resource_type', 'product_name'])
        result['product_name'] = product_name if product_name else '未知'
        result['product_type'] = self.normalize_product_type(product_name)
        
        spec = self._find_field_value(row, headers, ['规格', '实例规格', '配置', 'spec', 'instance_spec'])
        result['spec'] = spec if spec else '汇总账单，无规格明细'
        
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
        """在多个可能的字段名中查找值，支持清理后的表头匹配"""
        cleaned_headers = [self._normalize_header(h) for h in headers]
        for possible_name in possible_names:
            for idx, header in enumerate(cleaned_headers):
                if not header:
                    continue
                # 优先精确匹配，再尝试包含匹配
                if header == possible_name or possible_name.lower() in header.lower():
                    original_header = headers[idx]
                    value = row.get(original_header, row.get(header))
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
    
    def _normalize_header(self, header: str) -> str:
        """清理表头，去除空格、全角空格、BOM等特殊字符"""
        if not header:
            return ''
        # 去除BOM、全角空格、普通空格、制表符等
        header = header.replace('\ufeff', '')
        header = header.replace('\u3000', '')  # 全角空格
        header = header.replace('\xa0', '')    # 不间断空格
        header = header.strip()
        return header
    
    def _header_matches(self, header: str, possible_names: List[str]) -> bool:
        """检查表头是否匹配可能的列名，支持清理后精确匹配或包含匹配"""
        normalized = self._normalize_header(header)
        if not normalized:
            return False
        for name in possible_names:
            if normalized == name:
                return True
            if name in normalized and len(name) >= 2:
                return True
        return False
    
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
                    
                    headers = [self._normalize_header(h) for h in headers]
                    
                    product_type_names = ['产品类型', '产品名称', '服务类型', 'product_type', 'product_name', 'resource_type']
                    cost_names = ['应付金额', '费用', '金额', 'cost', 'amount', '实际费用']
                    
                    # 模糊匹配：col.strip() == '产品类型' 或 '产品类型' in col，兼容带空格或其他变体
                    has_product_type = any(
                        h.strip() == name or name in h
                        for h in headers
                        for name in product_type_names
                    )
                    has_cost = any(
                        h.strip() == name or name in h
                        for h in headers
                        for name in cost_names
                    )
                    
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
            deduplication_key_set = set()
            
            with open(file_path, 'r', encoding=self.detected_encoding, errors='replace') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                
                if not headers:
                    return {"code": 400, "message": "无法读取CSV表头"}
                
                headers = [self._normalize_header(h) for h in headers]
                
                for row_num, row in enumerate(reader, start=1):
                    normalized_row = {h: self._normalize_header(row.get(h, '').strip()) for h in headers}
                    
                    if not any(normalized_row.values()):
                        continue
                    
                    extracted = self.extract_fields(normalized_row, headers, row_num)
                    if extracted:
                        resources.append(extracted)
            
            if len(resources) == 0:
                return {"code": 400, "message": "CSV文件中没有有效的资源记录"}
            
            total_cost = sum(r['cost'] for r in resources)
            
            for r in resources:
                deduplication_key = f"{r.get('product_type', '')}_{r.get('product_name', '')}"
                deduplication_key_set.add(deduplication_key)
            
            deduplicated_count = len(deduplication_key_set)
            
            return {
                "code": 0,
                "message": "解析成功",
                "data": resources,
                "count": len(resources),
                "deduplicated_count": deduplicated_count,
                "total_cost": round(total_cost, 2)
            }
        
        except Exception as e:
            return {"code": 400, "message": f"解析CSV失败：{str(e)}"}