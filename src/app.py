import time
import viser
import numpy as np
from rich import print
from omegaconf import DictConfig

from robot import Robot
from animator import Animator
from gui import GUI


class RobotAnimatorApp:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        self.server = viser.ViserServer(label="Robot Animator")
        self.server.gui.configure_theme(control_width="large")

        self._setup_css()
        self._setup_scene()

        # 1. 初始化机器人
        self.robot = Robot(self.server, cfg.robot)
        self.robot.setup()

        # 1.1 初始化 Ghost 机器人
        self.ghost_robot = Robot(self.server, cfg.robot, name="/ghost", opacity=0.5, use_urdf=True)
        self.ghost_robot.setup()
        self.ghost_robot.base.visible = False
        for joint in self.ghost_robot.joints.values():
            joint.visible = False

        # 2. 初始化动画器
        self.animator = Animator()

        # 初始姿态
        self.current_pose = self.robot.get_default_pose()
        self.current_base_pos = [0.0, 0.0, 0.4]
        self.current_base_rpy = [0.0, 0.0, 0.0]

        self.robot.update_pose(self.current_pose)
        self.robot.update_base(self.current_base_pos, self.current_base_rpy)

        # 3. GUI 状态
        self.gui_state = {"playing": False, "time": 0.0, "speed": 1.0, "loop": True, "duration": 2.0}

        # 4. 构建 GUI
        self.gui = GUI(self)
        self.gui.setup()

    def _setup_css(self):
        self.server.gui.add_html(
            """
        <style>
        :root {
            --mantine-font-size-xs: 14px;
            --mantine-font-size-sm: 16px;
            --mantine-font-size-md: 18px;
            --mantine-font-size-lg: 22px;
            --mantine-font-size-xl: 26px;
        }
        </style>
        """
        )

    def _setup_scene(self):
        self.server.scene.add_grid("ground_grid", width=20, height=20, cell_size=0.5)
        self.server.scene.add_box(
            "ground_plane",
            dimensions=(20, 20, 0.01),
            position=(0, 0, -0.005),
            color=(0.95, 0.95, 0.95),
        )

    def run(self):
        last_time = time.time()

        # 初始更新一次 Ghost
        self.gui.update_ghost_pose(self.gui_state["time"])

        while True:
            now = time.time()
            dt = now - last_time
            last_time = now

            if self.gui_state["playing"]:
                # 更新时间
                self.gui_state["time"] += dt * self.gui_state["speed"]

                # 循环处理
                if self.gui_state["time"] > self.gui_state["duration"]:
                    if self.gui_state["loop"]:
                        self.gui_state["time"] %= self.gui_state["duration"]
                    else:
                        self.gui_state["time"] = self.gui_state["duration"]
                        self.gui_state["playing"] = False
                        self.gui.update_play_pause_buttons()

                # 更新时间滑块
                self.gui.update_time_slider(self.gui_state["time"])

                # 计算并应用姿态
                if self.animator.keyframes:
                    pose, b_pos, b_rpy = self.animator.get_state_at_time(self.gui_state["time"])
                    self.robot.update_pose(pose)
                    self.robot.update_base(b_pos, b_rpy)

                    # 更新 Ghost
                    self.gui.update_ghost_pose(self.gui_state["time"])

                    # 更新滑块显示
                    self.gui.sync_sliders(pose, b_pos, b_rpy)

                    # 同步内部状态
                    self.current_pose.update(pose)
                    self.current_base_pos[:] = b_pos
                    self.current_base_rpy[:] = b_rpy

            time.sleep(0.01)
