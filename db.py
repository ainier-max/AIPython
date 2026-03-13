import os
import json
import pymysql
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", ""),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )

def query_layer_count(layer_name: str) -> dict:
    """查询指定图层的数据总条数"""
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 第一步：根据图层名称查询表名
            cursor.execute(
                "SELECT table_name FROM layer_config WHERE layer_name = %s LIMIT 1",
                (layer_name,)
            )
            row = cursor.fetchone()
            if not row:
                return {"success": False, "error": f"未找到图层：{layer_name}"}

            table_name = row["table_name"]

            # 第二步：查询该表的数据条数
            cursor.execute(f"SELECT COUNT(*) AS total FROM `{table_name}`")
            result = cursor.fetchone()
            total = result["total"] if result else 0

        conn.close()
        return {"success": True, "layer_name": layer_name, "table_name": table_name, "total": total}
    except Exception as e:
        return {"success": False, "error": str(e)}
