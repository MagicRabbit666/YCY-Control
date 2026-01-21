"""
控制面板
整合基础控制与随机控制模块，提供用户交互界面
"""

import asyncio
from core import YCY_FJB_Device, RandomController, start_random_control, stop_random_control

async def main():
    print("=== YCY 设备控制面板 ===")
    device = YCY_FJB_Device()
    
    try:
        # 连接设备
        print("正在连接设备...")
        if not await device.connect():
            print("连接失败，退出...")
            return
        
        print("设备连接成功！")
        
        # 主菜单循环
        while True:
            print("\n请选择操作：")
            print("1. 基础控制（手动设置速度/模式）")
            print("2. 随机控制（自动随机操作）")
            print("3. 查看设备信息")
            print("4. 断开连接并退出")
            
            choice = input("输入选项编号：").strip()
            
            if choice == "1":
                # 基础控制逻辑
                await handle_basic_control(device)
            elif choice == "2":
                # 随机控制逻辑
                await handle_random_control(device)
            elif choice == "3":
                # 查看设备信息
                await handle_device_info(device)
            elif choice == "4":
                # 断开连接并退出
                break
            else:
                print("无效选项，请重新输入！")
                
    finally:
        # 确保断开连接
        await device.disconnect()
        print("设备已断开，程序退出。")

async def handle_basic_control(device):
    """
    处理基础控制操作
    """
    print("\n=== 基础控制 ===")
    print("输入 'speed A 10' 设置A通道速度为10")
    print("输入 'mode B 3' 设置B通道模式为3")
    print("输入 'back' 返回主菜单")
    
    while True:
        cmd = input("命令：").strip()
        if cmd.lower() == "back":
            break
        
        parts = cmd.split()
        if len(parts) != 3:
            print("格式错误，请重新输入！")
            continue
        
        cmd_type, channel, value_str = parts
        try:
            value = int(value_str)
            if cmd_type == "speed":
                await device.set_speed(channel.upper(), value)
                print(f"已设置 {channel.upper()} 通道速度为 {value}")
            elif cmd_type == "mode":
                await device.set_mode(channel.upper(), value)
                print(f"已设置 {channel.upper()} 通道模式为 {value}")
            else:
                print("命令类型错误，支持 'speed' 和 'mode'")
        except ValueError as e:
            print(f"错误：{e}")

async def handle_random_control(device):
    """
    处理随机控制操作
    """
    print("\n=== 随机控制 ===")
    print("输入 'speed' 启动速度随机控制")
    print("输入 'mode' 启动模式随机控制")
    print("输入 'back' 返回主菜单")
    
    while True:
        cmd = input("命令：").strip()
        if cmd.lower() == "back":
            break
        
        if cmd not in ["speed", "mode"]:
            print("无效命令，支持 'speed' 和 'mode'")
            continue
        
        # 示例上下限
        limits = {
            "A": (0, 20),
            "B": (0, 15),
            "C": (0, 10)
        }
        
        controller = RandomController(device)
        await controller.start(cmd, limits, auto_loop=True)
        print(f"随机控制已启动（{cmd} 模式），按 Enter 停止...")
        
        # 等待用户输入停止
        input()
        await controller.stop()
        print("随机控制已停止")

async def handle_device_info(device):
    """
    处理设备信息查询
    """
    print("\n=== 设备信息 ===")
    info = await device.get_device_info()
    battery = await device.get_battery()
    
    if info:
        print(f"设备信息：{info}")
    else:
        print("获取设备信息失败")
    
    if battery is not None:
        print(f"电池电量：{battery}%")
    else:
        print("获取电池电量失败")

if __name__ == "__main__":
    # Windows 兼容
    if asyncio.get_event_loop_policy().__class__.__name__ == "WindowsSelectorEventLoopPolicy":
        pass  # 已兼容
    else:
        import sys
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
