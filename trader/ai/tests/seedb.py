import sqlite3
import pandas as pd
import os


def export_sqlite_to_csv(database_path):
    """
    导出 SQLite 数据库中所有表到同名 CSV 文件

    Args:
        database_path: SQLite 数据库文件路径
    """
    # 连接数据库
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    try:
        # 获取所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        # 为每个表创建 CSV 文件
        for table in tables:
            table_name = table[0]

            # 跳过系统表
            if table_name.startswith('sqlite_'):
                continue

            print(f"导出表: {table_name}")

            # 读取表数据
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)

            # 生成 CSV 文件名
            csv_filename = f"{table_name}.csv"

            # 保存为 CSV 文件
            df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
            print(f"已保存: {csv_filename}")

    except Exception as e:
        print(f"导出过程中出现错误: {e}")
    finally:
        # 关闭连接
        cursor.close()
        conn.close()
        print("导出完成")


if __name__ == "__main__":
    # 数据库文件路径
    db_path = r"C:\Users\WangZiyu\Desktop\database.db"

    # 检查文件是否存在
    if not os.path.exists(db_path):
        print(f"错误: 文件 {db_path} 不存在")
    else:
        export_sqlite_to_csv(db_path)