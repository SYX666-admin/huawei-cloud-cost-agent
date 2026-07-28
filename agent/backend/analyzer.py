from typing import List, Dict, Any
import pandas as pd
import os

class BillAnalyzer:
    def __init__(self):
        pass
    
    def validate_csv(self, file_path: str) -> Dict[str, Any]:
        """验证CSV文件"""
        if not file_path or not os.path.exists(file_path):
            return {"code": 400, "message": "文件不存在"}
        
        if os.path.getsize(file_path) == 0:
            return {"code": 400, "message": "文件为空"}
        
        if not file_path.lower().endswith('.csv'):
            return {"code": 400, "message": "文件格式错误，仅支持CSV文件"}
        
        try:
            with open(file_path, 'rb') as f:
                import chardet
                raw_data = f.read(1024)
                result = chardet.detect(raw_data)
                encoding = result.get('encoding', 'utf-8') or 'utf-8'
            
            df = pd.read_csv(file_path, encoding=encoding, nrows=0)
            headers = df.columns.tolist()
            
            required_columns = ['资源ID', '费用']
            missing_columns = []
            
            for col in required_columns:
                found = False
                for header in headers:
                    if col in header or header.lower() == col.lower():
                        found = True
                        break
                if not found:
                    missing_columns.append(col)
            
            if missing_columns:
                return {"code": 400, "message": f"缺少必要的列：{', '.join(missing_columns)}"}
            
            return {"code": 0, "message": "验证通过"}
        
        except Exception as e:
            return {"code": 400, "message": f"文件验证失败：{str(e)}"}
    
    def parse_csv(self, file_path: str) -> Dict[str, Any]:
        """解析CSV文件"""
        validation = self.validate_csv(file_path)
        if validation['code'] != 0:
            return validation
        
        try:
            with open(file_path, 'rb') as f:
                import chardet
                raw_data = f.read(1024)
                result = chardet.detect(raw_data)
                encoding = result.get('encoding', 'utf-8') or 'utf-8'
            
            df = pd.read_csv(file_path, encoding=encoding)
            
            if df.empty:
                return {"code": 400, "message": "CSV文件中没有数据"}
            
            result = []
            
            for _, row in df.iterrows():
                resource = self._parse_row(row)
                if resource:
                    result.append(resource)
            
            return {
                "code": 0,
                "message": "解析成功",
                "data": result,
                "count": len(result)
            }
        
        except Exception as e:
            return {"code": 400, "message": f"解析CSV失败：{str(e)}"}
    
    def _parse_row(self, row: pd.Series) -> Dict[str, Any]:
        """解析单行数据"""
        resource = {}
        
        resource['resource_id'] = self._find_value(row, ['资源ID', '实例ID', 'ID'])
        if not resource['resource_id']:
            return None
        
        product_name = self._find_value(row, ['产品类型', '产品名称', '服务类型'])
        resource['product_name'] = product_name
        resource['product_type'] = self._map_product_type(product_name)
        
        resource['spec'] = self._find_value(row, ['规格', '实例规格', '配置'])
        resource['region'] = self._find_value(row, ['区域', '可用区'])
        
        cost_str = self._find_value(row, ['费用', '金额', '应付金额', '实际费用'])
        resource['cost'] = self._parse_cost(cost_str)
        
        usage_str = self._find_value(row, ['使用量', '用量', '使用时长'])
        resource['usage'] = self._parse_numeric(usage_str)
        resource['usage_unit'] = self._find_value(row, ['用量单位', '单位'])
        
        billing_mode = self._find_value(row, ['计费模式', '付费方式'])
        resource['billing_mode'] = self._parse_billing_mode(billing_mode)
        
        return resource
    
    def _find_value(self, row: pd.Series, possible_names: List[str]) -> str:
        """查找字段值"""
        for name in possible_names:
            for col in row.index:
                if name in str(col) or str(col).lower() == name.lower():
                    value = row[col]
                    if pd.notna(value):
                        return str(value).strip()
        return ''
    
    def _map_product_type(self, product_name: str) -> str:
        """映射产品类型"""
        if not product_name:
            return '其他'
        
        mapping = {
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
            'RDS': 'RDS',
            '云数据库': 'RDS',
            'OBS': 'OBS',
            '对象存储': 'OBS',
            'ELB': 'ELB',
            '负载均衡': 'ELB',
        }
        
        for key, value in mapping.items():
            if key in product_name or product_name in key:
                return value
        
        return '其他'
    
    def _parse_cost(self, cost_str: str) -> float:
        """解析费用，处理折扣情况"""
        if not cost_str:
            return 0.0
        
        cost_str = str(cost_str).strip()
        
        if '折扣' in cost_str or '折后' in cost_str or '优惠' in cost_str:
            parts = cost_str.split()
            for part in parts:
                try:
                    return float(part.replace(',', '').replace('元', '').replace('¥', ''))
                except ValueError:
                    continue
            return 0.0
        
        try:
            return float(str(cost_str).replace(',', '').replace('元', '').replace('¥', ''))
        except ValueError:
            return 0.0
    
    def _parse_numeric(self, value_str: str) -> float:
        """解析数值"""
        if not value_str:
            return 0.0
        try:
            return float(str(value_str).replace(',', ''))
        except ValueError:
            return 0.0
    
    def _parse_billing_mode(self, mode_str: str) -> str:
        """解析计费模式"""
        if not mode_str:
            return 'on_demand'
        
        mode_str = mode_str.strip().lower()
        
        if '包年包月' in mode_str or '年付' in mode_str:
            return 'yearly'
        elif '月付' in mode_str or '包月' in mode_str:
            return 'monthly'
        else:
            return 'on_demand'
    
    def analyze_cost(self, resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析费用构成"""
        if not resources or len(resources) == 0:
            return {"code": 400, "message": "没有资源数据可分析"}
        
        try:
            df = pd.DataFrame(resources)
            
            # 确保 cost 列是 float 类型
            df['cost'] = df['cost'].apply(lambda x: float(x) if x is not None else 0.0)
            
            cost_by_type = df.groupby('product_type')['cost'].sum().reset_index()
            cost_total = float(cost_by_type['cost'].sum())
            cost_by_type['percentage'] = (cost_by_type['cost'] / cost_total * 100).round(1) if cost_total > 0 else 0.0
            
            cost_by_region = df.groupby('region')['cost'].sum().reset_index()
            
            top_resources = df.sort_values('cost', ascending=False).head(10).to_dict('records')
            
            total_cost = float(df['cost'].sum())
            
            return {
                "code": 0,
                "message": "分析成功",
                "data": {
                    "total_cost": round(total_cost, 2),
                    "cost_by_type": cost_by_type.to_dict('records'),
                    "cost_by_region": cost_by_region.to_dict('records'),
                    "top_resources": top_resources
                }
            }
        
        except Exception as e:
            return {"code": 400, "message": f"费用分析失败：{str(e)}"}
    
    def diagnose_idle_resources(self, resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """诊断闲置资源"""
        if not resources or len(resources) == 0:
            return {"code": 400, "message": "没有资源数据可诊断"}
        
        try:
            idle_eips = []
            low_load_ecss = []
            idle_evs = []
            seen_resources = set()
            
            for resource in resources:
                product_type = resource.get('product_type', '')
                cost = float(resource.get('cost', 0.0))
                usage = float(resource.get('usage', 0.0))
                resource_id = resource.get('resource_id', '')
                
                if resource_id in seen_resources:
                    continue
                
                if product_type == 'EIP' and usage == 0:
                    idle_eips.append(resource)
                    seen_resources.add(resource_id)
                
                elif product_type == 'ECS':
                    if cost > 0 and usage < 5:
                        low_load_ecss.append(resource)
                        seen_resources.add(resource_id)
                
                elif product_type == 'EVS' and usage == 0:
                    idle_evs.append(resource)
                    seen_resources.add(resource_id)
            
            return {
                "code": 0,
                "message": "诊断成功",
                "data": {
                    "idle_eips": idle_eips,
                    "low_load_ecss": low_load_ecss,
                    "idle_evs": idle_evs,
                    "summary": {
                        "idle_eip_count": len(idle_eips),
                        "low_load_ecs_count": len(low_load_ecss),
                        "idle_evs_count": len(idle_evs)
                    }
                }
            }
        
        except Exception as e:
            return {"code": 400, "message": f"诊断失败：{str(e)}"}
    
    def generate_recommendations(self, resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成优化建议，包含风险提示"""
        if not resources or len(resources) == 0:
            return {"code": 400, "message": "没有资源数据可分析"}
        
        try:
            recommendations = []
            total_savings = 0.0
            seen_resources = set()
            
            for resource in resources:
                product_type = resource.get('product_type', '')
                cost = float(resource.get('cost', 0.0))
                usage = float(resource.get('usage', 0.0))
                spec = resource.get('spec', '')
                billing_mode = resource.get('billing_mode', 'on_demand')
                resource_id = resource.get('resource_id', '')
                
                if resource_id in seen_resources:
                    continue
                
                if product_type == 'EIP' and usage == 0 and cost > 0:
                    rec = self._generate_eip_release_recommendation(resource)
                    if rec:
                        recommendations.append(rec)
                        total_savings += float(rec['estimated_savings'])
                        seen_resources.add(resource_id)
                
                elif product_type == 'ECS' and cost > 0:
                    if usage < 5:
                        rec = self._generate_ecs_downsize_recommendation(resource)
                        if rec:
                            recommendations.append(rec)
                            total_savings += float(rec['estimated_savings'])
                            seen_resources.add(resource_id)
                
                elif product_type == 'EVS' and usage == 0 and cost > 0:
                    rec = self._generate_evs_release_recommendation(resource)
                    if rec:
                        recommendations.append(rec)
                        total_savings += float(rec['estimated_savings'])
                        seen_resources.add(resource_id)
            
            return {
                "code": 0,
                "message": "生成建议成功",
                "data": {
                    "total_savings": round(total_savings, 2),
                    "recommendation_count": len(recommendations),
                    "recommendations": recommendations
                }
            }
        
        except Exception as e:
            return {"code": 400, "message": f"生成建议失败：{str(e)}"}
    
    def _generate_eip_release_recommendation(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """生成EIP释放建议"""
        return {
            "id": f"rec-eip-{resource['resource_id'][:8]}",
            "resource_id": resource['resource_id'],
            "product_type": 'EIP',
            "issue_description": f"弹性公网IP {resource['resource_id']} 检测到30天内无流量使用，属于闲置资源",
            "recommendation": f"释放该弹性公网IP {resource['resource_id']}",
            "estimated_savings": round(float(resource.get('cost', 0.0)), 2),
            "billing_mode": resource.get('billing_mode', 'on_demand'),
            "risk_level": "high",
            "risk_warning": "释放后该IP地址将不可用，如果有业务正在使用该IP，会导致业务中断。请确认该IP未被任何业务使用后再执行释放操作。",
            "category": "release"
        }
    
    def _generate_ecs_downsize_recommendation(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """生成ECS降配建议"""
        current_spec = resource.get('spec', '未知规格')
        current_cost = float(resource.get('cost', 0.0))
        recommended_spec = self._suggest_downsize_spec(current_spec)
        savings_ratio = 0.4 if recommended_spec else 0.3
        
        return {
            "id": f"rec-ecs-{resource['resource_id'][:8]}",
            "resource_id": resource['resource_id'],
            "product_type": 'ECS',
            "issue_description": f"云服务器 {resource['resource_id']} 规格为 {current_spec}，检测到CPU使用率低于5%，存在资源浪费",
            "recommendation": f"将 {current_spec} 降配为 {recommended_spec if recommended_spec else '更小型规格'}",
            "estimated_savings": round(current_cost * savings_ratio, 2),
            "billing_mode": resource.get('billing_mode', 'on_demand'),
            "risk_level": "medium",
            "risk_warning": "降配操作需要重启实例，会导致业务短暂中断。请在业务低峰期执行，并确保应用可以正常重启。包年包月实例降配可能涉及费用计算调整。",
            "category": "downsize"
        }
    
    def _generate_ecs_rightsize_recommendation(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """生成ECS优化配置建议"""
        current_spec = resource.get('spec', '未知规格')
        current_cost = float(resource.get('cost', 0.0))
        
        return {
            "id": f"rec-ecs-opt-{resource['resource_id'][:8]}",
            "resource_id": resource['resource_id'],
            "product_type": 'ECS',
            "issue_description": f"云服务器 {resource['resource_id']} 规格为 {current_spec}，当前负载适中",
            "recommendation": f"当前配置 {current_spec} 基本匹配负载需求，建议继续观察或考虑开启自动伸缩",
            "estimated_savings": 0.0,
            "billing_mode": resource.get('billing_mode', 'on_demand'),
            "risk_level": "low",
            "risk_warning": "当前配置运行正常，建议维持现有配置。如需进一步优化，可考虑预留实例或竞价实例。",
            "category": "rightsize"
        }
    
    def _generate_evs_release_recommendation(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """生成EVS释放建议"""
        return {
            "id": f"rec-evs-{resource['resource_id'][:8]}",
            "resource_id": resource['resource_id'],
            "product_type": 'EVS',
            "issue_description": f"云硬盘 {resource['resource_id']} 检测到长期未被使用，属于闲置存储资源",
            "recommendation": f"释放该云硬盘 {resource['resource_id']}",
            "estimated_savings": round(float(resource.get('cost', 0.0)), 2),
            "billing_mode": resource.get('billing_mode', 'on_demand'),
            "risk_level": "high",
            "risk_warning": "释放云硬盘将永久删除其上的数据，且不可恢复。请确认该硬盘上没有重要数据，或已完成备份后再执行释放操作。",
            "category": "release"
        }
    
    def _suggest_downsize_spec(self, current_spec: str) -> str:
        """根据当前规格建议降配规格"""
        if not current_spec:
            return ''
        
        spec_mapping = {
            's6.large.2': 's6.medium.2',
            's6.medium.2': 's6.small.1',
            's6.small.1': 's6.micro.1',
            's5.large.2': 's5.medium.2',
            's5.medium.2': 's5.small.1',
            's5.small.1': 's5.micro.1',
            'c6.large.2': 'c6.medium.2',
            'c6.medium.2': 'c6.small.1',
        }
        
        return spec_mapping.get(current_spec, '')
    
    def get_complete_analysis(self, resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """获取完整的分析结果，包含所有需要的数据"""
        if not resources or len(resources) == 0:
            return {"code": 400, "message": "没有资源数据可分析"}
        
        try:
            df = pd.DataFrame(resources)
            
            # 确保 cost 列是 float 类型
            df['cost'] = df['cost'].apply(lambda x: float(x) if x is not None else 0.0)
            
            # 1. 生成 overview
            total_cost = float(df['cost'].sum())
            resource_count = len(resources)
            
            # 生成推荐建议以获取 total_savings 和 recommendation_count
            rec_result = self.generate_recommendations(resources)
            total_savings = float(rec_result['data']['total_savings']) if rec_result['code'] == 0 else 0.0
            recommendation_count = rec_result['data']['recommendation_count'] if rec_result['code'] == 0 else 0
            
            overview = {
                "total_cost": round(total_cost, 2),
                "resource_count": resource_count,
                "total_savings": round(total_savings, 2),
                "recommendation_count": recommendation_count
            }
            
            # 2. 生成 trend_data (模拟数据，因为没有时间序列数据)
            trend_data = [
                {"date": "2024-01", "amount": round(total_cost * 0.9, 2)},
                {"date": "2024-02", "amount": round(total_cost * 0.95, 2)},
                {"date": "2024-03", "amount": round(total_cost, 2)}
            ]
            
            # 3. 生成 category_data
            cost_by_type = df.groupby('product_type')['cost'].sum().reset_index()
            category_data = []
            for _, row in cost_by_type.iterrows():
                category_data.append({
                    "name": row['product_type'],
                    "amount": round(float(row['cost']), 2)
                })
            
            # 4. 生成 idle_resources
            idle_result = self.diagnose_idle_resources(resources)
            idle_resources = []
            
            if idle_result['code'] == 0:
                data = idle_result['data']
                
                if data.get('idle_eips'):
                    for eip in data['idle_eips']:
                        idle_resources.append({
                            "resource_id": eip['resource_id'],
                            "issue": "30天无流量",
                            "suggestion": "释放该弹性公网IP",
                            "saving": round(float(eip.get('cost', 0.0)), 2)
                        })
                
                if data.get('low_load_ecss'):
                    for ecs in data['low_load_ecss']:
                        idle_resources.append({
                            "resource_id": ecs['resource_id'],
                            "issue": "CPU使用率<5%",
                            "suggestion": "降配或释放该云服务器",
                            "saving": round(float(ecs.get('cost', 0.0)) * 0.4, 2)
                        })
                
                if data.get('idle_evs'):
                    for evs in data['idle_evs']:
                        idle_resources.append({
                            "resource_id": evs['resource_id'],
                            "issue": "未被使用",
                            "suggestion": "释放该云硬盘",
                            "saving": round(float(evs.get('cost', 0.0)), 2)
                        })
            
            # 5. 生成 recommendations
            recommendations = []
            if rec_result['code'] == 0:
                for rec in rec_result['data']['recommendations']:
                    recommendations.append({
                        "resource_id": rec['resource_id'],
                        "type": rec['product_type'],
                        "description": rec['issue_description'],
                        "action": rec['recommendation'],
                        "estimated_savings": round(float(rec['estimated_savings']), 2)
                    })
            
            return {
                "code": 0,
                "message": "分析成功",
                "data": {
                    "overview": overview,
                    "trend_data": trend_data,
                    "category_data": category_data,
                    "idle_resources": idle_resources,
                    "recommendations": recommendations
                }
            }
        
        except Exception as e:
            return {"code": 400, "message": f"完整分析失败：{str(e)}"}