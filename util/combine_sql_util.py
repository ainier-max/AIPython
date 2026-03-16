import os
import pymysql
from dotenv import load_dotenv

load_dotenv()


class CombineSqlUtil:
    """组合 SQL 执行工具"""
    
    def __init__(self):
        self.db_config = {
            'host': os.getenv("DB_HOST", "localhost"),
            'port': int(os.getenv("DB_PORT", 3306)),
            'user': os.getenv("DB_USER", "root"),
            'password': os.getenv("DB_PASSWORD", ""),
            'database': os.getenv("DB_NAME", ""),
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor
        }
    
    def _get_connection(self):
        """获取数据库连接"""
        return pymysql.connect(**self.db_config)
    
    def execute_combine_sql(self, param: dict) -> list:
        """
        执行组合 SQL
        :param param: 包含 sqls 数组和其他参数
        :return: 最后一个 SQL 的执行结果
        """
        print("executeCombineSql--执行组合 SQL")
        
        sqls = param.get("sqls", [])
        if not sqls:
            return None
        
        conn = None
        try:
            conn = self._get_connection()
            current_param = param.copy()
            result = None
            
            with conn.cursor() as cursor:
                for i, sql in enumerate(sqls):
                    # 执行当前 SQL，替换参数占位符
                    executed_sql = self._replace_params(sql, current_param)
                    cursor.execute(executed_sql)
                    result = cursor.fetchall()
                    
                    # 如果不是最后一个 SQL，将结果合并到参数中
                    if i < len(sqls) - 1 and result:
                        current_param.update(result[0])
            
            return result
            
        finally:
            if conn:
                conn.close()

    def execute_one_sql(self, param: dict) -> list:
        """
        执行单个 SQL
        :param param: 包含 sql 字段和其他参数
        :return: 单个 SQL 的执行结果
        """
        print("executeOneSql--执行单个 SQL")
        
        sql = param.get("sql")
        if not sql:
            return None
        
        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor() as cursor:
                executed_sql = self._replace_params(sql, param)
                cursor.execute(executed_sql)
                result = cursor.fetchall()
            
            return result
            
        finally:
            if conn:
                conn.close()
    
    def _replace_params(self, sql: str, params: dict) -> str:
        """
        替换 SQL 中的参数占位符
        :param sql: SQL 语句
        :param params: 参数字典
        :return: 替换后的 SQL
        """
        result = sql
        for key, value in params.items():
            if isinstance(value, str):
                result = result.replace(f"#{{{key}}}", f"'{value}'")
            else:
                result = result.replace(f"#{{{key}}}", str(value))
        return result


# 使用示例
if __name__ == "__main__":
    util = CombineSqlUtil()
    
    # 示例：通过图层名称查询表名，再统计总条数
    param = {
        "layerName": "网吧",
        "sqls": [
            "SELECT table_name FROM layer_config WHERE layer_name = #{layerName}",
            "SELECT COUNT(*) as count FROM #{table_name}"
        ]
    }
    
    result = util.execute_combine_sql(param)
    print(f"查询结果：{result}")
