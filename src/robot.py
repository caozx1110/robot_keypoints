import viser
from viser.extras import ViserUrdf
import numpy as np
import os
from pathlib import Path
from rich import print


from omegaconf import DictConfig


class Robot:
    def __init__(self, server: viser.ViserServer, cfg: DictConfig, name=None, opacity=1.0, use_urdf=True):
        self.server = server
        self.cfg = cfg
        self.name = name if name is not None else cfg.name
        self.opacity = opacity
        self.use_urdf = use_urdf
        self.joints = {}  # 存储关节句柄 name -> frame_handle
        self.urdf_loaded = False
        self.urdf_path = cfg.urdf_path
        self.fixed_urdf_path = cfg.fixed_urdf_path
        self.viser_urdf = None

        # 机器人尺寸参数
        self.body_dims = cfg.body_dims  # L, W, H
        self.hip_len = cfg.hip_len
        self.thigh_len = cfg.thigh_len
        self.calf_len = cfg.calf_len

        # 关节限制 (弧度) - 仅作参考，可视化可以宽松些
        self.limits = cfg.limits

    def setup(self):
        # 1. 创建躯干 (Base)
        # 抬高一点以便腿能伸展
        self.base = self.server.scene.add_frame(self.name, position=(0, 0, 0.4), show_axes=False)

        # 尝试加载 URDF
        if self.use_urdf and os.path.exists(self.urdf_path):
            try:
                # 修复 URDF 中的路径 (package:// -> ../)
                with open(self.urdf_path, "r") as f:
                    urdf_content = f.read()

                # 简单的字符串替换
                fixed_content = urdf_content.replace("package://go2_description/", "../")

                with open(self.fixed_urdf_path, "w") as f:
                    f.write(fixed_content)

                # 加载修复后的 URDF
                # 如果设置了 opacity，我们将其作为 mesh_color_override 传递
                # 注意：ViserUrdf 的 mesh_color_override 如果是 4 元组 (r, g, b, a)，则会覆盖颜色和透明度
                # 如果我们只想覆盖透明度而保留颜色，ViserUrdf 目前似乎不支持（它要么使用 mesh 颜色，要么完全覆盖）
                # 但为了实现 Ghost 效果，统一颜色（例如灰色）加透明度通常是可以接受的

                color_override = None
                if self.opacity < 0.99:
                    # 使用淡红色半透明
                    color_override = (0.8, 0.5, 0.5, self.opacity)

                self.viser_urdf = ViserUrdf(
                    self.server,
                    Path(self.fixed_urdf_path),
                    root_node_name=self.name,
                    mesh_color_override=color_override,
                )
                self.urdf_loaded = True
                print(f"[green]Loaded URDF from[/green] [bold]{self.fixed_urdf_path}[/bold]")

                # 获取关节名称列表以便后续更新
                self.joint_names = self.viser_urdf.get_actuated_joint_names()
                return
            except Exception as e:
                print(f"[red]Failed to load URDF: {e}[/red]")
                import traceback

                traceback.print_exc()

        # 如果没有 URDF，回退到几何体构建
        self._setup_geometric()

    def _setup_geometric(self):
        # 躯干几何体
        self.server.scene.add_box(
            f"{self.name}/body_geom",
            dimensions=self.body_dims,
            color=(0.8, 0.8, 0.8),
            position=(0, 0, 0),
            opacity=self.opacity,
        )

        # 2. 创建四条腿
        # FL, FR, RL, RR
        # 腿的安装位置 (相对于躯干中心)
        dx = self.body_dims[0] / 2 - 0.05
        dy = self.body_dims[1] / 2

        leg_configs = [
            {"name": "FL", "pos": (dx, dy, 0), "side": 1},
            {"name": "FR", "pos": (dx, -dy, 0), "side": -1},
            {"name": "RL", "pos": (-dx, dy, 0), "side": 1},
            {"name": "RR", "pos": (-dx, -dy, 0), "side": -1},
        ]

        for config in leg_configs:
            self._create_leg(config["name"], config["pos"], config["side"])

    def _create_leg(self, name, pos, side):
        # 1. Hip Joint (侧摆) - 绕 X 轴旋转
        # 髋关节基座位置
        hip_base_name = f"{self.name}/{name}_hip"
        hip_frame = self.server.scene.add_frame(
            hip_base_name, position=pos, axes_length=0.1, axes_radius=0.005, show_axes=True
        )
        self.joints[f"{name}_hip"] = hip_frame

        # Hip 连杆几何体
        self.server.scene.add_box(
            f"{hip_base_name}/geom",
            dimensions=(0.1, 0.04, 0.04),
            position=(0, side * self.hip_len / 2, 0),
            color=(0.3, 0.3, 0.3),
            opacity=self.opacity,
        )

        # 2. Thigh Joint (大腿) - 绕 Y 轴旋转
        # 连接在 Hip 的末端
        thigh_base_name = f"{hip_base_name}/thigh"
        thigh_frame = self.server.scene.add_frame(
            thigh_base_name, position=(0, side * self.hip_len, 0), show_axes=True, axes_length=0.1, axes_radius=0.005
        )
        self.joints[f"{name}_thigh"] = thigh_frame

        # Thigh 连杆几何体 (向下)
        # 假设初始状态是大腿垂直向下
        self.server.scene.add_box(
            f"{thigh_base_name}/geom",
            dimensions=(0.04, 0.04, self.thigh_len),
            position=(0, 0, -self.thigh_len / 2),
            color=(0.5, 0.5, 0.5),
            opacity=self.opacity,
        )

        # 3. Calf Joint (小腿) - 绕 Y 轴旋转
        # 连接在 Thigh 的末端
        calf_base_name = f"{thigh_base_name}/calf"
        calf_frame = self.server.scene.add_frame(
            calf_base_name, position=(0, 0, -self.thigh_len), show_axes=True, axes_length=0.1, axes_radius=0.005
        )
        self.joints[f"{name}_calf"] = calf_frame

        # Calf 连杆几何体
        self.server.scene.add_box(
            f"{calf_base_name}/geom",
            dimensions=(0.03, 0.03, self.calf_len),
            position=(0, 0, -self.calf_len / 2),
            color=(0.2, 0.2, 0.2),
            opacity=self.opacity,
        )

        # 足端 (Foot)
        self.server.scene.add_icosphere(
            f"{calf_base_name}/foot",
            radius=0.02,
            position=(0, 0, -self.calf_len),
            color=(0.1, 0.1, 0.1),
            opacity=self.opacity,
        )

    def update_base(self, pos, rpy):
        """
        pos: [x, y, z]
        rpy: [roll, pitch, yaw]
        """
        self.base.position = np.array(pos)
        # Euler to Quaternion (wxyz)
        # scipy Rotation is (x, y, z, w), viser uses (w, x, y, z)
        # We can implement simple conversion or use scipy if available
        # Here we use a simple helper or assume scipy is available in main context,
        # but better to keep it self-contained.

        # Simple Euler to Quat (XYZ order)
        roll, pitch, yaw = rpy

        cx = np.cos(roll / 2)
        sx = np.sin(roll / 2)
        cy = np.cos(pitch / 2)
        sy = np.sin(pitch / 2)
        cz = np.cos(yaw / 2)
        sz = np.sin(yaw / 2)

        w = cx * cy * cz + sx * sy * sz
        x = sx * cy * cz - cx * sy * sz
        y = cx * sy * cz + sx * cy * sz
        z = cx * cy * sz - sx * sy * cz

        self.base.wxyz = np.array([w, x, y, z])

    def update_pose(self, joint_angles):
        """
        joint_angles: dict { "FL_hip": rad, ... }
        """
        if self.urdf_loaded:
            # 准备配置数组
            # 映射: {name} -> {name}_joint
            # 需要按照 self.joint_names 的顺序构建数组
            cfg = []
            for j_name in self.joint_names:
                # j_name 类似于 "FL_hip_joint"
                # 我们的 joint_angles 键是 "FL_hip"
                # 尝试去掉 "_joint" 后缀来匹配
                short_name = j_name.replace("_joint", "")
                if short_name in joint_angles:
                    cfg.append(joint_angles[short_name])
                else:
                    cfg.append(0.0)  # 默认值

            self.viser_urdf.update_cfg(np.array(cfg))
            return

        # 几何体模式
        for name, angle in joint_angles.items():
            if name not in self.joints:
                continue

            frame = self.joints[name]

            # 根据关节类型确定旋转轴
            # Hip: 绕 X 轴 (Roll)
            # Thigh: 绕 Y 轴 (Pitch)
            # Calf: 绕 Y 轴 (Pitch)

            if "hip" in name:
                # quaternion for x-axis rotation
                frame.wxyz = self._angle_to_quat(angle, [1, 0, 0])
            else:
                # quaternion for y-axis rotation
                frame.wxyz = self._angle_to_quat(angle, [0, 1, 0])

    def _angle_to_quat(self, angle, axis):
        # axis-angle to quaternion (w, x, y, z)
        axis = np.array(axis)
        axis = axis / np.linalg.norm(axis)
        half_angle = angle / 2
        s = np.sin(half_angle)
        w = np.cos(half_angle)
        x, y, z = axis * s
        return np.array([w, x, y, z])

    def get_default_pose(self):
        # 返回一个默认的站立姿态
        return dict(self.cfg.default_pose)
