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
import time
from collections import Counter

from app.utils.logger import get_logger


class ExcelProcessor:
    """Excel 处理器"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.sheets_data: Dict[str, pd.DataFrame] = {}
        self.workbook = None
        self.logger = get_logger("excel_processor")
        self._attendance_cache: Optional[pd.DataFrame] = None
        self._travel_cache: Dict[str, pd.DataFrame] = {}
        self._combined_travel_cache: Optional[pd.DataFrame] = None
        
    def load_all_sheets(self, load_workbook_obj: bool = False) -> Dict[str, pd.DataFrame]:
        """
        加载所有 Sheet 数据

        Args:
            load_workbook_obj: 是否同时加载 openpyxl Workbook 对象（仅在需要回写时启用）
        """
        try:
            start = time.perf_counter()
            self.logger.info(f"开始读取 Excel 文件: {self.file_path}")
            all_sheets = pd.read_excel(self.file_path, sheet_name=None)
            elapsed = time.perf_counter() - start

            self.sheets_data = all_sheets
            self._attendance_cache = None
            self._travel_cache = {}
            self._combined_travel_cache = None

            sheet_names = ", ".join(all_sheets.keys())
            self.logger.info(f"Excel 读取完成（{sheet_names}），耗时 {elapsed:.2f}s")
            
            # 部分分析场景不需要 Workbook，仅在回写等场景按需加载
            if load_workbook_obj:
                wb_start = time.perf_counter()
                self.workbook = load_workbook(self.file_path, keep_links=False)
                self.logger.info(f"openpyxl 工作簿加载完成，耗时 {time.perf_counter() - wb_start:.2f}s")
            else:
                self.workbook = None
            
            return self.sheets_data
        except Exception as e:
            raise Exception(f"读取 Excel 文件失败: {str(e)}")

    def get_sheet_names(self) -> List[str]:
        """
        仅获取 Sheet 名称，避免读取全部数据导致耗时
        """
        try:
            workbook = load_workbook(
                self.file_path,
                read_only=True,
                data_only=True,
                keep_links=False
            )
            sheet_names = workbook.sheetnames
            workbook.close()
            return sheet_names
        except Exception as e:
            raise Exception(f"读取 Excel Sheet 名称失败: {str(e)}")
    
    def get_sheet(self, sheet_name: str) -> Optional[pd.DataFrame]:
        """获取指定 Sheet"""
        return self.sheets_data.get(sheet_name)
    
    def clean_attendance_data(self, use_cache: bool = True) -> pd.DataFrame:
        """
        清洗考勤数据（状态明细）
        """
        if use_cache and self._attendance_cache is not None:
            return self._attendance_cache

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

        if use_cache:
            self._attendance_cache = df
        
        return df
    
    def clean_travel_data(self, sheet_name: str, use_cache: bool = True) -> pd.DataFrame:
        """
        清洗差旅数据（机票/酒店/火车票）
        """
        if use_cache and sheet_name in self._travel_cache:
            return self._travel_cache[sheet_name]

        df = self.get_sheet(sheet_name)
        if df is None:
            return pd.DataFrame()
        
        df = df.copy()
        
        # 处理金额字段
        amount_col = '授信金额' if '授信金额' in df.columns else '金额'
        if amount_col in df.columns:
            df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce')
            # 将 NaN 填充为 0，但保留所有记录
            df[amount_col] = df[amount_col].fillna(0)
        
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

        if use_cache:
            self._travel_cache[sheet_name] = df
        
        return df

    def _get_combined_travel_df(self) -> pd.DataFrame:
        """
        获取带消费日期和差旅类型的汇总差旅数据（使用缓存避免重复计算）
        """
        if self._combined_travel_cache is not None:
            return self._combined_travel_cache

        frames: List[pd.DataFrame] = []
        date_columns = {
            '机票': '出发日期',
            '酒店': '入住日期',
            '火车票': '出发日期'
        }

        for sheet_name, date_col in date_columns.items():
            df = self.clean_travel_data(sheet_name)
            if df.empty or date_col not in df.columns:
                continue

            # 仅保留需要的字段，避免复制无关数据
            temp = df[['姓名', date_col]].copy()
            temp = temp[temp[date_col].notna()]
            if temp.empty:
                continue

            temp['消费日期'] = temp[date_col].dt.date
            temp['差旅类型'] = sheet_name
            frames.append(temp[['姓名', '消费日期', '差旅类型']])

        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
            columns=['姓名', '消费日期', '差旅类型']
        )
        self._combined_travel_cache = combined
        return combined
    
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
    
    def aggregate_project_costs(self, top_n: int = 20) -> List[Dict[str, Any]]:
        """
        项目成本归集
        
        Args:
            top_n: 返回前N个项目，其余汇总到"其他"（默认20）
        """
        self.logger.info("=" * 80)
        self.logger.info("开始执行项目成本归集 - 详细模式（Backend服务）")
        self.logger.info("=" * 80)
        
        results = []
        
        # 处理所有差旅相关的 Sheet
        travel_sheets = ['机票', '酒店', '火车票']
        
        all_records = []
        sheet_stats = {}
        
        for sheet_name in travel_sheets:
            self.logger.info(f"\n📋 处理差旅表: {sheet_name}")
            
            # 获取原始数据（未清洗）以获取真实行数
            df_raw = self.get_sheet(sheet_name)
            original_count = 0 if df_raw is None else len(df_raw)
            
            df = self.clean_travel_data(sheet_name)
            if df.empty:
                self.logger.warning(f"   ⚠️  {sheet_name} 数据为空")
                continue
            
            # 检查是否有项目字段
            if '项目' not in df.columns:
                self.logger.warning(f"   ⚠️  {sheet_name} 缺少'项目'列")
                continue
            
            amount_col = '授信金额' if '授信金额' in df.columns else '金额'
            self.logger.info(f"   - 原始记录数: {original_count}")
            self.logger.info(f"   - 清洗后记录数: {len(df)}")
            self.logger.info(f"   - 金额列: {amount_col}")
            
            # 统计信息
            record_count = 0
            empty_project_count = 0
            sheet_total_amount = 0
            
            for idx, row in df.iterrows():
                project_str = row.get('项目', '')
                project_code, project_name = self.extract_project_code(project_str)
                amount = row.get(amount_col, 0)
                
                # 空项目作为单独的项目类别处理
                if not project_code:
                    project_code = '空项目'
                    project_name = '未分配项目'
                    empty_project_count += 1
                
                all_records.append({
                    'project_code': project_code,
                    'project_name': project_name,
                    'amount': amount,
                    'type': sheet_name,
                    'person': row.get('姓名', ''),
                    'date': row.get('出发日期', '')
                })
                record_count += 1
                sheet_total_amount += amount
                
                # 输出前3条记录的详细信息
                if record_count <= 3:
                    person = row.get('姓名', '未知')
                    date_val = row.get('出发日期', '')
                    # 安全的日期格式化
                    if pd.notna(date_val) and hasattr(date_val, 'strftime'):
                        date_str = date_val.strftime('%Y-%m-%d')
                    else:
                        date_str = str(date_val) if pd.notna(date_val) else '未知'
                    self.logger.debug(f"      记录{record_count}: {project_code} | {person} | ¥{amount:,.2f} | {date_str}")
            
            sheet_stats[sheet_name] = {
                'original_total': original_count,
                'cleaned_total': len(df),
                'record_count': record_count,
                'empty_project_count': empty_project_count,
                'amount': sheet_total_amount
            }
            
            # 统计金额分布 - 基于所有清洗后记录
            zero_amount_count = (df[amount_col] == 0).sum() if amount_col in df.columns else 0
            negative_amount_count = (df[amount_col] < 0).sum() if amount_col in df.columns else 0
            positive_amount_count = (df[amount_col] > 0).sum() if amount_col in df.columns else 0
            filtered_count = original_count - len(df)
            
            # 计算正数/负数金额总和（基于所有清洗后记录）
            negative_amount_sum = df[df[amount_col] < 0][amount_col].sum() if amount_col in df.columns and negative_amount_count > 0 else 0
            positive_amount_sum = df[df[amount_col] > 0][amount_col].sum() if amount_col in df.columns and positive_amount_count > 0 else 0
            # 所有记录的净总金额（用于日志显示，确保与正数+负数一致）
            sheet_all_amount = df[amount_col].sum() if amount_col in df.columns else 0
            
            self.logger.info(f"   ✅ 处理完成:")
            self.logger.info(f"      - 总记录数: {record_count}")
            if empty_project_count > 0:
                self.logger.info(f"      - 空项目记录: {empty_project_count} (已归入\"空项目\"类别)")
            if filtered_count > 0:
                self.logger.warning(f"      ⚠️  数据清洗时过滤记录: {filtered_count}条")
            
            # 金额分布统计（基于所有清洗后记录）
            self.logger.info(f"      - 金额分布（全部记录）:")
            if positive_amount_count > 0:
                self.logger.info(f"         • 正数金额: {positive_amount_count}条, 合计 ¥{positive_amount_sum:,.2f}")
            if negative_amount_count > 0:
                self.logger.warning(f"         • 负数金额: {negative_amount_count}条, 合计 ¥{negative_amount_sum:,.2f} (退款/调整)")
            if zero_amount_count > 0:
                self.logger.info(f"         • 零值金额: {zero_amount_count}条")
            self.logger.info(f"         • 净总金额: ¥{sheet_all_amount:,.2f}")
        
        # 输出汇总统计
        self.logger.info(f"\n📊 差旅数据汇总:")
        original_total_records = sum(stats['original_total'] for stats in sheet_stats.values())
        cleaned_total_records = sum(stats['cleaned_total'] for stats in sheet_stats.values())
        total_records = sum(stats['record_count'] for stats in sheet_stats.values())
        empty_project_records = sum(stats['empty_project_count'] for stats in sheet_stats.values())
        total_amount = sum(stats['amount'] for stats in sheet_stats.values())
        
        self.logger.info(f"   - 原始总记录数: {original_total_records}")
        self.logger.info(f"   - 清洗后总记录数: {cleaned_total_records}")
        self.logger.info(f"   - 处理记录数: {total_records}")
        if empty_project_records > 0:
            self.logger.info(f"   - 空项目记录数: {empty_project_records} (已归入\"空项目\"类别)")
        if original_total_records > cleaned_total_records:
            filtered = original_total_records - cleaned_total_records
            self.logger.warning(f"   ⚠️  数据清洗过滤了 {filtered} 条记录（可能是无效数据或删除行）")
        self.logger.info(f"   - 净总金额: ¥{total_amount:,.2f}")
        self.logger.info(f"   - 💡 说明: 负数金额（退款/调整）已包含在净总金额计算中")
        
        # 按项目代码聚合
        if all_records:
            self.logger.info(f"\n🔄 开始聚合项目数据...")
            df_projects = pd.DataFrame(all_records)
            self.logger.debug(f"   - 待聚合记录数: {len(df_projects)}")
            
            grouped = df_projects.groupby(['project_code', 'project_name']).agg({
                'amount': 'sum',
                'person': 'count'
            }).reset_index()
            
            # 按成本降序排序
            grouped = grouped.sort_values('amount', ascending=False).reset_index(drop=True)
            
            total_count = len(grouped)
            self.logger.info(f"   ✅ 聚合完成，共 {total_count} 个唯一项目")
            
            # 验证金额总和
            grouped_total = grouped['amount'].sum()
            if abs(grouped_total - total_amount) > 0.01:
                self.logger.error(f"   ⚠️  金额验证失败！")
                self.logger.error(f"      原始总计: ¥{total_amount:,.2f}")
                self.logger.error(f"      聚合总计: ¥{grouped_total:,.2f}")
            
            self.logger.info(f"\n🏆 项目成本排名（Top {min(20, total_count)}）:")

            # 日志始终只显示前20个项目的详细信息（保持日志可读性）
            log_top_n = min(20, total_count)

            # 如果项目数量超过 top_n，将超出部分汇总到"其他"
            if total_count > top_n:
                self.logger.info(f"   - 展示前{top_n}个项目")
                self.logger.info(f"   - 其余{total_count - top_n}个项目汇总到\"其他\"")

                # 前 top_n 个项目（添加到结果）
                for idx, row in grouped.head(top_n).iterrows():
                    project_details = df_projects[
                        df_projects['project_code'] == row['project_code']
                    ].to_dict('records')

                    # 计算分类成本
                    project_df = df_projects[df_projects['project_code'] == row['project_code']]
                    flight_cost = project_df[project_df['type'] == '机票']['amount'].sum()
                    hotel_cost = project_df[project_df['type'] == '酒店']['amount'].sum()
                    train_cost = project_df[project_df['type'] == '火车票']['amount'].sum()

                    # 日志只输出前20个
                    if idx < log_top_n:
                        self.logger.info(f"\n   #{idx+1}. {row['project_code']} - {row['project_name']}")
                        self.logger.info(f"      总成本: ¥{row['amount']:,.2f} | 订单数: {int(row['person'])}")
                        self.logger.info(f"      ├─ 机票: ¥{flight_cost:,.2f}")
                        self.logger.info(f"      ├─ 酒店: ¥{hotel_cost:,.2f}")
                        self.logger.info(f"      └─ 火车票: ¥{train_cost:,.2f}")

                    results.append({
                        'project_code': row['project_code'],
                        'project_name': row['project_name'],
                        'total_cost': float(row['amount']),
                        'record_count': int(row['person']),
                        'details': project_details[:10]
                    })
                
                # 汇总"其他"项目
                others_df = grouped.iloc[top_n:]
                others_total_cost = float(others_df['amount'].sum())
                others_record_count = int(others_df['person'].sum())
                
                self.logger.info(f"\n   #{top_n+1}. 其他")
                self.logger.info(f"      汇总项目数: {total_count - top_n}")
                self.logger.info(f"      总成本: ¥{others_total_cost:,.2f} | 订单数: {others_record_count}")
                
                results.append({
                    'project_code': '其他',
                    'project_name': f'其他项目（{total_count - top_n}个）',
                    'total_cost': others_total_cost,
                    'record_count': others_record_count,
                    'details': []
                })
            else:
                # 如果不超过 top_n，返回全部
                self.logger.info(f"   - 项目总数不超过{top_n}，返回全部")
                
                for idx, row in grouped.iterrows():
                    project_details = df_projects[
                        df_projects['project_code'] == row['project_code']
                    ].to_dict('records')
                    
                    # 计算分类成本
                    project_df = df_projects[df_projects['project_code'] == row['project_code']]
                    flight_cost = project_df[project_df['type'] == '机票']['amount'].sum()
                    hotel_cost = project_df[project_df['type'] == '酒店']['amount'].sum()
                    train_cost = project_df[project_df['type'] == '火车票']['amount'].sum()
                    
                    self.logger.info(f"\n   #{idx+1}. {row['project_code']} - {row['project_name']}")
                    self.logger.info(f"      总成本: ¥{row['amount']:,.2f} | 订单数: {int(row['person'])}")
                    self.logger.info(f"      ├─ 机票: ¥{flight_cost:,.2f}")
                    self.logger.info(f"      ├─ 酒店: ¥{hotel_cost:,.2f}")
                    self.logger.info(f"      └─ 火车票: ¥{train_cost:,.2f}")
                    
                    results.append({
                        'project_code': row['project_code'],
                        'project_name': row['project_name'],
                        'total_cost': float(row['amount']),
                        'record_count': int(row['person']),
                        'details': project_details[:10]
                    })
            
            # 最终汇总
            self.logger.info(f"\n" + "=" * 80)
            self.logger.info(f"✅ 项目成本归集完成")
            self.logger.info(f"=" * 80)
            self.logger.info(f"📊 最终统计:")
            self.logger.info(f"   - 返回项目数: {len(results)}")
            self.logger.info(f"   - 总成本: ¥{sum(r['total_cost'] for r in results):,.2f}")
            self.logger.info(f"   - 总订单数: {sum(r['record_count'] for r in results)}")
            self.logger.info("=" * 80 + "\n")
        else:
            self.logger.warning("⚠️  没有找到任何项目记录")

        return results, total_count
    
    def cross_check_attendance_travel(self) -> List[Dict[str, Any]]:
        """
        交叉验证：考勤数据 vs 差旅数据
        """
        anomalies = []
        
        # 获取考勤数据
        attendance_df = self.clean_attendance_data()
        if attendance_df.empty or '当日状态判断' not in attendance_df.columns:
            return anomalies
        if '日期' not in attendance_df.columns:
            return anomalies

        # 仅保留有日期的数据，提前计算日期字段，避免后续重复转换
        attendance_df = attendance_df.dropna(subset=['日期']).copy()
        if attendance_df.empty:
            return anomalies

        attendance_df['日期'] = attendance_df['日期'].dt.date
        attendance_df['当日状态判断'] = attendance_df['当日状态判断'].astype(str)
        if '一级部门' in attendance_df.columns:
            attendance_df['一级部门'] = attendance_df['一级部门'].fillna('未知部门')
        else:
            attendance_df['一级部门'] = '未知部门'

        # 只关注考勤显示上班的记录，缩小计算范围
        work_attendance = attendance_df[
            attendance_df['当日状态判断'].str.contains('上班', na=False)
        ]
        if work_attendance.empty:
            return anomalies

        # 聚合所有差旅数据（姓名 + 消费日期 + 差旅类型），并缓存
        travel_df = self._get_combined_travel_df()
        if travel_df.empty:
            return anomalies

        travel_grouped = (
            travel_df.groupby(['姓名', '消费日期'])['差旅类型']
            .apply(list)
            .reset_index()
            .rename(columns={'消费日期': '日期'})
        )

        # 基于姓名+日期一次性关联，避免双重 for 循环
        merged = work_attendance.merge(
            travel_grouped,
            on=['姓名', '日期'],
            how='inner'
        )

        for _, row in merged.iterrows():
            date_val = row.get('日期')
            date_str = date_val.strftime('%Y-%m-%d') if hasattr(date_val, 'strftime') else str(date_val)
            travel_list = row.get('差旅类型', []) or []
            name = row.get('姓名', '')
            anomalies.append({
                'name': name,
                'date': date_str,
                'department': row.get('一级部门', '未知部门'),
                'anomaly_type': 'A',
                'attendance_status': row.get('当日状态判断', ''),
                'travel_records': travel_list,
                'description': f'{name} 在 {date_str} 考勤显示上班，但有 {",".join(travel_list)} 消费记录'
            })

        self.logger.info(f"交叉验证完成，发现 {len(anomalies)} 条异常记录")
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

    def count_over_standard_orders(self) -> Dict[str, Any]:
        """
        统计各差旅类型的超标订单数量

        业务规则：
        - 机票：超标类型包含“超折扣”或“超时间”
        - 酒店：按“是否超标”为“是”
        - 火车票：按“是否超标”为“是”
        """
        flight_df = self.clean_travel_data('机票')
        hotel_df = self.clean_travel_data('酒店')
        train_df = self.clean_travel_data('火车票')

        def _count_yes(df: pd.DataFrame, column: str) -> int:
            if df.empty or column not in df.columns:
                return 0
            return int(df[df[column].astype(str).str.contains('是', na=False)].shape[0])

        def _extract_over_types(value: str) -> List[str]:
            """
            提取机票的超标类型标签
            - 支持以空格、逗号、分号、斜杠等分隔的多标签格式
            - 若字符串中包含已知关键字（超折扣/超时间）但未分隔，也能捕获
            """
            if not value or pd.isna(value):
                return []

            raw = str(value)
            tokens = []

            # 常见分隔符拆分
            for part in re.split(r'[;,，、/\\s]+', raw):
                cleaned = part.strip()
                if cleaned and '超' in cleaned:
                    tokens.append(cleaned)

            # 兜底：处理未显式分隔但包含关键字的场景
            for keyword in ['超折扣', '超时间']:
                if keyword in raw and keyword not in tokens:
                    tokens.append(keyword)

            return tokens

        flight_over = 0
        flight_over_type_counter: Counter[str] = Counter()
        if not flight_df.empty:
            if '超标类型' in flight_df.columns:
                # 统计数量
                flight_over = int(
                    flight_df[
                        flight_df['超标类型']
                        .astype(str)
                        .str.contains('超折扣|超时间', na=False)
                    ].shape[0]
                )

                # 统计类型分布
                type_series = flight_df['超标类型'].dropna().astype(str)
                for raw_type in type_series:
                    for token in _extract_over_types(raw_type):
                        flight_over_type_counter[token] += 1

                # 如果有类型分布但未匹配到数量，用分布求和兜底
                if flight_over == 0 and flight_over_type_counter:
                    flight_over = sum(flight_over_type_counter.values())
            elif '是否超标' in flight_df.columns:
                flight_over = _count_yes(flight_df, '是否超标')
                if flight_over > 0:
                    flight_over_type_counter['未注明类型'] += flight_over

        hotel_over = _count_yes(hotel_df, '是否超标')
        train_over = _count_yes(train_df, '是否超标')

        total = flight_over + hotel_over + train_over

        return {
            'total': int(total),
            'flight': int(flight_over),
            'hotel': int(hotel_over),
            'train': int(train_over),
            'flight_over_types': {k: int(v) for k, v in flight_over_type_counter.items()},
        }

    def count_total_orders(self) -> Dict[str, int]:
        """
        统计各差旅类型及总订单数
        """
        flight_df = self.clean_travel_data('机票')
        hotel_df = self.clean_travel_data('酒店')
        train_df = self.clean_travel_data('火车票')

        flight = 0 if flight_df is None else int(len(flight_df))
        hotel = 0 if hotel_df is None else int(len(hotel_df))
        train = 0 if train_df is None else int(len(train_df))

        return {
            'total': int(flight + hotel + train),
            'flight': flight,
            'hotel': hotel,
            'train': train,
        }
    
    def calculate_department_costs(self, top_n: int = 15) -> List[Dict[str, Any]]:
        """
        部门成本汇总（包含平均工时和人数统计）
        
        Args:
            top_n: 返回前N个部门，其余汇总到"其他"（默认15）
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
                
                # 按成本降序排序
                grouped = grouped.sort_values('成本', ascending=False).reset_index(drop=True)
                
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
                
                # 应用 top_n 限制并添加"其他"
                return self._apply_top_n_with_others(results, top_n, 'department')
        
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
        results = sorted(results, key=lambda x: x['total_cost'], reverse=True)
        
        # 应用 top_n 限制并添加"其他"
        return self._apply_top_n_with_others(results, top_n, 'department')
    
    def _apply_top_n_with_others(self, results: List[Dict[str, Any]], top_n: int, name_key: str) -> List[Dict[str, Any]]:
        """
        应用 Top N 限制，将超出部分汇总到"其他"
        
        Args:
            results: 已排序的结果列表
            top_n: 保留的前N条记录
            name_key: 名称字段（'department' 或 'project_code'）
        
        Returns:
            处理后的结果列表
        """
        if not results or len(results) <= top_n:
            return results
        
        # 前 top_n 条
        top_results = results[:top_n]
        
        # 剩余的汇总到"其他"
        others = results[top_n:]
        total_count = len(results)
        
        others_summary = {
            name_key: '其他',
            'total_cost': sum(item.get('total_cost', 0) for item in others),
            'flight_cost': sum(item.get('flight_cost', 0) for item in others),
            'hotel_cost': sum(item.get('hotel_cost', 0) for item in others),
            'train_cost': sum(item.get('train_cost', 0) for item in others),
        }
        
        # 如果是部门数据，计算平均工时和总人数
        if name_key == 'department':
            avg_hours_list = [item.get('avg_hours', 0) for item in others if item.get('avg_hours', 0) > 0]
            others_summary['avg_hours'] = sum(avg_hours_list) / len(avg_hours_list) if avg_hours_list else 0
            others_summary['person_count'] = sum(item.get('person_count', 0) for item in others)
        
        # 如果是项目数据
        if name_key == 'project_code':
            others_summary['project_name'] = f'其他项目（{total_count - top_n}个）'
            others_summary['record_count'] = sum(item.get('record_count', 0) for item in others)
            others_summary['details'] = []
        
        top_results.append(others_summary)
        
        return top_results
    
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
