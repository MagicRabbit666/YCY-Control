"""
YCY 设备控制 GUI 界面
基于 Tkinter
"""

import tkinter as tk
from tkinter import ttk, messagebox
import asyncio
import threading
import queue
from core import YCY_FJB_Device, RandomController

class YCYControlGUI:
    """
    YCY 设备控制 GUI 类
    """

    def __init__(self, root):
        """
        初始化 GUI 界面

        参数：
        root: Tkinter 根窗口
        """
        self.root = root
        self.root.title("YCY 设备控制中心")
        self.root.geometry("1200x900")
        self.root.resizable(True, True)

        # 设置主题
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # 配置样式
        self.style.configure('TButton', font=('Helvetica', 10), padding=5)
        self.style.configure('TLabel', font=('Helvetica', 10))
        self.style.configure('TEntry', font=('Helvetica', 10))
        self.style.configure('TFrame', padding=10)
        self.style.configure('Header.TLabel', font=('Helvetica', 12, 'bold'))
        self.style.configure('Status.TLabel', font=('Helvetica', 10, 'italic'))

        # 初始化变量
        self.device = None
        self.controller = None
        self.loop = None
        self.thread = None
        self.queue = queue.Queue()
        self.is_connected = False
        self.is_random_running = False
        # 基础控制配置暂存
        self.basic_config = {
            'speed': {'A': 0, 'B': 0, 'C': 0},
            'mode': {'A': 0, 'B': 0, 'C': 0}
        }
        # 记录每个通道最后输入的类型和时间戳
        self.last_input = {
            'A': {'type': None, 'timestamp': 0},
            'B': {'type': None, 'timestamp': 0},
            'C': {'type': None, 'timestamp': 0}
        }

        # 创建主界面
        self.create_main_window()

        # 启动异步事件循环线程
        self.start_event_loop()

        # 定期检查队列
        self.root.after(100, self.check_queue)

    def start_event_loop(self):
        """
        启动异步事件循环线程
        """
        def run_event_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            try:
                self.loop.run_forever()
            finally:
                self.loop.close()

        self.thread = threading.Thread(target=run_event_loop, daemon=True)
        self.thread.start()

    def check_queue(self):
        """
        检查队列中的任务
        """
        try:
            while not self.queue.empty():
                task = self.queue.get(block=False)
                if callable(task):
                    task()
                self.queue.task_done()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.check_queue)

    def create_main_window(self):
        """
        创建主窗口界面
        """
        # 主框架
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 顶部状态栏
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(0, 20))

        # 设备状态
        self.status_var = tk.StringVar(value="未连接设备")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, style='Status.TLabel')
        status_label.pack(side=tk.LEFT, padx=10)

        # 电池状态
        battery_status_frame = ttk.Frame(status_frame)
        battery_status_frame.pack(side=tk.RIGHT, padx=10)

        # 电池电量指示灯
        self.battery_canvas = tk.Canvas(battery_status_frame, width=16, height=16, highlightthickness=0)
        self.battery_canvas.pack(side=tk.LEFT, padx=5)
        self.update_battery_indicator(None)  # 初始状态

        # 电池电量显示
        self.battery_var = tk.StringVar(value="电池电量: 未知")
        battery_label = ttk.Label(battery_status_frame, textvariable=self.battery_var, style='Status.TLabel')
        battery_label.pack(side=tk.LEFT)

        # 设备连接区域
        connect_frame = ttk.LabelFrame(main_frame, text="设备连接", padding=15)
        connect_frame.pack(fill=tk.X, pady=(0, 20))

        connect_btn = ttk.Button(connect_frame, text="连接设备", command=self.connect_device)
        connect_btn.pack(side=tk.LEFT, padx=10)

        disconnect_btn = ttk.Button(connect_frame, text="断开连接", command=self.disconnect_device, state=tk.DISABLED)
        disconnect_btn.pack(side=tk.LEFT, padx=10)
        self.disconnect_btn = disconnect_btn

        # 临时停止按钮（居中放置）
        pause_frame = ttk.Frame(connect_frame)
        pause_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 创建临时停止按钮样式
        self.style.configure('Pause.TButton', background='#ADD8E6', font=('Helvetica', 11, 'bold'), padding=8)
        
        pause_btn = ttk.Button(pause_frame, text="临时停止（寸止）", command=self.temp_pause, style='Pause.TButton')
        pause_btn.pack(side=tk.TOP, expand=True, padx=20)
        self.pause_btn = pause_btn

        # 设备名称显示
        device_name_frame = ttk.Frame(connect_frame)
        device_name_frame.pack(side=tk.RIGHT, padx=10)

        ttk.Label(device_name_frame, text="设备名称:").pack(side=tk.LEFT, padx=5)
        self.device_name_var = tk.StringVar(value="YCY-FJB-03")
        device_name_label = ttk.Label(device_name_frame, textvariable=self.device_name_var, width=20, background="#f0f0f0", padding=(5, 2))
        device_name_label.pack(side=tk.LEFT, padx=5)

        # 主要控制区域
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.BOTH, expand=True)

        # 左侧：基础控制
        basic_control_frame = ttk.LabelFrame(control_frame, text="基础控制", padding=15)
        basic_control_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # 速率控制
        speed_frame = ttk.LabelFrame(basic_control_frame, text="速率控制", padding=10)
        speed_frame.pack(fill=tk.X, pady=(0, 15))

        # 旋转伸缩通道
        a_speed_frame = ttk.Frame(speed_frame)
        a_speed_frame.pack(fill=tk.X, pady=5)

        ttk.Label(a_speed_frame, text="旋转伸缩:", width=10).pack(side=tk.LEFT, padx=5)
        self.a_speed_var = tk.IntVar(value=0)
        a_speed_entry = ttk.Entry(a_speed_frame, textvariable=self.a_speed_var, width=10)
        a_speed_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(a_speed_frame, text="(0-40)").pack(side=tk.LEFT, padx=5)
        ttk.Button(a_speed_frame, text="设置", command=lambda: self.set_speed('A', self.a_speed_var.get())).pack(side=tk.RIGHT, padx=5)

        # 吮吸通道
        b_speed_frame = ttk.Frame(speed_frame)
        b_speed_frame.pack(fill=tk.X, pady=5)

        ttk.Label(b_speed_frame, text="吮吸:", width=10).pack(side=tk.LEFT, padx=5)
        self.b_speed_var = tk.IntVar(value=0)
        b_speed_entry = ttk.Entry(b_speed_frame, textvariable=self.b_speed_var, width=10)
        b_speed_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(b_speed_frame, text="(0-20)").pack(side=tk.LEFT, padx=5)
        ttk.Button(b_speed_frame, text="设置", command=lambda: self.set_speed('B', self.b_speed_var.get())).pack(side=tk.RIGHT, padx=5)

        # 震动通道
        c_speed_frame = ttk.Frame(speed_frame)
        c_speed_frame.pack(fill=tk.X, pady=5)

        ttk.Label(c_speed_frame, text="震动:", width=10).pack(side=tk.LEFT, padx=5)
        self.c_speed_var = tk.IntVar(value=0)
        c_speed_entry = ttk.Entry(c_speed_frame, textvariable=self.c_speed_var, width=10)
        c_speed_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(c_speed_frame, text="(0-20)").pack(side=tk.LEFT, padx=5)
        ttk.Button(c_speed_frame, text="设置", command=lambda: self.set_speed('C', self.c_speed_var.get())).pack(side=tk.RIGHT, padx=5)

        # 内建模式控制
        mode_frame = ttk.LabelFrame(basic_control_frame, text="内建模式控制", padding=10)
        mode_frame.pack(fill=tk.X)

        # 旋转伸缩模式
        a_mode_frame = ttk.Frame(mode_frame)
        a_mode_frame.pack(fill=tk.X, pady=5)

        ttk.Label(a_mode_frame, text="旋转伸缩:", width=10).pack(side=tk.LEFT, padx=5)
        self.a_mode_var = tk.IntVar(value=0)
        a_mode_entry = ttk.Entry(a_mode_frame, textvariable=self.a_mode_var, width=10)
        a_mode_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(a_mode_frame, text="(0-7)").pack(side=tk.LEFT, padx=5)
        ttk.Button(a_mode_frame, text="设置", command=lambda: self.set_mode('A', self.a_mode_var.get())).pack(side=tk.RIGHT, padx=5)

        # 吮吸模式
        b_mode_frame = ttk.Frame(mode_frame)
        b_mode_frame.pack(fill=tk.X, pady=5)

        ttk.Label(b_mode_frame, text="吮吸:", width=10).pack(side=tk.LEFT, padx=5)
        self.b_mode_var = tk.IntVar(value=0)
        b_mode_entry = ttk.Entry(b_mode_frame, textvariable=self.b_mode_var, width=10)
        b_mode_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(b_mode_frame, text="(0-7)").pack(side=tk.LEFT, padx=5)
        ttk.Button(b_mode_frame, text="设置", command=lambda: self.set_mode('B', self.b_mode_var.get())).pack(side=tk.RIGHT, padx=5)

        # 震动模式
        c_mode_frame = ttk.Frame(mode_frame)
        c_mode_frame.pack(fill=tk.X, pady=5)

        ttk.Label(c_mode_frame, text="震动:", width=10).pack(side=tk.LEFT, padx=5)
        self.c_mode_var = tk.IntVar(value=0)
        c_mode_entry = ttk.Entry(c_mode_frame, textvariable=self.c_mode_var, width=10)
        c_mode_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(c_mode_frame, text="(0-7)").pack(side=tk.LEFT, padx=5)
        ttk.Button(c_mode_frame, text="设置", command=lambda: self.set_mode('C', self.c_mode_var.get())).pack(side=tk.RIGHT, padx=5)

        # 控制按钮
        control_buttons_frame = ttk.Frame(basic_control_frame)
        control_buttons_frame.pack(fill=tk.X, pady=10)

        start_btn = ttk.Button(control_buttons_frame, text="启动", command=self.start_basic_control)
        start_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        stop_btn = ttk.Button(control_buttons_frame, text="全部停止", command=self.stop_all_controls)
        stop_btn.pack(side=tk.RIGHT, padx=5, fill=tk.X, expand=True)

        # 说明区域
        info_frame = ttk.LabelFrame(basic_control_frame, text="说明", padding=10)
        info_frame.pack(fill=tk.X, pady=10)

        info_text = """
        使用说明：
        1. 速率控制：手动控制各模式的运行速度，范围0-20，0为停止
        2. 内建模式控制：手动控制各模式的机身内建模式，可选模式1-7，0为停止
        3. 同一个通道，速率控制和模式控制只发一个值给机器
        4. 哪个通道不为0发哪个
        5. 如果都不为0，选择最后输入的那个
        6. 点击"设置"按钮暂存配置，点击"启动"按钮应用配置
        7. 本程序为2.0杯杯制作，1.0理论上可用，但1.0本身无吮吸及震动功能，也无反转功能。
        8. 临时停止（寸止）功能是个好功能，但建议不要太过依赖这个按钮阻止自己强力喷射。
        """

        ttk.Label(info_frame, text=info_text, justify=tk.LEFT, wraplength=800).pack(fill=tk.X)

        # 右侧：随机控制和设备信息
        right_frame = ttk.Frame(control_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        # 随机控制
        random_frame = ttk.LabelFrame(right_frame, text="随机控制", padding=15)
        random_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # 随机模式选择
        mode_frame = ttk.Frame(random_frame)
        mode_frame.pack(fill=tk.X, pady=10)

        ttk.Label(mode_frame, text="模式:").pack(side=tk.LEFT, padx=5)
        self.random_mode_var = tk.StringVar(value="speed")
        # 创建下拉框，使用中文选项
        mode_combo = ttk.Combobox(mode_frame, width=15)
        mode_combo['values'] = ["随机速率模式", "随机内建模式"]
        mode_combo.current(0)  # 默认选择第一个
        mode_combo.pack(side=tk.LEFT, padx=5)
        # 设置下拉框选择事件
        mode_combo.bind('<<ComboboxSelected>>', self.on_mode_selected)

        # 随机速率模式上下限设置
        limits_frame = ttk.LabelFrame(random_frame, text="随机速率模式上下限设置", padding=10)
        limits_frame.pack(fill=tk.BOTH, expand=True)

        # 旋转伸缩范围
        a_limit_frame = ttk.Frame(limits_frame)
        a_limit_frame.pack(fill=tk.X, pady=5)

        ttk.Label(a_limit_frame, text="旋转伸缩:", width=10).pack(side=tk.LEFT, padx=5)
        self.a_min_var = tk.IntVar(value=0)
        self.a_max_var = tk.IntVar(value=20)
        ttk.Entry(a_limit_frame, textvariable=self.a_min_var, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Label(a_limit_frame, text="-").pack(side=tk.LEFT, padx=5)
        ttk.Entry(a_limit_frame, textvariable=self.a_max_var, width=5).pack(side=tk.LEFT, padx=5)

        # 吮吸范围
        b_limit_frame = ttk.Frame(limits_frame)
        b_limit_frame.pack(fill=tk.X, pady=5)

        ttk.Label(b_limit_frame, text="吮吸:", width=10).pack(side=tk.LEFT, padx=5)
        self.b_min_var = tk.IntVar(value=0)
        self.b_max_var = tk.IntVar(value=20)
        ttk.Entry(b_limit_frame, textvariable=self.b_min_var, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Label(b_limit_frame, text="-").pack(side=tk.LEFT, padx=5)
        ttk.Entry(b_limit_frame, textvariable=self.b_max_var, width=5).pack(side=tk.LEFT, padx=5)

        # 震动范围
        c_limit_frame = ttk.Frame(limits_frame)
        c_limit_frame.pack(fill=tk.X, pady=5)

        ttk.Label(c_limit_frame, text="震动:", width=10).pack(side=tk.LEFT, padx=5)
        self.c_min_var = tk.IntVar(value=0)
        self.c_max_var = tk.IntVar(value=20)
        ttk.Entry(c_limit_frame, textvariable=self.c_min_var, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Label(c_limit_frame, text="-").pack(side=tk.LEFT, padx=5)
        ttk.Entry(c_limit_frame, textvariable=self.c_max_var, width=5).pack(side=tk.LEFT, padx=5)

        # 随机控制按钮
        random_buttons_frame = ttk.Frame(random_frame)
        random_buttons_frame.pack(fill=tk.X, pady=10)

        self.start_random_btn = ttk.Button(random_buttons_frame, text="启动随机控制", command=self.start_random_control)
        self.start_random_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        self.stop_random_btn = ttk.Button(random_buttons_frame, text="停止随机控制", command=self.stop_random_control, state=tk.DISABLED)
        self.stop_random_btn.pack(side=tk.RIGHT, padx=5, fill=tk.X, expand=True)

        # 设备信息
        info_frame = ttk.LabelFrame(right_frame, text="设备信息", padding=15)
        info_frame.pack(fill=tk.BOTH, expand=True)

        # 设备信息显示
        self.device_info_var = tk.StringVar(value="点击'查看设备信息'按钮获取")
        info_text = tk.Text(info_frame, height=6, wrap=tk.WORD, state=tk.DISABLED)
        info_text.pack(fill=tk.BOTH, expand=True)
        self.info_text = info_text

        # 查看设备信息按钮
        info_btn = ttk.Button(info_frame, text="查看设备信息", command=self.get_device_info)
        info_btn.pack(fill=tk.X, pady=10)

    def on_mode_selected(self, event):
        """
        处理随机模式选择事件
        """
        combobox = event.widget
        value = combobox.get()
        if value == "随机速率模式":
            self.random_mode_var.set("speed")
        elif value == "随机内建模式":
            self.random_mode_var.set("mode")

    def show_connecting_dialog(self):
        """
        显示连接进度对话框
        """
        # 创建对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("连接设备")
        dialog.geometry("400x120")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (dialog.winfo_screenheight() // 2) - (120 // 2)
        dialog.geometry(f"400x120+{x}+{y}")

        # 标签
        label = ttk.Label(dialog, text="正在扫描并连接设备...", font=('Helvetica', 10))
        label.pack(pady=20)

        # 进度条
        progress = ttk.Progressbar(dialog, length=300, mode='indeterminate')
        progress.pack(pady=10)
        progress.start()

        return dialog, progress

    def connect_device(self):
        """
        连接设备
        """
        device_name = self.device_name_var.get()
        if not device_name:
            messagebox.showerror("错误", "请输入设备名称")
            return

        # 显示连接进度对话框
        dialog, progress = self.show_connecting_dialog()

        # 在异步线程中执行连接操作
        def connect_task():
            async def do_connect():
                self.device = YCY_FJB_Device(device_name)
                connected = await self.device.connect()
                
                # 关闭对话框
                self.queue.put(lambda:
                    self.close_connecting_dialog(dialog, progress)
                )
                
                if connected:
                    # 更新UI
                    self.queue.put(lambda:
                        self.on_device_connected()
                    )
                    # 获取设备信息
                    await asyncio.sleep(2)  # 等待通知
                    await self.get_device_info_async()
                else:
                    self.queue.put(lambda:
                        messagebox.showerror("错误", f"连接设备失败: {device_name}")
                    )
                    self.queue.put(lambda:
                        self.status_var.set("未连接设备")
                    )

            if self.loop:
                asyncio.run_coroutine_threadsafe(do_connect(), self.loop)

        threading.Thread(target=connect_task, daemon=True).start()

    def start_basic_control(self):
        """
        启动基础控制（应用暂存配置）
        """
        if not self.is_connected:
            messagebox.showinfo("提示", "请先连接设备")
            return

        print("开始执行基础控制配置...")

        # 在异步线程中执行操作
        def start_task():
            async def do_start():
                # 应用配置，根据逻辑决定发送哪个值
                for channel in ['A', 'B', 'C']:
                    speed_value = self.basic_config['speed'][channel]
                    mode_value = self.basic_config['mode'][channel]
                    last_type = self.last_input[channel]['type']

                    # 根据逻辑决定发送哪个值
                    if speed_value != 0 and mode_value != 0:
                        # 都不为0，选择最后输入的
                        if last_type == 'speed':
                            await self.device.set_speed(channel, speed_value)
                            print(f"{channel}通道: 发送速率值 {speed_value}（最后输入的是速率）")
                        elif last_type == 'mode':
                            await self.device.set_mode(channel, mode_value)
                            print(f"{channel}通道: 发送模式值 {mode_value}（最后输入的是模式）")
                        else:
                            # 默认发送速率值
                            await self.device.set_speed(channel, speed_value)
                            print(f"{channel}通道: 发送速率值 {speed_value}（默认）")
                    elif speed_value != 0:
                        # 只有速率不为0
                        await self.device.set_speed(channel, speed_value)
                        print(f"{channel}通道: 发送速率值 {speed_value}")
                    elif mode_value != 0:
                        # 只有模式不为0
                        await self.device.set_mode(channel, mode_value)
                        print(f"{channel}通道: 发送模式值 {mode_value}")
                    else:
                        # 都为0，不发送
                        print(f"{channel}通道: 速率和模式都为0，不发送指令")

                print("基础控制已启动，应用了暂存配置")

            if self.loop:
                asyncio.run_coroutine_threadsafe(do_start(), self.loop)

        threading.Thread(target=start_task, daemon=True).start()

    def stop_all_controls(self):
        """
        全部停止控制
        """
        if not self.is_connected:
            messagebox.showinfo("提示", "请先连接设备")
            return

        # 停止随机控制（如果正在运行）
        if self.is_random_running:
            self.stop_random_control()

        # 停止所有通道的控制
        def stop_task():
            async def do_stop():
                # 停止所有马达
                await self.device.set_speed('A', 0)
                await self.device.set_speed('B', 0)
                await self.device.set_speed('C', 0)
                await self.device.set_mode('A', 0)
                await self.device.set_mode('B', 0)
                await self.device.set_mode('C', 0)
                self.queue.put(lambda:
                    messagebox.showinfo("成功", "所有控制已停止")
                )

            if self.loop:
                asyncio.run_coroutine_threadsafe(do_stop(), self.loop)

        threading.Thread(target=stop_task, daemon=True).start()

    def temp_pause(self):
        """
        临时停止（寸止）功能
        停止10-30秒，然后恢复
        """
        if not self.is_connected:
            messagebox.showinfo("提示", "请先连接设备")
            return

        print("开始临时停止...")

        # 保存当前配置
        current_config = {
            'speed': {k: v for k, v in self.basic_config['speed'].items()},
            'mode': {k: v for k, v in self.basic_config['mode'].items()}
        }
        current_last_input = {
            k: {'type': v['type'], 'timestamp': v['timestamp']} 
            for k, v in self.last_input.items()
        }
        # 保存随机控制状态
        is_random_running = self.is_random_running
        random_controller = self.controller if self.is_random_running else None

        # 生成10-30秒的随机时间
        import random
        pause_time = random.randint(10, 30)
        print(f"临时停止时间: {pause_time}秒")

        # 在新线程中执行暂停和恢复操作
        def pause_task():
            async def do_pause():
                # 如果随机控制正在运行，停止它
                if is_random_running and random_controller:
                    print("暂停随机控制...")
                    await random_controller.stop()

                # 停止所有通道
                for channel in ['A', 'B', 'C']:
                    await self.device.set_speed(channel, 0)
                    await self.device.set_mode(channel, 0)

                # 等待随机时间
                await asyncio.sleep(pause_time)

                # 恢复之前的配置
                if is_random_running and random_controller:
                    # 恢复随机控制
                    print("恢复随机控制...")
                    # 重新启动随机控制，使用之前的模式和范围
                    try:
                        mode = self.random_mode_var.get()
                        if mode not in ['speed', 'mode']:
                            mode = 'speed'
                        limits = {
                            'A': (self.a_min_var.get(), self.a_max_var.get()),
                            'B': (self.b_min_var.get(), self.b_max_var.get()),
                            'C': (self.c_min_var.get(), self.c_max_var.get())
                        }
                        await random_controller.start(mode, limits, auto_loop=True)
                        print("随机控制已恢复")
                    except Exception as e:
                        print(f"恢复随机控制失败: {e}")
                else:
                    # 恢复基础控制配置
                    for channel in ['A', 'B', 'C']:
                        speed_value = current_config['speed'][channel]
                        mode_value = current_config['mode'][channel]
                        last_type = current_last_input[channel]['type']

                        # 根据之前的逻辑恢复配置
                        if speed_value != 0 and mode_value != 0:
                            if last_type == 'speed':
                                await self.device.set_speed(channel, speed_value)
                                print(f"恢复{channel}通道: 发送速率值 {speed_value}（最后输入的是速率）")
                            elif last_type == 'mode':
                                await self.device.set_mode(channel, mode_value)
                                print(f"恢复{channel}通道: 发送模式值 {mode_value}（最后输入的是模式）")
                            else:
                                await self.device.set_speed(channel, speed_value)
                                print(f"恢复{channel}通道: 发送速率值 {speed_value}（默认）")
                        elif speed_value != 0:
                            await self.device.set_speed(channel, speed_value)
                            print(f"恢复{channel}通道: 发送速率值 {speed_value}")
                        elif mode_value != 0:
                            await self.device.set_mode(channel, mode_value)
                            print(f"恢复{channel}通道: 发送模式值 {mode_value}")

                print(f"临时停止结束，已恢复控制")

            if self.loop:
                asyncio.run_coroutine_threadsafe(do_pause(), self.loop)

        threading.Thread(target=pause_task, daemon=True).start()

    def close_connecting_dialog(self, dialog, progress):
        """
        关闭连接进度对话框
        """
        progress.stop()
        dialog.destroy()

    def update_battery_indicator(self, battery_level):
        """
        电池电量指示灯

        参数：
        battery_level (int or None): 电池电量百分比
        """
        self.battery_canvas.delete("all")
        
        if battery_level is None:
            # 未知状态
            color = "#CCCCCC"  # 灰色
        elif battery_level <= 10:
            # 低电量
            color = "#FF4444"  # 红色
        elif battery_level <= 30:
            # 中电量
            color = "#FFAA00"  # 橙色
        else:
            # 高电量
            color = "#44AA44"  # 绿色
        
        # 绘制圆形指示灯
        self.battery_canvas.create_oval(2, 2, 14, 14, fill=color, outline="")

    def on_battery_update(self, battery_level):
        """
        电池电量更新回调
        """
        self.queue.put(lambda:
            self.battery_var.set(f"电池电量: {battery_level}%")
        )
        self.queue.put(lambda:
            self.update_battery_indicator(battery_level)
        )

    def on_device_connected(self):
        """
        设备连接成功后的回调
        """
        self.is_connected = True
        self.status_var.set(f"已连接设备: {self.device_name_var.get()}")
        self.disconnect_btn.config(state=tk.NORMAL)
        # 设置电池电量回调
        if self.device:
            self.device.battery_callback = self.on_battery_update
        messagebox.showinfo("成功", "设备连接成功！")

    def disconnect_device(self):
        """
        断开设备连接
        """
        if not self.is_connected:
            messagebox.showinfo("提示", "设备未连接")
            return

        # 停止随机控制
        if self.is_random_running:
            self.stop_random_control()

        # 在异步线程中执行断开操作
        def disconnect_task():
            async def do_disconnect():
                if self.device:
                    await self.device.disconnect()
                self.queue.put(lambda:
                    self.on_device_disconnected()
                )

            if self.loop:
                asyncio.run_coroutine_threadsafe(do_disconnect(), self.loop)

        threading.Thread(target=disconnect_task, daemon=True).start()

    def on_device_disconnected(self):
        """
        设备断开连接后的回调
        """
        self.is_connected = False
        self.status_var.set("未连接设备")
        self.battery_var.set("电池电量: 未知")
        self.disconnect_btn.config(state=tk.DISABLED)
        self.device = None
        messagebox.showinfo("成功", "设备已断开连接")

    def set_speed(self, channel, value):
        """
        设置通道速率（暂存配置）
        """
        if not self.is_connected:
            messagebox.showinfo("提示", "请先连接设备")
            return

        try:
            # 验证值范围
            if channel == 'A':
                if not 0 <= value <= 40:
                    raise ValueError("A通道速率必须在0-40之间")
            else:
                if not 0 <= value <= 20:
                    raise ValueError(f"{channel}通道速率必须在0-20之间")

            # 暂存配置
            self.basic_config['speed'][channel] = value
            # 更新时间戳
            import time
            self.last_input[channel]['type'] = 'speed'
            self.last_input[channel]['timestamp'] = time.time()
            print(f"已暂存{channel}通道速率配置: {value}")

        except ValueError as e:
            messagebox.showerror("错误", str(e))

    def set_mode(self, channel, value):
        """
        设置通道内建模式（暂存配置）
        """
        if not self.is_connected:
            messagebox.showinfo("提示", "请先连接设备")
            return

        try:
            # 验证值范围
            if not 0 <= value <= 7:
                raise ValueError("模式值必须在0-7之间")

            # 暂存配置
            self.basic_config['mode'][channel] = value
            # 更新时间戳
            import time
            self.last_input[channel]['type'] = 'mode'
            self.last_input[channel]['timestamp'] = time.time()
            print(f"已暂存{channel}通道模式配置: {value}")

        except ValueError as e:
            messagebox.showerror("错误", str(e))

    def start_random_control(self):
        """
        启动随机控制
        """
        if not self.is_connected:
            messagebox.showinfo("提示", "请先连接设备")
            return

        try:
            # 获取参数
            mode = self.random_mode_var.get()
            # 确保mode值正确
            if mode not in ['speed', 'mode']:
                # 默认使用speed模式
                mode = 'speed'
                self.random_mode_var.set('speed')
            limits = {
                'A': (self.a_min_var.get(), self.a_max_var.get()),
                'B': (self.b_min_var.get(), self.b_max_var.get()),
                'C': (self.c_min_var.get(), self.c_max_var.get())
            }

            # 验证参数
            for channel, (min_val, max_val) in limits.items():
                if channel == 'A':
                    if not (0 <= min_val <= max_val <= 40):
                        raise ValueError("A通道范围必须在0-40之间，且最小值≤最大值")
                else:
                    if not (0 <= min_val <= max_val <= 20):
                        raise ValueError(f"{channel}通道范围必须在0-20之间，且最小值≤最大值")

            # 创建控制器
            self.controller = RandomController(self.device)

            # 启动随机控制
            def start_task():
                async def do_start():
                    await self.controller.start(mode, limits, auto_loop=True)
                    self.queue.put(lambda:
                        self.on_random_control_started()
                    )

                if self.loop:
                    asyncio.run_coroutine_threadsafe(do_start(), self.loop)

            threading.Thread(target=start_task, daemon=True).start()

        except ValueError as e:
            messagebox.showerror("错误", str(e))

    def on_random_control_started(self):
        """
        随机控制启动后的回调
        """
        self.is_random_running = True
        self.start_random_btn.config(state=tk.DISABLED)
        self.stop_random_btn.config(state=tk.NORMAL)
        # 不显示弹窗，只在控制台打印
        print("随机控制已启动")

    def stop_random_control(self):
        """
        停止随机控制
        """
        if not self.is_random_running:
            messagebox.showinfo("提示", "随机控制未启动")
            return

        def stop_task():
            async def do_stop():
                if self.controller:
                    await self.controller.stop()
                self.queue.put(lambda:
                    self.on_random_control_stopped()
                )

            if self.loop:
                asyncio.run_coroutine_threadsafe(do_stop(), self.loop)

        threading.Thread(target=stop_task, daemon=True).start()

    def on_random_control_stopped(self):
        """
        随机控制停止后的回调
        """
        self.is_random_running = False
        self.start_random_btn.config(state=tk.NORMAL)
        self.stop_random_btn.config(state=tk.DISABLED)
        messagebox.showinfo("成功", "随机控制已停止")

    def get_device_info(self):
        """
        查看设备信息
        """
        if not self.is_connected:
            messagebox.showinfo("提示", "请先连接设备")
            return

        # 在异步线程中执行操作
        def get_info_task():
            if self.loop:
                asyncio.run_coroutine_threadsafe(self.get_device_info_async(), self.loop)

        threading.Thread(target=get_info_task, daemon=True).start()

    async def get_device_info_async(self):
        """
        异步获取设备信息
        """
        if self.device:
            info = await self.device.get_device_info()
            battery = await self.device.get_battery()

            info_text = "设备信息:\n"
            if info:
                info_text += f"产品ID: {info.get('product_id')}\n"
                info_text += f"版本: {info.get('version')}\n"
                info_text += f"A模式数量: {info.get('a_modes')}\n"
                info_text += f"B模式数量: {info.get('b_modes')}\n"
                info_text += f"C模式数量: {info.get('c_modes')}\n"
            else:
                info_text += "获取设备信息失败\n"

            if battery is not None:
                info_text += f"电池电量: {battery}%\n"
                self.queue.put(lambda:
                    self.battery_var.set(f"电池电量: {battery}%")
                )
                self.queue.put(lambda:
                    self.update_battery_indicator(battery)
                )
            else:
                info_text += "获取电池电量失败\n"

            self.queue.put(lambda:
                self.update_device_info(info_text)
            )

    def update_device_info(self, info_text):
        """
        更新设备信息显示
        """
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, info_text)
        self.info_text.config(state=tk.DISABLED)

    def on_closing(self):
        """
        窗口关闭时的处理
        """
        if self.is_connected:
            # 断开设备连接
            def close_task():
                async def do_close():
                    if self.device:
                        await self.device.disconnect()
                        # 等待操作完成
                        await asyncio.sleep(1)
                if self.loop:
                    asyncio.run_coroutine_threadsafe(do_close(), self.loop)
                    # 停止事件循环
                    self.loop.call_soon_threadsafe(self.loop.stop)

            threading.Thread(target=close_task, daemon=True).start()
            # 等待线程完成
            import time
            time.sleep(1)

        self.root.destroy()

if __name__ == "__main__":
    # 创建主窗口
    root = tk.Tk()
    app = YCYControlGUI(root)

    # 设置窗口关闭处理
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    # 启动主循环
    root.mainloop()
