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
    
    def execute_combine_sql(self, param: dict):
        """
        执行组合 SQL
        :param param: 包含 sqls 数组和其他参数
        :return: 最后一个 SQL 的执行结果
        """
        print("executeCombineSql--执行组合 SQL")
        
        sqls = param.get("sqls", [])
        if not sqls:
            return {"success": False, "error": "sqls 参数为空"}
        
        conn = None
        try:
            conn = self._get_connection()
            current_param = param.copy()
            result = None

            with conn.cursor() as cursor:
                for i, sql in enumerate(sqls):
                    executed_sql = self._replace_params(sql, current_param)
                    print(f"执行 SQL[{i}]: {executed_sql}")
                    cursor.execute(executed_sql)
                    result = cursor.fetchall()
                    
                    # 如果不是最后一条 SQL
                    if i < len(sqls) - 1:
                        if not result:
                            return {"success": False, "error": f"第{i+1}条SQL无结果，后续SQL无法执行"}
                        
                        # 如果返回多条记录，遍历执行后续 SQL
                        if len(result) > 1:
                            all_results = []
                            for row in result:
                                row_param = current_param.copy()
                                row_param.update(row)
                                # 递归执行剩余 SQL
                                sub_param = row_param.copy()
                                sub_param["sqls"] = sqls[i+1:]
                                sub_result = self.execute_combine_sql(sub_param)
                                # 跳过失败的结果
                                if isinstance(sub_result, dict) and sub_result.get("success") == False:
                                    continue
                                if isinstance(sub_result, list):
                                    all_results.extend(sub_result)
                                elif sub_result:
                                    all_results.append(sub_result)
                            print(f"遍历结果集合并: {len(all_results)} 条记录")
                            return all_results
                        else:
                            # 单条记录，合并参数继续
                            current_param.update(result[0])
                            current_param.update(result[0])
            return result
            
        except Exception as e:
            print(f"执行组合 SQL 异常: {e}")
            return {"success": False, "error": str(e)}
        finally:
            if conn:
                conn.close()

    def execute_one_sql(self, param: dict):
        """
        执行单个 SQL
        :param param: 包含 sql 字段和其他参数
        :return: 单个 SQL 的执行结果
        """
        print("executeOneSql--执行单个 SQL")
        
        sql = param.get("sql")
        if not sql:
            return {"success": False, "error": "sql 参数为空"}
        
        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor() as cursor:
                executed_sql = self._replace_params(sql, param)
                cursor.execute(executed_sql)
                result = cursor.fetchall()
            
            return result
            
        except Exception as e:
            print(f"执行单个 SQL 异常: {e}")
            return {"success": False, "error": str(e)}
        finally:
            if conn:
                conn.close()
    
    # 不需要加引号的参数名（用于 SELECT 字段列表等场景）
    RAW_PARAMS = {"field_names", "fields", "columns"}

    def _replace_params(self, sql: str, params: dict) -> str:
        """
        替换 SQL 中的参数占位符
        :param sql: SQL 语句
        :param params: 参数字典
        :return: 替换后的 SQL
        """
        result = sql
        for key, value in params.items():
            placeholder = f"#{{{key}}}"
            if placeholder not in result:
                continue
                
            # 1. 反引号包裹的表名/字段名
            if f"`{placeholder}`" in result:
                result = result.replace(f"`{placeholder}`", f"`{value}`")
            # 2. LIKE 模糊查询（优先处理，避免被加引号）
            elif f"'%{placeholder}%'" in result:
                result = result.replace(f"'%{placeholder}%'", f"'%{value}%'")
            # 3. 字段列表等不加引号
            elif key in self.RAW_PARAMS:
                result = result.replace(placeholder, str(value))
            # 4. 普通字符串参数
            elif isinstance(value, str):
                result = result.replace(placeholder, f"'{value}'")
            # 5. 数字等其他类型
            else:
                result = result.replace(placeholder, str(value))
        return result


# 使用示例
if __name__ == "__main__":
    util = CombineSqlUtil()
    
    param = {
        "layerName": "网吧",
        "sqls": [
            "SELECT table_name FROM gather_task WHERE name = #{layerName}",
            "SELECT COUNT(*) as countNum FROM `#{table_name}`"
        ]
    }
    
    result = util.execute_combine_sql(param)
    print(f"查询结果：{result}")
