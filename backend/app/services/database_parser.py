"""Database parsing service to insert Excel data into database."""
from typing import List, Optional, Callable
import pandas as pd
from sqlalchemy.orm import Session
from app.db.crud import (
    create_or_get_upload_record,
    delete_upload_data,
    batch_insert_attendance,
    batch_insert_travel_expenses,
    batch_insert_anomalies,
)
from app.services.excel_processor import ExcelProcessor
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseParser:
    """Parse Excel file and insert data into database."""

    def __init__(self, file_path: str, progress_callback: Optional[Callable[[int, str], None]] = None):
        self.file_path = file_path
        self.processor = ExcelProcessor(file_path)
        self.logger = logger
        self.progress_callback = progress_callback

    def _update_progress(self, progress: int, message: str) -> None:
        """Update progress if callback is provided"""
        if self.progress_callback:
            self.progress_callback(progress, message)
        self.logger.info(f"Progress {progress}%: {message}")

    def parse_and_insert(self, db: Session) -> dict:
        """
        Parse Excel file and insert all data into database.

        Returns:
            dict with statistics about inserted records
        """
        try:
            self._update_progress(45, "正在读取Excel文件...")
            
            self.logger.info(f"Starting database parsing for {self.file_path}")
            sheets_data = self.processor.load_all_sheets()

            # Get sheet names
            sheet_names = list(sheets_data.keys())

            self._update_progress(50, "正在创建上传记录...")
            
            # Create or get upload record
            upload_record = create_or_get_upload_record(
                db,
                file_name=self.file_path.split("/")[-1],
                file_path=self.file_path,
                file_size=len(open(self.file_path, "rb").read()),
                sheets_info=sheet_names,
            )

            # Delete existing data for this upload if it exists
            delete_upload_data(db, upload_record.id)

            stats = {
                "upload_id": upload_record.id,
                "attendance_count": 0,
                "flight_count": 0,
                "hotel_count": 0,
                "train_count": 0,
                "total_expenses": 0,
                "anomalies_count": 0,
            }

            # Insert attendance data
            if "状态明细" in sheets_data:
                self._update_progress(55, "正在解析考勤数据...")
                attendance_df = self.processor.clean_attendance_data()
                if not attendance_df.empty:
                    stats["attendance_count"] = batch_insert_attendance(
                        db, upload_record.id, attendance_df
                    )
                    self.logger.info(
                        f"Inserted {stats['attendance_count']} attendance records"
                    )
                    self._update_progress(60, f"✅ 已写入考勤数据: {stats['attendance_count']} 条")

            # Insert travel expense data
            expense_types = [
                ("机票", "flight_count", 65),
                ("酒店", "hotel_count", 75),
                ("火车票", "train_count", 85),
            ]

            # 获取考勤数据用于填充部门信息
            attendance_df = None
            if "状态明细" in sheets_data:
                attendance_df = self.processor.clean_attendance_data()
                if not attendance_df.empty and '姓名' in attendance_df.columns and '一级部门' in attendance_df.columns:
                    # 构建姓名到部门的映射
                    person_dept_map = attendance_df[['姓名', '一级部门']].drop_duplicates().set_index('姓名')['一级部门'].to_dict()
                else:
                    person_dept_map = {}
                    attendance_df = None
            else:
                person_dept_map = {}

            for sheet_name, count_key, progress_value in expense_types:
                if sheet_name in sheets_data:
                    self._update_progress(progress_value - 5, f"正在解析{sheet_name}数据...")
                    self.logger.info(f"[{sheet_name}] 开始解析差旅数据")
                    
                    expense_df = self.processor.clean_travel_data(sheet_name)
                    
                    if not expense_df.empty:
                        self.logger.info(f"[{sheet_name}] 清洗后数据: {len(expense_df)} 行")
                        self.logger.info(f"[{sheet_name}] 数据列: {list(expense_df.columns)}")
                        self.logger.info(f"[{sheet_name}] 前3行数据预览:")
                        for idx in range(min(3, len(expense_df))):
                            row_data = expense_df.iloc[idx].to_dict()
                            self.logger.info(f"[{sheet_name}]   行{idx}: {row_data}")
                        
                        # 如果差旅表中一级部门为空，尝试从考勤表中填充
                        if attendance_df is not None and '一级部门' in expense_df.columns:
                            # 对于一级部门为NaN的记录，从考勤表查找部门信息
                            mask = expense_df['一级部门'].isna()
                            if mask.any():
                                self.logger.info(f"[{sheet_name}] 发现 {mask.sum()} 条记录部门信息为空，尝试从考勤表填充")
                                expense_df.loc[mask, '一级部门'] = expense_df.loc[mask, '姓名'].map(person_dept_map)

                        count = batch_insert_travel_expenses(
                            db, upload_record.id, expense_df, sheet_name
                        )
                        stats[count_key] = count
                        self.logger.info(f"Inserted {count} {sheet_name} records")
                        self._update_progress(progress_value, f"✅ 已写入{sheet_name}数据: {count} 条")
                    else:
                        self.logger.warning(f"[{sheet_name}] 清洗后数据为空，跳过入库")

            stats["total_expenses"] = (
                stats["flight_count"] + stats["hotel_count"] + stats["train_count"]
            )

            # Insert anomalies (requires cross-check analysis)
            if "状态明细" in sheets_data and any(
                t in sheets_data for t in ["机票", "酒店", "火车票"]
            ):
                self._update_progress(88, "正在分析异常数据...")
                anomalies = self.processor.cross_check_attendance_travel()
                if anomalies:
                    stats["anomalies_count"] = batch_insert_anomalies(
                        db, upload_record.id, anomalies
                    )
                    self.logger.info(f"Inserted {stats['anomalies_count']} anomaly records")
                    self._update_progress(90, f"✅ 已写入异常数据: {stats['anomalies_count']} 条")

            # Update upload record status
            upload_record.parse_status = "parsed"
            db.commit()

            self.logger.info(f"Database parsing completed: {stats}")
            return stats

        except Exception as e:
            db.rollback()
            self.logger.error(f"Database parsing failed: {e}")
            raise
