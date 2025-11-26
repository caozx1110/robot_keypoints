# Robot Keypoints Animator

这是一个基于 [Viser](https://github.com/nerfstudio-project/viser) 的机器人关键帧动画编辑工具。支持可视化编辑机器人的关节姿态，生成关键帧动画，并导出为 JSON 文件。

## 目录结构

```
.
├── assets/                 # 机器人资源文件 (URDF, Meshes)
│   └── go2_description/    # Unitree Go2 描述文件
├── config/                 # Hydra 配置文件
│   ├── config.yaml         # 主配置
│   └── robot/              # 机器人特定配置
│       └── go2.yaml
├── src/                    # 源代码
│   ├── main.py             # 入口点
│   ├── app.py              # 应用逻辑
│   ├── gui.py              # 界面逻辑
│   ├── robot.py            # 机器人模型
│   └── animator.py         # 动画逻辑
├── animation.json          # 保存的动画文件示例
└── requirements.txt        # Python 依赖
```

## 安装

1.  **安装依赖**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **准备资源文件**:
    本项目需要机器人的 URDF 和模型文件。默认配置使用 Unitree Go2。
    
    资源来源: [unitreerobotics/unitree_ros](https://github.com/unitreerobotics/unitree_ros/tree/master/robots/go2_description)

    请确保 `assets/go2_description` 目录包含完整的文件。如果该目录为空，你可以使用以下命令下载（需要 `svn`）：

    ```bash
    # 确保 assets 目录存在
    mkdir -p assets
    # 下载 go2_description
    svn export https://github.com/unitreerobotics/unitree_ros/trunk/robots/go2_description assets/go2_description --force
    ```
    
    或者手动下载并解压到 `assets/go2_description`。

## 运行

启动应用程序：

```bash
python src/main.py
```

使用不同的机器人配置（如果在 `config/robot/` 下有其他配置）：

```bash
python src/main.py robot=my_robot
```

## 功能特性

*   **时间轴编辑**: 播放、暂停、循环、调整速度。
*   **关键帧管理**: 添加、更新、删除关键帧，支持多种插值算法。
*   **姿态编辑**: 
    *   直接拖动滑块调整关节角度。
    *   **Ghost 模式**: 显示上一帧或时间偏移的残影，方便调整动作衔接。
    *   **镜像工具**: 快速将左侧肢体姿态镜像到右侧，反之亦然。
    *   **复制/粘贴**: 在不同时间点之间复制姿态。
*   **保存/加载**: 将动画保存为 JSON 文件。
