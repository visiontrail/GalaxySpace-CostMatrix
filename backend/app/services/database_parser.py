"""Database parsing service to insert Excel data into database."""
from typing import List
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

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.processor = ExcelProcessor(file_path)
        self.logger = logger

    def parse_and_insert(self, db: Session) -> dict:
        """
        Parse Excel file and insert all data into database.

        Returns:
            dict with statistics about inserted records
        """
        try:
            # Load all sheets
            self.logger.info(f"Starting database parsing for {self.file_path}")
            sheets_data = self.processor.load_all_sheets()

            # Get sheet names
            sheet_names = list(sheets_data.keys())

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
                attendance_df = self.processor.clean_attendance_data()
                if not attendance_df.empty:
                    stats["attendance_count"] = batch_insert_attendance(
                        db, upload_record.id, attendance_df
                    )
                    self.logger.info(
                        f"Inserted {stats['attendance_count']} attendance records"
                    )

            # Insert travel expense data
            expense_types = [
                ("机票", "flight_count"),
                ("酒店", "hotel_count"),
                ("火车票", "train_count"),
            ]

            for sheet_name, count_key in expense_types:
                if sheet_name in sheets_data:
                    expense_df = self.processor.clean_travel_data(sheet_name)
                    if not expense_df.empty:
                        count = batch_insert_travel_expenses(
                            db, upload_record.id, expense_df, sheet_name
                        )
                        stats[count_key] = count
                        self.logger.info(f"Inserted {count} {sheet_name} records")

            stats["total_expenses"] = (
                stats["flight_count"] + stats["hotel_count"] + stats["train_count"]
            )

            # Insert anomalies (requires cross-check analysis)
            if "状态明细" in sheets_data and any(
                t in sheets_data for t in ["机票", "酒店", "火车票"]
            ):
                anomalies = self.processor.cross_check_attendance_travel()
                if anomalies:
                    stats["anomalies_count"] = batch_insert_anomalies(
                        db, upload_record.id, anomalies
                    )
                    self.logger.info(f"Inserted {stats['anomalies_count']} anomaly records")

            # Update upload record status
            upload_record.parse_status = "parsed"
            db.commit()

            self.logger.info(f"Database parsing completed: {stats}")
            return stats

        except Exception as e:
            db.rollback()
            self.logger.error(f"Database parsing failed: {e}")
            raise
