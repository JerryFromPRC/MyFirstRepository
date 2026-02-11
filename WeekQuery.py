# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date
import calendar
import threading
import time

class WeekQueryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("日期周数查询---by zhou11")
        self.root.geometry("350x400")
        self.root.resizable(False, False)
        
        self.center_window_on_top_right()
        
        self.current_date = datetime.now().date()
        self.selected_date = self.current_date    
        self.enter_target_time = 0
        self.leave_target_time = 0
        self.mouse_in_window = False
        self.monitoring = False
        self.monitor_thread = None
        self.transparency_thread = None
        self.lock = threading.Lock()
        
        self.create_ui()
        self.update_display()        
        self.setup_transparency()
    
    def center_window_on_top_right(self):
        self.root.update_idletasks()
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()        
        window_width = 350
        window_height = 400        
        x = screen_width - window_width - 20
        y = screen_height - window_height - 100
        
        self.root.geometry(str(window_width) + "x" + str(window_height) + "+" + str(x) + "+" + str(y))
    
    def setup_transparency(self):
        try:
            self.root.attributes('-alpha', 0.3)
            self.start_mouse_monitoring()
        except Exception as e:
            print("透明度设置错误: " + str(e))
    
    def start_mouse_monitoring(self):
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self.monitor_mouse_position, daemon=True)
        self.monitor_thread.start()
    
    def monitor_mouse_position(self):
        while self.monitoring:
            try:
                x = self.root.winfo_pointerx()  # 获取鼠标当前屏幕X坐标（像素）
                y = self.root.winfo_pointery()  # 获取鼠标当前屏幕Y坐标（像素）
                root_x = self.root.winfo_rootx()  # 获取窗口左上角屏幕X坐标
                root_y = self.root.winfo_rooty()  # 获取窗口左上角屏幕Y坐标
                width = self.root.winfo_width()  # 获取窗口当前实际宽度
                height = self.root.winfo_height()  # 获取窗口当前实际高度
                
                mouse_in = (root_x <= x <= root_x + width and 
                           root_y <= y <= root_y + height)  # 判断鼠标是否在窗口内
                
                if (mouse_in and not self.mouse_in_window):
                    with self.lock:
                        self.mouse_in_window = True
                        self.enter_target_time = time.time() + 0.5  # 延时0.5秒后显示
                    threading.Thread(target=self.wait_and_set_transparency, args=(1.0, True), daemon=True).start()
                    
                elif (not mouse_in and self.mouse_in_window):
                    with self.lock:
                        self.mouse_in_window = False
                        self.leave_target_time = time.time() + 0.5  # 延时0.5秒后隐藏
                    threading.Thread(target=self.wait_and_set_transparency, args=(0.3, False), daemon=True).start()
                
                time.sleep(0.1)
            except Exception as e:
                time.sleep(0.1)
    
    def wait_and_set_transparency(self, alpha, is_enter):
        target_time = self.enter_target_time if is_enter else self.leave_target_time
        current_time = time.time()
        wait_time = target_time - current_time  #动态计算等待时间，保证总延时为0.5s,避免线程执行导致的延迟加长0.5S的延时效果
        
        if wait_time > 0:
            time.sleep(wait_time)
        
        if self.monitoring:
            with self.lock:
                should_change = False
                if is_enter and self.mouse_in_window:
                    should_change = True
                elif not is_enter and not self.mouse_in_window:
                    should_change = True
                
                if should_change:
                    try:
                        self.root.after(0, lambda a=alpha: self.root.attributes('-alpha', a))
                    except Exception as e:
                        print("设置透明度错误: " + str(e))
    
    def create_ui(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = ttk.Label(main_frame, text="日期/周数查询工具", 
                           font=("微软雅黑", 11, "bold"))
        title_label.pack(pady=(0, 10))
        
        date_frame = ttk.Frame(main_frame)
        date_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(date_frame, text="当前日期:", 
                font=("微软雅黑", 9)).pack(side=tk.LEFT)
        
        self.date_label = ttk.Label(date_frame, text="", 
                                 font=("微软雅黑", 9, "bold"), 
                                 foreground="blue")
        self.date_label.pack(side=tk.LEFT, padx=10)
        
        week_frame = ttk.Frame(main_frame)
        week_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(week_frame, text="当前周数:", 
                font=("微软雅黑", 9)).pack(side=tk.LEFT)
        
        self.week_label = ttk.Label(week_frame, text="", 
                                  font=("微软雅黑", 9, "bold"), 
                                  foreground="red")
        self.week_label.pack(side=tk.LEFT, padx=10)
        
        week_select_frame = ttk.Frame(main_frame)
        week_select_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(week_select_frame, text="选择周数:", 
                font=("微软雅黑", 9)).pack(side=tk.LEFT)
        
        self.week_var = tk.StringVar()
        self.week_spinbox = ttk.Spinbox(week_select_frame, from_=1, to=53, 
                                       textvariable=self.week_var,
                                       width=5,
                                       font=("微软雅黑", 9))
        self.week_spinbox.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(week_select_frame, text="跳转到该周",
                 command=self.jump_to_week).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(week_select_frame, text="返回今天",
                 command=self.go_to_today).pack(side=tk.LEFT, padx=5)
        
        calendar_frame = ttk.Frame(main_frame)
        calendar_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(calendar_frame, text="日历 (点击日期查询周数)", 
                font=("微软雅黑", 9)).pack(pady=(0, 5))
        
        self.create_calendar(calendar_frame)  
    
    def create_calendar(self, parent):
        self.cal_frame = ttk.Frame(parent)
        self.cal_frame.pack(fill=tk.BOTH, expand=True)
        
        try:
            from tkcalendar import Calendar
            self.calendar = Calendar(self.cal_frame, 
                                   selectmode='day',
                                   year=self.selected_date.year,
                                   month=self.selected_date.month,
                                   day=self.selected_date.day,
                                   font=("微软雅黑", 8),
                                   locale='zh_CN',
                                   cursor="hand2")
            self.calendar.pack(fill=tk.BOTH, expand=True)
            self.calendar.bind("<<CalendarSelected>>", self.on_calendar_select)
        except ImportError:
            self.create_fallback_calendar()
    
    def create_fallback_calendar(self):
        year = self.selected_date.year
        month = self.selected_date.month
        
        month_frame = ttk.Frame(self.cal_frame)
        month_frame.pack(fill=tk.BOTH, expand=True)
        
        month_label = ttk.Label(month_frame, 
                             text=str(year) + "年" + str(month) + "月", 
                             font=("微软雅黑", 8, "bold"))
        month_label.grid(row=0, column=0, columnspan=7, pady=(0, 5))
        
        nav_frame = ttk.Frame(month_frame)
        nav_frame.grid(row=1, column=0, columnspan=7, pady=(0, 5))
        
        ttk.Button(nav_frame, text="◀ 上个月", 
                 command=self.previous_month).pack(side=tk.LEFT, padx=5)
        ttk.Button(nav_frame, text="下个月 ▶", 
                 command=self.next_month).pack(side=tk.LEFT, padx=5)
        
        weekdays = ['日', '一', '二', '三', '四', '五', '六']
        for i, day in enumerate(weekdays):
            label = ttk.Label(month_frame, text=day, 
                           font=("微软雅黑", 8))
            label.grid(row=2, column=i, padx=3, pady=3)
        
        cal = calendar.monthcalendar(year, month)
        
        today = datetime.now().date()
        
        for week_num, week in enumerate(cal, start=3):
            for day_num, day in enumerate(week):
                if day == 0:
                    continue
                
                day_date_obj = date(year, month, day)
                week_of_year = day_date_obj.isocalendar()[1]
                
                bg_color = "white"
                fg_color = "black"
                font_style = ("微软雅黑", 8)
                
                if day_date_obj == today:
                    bg_color = "lightblue"
                    fg_color = "white"
                    font_style = ("微软雅黑", 8, "bold")
                
                if day_date_obj == self.selected_date:
                    bg_color = "yellow"
                    fg_color = "black"
                    font_style = ("微软雅黑", 8, "bold")
                
                day_text = str(day)
                
                day_button = tk.Button(month_frame, text=day_text, 
                                   font=font_style,
                                   bg=bg_color, fg=fg_color,
                                   width=3, height=1,
                                   command=lambda d=day_date_obj: self.select_date(d))
                day_button.grid(row=week_num, column=day_num, padx=1, pady=1)
    
    def on_calendar_select(self, event):
        try:
            selected = self.calendar.selection_get()
            if selected:
                self.selected_date = selected
                self.update_display()
        except:
            pass
    
    def select_date(self, date_obj):
        self.selected_date = date_obj
        self.update_display()
        self.update_fallback_calendar()
    
    def update_fallback_calendar(self):
        if hasattr(self, 'calendar'):
            return
        
        for widget in self.cal_frame.winfo_children():
            widget.destroy()
        
        self.create_fallback_calendar()
    
    def update_display(self):
        date_str = self.selected_date.strftime("%Y年%m月%d日")
        self.date_label.config(text=date_str)
        
        week_num = self.selected_date.isocalendar()[1]
        self.week_label.config(text="第" + str(week_num) + "周")
        self.week_var.set(str(week_num))
    
    def go_to_today(self):
        self.selected_date = datetime.now().date()
        self.update_display()
        
        if hasattr(self, 'calendar'):
            self.calendar.selection_set(self.selected_date)
            self.calendar.focus_set()
        else:
            self.update_fallback_calendar()
    
    def previous_month(self):
        if self.selected_date.month == 1:
            self.selected_date = self.selected_date.replace(year=self.selected_date.year - 1, month=12)
        else:
            self.selected_date = self.selected_date.replace(month=self.selected_date.month - 1)
        self.update_display()
        self.update_fallback_calendar()
    
    def next_month(self):
        if self.selected_date.month == 12:
            self.selected_date = self.selected_date.replace(year=self.selected_date.year + 1, month=1)
        else:
            self.selected_date = self.selected_date.replace(month=self.selected_date.month + 1)
        self.update_display()
        self.update_fallback_calendar()
    
    def jump_to_week(self):
        try:
            week_num = int(self.week_var.get())
            if week_num < 1 or week_num > 53:
                messagebox.showerror("错误", "请输入1-53之间的周数")
                return
            
            year = self.selected_date.year
            
            for month in range(1, 13):
                cal = calendar.monthcalendar(year, month)
                for week in cal:
                    for day in week:
                        if day == 0:
                            continue
                        day_date = date(year, month, day)
                        if day_date.isocalendar()[1] == week_num:
                            self.selected_date = day_date
                            self.update_display()
                            
                            if hasattr(self, 'calendar'):
                                self.calendar.selection_set(self.selected_date)
                                self.calendar.focus_set()
                            else:
                                self.update_fallback_calendar()
                            return
            
            messagebox.showinfo("提示", "在" + str(year) + "年中未找到第" + str(week_num) + "周")
        
        except ValueError:
            messagebox.showerror("错误", "请输入有效的周数")

if __name__ == "__main__":
    root = tk.Tk()
    app = WeekQueryApp(root)
    root.mainloop()