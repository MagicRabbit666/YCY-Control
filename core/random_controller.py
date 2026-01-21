"""
随机化控制模块 (random_controller.py)

提供两种随机控制模式，支持 YCY-FJB 设备的自动化随机控制。

API 快速参考

1. 初始化控制器:
   controller = RandomController(device)  # device 是 YCY_FJB_Device 实例

2. 启动随机控制:
   await controller.start(mode, limits, auto_loop=True)
   # mode: 'speed' 或 'mode'
   # limits: {'A': (min, max), 'B': (min, max), 'C': (min, max)}
   # auto_loop: True=定时循环，False=不定时（执行一次后保持状态）

3. 停止随机控制:
   await controller.stop()

4. 获取状态:
   status = controller.status  # 返回 {'is_running': bool, 'mode': str, 'limits': dict}

5. 便捷函数:
   controller = await start_random_control(device, mode, limits)
   await stop_random_control(controller)

上下限传入方法

limits 参数是一个字典，包含A、B、C三个通道的上下限：

limits = {
    'A': (0, 15),   # A通道：最小值0，最大值15
    'B': (1, 10),   # B通道：最小值1，最大值10
    'C': (0, 8)     # C通道：最小值0，最大值8
}

注意：
- A通道范围：0-40（0=暂停，1-20=正转，21-40=反转）
- B通道范围：0-20（0=放气，1=不吸不放，2-20=吸气）
- C通道范围：0-20（震动强度）
- 最小值必须 ≤ 最大值

控制模式详解

速率控制模式 ('speed'):
- 调用 device.set_speed() API
- A通道: 0-40 (0=暂停, 1-20=正转, 21-40=反转)
- B通道: 0-20 (0=放气, 1=不吸不放, 2-20=吸气) + 自动放气定时器
- C通道: 0-20 (震动强度)

固定模式 ('mode'):
- 调用 device.set_mode() API
- 三个通道都使用 0-7 的模式值
- 0=关闭，其他值对应预设模式

随机算法特性

- 频率变化: 5-15秒之间随机 (包含小数，便于观察)
- 通道独立: A、B、C三个通道值相互独立，避免同时相同
- A通道智能: 根据上下限自动选择可用范围 (正转/反转/暂停)
- B通道安全: 吸气后自动在60%时间后放气，防止持续吸气
- 范围限制: 严格按照用户设置的上下限进行随机

使用示例

import asyncio
from core.ycy_fjb import YCY_FJB_Device
from core.random_controller import RandomController

async def example_auto_loop():
    '''自动循环模式示例'''
    device = YCY_FJB_Device()
    await device.connect()

    controller = RandomController(device)
    limits = {
        'A': (0, 15),   # A: 0-15 (暂停 + 正转0-15 + 反转21-35)
        'B': (1, 10),   # B: 1-10 (吸气强度)
        'C': (0, 8)     # C: 0-8 (震动强度)
    }

    # 启动自动循环（默认）
    await controller.start('speed', limits, auto_loop=True)

    # 运行 60 秒后停止
    await asyncio.sleep(60)
    await controller.stop()
    await device.disconnect()

async def example_continuous_execution():
    '''不定时模式示例（执行一次后保持状态）'''
    device = YCY_FJB_Device()
    await device.connect()

    controller = RandomController(device)
    limits = {
        'A': (5, 20),   # A: 5-20 (正转5-20)
        'B': (2, 8),    # B: 2-8 (吸气强度)
        'C': (10, 20)   # C: 10-20 (高强度震动)
    }

    # 不定时模式：执行一次随机动作，然后保持这个状态直到手动停止
    await controller.start('speed', limits, auto_loop=False)

    # 控制器会保持运行状态，设备会按照随机设置的值持续工作
    # 直到调用 controller.stop() 才会停止

    await device.disconnect()

注意事项

- 所有操作都是异步的，必须使用 await
- 上下限必须满足: A通道 0-40, B/C通道 0-20, 且 min <= max
- B通道放气时间为吸气时间的60%，范围 0.5-3秒
- 控制器会自动处理设备断开时的清理工作
- 支持多实例，但每个设备建议只创建一个控制器
"""

import asyncio
import random
import time
from typing import Dict, List, Optional, Tuple, Callable
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# 添加控制台处理器
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class RandomController:
    """
    随机控制类

    支持速率模式和固定模式的随机控制。
    """

    def __init__(self, device):
        """
        初始化随机控制器

        参数：
        device: YCY_FJB_Device 实例
        """
        self.device = device
        self.is_running = False
        self.mode = None  # 'speed' 或 'mode'
        self.limits = {'A': (0, 20), 'B': (1, 20), 'C': (0, 20)}  # 默认上下限
        self.auto_loop = True  # 是否自动循环
        self.task = None
        self.b_channel_timer = None  # B通道吸气定时器
        self.last_b_command_time = 0  # 最后发送B通道命令的时间

    async def start(self, mode: str, limits: Dict[str, Tuple[int, int]], auto_loop: bool = True):
        """
        启动随机控制

        参数：
        mode (str): 'speed' 或 'mode'
        limits (dict): 三个通道的上下限 {'A': (min, max), 'B': (min, max), 'C': (min, max)}
        auto_loop (bool): 是否定时循环，默认为True（定时）。False为不定时（执行一次后保持状态）

        抛出：
        ValueError: 参数无效
        """
        if mode not in ['speed', 'mode']:
            raise ValueError("模式必须是 'speed' 或 'mode'")

        if not all(channel in limits for channel in ['A', 'B', 'C']):
            raise ValueError("必须提供A、B、C三个通道的上下限")

        # 验证上下限
        for channel, (min_val, max_val) in limits.items():
            if channel == 'A':
                if not (0 <= min_val <= max_val <= 40):
                    raise ValueError(f"A通道上下限必须在0-40之间，且下限≤上限")
            else:
                if not (0 <= min_val <= max_val <= 20):
                    raise ValueError(f"{channel}通道上下限必须在0-20之间，且下限≤上限")

        self.mode = mode
        self.limits = limits
        self.auto_loop = auto_loop

        if self.is_running:
            await self.stop()

        self.is_running = True
        if auto_loop:
            self.task = asyncio.create_task(self._random_loop())
            logger.info(f"随机控制已启动，模式: {mode}，定时循环")
        else:
            # 不定时模式：执行一次后保持状态
            await self._execute_once()
            logger.info(f"随机控制已启动，模式: {mode}，不定时（保持当前状态）")

    async def stop(self):
        """
        停止随机控制
        """
        self.is_running = False
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        # 停止所有马达
        if self.mode == 'speed':
            await self.device.set_speed('A', 0)
            await self.device.set_speed('B', 0)
            await self.device.set_speed('C', 0)
        else:
            await self.device.set_mode('A', 0)
            await self.device.set_mode('B', 0)
            await self.device.set_mode('C', 0)

        # 取消B通道定时器
        if self.b_channel_timer:
            self.b_channel_timer.cancel()
            self.b_channel_timer = None

        logger.info("随机控制已停止")

    def _generate_random_value(self, channel: str, exclude_values: List[int] = None) -> int:
        """
        为指定通道生成随机值

        参数：
        channel (str): 通道 'A', 'B', 'C'
        exclude_values (list): 要排除的值列表

        返回：
        int: 随机值
        """
        min_val, max_val = self.limits[channel]
        exclude_values = exclude_values or []

        # A通道特殊处理
        if channel == 'A':
            # 0为暂停，1-20正转，21-40反转
            # 需要根据上下限计算实际可用的值范围
            possible_values = []

            # 如果下限为0，包含0（暂停）
            if min_val == 0:
                possible_values.append(0)

            # 计算正转范围
            forward_min = max(1, min_val)
            forward_max = min(20, max_val)
            if forward_min <= forward_max:
                possible_values.extend(range(forward_min, forward_max + 1))

            # 计算反转范围 (21-40对应实际的21-40)
            reverse_min = max(21, min_val)
            reverse_max = min(40, max_val)
            if reverse_min <= reverse_max:
                possible_values.extend(range(reverse_min, reverse_max + 1))

            # 移除排除的值
            possible_values = [v for v in possible_values if v not in exclude_values]

            if not possible_values:
                # 如果没有可用值，返回下限
                return min_val

            return random.choice(possible_values)
        else:
            # B和C通道直接从上下限范围内选择
            possible_values = [v for v in range(min_val, max_val + 1) if v not in exclude_values]
            if not possible_values:
                return min_val
            return random.choice(possible_values)

    def _generate_frequency_delay(self) -> float:
        """
        生成随机频率延迟（3-11秒）

        返回：
        float: 延迟时间（秒）
        """
        return random.uniform(3.0, 11.0)

    async def _handle_b_channel_exhale(self):
        """
        处理B通道放气（吸气后的自动放气）
        """
        try:
            if self.mode == 'speed':
                await self.device.set_speed('B', 0)
                logger.debug("B通道自动放气")
        except Exception as e:
            logger.error(f"B通道自动放气失败: {e}")

    async def _handle_b_channel_exhale_cycle(self, inhale_duration: float):
        """
        处理B通道循环结束后的放气

        参数：
        inhale_duration (float): 本次吸气持续时间（秒）
        """
        try:
            # 计算放气时间：吸气时间的60%
            exhale_duration = inhale_duration * 0.6
            exhale_duration = max(0.5, min(exhale_duration, 3.0))  # 限制在0.5-3秒

            logger.debug(f"B通道开始放气，持续时间: {exhale_duration:.1f}秒")

            # 发送放气命令（设置为0）
            await self.device.set_speed('B', 0)

            # 等待放气时间
            await asyncio.sleep(exhale_duration)

            logger.debug("B通道放气完成")

        except Exception as e:
            logger.error(f"B通道循环放气失败: {e}")

    async def _random_loop(self):
        """
        随机控制主循环
        """
        logger.info("随机控制主循环已启动")
        while self.is_running and self.auto_loop:
            try:
                logger.info(f"开始新一轮随机控制，模式: {self.mode}")
                if self.mode == 'speed':
                    await self._execute_speed_mode()
                elif self.mode == 'mode':
                    await self._execute_mode_mode()

                # 保持当前随机值一段时间（随机5-15s）
                hold_duration = self._generate_frequency_delay()
                logger.info(f"保持当前状态 {hold_duration:.1f} 秒")
                await asyncio.sleep(hold_duration)

                # Speed模式：循环结束放气
                if self.mode == 'speed':
                    logger.info("循环结束，开始放气")
                    await self._handle_b_channel_exhale_cycle(hold_duration)

            except Exception as e:
                logger.error(f"随机控制循环出错: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await asyncio.sleep(1)  # 出错后等待1秒再继续

    async def _execute_once(self):
        """
        执行单次随机控制
        """
        try:
            if self.mode == 'speed':
                await self._execute_speed_mode()
            elif self.mode == 'mode':
                await self._execute_mode_mode()

            # 保持10s观察
            await asyncio.sleep(10)

            # Speed模式放气
            if self.mode == 'speed':
                await self._handle_b_channel_exhale_cycle(10)

        except Exception as e:
            logger.error(f"单次随机控制执行出错: {e}")

    async def _execute_speed_mode(self):
        """
        执行速率模式随机控制
        """
        # 生成三个通道的值，不要求完全不同
        values = {}

        for channel in ['A', 'B', 'C']:
            values[channel] = self._generate_random_value(channel)

        # 发送命令到设备
        await self.device.set_speed('A', values['A'])
        await self.device.set_speed('C', values['C'])
        await self.device.set_speed('B', values['B'] if values['B'] > 0 else 0)
        
        # 记录吸气开始时间（如果需要）
        if values['B'] > 0:
            self.last_b_command_time = asyncio.get_event_loop().time()
        
        # 使用 info 级别日志，确保能看到执行信息
        logger.info(f"速率模式设置完成: A={values['A']}, B={values['B'] if values['B'] > 0 else 0}, C={values['C']}")

    async def _schedule_exhale(self, delay: float):
        """
        调度B通道放气

        参数：
        delay (float): 延迟时间（秒）
        """
        await asyncio.sleep(delay)
        await self._handle_b_channel_exhale()

    async def _execute_mode_mode(self):
        """
        执行固定模式随机控制
        """
        # 生成三个通道的模式值（1-7）
        values = {}

        for channel in ['A', 'B', 'C']:
            # 模式范围1-7，避免0关闭，不要求完全不同
            mode_value = random.randint(1, 7)
            values[channel] = mode_value

        # 发送模式命令
        for channel, mode_value in values.items():
            await self.device.set_mode(channel, mode_value)
            logger.debug(f"{channel}通道设置模式: {mode_value}")

    @property
    def status(self) -> Dict:
        """
        获取当前状态

        返回：
        dict: 状态信息
        """
        return {
            'is_running': self.is_running,
            'mode': self.mode,
            'limits': self.limits
        }

# 便捷函数
async def start_random_control(device, mode: str, limits: Dict[str, Tuple[int, int]]):
    """
    启动随机控制的便捷函数

    参数：
    device: YCY_FJB_Device 实例
    mode (str): 'speed' 或 'mode'
    limits (dict): 通道上下限

    返回：
    RandomController: 控制器实例
    """
    controller = RandomController(device)
    await controller.start(mode, limits)
    return controller

async def stop_random_control(controller: RandomController):
    """
    停止随机控制的便捷函数

    参数：
    controller (RandomController): 控制器实例
    """
    await controller.stop()
