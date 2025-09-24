from itertools import product
import pymysql
def distinct_cols(table,*args):
    col_lst = list(args) if args else []
    col_pri_val={}
    data_all=[]
    if args:
        con = pymysql.connect(
            host='10.0.0.173',
            port=3306,
            user='root',
            password='root',
            database='dws',
            charset='utf8mb4'
        )
        cursor = con.cursor()
        # 列出所有可能组合
        # 1、自己数据库里已有的值
        for col in col_lst:
            cursor.execute(f'select distinct {col} from {table}')
            data_lst=cursor.fetchall()
            data_val=[data[0] for data in data_lst]
            data_all.append(data_val)
        all_result = set(list(product(*data_all)))
        # 2、配置的字段值
        # 列出已有组合
        query_sql=f'select distinct {','.join(col_lst)} from {table}'
        cursor.execute(query_sql)
        already_data=set(cursor.fetchall())
        # 计算出可用组合
        final_data=list(all_result-already_data)
        # 拼接字段名与字段值
        for k,v in enumerate(col_lst):
            col_pri_val[v]=[data[k] for data in final_data]
        return col_pri_val,len(final_data)
    else:
        return None

if __name__ == '__main__':
    # print(distinct_cols())
    # arr1 = ('a', 'b', 'c')
    # arr2 = (1, 2)
    # arr3 = [4,5,6,7]
    # result2 = list(product(arr1,arr2,arr3))
    # print("两个数组的组合:")
    # print(result2)
    print(distinct_cols('dws_trade_contract_pair_trade_stat', 'stat_period', 'contract_pair'))