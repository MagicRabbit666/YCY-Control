"""
YCY-FJB 设备控制模块

这是一个用于控制 YCY-FJB 系列蓝牙设备的Python模块。
模块基于Bleak库实现，提供异步API用于设备连接、控制和监控。

主要功能：
- 自动扫描并连接指定名称的蓝牙设备
- 支持速率控制（A/B/C马达）
- 支持模式控制（A/B/C马达）
- 获取设备信息和电池电量
- 异步通知处理

                   
API使用说明：
1. 初始化设备对象：device = YCY_FJB_Device()
2. 连接设备：await device.connect()
3. 控制马达：
   - 设置速率：await device.set_speed('A', 10)  # A马达速率10
   - 设置模式：await device.set_mode('B', 3)    # B马达模式3
4. 获取信息：
   - 获取设备信息：info = await device.get_device_info()
   - 获取电池电量：battery = await device.get_battery()
5. 断开连接：await device.disconnect()

注意：
- 所有操作都是异步的，需要使用await
- 马达速率范围：A(0-40)，B/C(0-20)
- 模式范围：0-7 (0=关闭)
- A马达：0-20正转，21-40反转
- B马达：0=放气，1=不吸不放，2-20吸气
"""

import asyncio
from bleak import BleakScanner, BleakClient
import sys

# 根据协议定义UUID
SERVICE_UUID = "0000ff40-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID = "0000ff41-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR_UUID = "0000ff42-0000-1000-8000-00805f9b34fb"

def calculate_checksum(data):
    """
    计算校验和：所有字节的和取模256

    参数：
    data (list): 数据字节列表

    返回：
    int: 校验和
    """
    return sum(data) % 256

class YCY_FJB_Device:
    """
    YCY-FJB 设备控制类

    封装了与设备的蓝牙通信，提供易用的API接口。
    """

    def __init__(self, device_name="YCY-FJB-03"):
        """
        初始化设备对象

        参数：
        device_name (str): 目标设备名称，默认为"YCY-FJB-03"
        """
        self.device_name = device_name
        self.client = None
        self.device_info = None
        self.current_levels = {'A': 0, 'B': 0, 'C': 0}
        self.battery_level = None
        self._connected = False
        self.battery_callback = None

    async def notification_handler(self, sender, data):
        """
        处理从设备接收到的通知数据

        参数：
        sender: 发送者
        data: 接收到的数据字节
        """
        data_list = list(data)
        if len(data_list) < 3 or data_list[0] != 0x35:
            print("接收到无效数据")
            return

        cmd = data_list[1]
        checksum = data_list[-1]
        if checksum != calculate_checksum(data_list[:-1]):
            print("校验和不匹配")
            return

        if cmd == 0x10:  # 设备信息响应
            if len(data_list) == 10:
                product_id = data_list[2]
                version = data_list[3]
                a_modes = data_list[4]
                b_modes = data_list[5]
                c_modes = data_list[6]
                self.device_info = {
                    'product_id': product_id,
                    'version': version,
                    'a_modes': a_modes,
                    'b_modes': b_modes,
                    'c_modes': c_modes
                }
                print(f"设备信息: 产品ID={product_id}, 版本={version}, "
                      f"A模式数量={a_modes}, B模式数量={b_modes}, C模式数量={c_modes}")
            else:
                print("设备信息长度无效")
        elif cmd == 0x13:  # 电量上报
            if len(data_list) == 5 and data_list[2] == 0x01:
                battery = data_list[3]
                self.battery_level = battery
                print(f"电池电量: {battery}%")
                # 调用电池电量回调
                if self.battery_callback:
                    self.battery_callback(battery)
            else:
                print("电量上报长度无效")
        else:
            if cmd == 0x14 and len(data_list) == 3 and data_list == [0x35, 0x14, 0x49]:
                # 心跳包，静默忽略，不打印
                pass
            else:
                print(f"未知命令: {cmd:02x}, 完整数据: {data_list}")

    async def connect(self):
        """
        扫描并连接到设备

        返回：
        bool: 连接是否成功
        """
        print("正在扫描设备...")
        devices = await BleakScanner.discover(timeout=10.0)

        target_device = None
        for d in devices:
            print(f"发现设备: {d.name} ({d.address})")
            if d.name == self.device_name:
                target_device = d
                break

        if not target_device:
            print(f"未找到名为 '{self.device_name}' 的设备")
            return False

        print(f"正在连接到 {target_device.name} ({target_device.address})")

        self.client = BleakClient(target_device)
        await self.client.connect()

        if not self.client.is_connected:
            print("连接失败")
            return False

        print("已连接。启动通知...")
        await self.client.start_notify(NOTIFY_CHAR_UUID, self.notification_handler)

        self._connected = True
        return True

    async def disconnect(self):
        """
        断开与设备的连接
        """
        if self.client and self.client.is_connected:
            # 退出时关闭所有马达
            await self.set_speed('A', 0)
            await self.set_speed('B', 0)
            await self.set_speed('C', 0)
            await self.set_mode('A', 0)
            await self.set_mode('B', 0)
            await self.set_mode('C', 0)
            await self.client.disconnect()
            print("已断开连接")
        self._connected = False

    async def get_device_info(self):
        """
        获取设备信息

        返回：
        dict or None: 设备信息字典，包含product_id, version, a_modes, b_modes, c_modes
        """
        if not self._connected:
            print("设备未连接")
            return None

        # 发送设备信息查询命令
        header = 0x35
        cmd = 0x10
        data = [header, cmd]
        checksum = calculate_checksum(data)
        data.append(checksum)
        await self.client.write_gatt_char(WRITE_CHAR_UUID, bytes(data))
        print("已发送设备信息查询")

        # 等待响应
        await asyncio.sleep(2)
        return self.device_info

    async def get_battery(self):
        """
        获取电池电量

        返回：
        int or None: 电池电量百分比
        """
        if not self._connected:
            print("设备未连接")
            return None

        # 电量是自动上报的，这里返回当前值
        return self.battery_level

    async def set_speed(self, motor, level):
        """
        设置马达速率

        参数：
        motor (str): 马达标识 ('A', 'B', 'C')
        level (int): 速率级别
                     A: 0-40 (0=关闭, 1-20正转, 21-40反转)
                     B: 0-20 (0=放气, 1=不吸不放, 2-20吸气)
                     C: 0-20 (0=关闭)

        抛出：
        ValueError: 参数无效
        """
        if motor not in ['A', 'B', 'C']:
            raise ValueError("无效马达 (A/B/C)")

        if motor == 'A':
            if not 0 <= level <= 40:
                raise ValueError("A速率级别必须在0-40之间")
        else:
            if not 0 <= level <= 20:
                raise ValueError(f"{motor}速率级别必须在0-20之间")

        self.current_levels[motor] = level
        await self._send_speed_control()

    async def set_mode(self, motor, mode_value):
        """
        设置马达模式

        参数：
        motor (str): 马达标识 ('A', 'B', 'C')
        mode_value (int): 模式值 (0-7, 0=关闭)

        抛出：
        ValueError: 参数无效
        """
        if motor not in ['A', 'B', 'C']:
            raise ValueError("无效马达 (A/B/C)")

        if not 0 <= mode_value <= 7:
            raise ValueError("模式必须在0-7之间")

        await self._send_mode_control(motor, mode_value)

    async def _send_speed_control(self):
        """
        发送速率控制命令到设备（内部方法）
        """
        if not self._connected:
            raise RuntimeError("设备未连接")

        header = 0x35
        cmd = 0x12
        a_level = self.current_levels['A']
        b_level = self.current_levels['B']
        c_level = self.current_levels['C']
        data = [header, cmd, a_level, b_level, c_level]
        checksum = calculate_checksum(data)
        data.append(checksum)
        await self.client.write_gatt_char(WRITE_CHAR_UUID, bytes(data))
        print(f"发送速率控制: A={a_level}, B={b_level}, C={c_level}")

    async def _send_mode_control(self, motor, mode_value):
        """
        发送固定模式控制命令到设备（内部方法）

        参数：
        motor (str): 马达标识
        mode_value (int): 模式值
        """
        if not self._connected:
            raise RuntimeError("设备未连接")

        header = 0x35
        cmd = 0x11
        if motor == 'A':
            motor_code = 0x01
        elif motor == 'B':
            motor_code = 0x12
        elif motor == 'C':
            motor_code = 0x14
        else:
            raise ValueError("无效马达")

        data = [header, cmd, motor_code, mode_value]
        checksum = calculate_checksum(data)
        data.append(checksum)
        await self.client.write_gatt_char(WRITE_CHAR_UUID, bytes(data))
        print(f"发送模式控制: {motor}马达 模式={mode_value}")

    @property
    def is_connected(self):
        """
        检查设备是否已连接

        返回：
        bool: 连接状态
        """
        return self._connected

# 如果直接运行此模块，提供简单的测试
if __name__ == "__main__":
    async def test():
        device = YCY_FJB_Device()
        try:
            connected = await device.connect()
            if connected:
                info = await device.get_device_info()
                print(f"设备信息: {info}")
                # 示例控制
                await device.set_speed('A', 10)
                await asyncio.sleep(2)
                await device.set_speed('A', 0)
        finally:
            await device.disconnect()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test())
