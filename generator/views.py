import random
import pymysql
import configparser
import time
import datetime
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
import os
from django.utils import timezone
import json  # 新增：用于处理日志中的JSON数据

# 导入日志模型
from .models import GenerationLog  # 新增：导入日志模型

# 确保配置文件存在
CONFIG_PATH = os.path.join(settings.BASE_DIR, 'conf.ini')
if not os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, 'w') as f:
        f.write('[database]\n')
        f.write('host = 10.0.0.173\n')
        f.write('port = 3306\n')
        f.write('user = root\n')
        f.write('password = \n')
        f.write('db_name = \n')
        f.write('tab_name = \n\n')
        f.write('[data_conf]\n')
        f.write('num = 100\n')
        f.write('start = 20230101\n')
        f.write('end = 20231231\n\n')
        f.write('[columns]\n')
        f.write('# 格式: 字段名=值1,值2,值3 或 字段名=SELECT语句\n')


def index(request):
    """首页视图"""
    # 重置会话数据
    request.session.flush()
    return render(request, 'generator/index.html')


def reset(request):
    """重置所有配置"""
    request.session.flush()
    messages.success(request, "已重置所有配置，可以重新开始")
    return redirect('index')


def database_config(request):
    """数据库配置视图"""
    if request.method == 'POST':
        # 保存数据库配置到会话
        db_config = {
            'host': request.POST.get('host', 'localhost'),
            'port': request.POST.get('port', 3306),
            'user': request.POST.get('user', 'root'),
            'password': request.POST.get('password', ''),
            'db_name': request.POST.get('db_name', '')
        }

        # 验证数据库连接
        try:
            conn = pymysql.connect(
                host=db_config['host'],
                port=int(db_config['port']),
                user=db_config['user'],
                password=db_config['password'],
                database=db_config['db_name'],
                charset='utf8mb4'
            )
            conn.close()
            request.session['db_config'] = db_config
            messages.success(request, "数据库连接成功！")
            return redirect('table_selection')
        except Exception as e:
            messages.error(request, f"数据库连接失败: {str(e)}")
            return render(request, 'generator/database_config.html', {'db_config': db_config})

    # GET请求，尝试从会话或配置文件加载默认值
    db_config = request.session.get('db_config', {})
    if not db_config:
        config = configparser.ConfigParser()
        config.read(CONFIG_PATH)
        if 'database' in config:
            db_config = {
                'host': config.get('database', 'host', fallback='localhost'),
                'port': config.get('database', 'port', fallback=3306),
                'user': config.get('database', 'user', fallback='root'),
                'password': config.get('database', 'password', fallback=''),
                'db_name': config.get('database', 'db_name', fallback='')
            }

    return render(request, 'generator/database_config.html', {'db_config': db_config})


def table_selection(request):
    """表选择视图"""
    # 检查是否已配置数据库
    if 'db_config' not in request.session:
        messages.warning(request, "请先配置数据库连接")
        return redirect('database_config')

    db_config = request.session['db_config']

    if request.method == 'POST':
        # 保存选择的表
        selected_tables = request.POST.getlist('tables')
        if not selected_tables:
            messages.error(request, "请至少选择一个表")
            return redirect('table_selection')

        request.session['selected_tables'] = selected_tables
        return redirect('field_config')

    # 获取数据库中的所有表
    try:
        conn = pymysql.connect(
            host=db_config['host'],
            port=int(db_config['port']),
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['db_name'],
            charset='utf8mb4'
        )

        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [table[0] for table in cursor.fetchall()]

        conn.close()
        return render(request, 'generator/table_selection.html', {'tables': tables})
    except Exception as e:
        messages.error(request, f"获取表列表失败: {str(e)}")
        return redirect('database_config')


def query_cols(database, table, db_config):
    """查询表的列信息"""
    try:
        conn = pymysql.connect(
            host=db_config['host'],
            port=int(db_config['port']),
            user=db_config['user'],
            password=db_config['password'],
            database=database,
            charset='utf8mb4'
        )

        with conn.cursor() as cursor:
            # 获取列信息
            cursor.execute(f"desc {database}.{table};")
            all_datas = cursor.fetchall()
            cols_lst = [data[0] for data in all_datas]

            # 获取每列的 distinct 值
            col_dic = {}
            for col in cols_lst:
                cursor.execute(f"select distinct {col} from {database}.{table} limit 10000 ;")
                col_data = cursor.fetchall()
                col_dic[col] = [v[0] for v in col_data if v[0] is not None]

            # 获取主键信息
            pri_sql = f""" 
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
                WHERE TABLE_SCHEMA = '{database}' AND TABLE_NAME = '{table}'
                AND CONSTRAINT_NAME = 'PRIMARY' ORDER BY ORDINAL_POSITION;
            """
            cursor.execute(pri_sql)
            pri_lst = [v[0] for v in cursor.fetchall()]

        conn.close()
        return col_dic, pri_lst
    except Exception as e:
        print(f"查询列信息失败: {e}")
        return None, None


def field_config(request):
    """字段配置视图"""
    # 检查会话数据
    if 'db_config' not in request.session or 'selected_tables' not in request.session:
        messages.warning(request, "请先完成前面的配置步骤")
        return redirect('index')

    db_config = request.session['db_config']
    selected_tables = request.session['selected_tables']

    # 加载列配置
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    cols_dict = {}
    if 'columns' in config:
        cols_dict = dict(config['columns'])

    # 处理表单提交
    if request.method == 'POST':
        field_configs = {}
        for table in selected_tables:
            table_fields = {}
            for key, value in request.POST.items():
                if key.startswith(f"{table}_"):
                    field_name = key[len(f"{table}_"):]
                    table_fields[field_name] = value.strip()
            field_configs[table] = table_fields

        # 保存到配置文件
        if 'columns' not in config:
            config.add_section('columns')

        for table, fields in field_configs.items():
            for field, value in fields.items():
                config.set('columns', f"{table}.{field}", value)

        with open(CONFIG_PATH, 'w') as f:
            config.write(f)

        request.session['field_configs'] = field_configs
        return redirect('generate_config')

    # 准备字段配置数据
    table_data = {}
    for table in selected_tables:
        col_dic, pri_lst = query_cols(db_config['db_name'], table, db_config)
        if col_dic is None:
            messages.error(request, f"无法获取表 {table} 的结构信息")
            return redirect('table_selection')

        table_data[table] = {
            'columns': col_dic,
            'primary_keys': pri_lst,
            'config': {}
        }

        # 加载已有的配置
        for col in col_dic.keys():
            config_key = f"{table}.{col}"
            if config.has_option('columns', config_key):
                table_data[table]['config'][col] = config.get('columns', config_key)

    return render(request, 'generator/field_config.html', {
        'table_data': table_data,
        'selected_tables': selected_tables
    })


def generate_config(request):
    """生成配置视图"""
    # 检查会话数据
    required_keys = ['db_config', 'selected_tables', 'field_configs']
    if not all(key in request.session for key in required_keys):
        messages.warning(request, "请先完成前面的配置步骤")
        return redirect('index')

    # 加载默认配置
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    default_num = config.get('data_conf', 'num', fallback='100')
    default_start = config.get('data_conf', 'start', fallback='20230101')
    default_end = config.get('data_conf', 'end', fallback='20231231')

    if request.method == 'POST':
        # 保存生成配置
        generate_config = {
            'num': request.POST.get('num', default_num),
            'start': request.POST.get('start', default_start),
            'end': request.POST.get('end', default_end)
        }

        # 验证数据
        try:
            # 验证数量
            num = int(generate_config['num'])
            if num <= 0:
                raise ValueError("生成数量必须为正数")

            # 验证日期格式
            datetime.datetime.strptime(generate_config['start'], "%Y%m%d")
            datetime.datetime.strptime(generate_config['end'], "%Y%m%d")

            # 保存到配置文件
            if 'data_conf' not in config:
                config.add_section('data_conf')

            config.set('data_conf', 'num', generate_config['num'])
            config.set('data_conf', 'start', generate_config['start'])
            config.set('data_conf', 'end', generate_config['end'])

            with open(CONFIG_PATH, 'w') as f:
                config.write(f)

            request.session['generate_config'] = generate_config
            return redirect('generate_data')
        except ValueError as e:
            messages.error(request, f"配置错误: {str(e)}")
        except Exception as e:
            messages.error(request, f"保存配置失败: {str(e)}")

    return render(request, 'generator/generate_config.html', {
        'default_num': default_num,
        'default_start': default_start,
        'default_end': default_end,
        'selected_tables': request.session['selected_tables']
    })


def generate_random_datetime(start_date_str, end_date_str):
    """生成指定范围内的随机日期时间"""
    try:
        # 解析开始日期
        start_date = datetime.datetime.strptime(start_date_str, "%Y%m%d")
        # 解析结束日期，并设置为当天的23:59:59
        end_date = datetime.datetime.strptime(end_date_str, "%Y%m%d") + datetime.timedelta(days=1) - datetime.timedelta(
            seconds=1)

        # 计算两个日期之间的总秒数
        time_delta = end_date - start_date
        total_seconds = int(time_delta.total_seconds())

        # 生成随机秒数偏移
        random_seconds = random.randint(0, total_seconds)

        # 计算随机时间
        random_datetime = start_date + datetime.timedelta(seconds=random_seconds)

        # 格式化为指定字符串
        return random_datetime.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"生成随机日期失败: {e}")
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def max_pri(col, table, db_config):
    """获取主键的最大值"""
    try:
        conn = pymysql.connect(
            host=db_config['host'],
            port=int(db_config['port']),
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['db_name'],
            charset='utf8mb4'
        )

        with conn.cursor() as cursor:
            max_sql = f"select max({col}) from {db_config['db_name']}.{table};"
            cursor.execute(max_sql)
            max_value = cursor.fetchone()[0]

        conn.close()
        return max_value if max_value is not None else 0
    except Exception as e:
        print(f"获取主键最大值失败: {e}")
        return 0


def generate_data(request):
    """生成数据并显示结果（添加日志记录功能）"""
    # 检查会话数据
    required_keys = ['db_config', 'selected_tables', 'field_configs', 'generate_config']
    if not all(key in request.session for key in required_keys):
        messages.warning(request, "请先完成前面的配置步骤")
        return redirect('index')

    db_config = request.session['db_config']
    selected_tables = request.session['selected_tables']
    field_configs = request.session['field_configs']
    generate_config = request.session['generate_config']

    num = int(generate_config['num'])
    start_date = generate_config['start']
    end_date = generate_config['end']

    results = []
    total_time = 0
    error_msg = ""  # 记录整体错误信息

    try:
        # 连接数据库
        conn = pymysql.connect(
            host=db_config['host'],
            port=int(db_config['port']),
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['db_name'],
            charset='utf8mb4'
        )

        for table in selected_tables:
            start_time = time.time()

            # 获取表结构信息
            col_dic, pri_lst = query_cols(db_config['db_name'], table, db_config)
            if not col_dic:
                results.append({
                    'table': table,
                    'success': False,
                    'count': 0,
                    'time': 0,
                    'error': "无法获取表结构信息"
                })
                continue

            # 处理主键最大值
            max_dic = {}
            for pri in pri_lst:
                max_dic[pri] = max_pri(pri, table, db_config)

            # 准备字段配置
            cols_dict = {}
            for col, config_value in field_configs[table].items():
                if not config_value:
                    continue
                if 'select' in config_value.lower():
                    # 执行SQL查询获取值列表
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute(config_value)
                            values_lst = [v[0] for v in cursor.fetchall() if v[0] is not None]
                            cols_dict[col] = values_lst
                    except Exception as e:
                        print(f"执行查询失败 {config_value}: {e}")
                        cols_dict[col] = []
                else:
                    # 分割为值列表
                    cols_dict[col] = [v.strip() for v in config_value.split(',') if v.strip()]

            # 生成数据
            data_lst = []
            col_names = list(col_dic.keys())
            col_placeholders = ', '.join(['%s'] * len(col_names))
            col_str = ', '.join(col_names)

            for _ in range(num):
                data = []
                for col in col_names:
                    if col in pri_lst:
                        # 主键自增
                        max_dic[col] += 1
                        data.append(max_dic[col])
                    elif col in cols_dict and cols_dict[col]:
                        # 使用配置的值
                        data.append(random.choice(cols_dict[col]))
                    elif col.lower().endswith('time'):
                        # 生成时间
                        data.append(generate_random_datetime(start_date, end_date))
                    elif col_dic[col]:
                        # 使用表中已有的值
                        data.append(random.choice(col_dic[col]))
                    else:
                        # 无法生成值，使用默认值
                        data.append(None)

                data_lst.append(data)

            # 批量插入数据
            try:
                with conn.cursor() as cursor:
                    insert_sql = f"insert into {db_config['db_name']}.{table} ({col_str}) values ({col_placeholders}) ;"
                    cursor.executemany(insert_sql, data_lst)
                    conn.commit()

                # 记录结果
                elapsed_time = round(time.time() - start_time, 2)
                total_time += elapsed_time
                results.append({
                    'table': table,
                    'success': True,
                    'count': num,
                    'time': elapsed_time,
                    'error': ""
                })

            except Exception as e:
                conn.rollback()
                error_detail = str(e)
                results.append({
                    'table': table,
                    'success': False,
                    'count': 0,
                    'time': round(time.time() - start_time, 2),
                    'error': error_detail
                })
                error_msg += f"表 {table} 错误: {error_detail}; "

        conn.close()

    except Exception as e:
        error_msg = f"数据库连接错误: {str(e)}"
        results.append({
            'table': '数据库连接',
            'success': False,
            'count': 0,
            'time': 0,
            'error': error_msg
        })

    # 记录日志（核心新增部分）
    try:
        # 判断整体操作状态（只要有一个表失败就视为整体失败）
        overall_success = all(r['success'] for r in results)

        # 创建日志记录
        log = GenerationLog(
            ip_address=request.META.get('REMOTE_ADDR'),  # 操作IP
            database_name=db_config['db_name'],  # 目标数据库
            table_name=",".join(selected_tables),  # 目标表名（多表用逗号分隔）
            generation_count=num,  # 生成数量
            start_date=start_date,  # 开始日期
            end_date=end_date,  # 结束日期
            status=overall_success,  # 操作状态
            error_msg=error_msg if not overall_success else ""  # 错误信息
        )

        # 存储造数规则（从field_configs转换）
        log.set_rules(field_configs)

        # 保存日志
        log.save()
    except Exception as log_err:
        print(f"日志记录失败: {str(log_err)}")

    # 保存结果到会话
    request.session['results'] = results
    request.session['total_time'] = round(total_time, 2)

    return redirect('result')


def result(request):
    """显示结果视图"""
    if 'results' not in request.session or 'total_time' not in request.session:
        messages.warning(request, "请先执行数据生成")
        return redirect('index')

    return render(request, 'generator/result.html', {
        'results': request.session['results'],
        'total_time': request.session['total_time'],
        'total_tables': len(request.session['results']),
        'success_tables': sum(1 for r in request.session['results'] if r['success']),
        'total_records': sum(r['count'] for r in request.session['results'] if r['success'])
    })


def check_connection(request):
    """AJAX检查数据库连接"""
    if request.method == 'POST':
        try:
            db_config = {
                'host': request.POST.get('host', 'localhost'),
                'port': int(request.POST.get('port', 3306)),
                'user': request.POST.get('user', 'root'),
                'password': request.POST.get('password', ''),
                'db_name': request.POST.get('db_name', '')
            }

            conn = pymysql.connect(
                host=db_config['host'],
                port=db_config['port'],
                user=db_config['user'],
                password=db_config['password'],
                database=db_config['db_name'],
                charset='utf8mb4'
            )
            conn.close()

            return JsonResponse({
                'status': 'success',
                'message': '数据库连接成功'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'连接失败: {str(e)}'
            })

    return JsonResponse({
        'status': 'error',
        'message': '无效请求'
    })


# 新增：日志列表视图
def log_list(request):
    """查看操作日志列表"""
    logs = GenerationLog.objects.all().order_by("-operation_time")
    # 转换为本地时区

    return render(request, 'generator/log_list.html', {'logs': logs})