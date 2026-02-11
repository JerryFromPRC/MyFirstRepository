# -*- coding: utf-8 -*-  # 声明脚本文件的编码
import tkinter as tk
import tkcalendar
from tkinter import ttk,messagebox,filedialog
import pymysql
from pymysql.err import ProgrammingError
from dotenv import load_dotenv, dotenv_values
from collections import Counter
import configparser

# 定义加载各产品数据库.env文件的函数用于配置不同产品的不同数据库信息
def get_env_config(env_filename):
    """读取指定.env文件,返回配置字典"""
    # dotenv_values直接读取文件为字典
    env_dict = dotenv_values(env_filename)
    # 转换并构建数据库配置
    db_config = {
        'host': env_dict.get('DB_HOST'),
        'port': int(env_dict.get('DB_PORT', 3306)),
        'user': env_dict.get('DB_USER'),
        'password': env_dict.get('DB_PASSWORD'),
        'database': env_dict.get('DB_NAME'),
        'charset': 'utf8mb4'
    }
    return db_config

def load_stations_config(config_file="stations_config.ini"):
    """从.ini文件读取工站配置"""
    config = configparser.ConfigParser()
    config.optionxform = str
    config.read(config_file, encoding='utf-8')
    return config

def parse_station_value(value):
    """解析工站配置值，支持单个值和逗号分隔的多个值"""
    if ',' in value:
        return [int(v.strip()) for v in value.split(',')]   #多值处理：分割→去空格→转整数，返回整数列表
    else:
        try:
            return int(value)   #单值处理：转整数，返回整数
        except ValueError:
            return value.strip()

def check_date(start_date,end_date): #定义检查输入日期前后逻辑的函数
    if start_date > end_date:
        messagebox.showwarning("警告", "开始日期不能晚于结束日期！")
        return False
    return True
    
def query_lc_data(env_file,start_date, end_date):      #封装从数据库获取的数据
    table_name="" 
    # 获取数据库配置
    db_config = get_env_config(env_file)
    
    # 从stations_config.ini中获取table_name
    stations_config = load_stations_config()
    table_name = None
    for project_name in stations_config.sections():
        project_config = stations_config[project_name]
        if project_config.get('env_file') == env_file:
            table_name = project_config.get('table_name')
            break
    
    if not table_name:
        messagebox.showwarning("警告", f"未找到{env_file}对应的table_name配置")
        return

    # 连接数据库并执行查询
    connection = None
    try:
        # 建立数据库连接
        connection = pymysql.connect(**db_config)
        # 使用字典游标，结果以{字段名: 值}返回，更易读取
        cursor = connection.cursor(pymysql.cursors.DictCursor)

        # 先测试表是否存在
        cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            messagebox.showwarning("警告", f"表 {table_name} 不存在")
            return []
        
        # SQL数据读取：截取timestamp前10位（yyyy-mm-dd）做日期筛选，取出变种号artno，序列号sno，设备编号traceid，测试类型test，测试结果io
        # 反引号包裹timestamp（MySQL关键字）和表名，避免语法错误
        sql = """
            SELECT artno,sno,traceid,test,io,os0        
            FROM `{table}` 
            WHERE LEFT(`timestamp`, 10) BETWEEN %s AND %s 
        """.format(table=table_name)

        # 执行参数化查询（避免SQL注入，安全规范）
        cursor.execute(sql, (start_date, end_date))
        
        # 获取查询结果
        results = cursor.fetchall()
        return results

    except pymysql.MySQLError as e:
        # 捕获数据库错误并提示
        if e.args[0] == 1049:
            messagebox.showwarning("警告", f"找不到指定的数据库！请检查.env文件中的DB_NAME配置是否正确: {e}")
        elif e.args[0] == 1146:
            messagebox.showwarning("警告", f"找不到表{table_name}！请确认表名是否正确。详情：{e}")
        else:
            messagebox.showwarning("警告", f"数据库查询失败：{e}")
        return []
    finally:
        # 确保连接关闭
        if connection:
            connection.close()

#定义从LC取数据自动计算FPY的函数
def calculate_each_project_FPY(project,startdate, enddate):
    stations_config = load_stations_config()    # 从.ini文件加载工站配置
    
    # 检查项目是否在配置文件中
    if project not in stations_config:
        messagebox.showwarning("警告", f"配置文件中未找到项目{project}的工站配置")
        return
    
    # 从配置文件中获取env_file
    env_file = stations_config[project].get('env_file')
    if not env_file:
        messagebox.showwarning("警告", f"配置文件中未找到项目{project}的env_file配置")
        return

    data_list= query_lc_data(env_file, startdate, enddate)   #一次性从LC数据库获取符合条件的数据，避免多次从数据库取数据导致响应时间长

    if not data_list:
        messagebox.showwarning("警告", f"未查询到符合条件的数据，请检查日期范围或数据库配置")
        return
    else:
        result_dict = {}       
        project_stations = stations_config[project]        # 获取该项目的所有工站配置        
        # 构建工站列表
        stations = []
        for station_name in project_stations:
            if station_name == 'env_file' or station_name == 'table_name':
                continue
            station_value = project_stations[station_name]
            parsed_value = parse_station_value(station_value)
            stations.append((station_name, parsed_value))

        # 定义工站数据提取函数
        def extract_station_data(station_value):
            if isinstance(station_value, list):
                return [data for data in data_list if data.get('traceid') in [int(v) for v in station_value]]
            elif isinstance(station_value, int):
                return [data for data in data_list if data.get('traceid') == station_value]
            else:
                return [data for data in data_list if data.get('test') == station_value]

        # 定义判断测试是否通过的函数
        def is_io_pass(io_value):
            if io_value == "-1" or io_value == -1:
                return True
            elif isinstance(io_value, str) and io_value.strip() == "-1":
                return True
            return False

        for station_name, station_name_LC in stations:        # 遍历每个工位计算通过率
            if not station_name_LC:
                result_dict[station_name] = 0.0
                continue
            
            if station_name == 'Function':
                if isinstance(station_name_LC, list):
                    function_data = [data for data in data_list if data.get('traceid') in [int(v) for v in station_name_LC]]
                elif isinstance(station_name_LC, int):
                    function_data = [data for data in data_list if data.get('traceid') == station_name_LC]
                else:
                    function_data = [data for data in data_list if data.get('test') == station_name_LC]
                
                if not function_data:
                    result_dict['PRE'] = 0.0
                    result_dict['EOL'] = 0.0
                    continue
                
                pre_data = [data for data in function_data if data.get('test') == 'PRE']
                eol_data = [data for data in function_data if data.get('test') == 'EOL']
                
                for test_type, test_data in [('PRE', pre_data), ('EOL', eol_data)]:
                    if not test_data:
                        result_dict[test_type] = 0.0
                        continue
                    
                    sno_count = Counter([data['sno'] for data in test_data])
                    
                    sno_list_firstpass = [data['sno'] for data in test_data if is_io_pass(data.get('io')) and sno_count[data['sno']] == 1]
                    sno_unique_pass_count = len(set(sno_list_firstpass))
                    
                    sno_list_total = [data['sno'] for data in test_data]
                    sno_unique_total_count = len(set(sno_list_total))
                    
                    if sno_unique_total_count == 0:
                        result_dict[test_type] = 0.0
                    else:
                        result_dict[test_type] = sno_unique_pass_count / sno_unique_total_count
            else:
                station_data = extract_station_data(station_name_LC)
                if not station_data:
                    result_dict[station_name] = 0.0
                    continue
                
                sno_count = Counter([data['sno'] for data in station_data])
                
                sno_list_firstpass = [data['sno'] for data in station_data if is_io_pass(data.get('io')) and sno_count[data['sno']] == 1]
                sno_unique_pass_count = len(set(sno_list_firstpass))
                
                sno_list_total = [data['sno'] for data in extract_station_data(station_name_LC)]
                sno_unique_total_count = len(set(sno_list_total))
                
                if sno_unique_total_count == 0:
                    result_dict[station_name] = 0.0
                else:
                    result_dict[station_name] = sno_unique_pass_count / sno_unique_total_count        
        return result_dict

def extract_failure_info(project, startdate, enddate):
    stations_config = load_stations_config()
    
    if project not in stations_config:
        messagebox.showwarning("警告", f"配置文件中未找到项目{project}的工站配置")
        return
    
    env_file = stations_config[project].get('env_file')
    if not env_file:
        messagebox.showwarning("警告", f"配置文件中未找到项目{project}的env_file配置")
        return

    data_list = query_lc_data(env_file, startdate, enddate)    
    if not data_list:
        return None
    
    project_stations = stations_config[project]
    stations = []
    for station_name in project_stations:
        if station_name == 'env_file' or station_name == 'table_name':
            continue
        station_value = project_stations[station_name]
        parsed_value = parse_station_value(station_value)
        stations.append((station_name, parsed_value))
    
    def extract_station_data(station_value):
        if isinstance(station_value, list):
            return [data for data in data_list if data.get('traceid') in [int(v) for v in station_value]]
        elif isinstance(station_value, int):
            return [data for data in data_list if data.get('traceid') == station_value]
        else:
            return [data for data in data_list if data.get('test') == station_value]
    failure_dict = {}
    
    for station_name, station_name_LC in stations:
        if station_name == 'Function':
            if isinstance(station_name_LC, list):
                function_data = [data for data in data_list if data.get('traceid') in [int(v) for v in station_name_LC]]
            elif isinstance(station_name_LC, int):
                function_data = [data for data in data_list if data.get('traceid') == station_name_LC]
            else:
                function_data = [data for data in data_list if data.get('test') == station_name_LC]
            
            pre_data = [data for data in function_data if data.get('test') == 'PRE']
            eol_data = [data for data in function_data if data.get('test') == 'EOL']
            
            for test_type, test_data in [('PRE', pre_data), ('EOL', eol_data)]:
                failure_dict[test_type] = {}
                for data in test_data:
                    os0_value = data.get('os0', '')
                    if os0_value and isinstance(os0_value, str):
                        if 'Test Step: ' in os0_value:
                            idx = os0_value.index('Test Step: ')
                            if idx + 10 <= len(os0_value):
                                step_info = os0_value[idx+10:idx+19]
                                if step_info in failure_dict[test_type]:
                                    failure_dict[test_type][step_info] += 1
                                else:
                                    failure_dict[test_type][step_info] = 1
                        elif 'Fail Step: ' in os0_value:
                            idx = os0_value.index('Fail Step: ')
                            if idx + 10 <= len(os0_value):
                                step_info = os0_value[idx+10:idx+19]
                                if step_info in failure_dict[test_type]:
                                    failure_dict[test_type][step_info] += 1
                                else:
                                    failure_dict[test_type][step_info] = 1
        else:
            station_data = extract_station_data(station_name_LC)
            failure_dict[station_name] = {}
            for data in station_data:
                os0_value = data.get('os0', '')
                if os0_value and isinstance(os0_value, str):
                    if 'Test Step: ' in os0_value:
                        idx = os0_value.index('Test Step: ')
                        if idx + 10 <= len(os0_value):
                            step_info = os0_value[idx+10:idx+19]
                            if step_info in failure_dict[station_name]:
                                failure_dict[station_name][step_info] += 1
                            else:
                                failure_dict[station_name][step_info] = 1
                    elif 'Fail Step: ' in os0_value:
                        idx = os0_value.index('Fail Step: ')
                        if idx + 10 <= len(os0_value):
                            step_info = os0_value[idx+10:idx+19]
                            if step_info in failure_dict[station_name]:
                                failure_dict[station_name][step_info] += 1
                            else:
                                failure_dict[station_name][step_info] = 1
    return failure_dict

'''通过TKinter创建FPY_LC类及按钮/输出框等各种控件并调用函数输出结果'''
class FPY_LC:
    #定义类的变量
    Default_FileName = "OBC FPY result.txt"

    def __init__(self,root):
        #初始化界面跟按钮显示框等
        self.root = root
        self.root.title("OBC产品FPY(First-Pass-Yield)自动计算 V2---by Zhou11")
        self.root.geometry("1000x800")      #窗口设定成1000x800大小
        self.root.resizable(True,True)      #允许调整窗口大小
        self.font=("微软雅黑",12)            #设置字体及大小
        
        # 创建主框架导入界面的设置
        main_frame = ttk.Frame(root, padding="10")  #将主框架添加到root主窗口里,框架边缘与内部组件间距10个像素
        main_frame.pack(fill=tk.BOTH, expand=True)  #沿水平 + 垂直方向填充，宽高都拉满父容器；组件自动扩展占满父容器

        # ----------------------  配置FPY操作显示界面 ----------------------
        FPY_operation_frame = ttk.LabelFrame(main_frame, text="基于MySQL数据库数据计算FPY", padding="10")
        FPY_operation_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 开始,结束日期选择框
        label_frame = ttk.Frame(FPY_operation_frame)
        label_frame.pack(fill=tk.X,pady=10)
        cal_frame = ttk.Frame(FPY_operation_frame)
        cal_frame.pack(fill=tk.X,pady=1)

        ttk.Label(label_frame, text="选择开始日期:", font=self.font).pack(side=tk.LEFT, padx=5)
        ttk.Label(label_frame, text="选择结束日期:", font=self.font).pack(side=tk.LEFT, padx=20)
        self.cal_select1 = tkcalendar.DateEntry(cal_frame,width=12,date_pattern="yyyy-mm-dd")
        self.cal_select1.pack(side=tk.LEFT, padx=5)
        self.cal_select2 = tkcalendar.DateEntry(cal_frame,width=12,date_pattern="yyyy-mm-dd")   
        self.cal_select2.pack(side=tk.LEFT, padx=20)

        # 项目选择下拉框
        transfer_frame= ttk.Frame(FPY_operation_frame)
        transfer_frame.pack(fill=tk.X, padx=1,pady=10)
        ttk.Label(transfer_frame, text="选择项目:", font=self.font).pack(anchor=tk.W)
        stations_config = load_stations_config()
        project_list = stations_config.sections()
        self.combo_project = ttk.Combobox(transfer_frame, values=project_list)
        self.combo_project.pack(anchor=tk.W, padx=5,pady=10)
        if project_list:
            self.combo_project.set(project_list[0])  # 默认选中第一个项目

        # 生成FPY数据按钮
        self.btn_transfer = ttk.Button(FPY_operation_frame, text="点击生成数据", command=self.calculate_and_generate_FPY, style="Accent.TButton").pack(anchor=tk.W, pady=20)

        # 创建双输出框
        output_frame = ttk.Frame(FPY_operation_frame)
        output_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # 左侧结果框（FPY结果）
        left_frame = ttk.Frame(output_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        ttk.Label(left_frame, text="一次通过率结果(Ctrl+C复制):", font=self.font).pack(anchor=tk.W)
        self.FPY_result = tk.Text(left_frame, width=32, height=15, font=self.font)
        self.FPY_result.pack(fill=tk.BOTH, expand=True, pady=5)
        self.FPY_result.config(state=tk.NORMAL)

        # 右侧结果框（测试失败TOP5）
        right_frame = ttk.Frame(output_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        ttk.Label(right_frame, text="测试失败TOP5:", font=self.font).pack(anchor=tk.W)
        self.Fail_result = tk.Text(right_frame, width=68, height=15, font=self.font)
        self.Fail_result.pack(fill=tk.BOTH, expand=True, pady=5)
        self.Fail_result.config(state=tk.NORMAL)

        # 文件存储按钮
        ttk.Button(FPY_operation_frame,text="保存数据为txt",command=self.store_file_txt,style="Accent.TButton").pack(anchor=tk.W, pady=5)

        # 清空退出按钮设置
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="清空所有", command=self.clear_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="退出", command=root.quit).pack(side=tk.LEFT, padx=5)

        # 设置按钮样式（美化）
        style = ttk.Style()
        style.configure("Accent.TButton", font=self.font, padding=5)
     
    def calculate_and_generate_FPY(self):
        #计算并显示计算结果
        project=self.combo_project.get()
        startdate=self.cal_select1.get_date().strftime('%Y-%m-%d')
        enddate=self.cal_select2.get_date().strftime('%Y-%m-%d')
        self.FPY_result.delete("1.0", tk.END)
        self.Fail_result.delete("1.0", tk.END)
        self.FPY_result.insert(tk.END, f"{project}：\n")
        self.FPY_result.insert(tk.END, f"日期范围: [{startdate}] 至 [{enddate}]\n\n")

        if not check_date(startdate,enddate):
            return
        else:
            stations_config = load_stations_config()
            project_list = stations_config.sections()
            if project in project_list:              
                # 计算各工站一次通过率并输出显示
                results = []            
                fpy_results = calculate_each_project_FPY(project, startdate, enddate)
                if fpy_results:
                    if project in ['ICCU1', 'ICCU2']:
                        eol_value = None
                        for station_name, project_result in fpy_results.items():
                            if station_name == 'EOL':
                                eol_value = (station_name, project_result)
                            else:
                                rate = round(project_result, 4)
                                results.append(rate)
                                self.FPY_result.insert(tk.END, f"{station_name}: {round(rate*100,4)}%\n")
                        
                        if eol_value:
                            station_name, project_result = eol_value
                            rate = round(project_result, 4)
                            results.append(rate)
                            self.FPY_result.insert(tk.END, f"{station_name}: {round(rate*100,4)}%\n")
                    else:
                        for station_name, project_result in fpy_results.items():
                            rate = round(project_result, 4)
                            results.append(rate)
                            self.FPY_result.insert(tk.END, f"{station_name}: {round(rate*100,4)}%\n")
                    
                    # 计算总通过率并输出显示
                    totally_result = 1.0
                    for rate in results:
                        totally_result *= rate
                    totally_result = round(totally_result, 4)
                    self.FPY_result.insert(tk.END, f"Totally: {round(totally_result*100,4)}%")
                else:
                    self.FPY_result.insert(tk.END, f"未计算出FPY数据，请检查数据库配置或日期范围")
                
                # 获取失败信息TOP5
                failure_results = extract_failure_info(project, startdate, enddate)
                if failure_results:
                    self.Fail_result.insert(tk.END, f"{project}：\n")
                    self.Fail_result.insert(tk.END, f"日期范围: [{startdate}] 至 [{enddate}]\n\n")
                    
                    # 先显示除EOL外的工站
                    eol_data = None
                    for station_name, step_dict in failure_results.items():
                        if station_name == 'EOL':
                            eol_data = (station_name, step_dict)
                        else:
                            if step_dict:
                                sorted_steps = sorted(step_dict.items(), key=lambda x: x[1], reverse=True)[:5]
                                step_str = "; ".join([f"{step}, {count}" for step, count in sorted_steps])
                                self.Fail_result.insert(tk.END, f"{station_name}: {step_str}\n")
                            else:
                                self.Fail_result.insert(tk.END, f"{station_name}: 无失败数据\n")
                    
                    # 最后显示EOL工站
                    if eol_data:
                        station_name, step_dict = eol_data
                        if step_dict:
                            sorted_steps = sorted(step_dict.items(), key=lambda x: x[1], reverse=True)[:5]
                            step_str = "; ".join([f"{step}, {count}" for step, count in sorted_steps])
                            self.Fail_result.insert(tk.END, f"{station_name}: {step_str}\n\n")
                        else:
                            self.Fail_result.insert(tk.END, f"{station_name}: 无失败数据\n\n")
                else:
                    self.Fail_result.insert(tk.END, f"未获取到失败信息数据")
    
      #定义数据存储为txt文件，~~作者太懒了~~想存excel格式的话下次再补充代码   
    def store_file_txt(self):
        file=None
        content_FPY=self.FPY_result.get("1.0", tk.END)
        content_Fail=self.Fail_result.get("1.0", tk.END)  
        content=content_FPY+"\n"+content_Fail              #获取输出框的内容并在后续写入的txt文件里
        if not content:
            return
        # 弹出文件保存对话框选择存储路径
        file_path = filedialog.asksaveasfilename(
        defaultextension=".txt",  # 默认后缀为txt
        filetypes=[("txt文件", "*.txt"), ("所有文件", "*.*")], #定义下拉框可选选项
        initialfile=self.Default_FileName,                      #定义"文件名"输入框的默认显示内容
        title="选择txt文件保存位置")                            #设置对话框的窗口标题
        
        if not file_path:
            return
        try:
            with open(file_path, "w", encoding="utf-8") as f:  # 使用用户选择的文件路径
                f.write(content)
            messagebox.showinfo("提示","数据已成功写入文件")
        
        except IOError as e:
            print(f"写入文件时出错:{e}")
            import traceback
            traceback.print_exc()     # 打印堆栈，定位文件错误原因
 
    def clear_all(self):
        #清空所有输入和结果框
        self.FPY_result.delete("1.0", tk.END)
        self.Fail_result.delete("1.0", tk.END)

if __name__ == "__main__":    # 创建主窗口并运行
    root = tk.Tk()
    app = FPY_LC(root)
    root.mainloop()