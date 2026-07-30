from typing import List, Dict, Any
import pandas as pd
import os

class BillAnalyzer:
    def __init__(self):
        pass
    
    def _has_monitor_data(self, resources: List[Dict[str, Any]]) -> bool:
        """判断是否有真实监控数据（检查是否有流量或CPU使用率数据）"""
        for r in resources:
            # 检查流量相关字段
            usage_unit = r.get('usage_unit', '').lower()
            if usage_unit and any(unit in usage_unit for unit in ['mb', 'gb', 'kb', 'bps', 'mbit/s', 'gbit/s']):
                usage = r.get('usage', 0)
                if usage is not None and float(usage) >= 0:
                    return True
            
            # 检查是否存在流量字段
            if r.get('流量') is not None:
                return True
            
            # 检查CPU使用率字段
            cpu_usage = r.get('cpu_usage') or r.get('cpu利用率') or r.get('cpu_utilization')
            if cpu_usage is not None:
                try:
                    float(cpu_usage)
                    return True
                except ValueError:
                    pass
            
            # 检查存储利用率字段
            storage_usage = r.get('storage_usage') or r.get('存储利用率')
            if storage_usage is not None:
                try:
                    float(storage_usage)
                    return True
                except ValueError:
                    pass
        return False
    
    def _get_diagnosis_type(self, resources: List[Dict[str, Any]]) -> str:
        """获取诊断类型：'actual_monitor' 或 'cost_infer'"""
        if self._has_monitor_data(resources):
            return 'actual_monitor'
        return 'cost_infer'
    
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
    
    def _deduplicate_resources(self, resource_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """对资源列表进行去重，优先使用resource_id，其次使用产品类型+产品名称"""
        seen = set()
        result = []
        for resource in resource_list:
            resource_id = resource.get('resource_id', '')
            product_type = resource.get('product_type', '')
            product_name = resource.get('product_name', '')
            
            # 优先使用资源ID作为去重键
            if resource_id and not resource_id.startswith('row_') and not resource_id.startswith('product_') and not resource_id.startswith('order_'):
                key = resource_id
            else:
                # 没有真实资源ID，使用产品类型+产品名称作为去重键
                key = f"{product_type}_{product_name}"
            
            if key not in seen:
                seen.add(key)
                result.append(resource)
        return result
    
    def diagnose_idle_resources(self, resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """诊断闲置资源"""
        if not resources or len(resources) == 0:
            return {"code": 400, "message": "没有资源数据可诊断"}
        
        try:
            idle_eips = []
            low_load_ecss = []
            idle_evs = []
            idle_rds = []
            
            diagnosis_type = self._get_diagnosis_type(resources)
            has_monitor_data = diagnosis_type == 'actual_monitor'
            
            for resource in resources:
                product_type = resource.get('product_type', '')
                cost = float(resource.get('cost', 0.0))
                usage = float(resource.get('usage', 0.0))
                resource_id = resource.get('resource_id', '')
                
                if cost <= 0:
                    continue
                
                # EIP诊断
                if product_type == 'EIP':
                    if has_monitor_data:
                        if usage == 0:
                            resource['diagnosis_type'] = 'actual_monitor'
                            resource['issue'] = '30天无流量'
                            resource['diagnosis_note'] = '30天无流量'
                            idle_eips.append(resource)
                        elif usage < 100:
                            resource['diagnosis_type'] = 'actual_monitor'
                            resource['issue'] = f'30天流量仅{usage:.2f} MB'
                            resource['diagnosis_note'] = f'流量{usage:.2f} MB'
                            idle_eips.append(resource)
                    else:
                        resource['diagnosis_type'] = 'cost_infer'
                        resource['issue'] = '根据费用模式推断为闲置'
                        resource['diagnosis_note'] = 'cost_infer'
                        idle_eips.append(resource)
                
                # ECS诊断
                elif product_type == 'ECS':
                    cpu_usage = float(resource.get('cpu_usage') or resource.get('cpu利用率') or resource.get('cpu_utilization') or usage)
                    
                    if has_monitor_data:
                        if cpu_usage < 5:
                            resource['diagnosis_type'] = 'actual_monitor'
                            resource['issue'] = f'CPU使用率{cpu_usage:.1f}%'
                            resource['diagnosis_note'] = f'CPU使用率{cpu_usage:.1f}%'
                            low_load_ecss.append(resource)
                    else:
                        resource['diagnosis_type'] = 'cost_infer'
                        resource['issue'] = '根据费用模式推断为闲置'
                        resource['diagnosis_note'] = 'cost_infer'
                        low_load_ecss.append(resource)
                
                # EVS诊断
                elif product_type == 'EVS':
                    storage_usage = float(resource.get('storage_usage') or resource.get('存储利用率') or usage)
                    
                    if has_monitor_data:
                        if storage_usage < 10:
                            resource['diagnosis_type'] = 'actual_monitor'
                            resource['issue'] = f'存储利用率{storage_usage:.1f}%'
                            resource['diagnosis_note'] = f'存储利用率{storage_usage:.1f}%'
                            idle_evs.append(resource)
                    else:
                        resource['diagnosis_type'] = 'cost_infer'
                        resource['issue'] = '根据费用模式推断为闲置'
                        resource['diagnosis_note'] = 'cost_infer'
                        idle_evs.append(resource)
                
                # RDS诊断
                elif product_type == 'RDS':
                    conn_usage = float(resource.get('connection_usage') or resource.get('连接数利用率') or usage)
                    
                    if has_monitor_data:
                        if conn_usage < 10:
                            resource['diagnosis_type'] = 'actual_monitor'
                            resource['issue'] = f'连接数利用率{conn_usage:.1f}%'
                            resource['diagnosis_note'] = f'连接数利用率{conn_usage:.1f}%'
                            idle_rds.append(resource)
                    else:
                        resource['diagnosis_type'] = 'cost_infer'
                        resource['issue'] = '根据费用模式推断为闲置'
                        resource['diagnosis_note'] = 'cost_infer'
                        idle_rds.append(resource)
            
            # 对诊断结果进行去重
            idle_eips = self._deduplicate_resources(idle_eips)
            low_load_ecss = self._deduplicate_resources(low_load_ecss)
            idle_evs = self._deduplicate_resources(idle_evs)
            idle_rds = self._deduplicate_resources(idle_rds)
            
            return {
                "code": 0,
                "message": "诊断成功",
                "data": {
                    "idle_eips": idle_eips,
                    "low_load_ecss": low_load_ecss,
                    "idle_evs": idle_evs,
                    "idle_rds": idle_rds,
                    "summary": {
                        "idle_eip_count": len(idle_eips),
                        "low_load_ecs_count": len(low_load_ecss),
                        "idle_evs_count": len(idle_evs),
                        "idle_rds_count": len(idle_rds)
                    },
                    "diagnosis_type": diagnosis_type,
                    "has_monitor_data": has_monitor_data
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
            diagnosis_type = self._get_diagnosis_type(resources)
            has_monitor_data = diagnosis_type == 'actual_monitor'
            
            for resource in resources:
                product_type = resource.get('product_type', '')
                cost = float(resource.get('cost', 0.0))
                usage = float(resource.get('usage', 0.0))
                spec = resource.get('spec', '')
                billing_mode = resource.get('billing_mode', 'on_demand')
                resource_id = resource.get('resource_id', '')
                
                if cost <= 0:
                    continue
                
                if product_type == 'EIP':
                    if has_monitor_data:
                        should_recommend = usage == 0 or usage < 100
                    else:
                        should_recommend = True
                    
                    if should_recommend:
                        rec = self._generate_eip_release_recommendation(resource, not has_monitor_data)
                        if rec:
                            rec['diagnosis_type'] = diagnosis_type
                            recommendations.append(rec)
                            total_savings += float(rec['estimated_savings'])
                
                elif product_type == 'ECS':
                    cpu_usage = float(resource.get('cpu_usage') or resource.get('cpu利用率') or resource.get('cpu_utilization') or usage)
                    
                    if has_monitor_data:
                        should_recommend = cpu_usage < 5
                    else:
                        should_recommend = True
                    
                    if should_recommend:
                        rec = self._generate_ecs_downsize_recommendation(resource, not has_monitor_data)
                        if rec:
                            rec['diagnosis_type'] = diagnosis_type
                            recommendations.append(rec)
                            total_savings += float(rec['estimated_savings'])
                
                elif product_type == 'EVS':
                    storage_usage = float(resource.get('storage_usage') or resource.get('存储利用率') or usage)
                    
                    if has_monitor_data:
                        should_recommend = storage_usage < 10
                    else:
                        should_recommend = True
                    
                    if should_recommend:
                        rec = self._generate_evs_release_recommendation(resource, not has_monitor_data)
                        if rec:
                            rec['diagnosis_type'] = diagnosis_type
                            recommendations.append(rec)
                            total_savings += float(rec['estimated_savings'])
                
                elif product_type == 'RDS':
                    conn_usage = float(resource.get('connection_usage') or resource.get('连接数利用率') or usage)
                    
                    if has_monitor_data:
                        should_recommend = conn_usage < 10
                    else:
                        should_recommend = True
                    
                    if should_recommend:
                        rec = self._generate_rds_downsize_recommendation(resource, not has_monitor_data)
                        if rec:
                            rec['diagnosis_type'] = diagnosis_type
                            recommendations.append(rec)
                            total_savings += float(rec['estimated_savings'])
            
            return {
                "code": 0,
                "message": "生成建议成功",
                "data": {
                    "total_savings": round(total_savings, 2),
                    "recommendation_count": len(recommendations),
                    "recommendations": recommendations,
                    "diagnosis_type": diagnosis_type,
                    "has_monitor_data": has_monitor_data
                }
            }
        
        except Exception as e:
            return {"code": 400, "message": f"生成建议失败：{str(e)}"}
    
    def _generate_eip_release_recommendation(self, resource: Dict[str, Any], inferred: bool = False) -> Dict[str, Any]:
        """生成EIP释放建议"""
        prefix = "无监控用量数据，仅按月费推断闲置，" if inferred else ""
        issue_desc = f"弹性公网IP {resource['resource_id']} {prefix}30天无流量"
        return {
            "id": f"rec-eip-{resource['resource_id'][:8]}",
            "resource_id": resource['resource_id'],
            "product_type": 'EIP',
            "issue_description": issue_desc,
            "recommendation": f"释放该弹性公网IP {resource['resource_id']}",
            "estimated_savings": round(float(resource.get('cost', 0.0)), 2),
            "billing_mode": resource.get('billing_mode', 'on_demand'),
            "risk_level": "high",
            "risk_warning": "释放后该IP地址将不可用，如果有业务正在使用该IP，会导致业务中断。请确认该IP未被任何业务使用后再执行释放操作。",
            "category": "release"
        }
    
    def _generate_ecs_downsize_recommendation(self, resource: Dict[str, Any], inferred: bool = False) -> Dict[str, Any]:
        """生成ECS降配建议"""
        current_spec = resource.get('spec', '未知规格')
        current_cost = float(resource.get('cost', 0.0))
        recommended_spec = self._suggest_downsize_spec(current_spec)
        savings_ratio = 0.4 if recommended_spec else 0.3
        
        if inferred:
            issue_desc = f"云服务器 {resource['resource_id']} 无监控用量数据，仅按月费推断闲置"
        else:
            usage = float(resource.get('usage', 0.0))
            issue_desc = f"云服务器 {resource['resource_id']} CPU使用率{usage:.1f}%"
        
        return {
            "id": f"rec-ecs-{resource['resource_id'][:8]}",
            "resource_id": resource['resource_id'],
            "product_type": 'ECS',
            "issue_description": issue_desc,
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
    
    def _generate_evs_release_recommendation(self, resource: Dict[str, Any], inferred: bool = False) -> Dict[str, Any]:
        """生成EVS释放建议"""
        if inferred:
            issue_desc = f"云硬盘 {resource['resource_id']} 无监控用量数据，仅按月费推断闲置"
        else:
            usage = float(resource.get('usage', 0.0))
            issue_desc = f"云硬盘 {resource['resource_id']} 存储利用率{usage:.1f}%"
        
        return {
            "id": f"rec-evs-{resource['resource_id'][:8]}",
            "resource_id": resource['resource_id'],
            "product_type": 'EVS',
            "issue_description": issue_desc,
            "recommendation": f"释放该云硬盘 {resource['resource_id']} 或调整存储规格",
            "estimated_savings": round(float(resource.get('cost', 0.0)), 2),
            "billing_mode": resource.get('billing_mode', 'on_demand'),
            "risk_level": "high",
            "risk_warning": "释放云硬盘将永久删除其上的数据，且不可恢复。请确认该硬盘上没有重要数据，或已完成备份后再执行释放操作。",
            "category": "release"
        }
    
    def _generate_rds_downsize_recommendation(self, resource: Dict[str, Any], inferred: bool = False) -> Dict[str, Any]:
        """生成RDS降配建议"""
        current_spec = resource.get('spec', '未知规格')
        current_cost = float(resource.get('cost', 0.0))
        savings_ratio = 0.3
        
        if inferred:
            issue_desc = f"云数据库 {resource['resource_id']} 无监控用量数据，仅按月费推断闲置"
        else:
            usage = float(resource.get('usage', 0.0))
            issue_desc = f"云数据库 {resource['resource_id']} 连接数利用率{usage:.1f}%"
        
        return {
            "id": f"rec-rds-{resource['resource_id'][:8]}",
            "resource_id": resource['resource_id'],
            "product_type": 'RDS',
            "issue_description": issue_desc,
            "recommendation": f"将数据库规格 {current_spec} 降配为更小型规格",
            "estimated_savings": round(current_cost * savings_ratio, 2),
            "billing_mode": resource.get('billing_mode', 'on_demand'),
            "risk_level": "medium",
            "risk_warning": "降配操作可能需要重启实例，会导致业务短暂中断。请在业务低峰期执行，并确保应用可以正常重启。包年包月实例降配可能涉及费用计算调整。",
            "category": "downsize"
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
            
            # 按资源ID去重统计实例数量
            resource_ids = set()
            for r in resources:
                rid = r.get('resource_id', '')
                if rid:
                    resource_ids.add(rid)
            resource_count = len(resource_ids)
            
            # 生成推荐建议以获取 total_savings 和 recommendation_count
            rec_result = self.generate_recommendations(resources)
            recommendations = rec_result['data']['recommendations'] if rec_result['code'] == 0 else []
            
            # 确保 total_savings 等于所有推荐的 estimated_savings 之和
            total_savings = sum(float(rec.get('estimated_savings', 0.0)) for rec in recommendations)
            recommendation_count = len(recommendations)
            
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
            
            # 4. 生成 recommendations - 按产品类型合并去重
            final_recommendations = []
            merged_recs = {}  # key: product_type, value: merged recommendation
            diagnosis_type = rec_result['data'].get('diagnosis_type', 'cost_infer') if rec_result['code'] == 0 else 'cost_infer'
            
            if rec_result['code'] == 0:
                for rec in rec_result['data']['recommendations']:
                    product_type = rec.get('product_type', 'Other')
                    estimated_savings = float(rec.get('estimated_savings', 0.0))
                    rec_diagnosis_type = rec.get('diagnosis_type', diagnosis_type)
                    
                    if product_type in merged_recs:
                        # 合并金额
                        merged_recs[product_type]['estimated_savings'] += estimated_savings
                    else:
                        # 创建新记录
                        merged_recs[product_type] = {
                            "resource_id": rec.get('resource_id', f"{product_type.lower()}-merged"),
                            "type": product_type,
                            "description": rec.get('issue_description', ''),
                            "action": rec.get('recommendation', ''),
                            "estimated_savings": estimated_savings,
                            "diagnosis_type": rec_diagnosis_type
                        }
            
            # 转换为列表并四舍五入
            for pt, rec in merged_recs.items():
                final_recommendations.append({
                    "resource_id": rec['resource_id'],
                    "type": rec['type'],
                    "description": rec['description'],
                    "action": rec['action'],
                    "estimated_savings": round(rec['estimated_savings'], 2),
                    "diagnosis_type": rec['diagnosis_type']
                })
            
            # 更新 overview 中的 total_savings 和 recommendation_count（使用合并后的列表）
            total_savings = sum(rec['estimated_savings'] for rec in final_recommendations)
            overview['total_savings'] = round(total_savings, 2)
            overview['recommendation_count'] = len(final_recommendations)
            
            # 5. 生成 idle_resources - 直接从合并后的 recommendations 生成，确保资源ID一致
            idle_resources = []
            type_configs = {
                'EIP': {'suggestion': '释放弹性公网IP'},
                'ECS': {'suggestion': '降配或释放云服务器'},
                'EVS': {'suggestion': '释放云硬盘或调整存储规格'},
                'RDS': {'suggestion': '降配或释放数据库'}
            }
            
            for rec in final_recommendations:
                product_type = rec.get('type', 'Other')
                config = type_configs.get(product_type, {'suggestion': '优化资源配置'})
                rec_diagnosis_type = rec.get('diagnosis_type', 'cost_infer')
                
                # 根据诊断类型设置问题描述
                issue_desc = rec.get('description', '')
                if not issue_desc:
                    if rec_diagnosis_type == 'actual_monitor':
                        issue_desc = '根据监控数据检测到闲置'
                    else:
                        issue_desc = '根据费用模式推断为闲置'
                
                idle_resources.append({
                    "resource_id": rec['resource_id'],
                    "issue": issue_desc,
                    "suggestion": config['suggestion'],
                    "saving": rec['estimated_savings'],
                    "diagnosis_type": rec_diagnosis_type
                })
            
            return {
                "code": 0,
                "message": "分析成功",
                "data": {
                    "overview": overview,
                    "trend_data": trend_data,
                    "category_data": category_data,
                    "idle_resources": idle_resources,
                    "recommendations": final_recommendations
                }
            }
        
        except Exception as e:
            return {"code": 400, "message": f"完整分析失败：{str(e)}"}