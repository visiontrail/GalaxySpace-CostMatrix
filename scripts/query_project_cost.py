"""
示例脚本：查询指定月份特定项目的总成本

使用方法:
    cd backend
    source venv/bin/activate
    python ../scripts/query_project_cost.py
"""
import sys
from pathlib import Path

# 添加 backend 目录到 Python 路径
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.db.database import SessionLocal, init_db
from app.db import crud


def main():
    # 初始化数据库
    init_db()

    # 获取数据库会话
    db = SessionLocal()

    try:
        # 获取第一个上传记录（可根据需要修改）
        upload = db.query(crud.Upload).first()
        if not upload:
            print("数据库中没有上传记录")
            return

        print(f"使用文件: {upload.file_name}")
        print(f"文件路径: {upload.file_path}")
        print("-" * 60)

        # 查询8月份"公司公共"项目的总成本
        project_code = "00000"  # 公司公共的项目代码
        month = "2025-08"

        total_cost = crud.get_project_total_cost_by_month(
            db,
            upload.file_path,
            project_code,
            month
        )

        print(f"查询条件:")
        print(f"  项目代码: {project_code} (公司公共)")
        print(f"  月份: {month}")
        print("-" * 60)
        print(f"8月份\"公司公共\"项目的总成本: {total_cost:,.2f} 元")

    finally:
        db.close()


if __name__ == "__main__":
    main()
