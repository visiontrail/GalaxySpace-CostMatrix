"""
Excel 数据处理服务
负责读取、分析、处理 Excel 文件
"""
import pandas as pd
import numpy as np
from openpyxl import load_workbook
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
import re
import os


class ExcelProcessor:
    """Excel 处理器"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.sheets_data: Dict[str, pd.DataFrame] = {}
        self.workbook = None
        
    def load_all_sheets(self) -> Dict[str, pd.DataFrame]:
        """
        加载所有 Sheet 数据
        """
        try:
            # 使用 pandas 读取所有 sheets
            all_sheets = pd.read_excel(self.file_path, sheet_name=None)
            self.sheets_data = all_sheets
            
            # 同时用 openpyxl 加载，以便后续回写时保留格式
            self.workbook = load_workbook(self.file_path)
            
            return self.sheets_data
        except Exception as e:
            raise Exception(f"读取 Excel 文件失败: {str(e)}")
    
    def get_sheet(self, sheet_name: str) -> Optional[pd.DataFrame]:
        """获取指定 Sheet"""
        return self.sheets_data.get(sheet_name)
    
    def clean_attendance_data(self) -> pd.DataFrame:
        """
        清洗考勤数据（状态明细）
        """
        df = self.get_sheet("状态明细")
        if df is None:
            return pd.DataFrame()
        
        # 标准化列名
        df = df.copy()
        
        # 处理日期格式
        if '日期' in df.columns:
            df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
        
        # 处理工时数据
        if '工时' in df.columns:
            df['工时'] = pd.to_numeric(df['工时'], errors='coerce')
        
        # 删除空行
        df = df.dropna(subset=['姓名'], how='all')
        
        return df
    
    def clean_travel_data(self, sheet_name: str) -> pd.DataFrame:
        """
        清洗差旅数据（机票/酒店/火车票）
        """
        df = self.get_sheet(sheet_name)
        if df is None:
            return pd.DataFrame()
        
        df = df.copy()
        
        # 处理金额字段
        amount_col = '授信金额' if '授信金额' in df.columns else '金额'
        if amount_col in df.columns:
            df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce')
            df = df[df[amount_col] > 0]  # 过滤无效金额
        
        # 处理日期字段
        date_cols = ['出发日期', '入住日期', '订单日期']
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # 统一差旅人员姓名字段
        if '差旅人员姓名' in df.columns:
            df['姓名'] = df['差旅人员姓名']
        elif '预订人姓名' in df.columns:
            df['姓名'] = df['预订人姓名']
        
        return df
    
    def extract_project_code(self, project_str: str) -> Tuple[str, str]:
        """
        从项目字段提取项目代码和名称
        格式: "05010013 市场-整星..."
        """
        if pd.isna(project_str) or not isinstance(project_str, str):
            return "", ""
        
        # 尝试提取项目代码（通常是开头的数字）
        match = re.match(r'(\d+)\s+(.*)', project_str.strip())
        if match:
            return match.group(1), match.group(2)
        
        return "", project_str
    
    def aggregate_project_costs(self) -> List[Dict[str, Any]]:
        """
        项目成本归集
        """
        results = []
        
        # 处理所有差旅相关的 Sheet
        travel_sheets = ['机票', '酒店', '火车票']
        
        all_records = []
        
        for sheet_name in travel_sheets:
            df = self.clean_travel_data(sheet_name)
            if df.empty:
                continue
            
            # 检查是否有项目字段
            if '项目' not in df.columns:
                continue
            
            amount_col = '授信金额' if '授信金额' in df.columns else '金额'
            
            for _, row in df.iterrows():
                project_code, project_name = self.extract_project_code(row.get('项目', ''))
                if project_code:
                    all_records.append({
                        'project_code': project_code,
                        'project_name': project_name,
                        'amount': row.get(amount_col, 0),
                        'type': sheet_name,
                        'person': row.get('姓名', ''),
                        'date': row.get('出发日期', '')
                    })
        
        # 按项目代码聚合
        if all_records:
            df_projects = pd.DataFrame(all_records)
            grouped = df_projects.groupby(['project_code', 'project_name']).agg({
                'amount': 'sum',
                'person': 'count'
            }).reset_index()
            
            for _, row in grouped.iterrows():
                project_details = df_projects[
                    df_projects['project_code'] == row['project_code']
                ].to_dict('records')
                
                results.append({
                    'project_code': row['project_code'],
                    'project_name': row['project_name'],
                    'total_cost': float(row['amount']),
                    'record_count': int(row['person']),
                    'details': project_details[:10]  # 限制返回详情数量
                })
        
        return sorted(results, key=lambda x: x['total_cost'], reverse=True)
    
    def cross_check_attendance_travel(self) -> List[Dict[str, Any]]:
        """
        交叉验证：考勤数据 vs 差旅数据
        """
        anomalies = []
        
        # 获取考勤数据
        attendance_df = self.clean_attendance_data()
        if attendance_df.empty:
            return anomalies
        
        # 获取所有差旅数据
        travel_sheets = ['机票', '酒店', '火车票']
        all_travel = []
        
        for sheet_name in travel_sheets:
            df = self.clean_travel_data(sheet_name)
            if not df.empty:
                df['差旅类型'] = sheet_name
                all_travel.append(df)
        
        if not all_travel:
            return anomalies
        
        travel_df = pd.concat(all_travel, ignore_index=True)
        
        # 按姓名和日期分组
        for name in attendance_df['姓名'].unique():
            if pd.isna(name):
                continue
            
            person_attendance = attendance_df[attendance_df['姓名'] == name]
            person_travel = travel_df[travel_df['姓名'] == name]
            
            if person_travel.empty:
                continue
            
            for _, att_row in person_attendance.iterrows():
                att_date = att_row.get('日期')
                att_status = att_row.get('当日状态判断', '')
                
                if pd.isna(att_date):
                    continue
                
                # 查找当日的差旅记录
                day_travel = person_travel[
                    person_travel['出发日期'].dt.date == att_date.date()
                ] if '出发日期' in person_travel.columns else pd.DataFrame()
                
                # 获取部门信息
                department = att_row.get('一级部门', '未知部门')
                if pd.isna(department):
                    department = '未知部门'
                
                # 异常 A: 考勤显示上班，但有差旅消费
                if '上班' in att_status and not day_travel.empty:
                    travel_list = day_travel['差旅类型'].tolist()
                    anomalies.append({
                        'name': name,
                        'date': att_date.strftime('%Y-%m-%d'),
                        'department': department,
                        'anomaly_type': 'A',
                        'attendance_status': att_status,
                        'travel_records': travel_list,
                        'description': f'{name} 在 {att_date.strftime("%Y-%m-%d")} 考勤显示上班，但有 {",".join(travel_list)} 消费记录'
                    })
                
                # 异常 B: 考勤显示出差，但无差旅消费
                if '出差' in att_status and day_travel.empty:
                    anomalies.append({
                        'name': name,
                        'date': att_date.strftime('%Y-%m-%d'),
                        'department': department,
                        'anomaly_type': 'B',
                        'attendance_status': att_status,
                        'travel_records': [],
                        'description': f'{name} 在 {att_date.strftime("%Y-%m-%d")} 考勤显示出差，但无差旅消费记录'
                    })
        
        return anomalies
    
    def analyze_booking_behavior(self) -> Dict[str, Any]:
        """
        预订行为分析（机票）
        """
        df = self.clean_travel_data('机票')
        if df.empty or '提前预定天数' not in df.columns:
            return {}
        
        # 过滤有效数据
        valid_df = df[df['提前预定天数'].notna() & (df['提前预定天数'] >= 0)]
        
        if valid_df.empty:
            return {}
        
        amount_col = '授信金额' if '授信金额' in valid_df.columns else '金额'
        
        # 计算统计指标
        avg_advance = float(valid_df['提前预定天数'].mean())
        
        # 相关性分析
        correlation = float(valid_df[['提前预定天数', amount_col]].corr().iloc[0, 1])
        
        # 提前天数分布
        advance_distribution = valid_df['提前预定天数'].value_counts().to_dict()
        advance_distribution = {str(int(k)): int(v) for k, v in advance_distribution.items()}
        
        # 按提前天数分组的平均成本
        cost_by_advance = valid_df.groupby('提前预定天数')[amount_col].mean().reset_index()
        cost_by_advance_list = [
            {'advance_days': int(row['提前预定天数']), 'avg_cost': float(row[amount_col])}
            for _, row in cost_by_advance.iterrows()
        ]
        
        return {
            'avg_advance_days': round(avg_advance, 2),
            'correlation_advance_cost': round(correlation, 3),
            'advance_day_distribution': advance_distribution,
            'cost_by_advance_days': sorted(cost_by_advance_list, key=lambda x: x['advance_days'])
        }
    
    def calculate_department_costs(self) -> List[Dict[str, Any]]:
        """
        部门成本汇总（包含平均工时和人数统计）
        """
        results = []
        
        # 获取考勤数据以计算工时和人数
        attendance_df = self.clean_attendance_data()
        dept_attendance_stats = {}
        
        if not attendance_df.empty and '一级部门' in attendance_df.columns:
            # 计算每个部门的平均工时和人数
            for dept in attendance_df['一级部门'].unique():
                if pd.isna(dept):
                    continue
                dept_data = attendance_df[attendance_df['一级部门'] == dept]
                avg_hours = 0
                if '工时' in dept_data.columns:
                    avg_hours = dept_data['工时'].mean()
                    if pd.isna(avg_hours):
                        avg_hours = 0
                person_count = dept_data['姓名'].nunique() if '姓名' in dept_data.columns else 0
                dept_attendance_stats[dept] = {
                    'avg_hours': float(avg_hours),
                    'person_count': int(person_count)
                }
        
        # 尝试从差旅汇总 Sheet 获取
        summary_df = self.get_sheet('差旅汇总')
        if summary_df is not None and not summary_df.empty:
            if '一级部门' in summary_df.columns and '成本' in summary_df.columns:
                grouped = summary_df.groupby('一级部门').agg({
                    '成本': 'sum'
                }).reset_index()
                
                for _, row in grouped.iterrows():
                    dept = row['一级部门']
                    stats = dept_attendance_stats.get(dept, {'avg_hours': 0, 'person_count': 0})
                    results.append({
                        'department': dept,
                        'total_cost': float(row['成本']),
                        'flight_cost': 0,
                        'hotel_cost': 0,
                        'train_cost': 0,
                        'avg_hours': stats['avg_hours'],
                        'person_count': stats['person_count']
                    })
                
                return results
        
        # 如果没有汇总表，从明细计算
        travel_data = {
            '机票': 'flight_cost',
            '酒店': 'hotel_cost',
            '火车票': 'train_cost'
        }
        
        dept_costs = {}
        
        for sheet_name, cost_key in travel_data.items():
            df = self.clean_travel_data(sheet_name)
            if df.empty:
                continue
            
            # 尝试关联部门信息
            if not attendance_df.empty and '一级部门' in attendance_df.columns:
                # Merge with attendance to get department
                name_dept = attendance_df[['姓名', '一级部门']].drop_duplicates()
                df = df.merge(name_dept, on='姓名', how='left')
            
            if '一级部门' not in df.columns:
                continue
            
            amount_col = '授信金额' if '授信金额' in df.columns else '金额'
            
            for _, row in df.iterrows():
                dept = row.get('一级部门', '未知部门')
                if pd.isna(dept):
                    dept = '未知部门'
                
                if dept not in dept_costs:
                    stats = dept_attendance_stats.get(dept, {'avg_hours': 0, 'person_count': 0})
                    dept_costs[dept] = {
                        'department': dept,
                        'total_cost': 0,
                        'flight_cost': 0,
                        'hotel_cost': 0,
                        'train_cost': 0,
                        'avg_hours': stats['avg_hours'],
                        'person_count': stats['person_count']
                    }
                
                amount = row.get(amount_col, 0) or 0
                dept_costs[dept][cost_key] += amount
                dept_costs[dept]['total_cost'] += amount
        
        results = list(dept_costs.values())
        return sorted(results, key=lambda x: x['total_cost'], reverse=True)
    
    def get_attendance_summary(self) -> Dict[str, Any]:
        """
        考勤数据汇总
        """
        df = self.clean_attendance_data()
        if df.empty:
            return {}
        
        total_records = len(df)
        total_persons = df['姓名'].nunique() if '姓名' in df.columns else 0
        
        status_distribution = {}
        if '当日状态判断' in df.columns:
            status_distribution = df['当日状态判断'].value_counts().to_dict()
        
        avg_work_hours = 0
        if '工时' in df.columns:
            avg_work_hours = float(df['工时'].mean())
        
        return {
            'total_records': total_records,
            'total_persons': total_persons,
            'status_distribution': status_distribution,
            'avg_work_hours': round(avg_work_hours, 2)
        }
    
    def write_analysis_results(self, results: Dict[str, Any], output_path: Optional[str] = None) -> str:
        """
        将分析结果回写到 Excel（新增 Sheet）
        使用 openpyxl 保留原格式
        """
        if output_path is None:
            base_name = os.path.splitext(self.file_path)[0]
            output_path = f"{base_name}_analyzed.xlsx"
        
        if self.workbook is None:
            self.workbook = load_workbook(self.file_path)
        
        # 创建分析结果 Sheet
        sheet_name = "分析结果"
        if sheet_name in self.workbook.sheetnames:
            del self.workbook[sheet_name]
        
        ws = self.workbook.create_sheet(sheet_name)
        
        # 写入标题
        ws.append(["CorpPilot 数据分析报告"])
        ws.append([f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
        ws.append([])
        
        # 写入项目成本
        if 'project_costs' in results and results['project_costs']:
            ws.append(["项目成本归集"])
            ws.append(["项目代码", "项目名称", "总成本", "记录数"])
            for item in results['project_costs']:
                ws.append([
                    item['project_code'],
                    item['project_name'],
                    item['total_cost'],
                    item['record_count']
                ])
            ws.append([])
        
        # 写入部门成本
        if 'department_costs' in results and results['department_costs']:
            ws.append(["部门成本汇总"])
            ws.append(["部门", "总成本", "机票", "酒店", "火车票"])
            for item in results['department_costs']:
                ws.append([
                    item['department'],
                    item['total_cost'],
                    item['flight_cost'],
                    item['hotel_cost'],
                    item['train_cost']
                ])
            ws.append([])
        
        # 写入异常记录
        if 'anomalies' in results and results['anomalies']:
            ws.append(["交叉验证异常"])
            ws.append(["姓名", "日期", "异常类型", "考勤状态", "说明"])
            for item in results['anomalies']:
                ws.append([
                    item['name'],
                    item['date'],
                    item['anomaly_type'],
                    item['attendance_status'],
                    item['description']
                ])
        
        # 保存文件
        self.workbook.save(output_path)
        
        return output_path


