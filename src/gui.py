import viser
import numpy as np
from rich import print


class GUI:
    def __init__(self, app):
        self.app = app
        self.server = app.server

        # UI Elements Storage
        self.joint_sliders = {}
        self.base_sliders = {}

        # Timeline Elements
        self.play_button = None
        self.pause_button = None
        self.time_slider = None
        self.keyframe_selector = None
        self.keyframe_info = None
        self.duration_number = None
        self.interp_dropdown = None

        # Ghost Elements
        self.show_ghost_checkbox = None
        self.ghost_mode_dropdown = None
        self.ghost_offset_slider = None

        # System Elements
        self.file_name_input = None

    def setup(self):
        tabs = self.server.gui.add_tab_group()

        with tabs.add_tab("Timeline", icon=viser.Icon.CLOCK):
            self._setup_timeline_tab()

        with tabs.add_tab("Pose", icon=viser.Icon.USER):
            self._setup_pose_tab()

        with tabs.add_tab("System", icon=viser.Icon.SETTINGS):
            self._setup_system_tab()

    def _setup_timeline_tab(self):
        with self.server.gui.add_folder("Playback"):
            self.play_button = self.server.gui.add_button("Play", icon=viser.Icon.PLAYER_PLAY)
            self.pause_button = self.server.gui.add_button("Pause", icon=viser.Icon.PLAYER_PAUSE, visible=False)
            stop_button = self.server.gui.add_button("Stop", icon=viser.Icon.PLAYER_STOP)

            loop_checkbox = self.server.gui.add_checkbox("Loop", initial_value=True)
            speed_slider = self.server.gui.add_slider("Speed", min=0.1, max=3.0, step=0.1, initial_value=1.0)

            self.time_slider = self.server.gui.add_slider(
                "Time", min=0.0, max=self.app.gui_state["duration"], step=0.01, initial_value=0.0
            )

            self.duration_number = self.server.gui.add_number("Duration (s)", initial_value=2.0, min=0.1, max=10.0)

            self.interp_dropdown = self.server.gui.add_dropdown(
                "Interpolation", options=["linear", "cubic", "zero", "slinear", "quadratic"], initial_value="linear"
            )

            # Callbacks
            @self.play_button.on_click
            def _(_):
                self.app.gui_state["playing"] = True
                self.update_play_pause_buttons()

            @self.pause_button.on_click
            def _(_):
                self.app.gui_state["playing"] = False
                self.update_play_pause_buttons()

            @stop_button.on_click
            def _(_):
                self.app.gui_state["playing"] = False
                self.app.gui_state["time"] = 0.0
                self.time_slider.value = 0.0
                self.update_play_pause_buttons()

            @loop_checkbox.on_update
            def _(event):
                self.app.gui_state["loop"] = event.target.value

            @speed_slider.on_update
            def _(event):
                self.app.gui_state["speed"] = event.target.value

            @self.time_slider.on_update
            def _(event):
                if not self.app.gui_state["playing"]:
                    t = event.target.value
                    self.app.gui_state["time"] = t
                    if self.app.animator.keyframes:
                        pose, b_pos, b_rpy = self.app.animator.get_state_at_time(t)
                        self.app.robot.update_pose(pose)
                        self.app.robot.update_base(b_pos, b_rpy)
                        self.sync_sliders(pose, b_pos, b_rpy)
                        self.update_ghost_pose(t)

                        # Sync app state
                        self.app.current_pose.update(pose)
                        self.app.current_base_pos[:] = b_pos
                        self.app.current_base_rpy[:] = b_rpy

            @self.duration_number.on_update
            def _(event):
                self.app.gui_state["duration"] = event.target.value
                self.app.animator.duration = event.target.value
                self.time_slider.max = event.target.value

            @self.interp_dropdown.on_update
            def _(event):
                self.app.animator.set_interpolation_method(event.target.value)

        with self.server.gui.add_folder("Keyframes"):
            add_keyframe_btn = self.server.gui.add_button("Add Keyframe", icon=viser.Icon.PLUS)
            update_keyframe_btn = self.server.gui.add_button("Update Selected Keyframe", icon=viser.Icon.REFRESH)
            delete_keyframe_btn = self.server.gui.add_button(
                "Delete Selected Keyframe", icon=viser.Icon.TRASH, color="red"
            )
            clear_keyframes_btn = self.server.gui.add_button("Clear All", icon=viser.Icon.TRASH)

            self.keyframe_selector = self.server.gui.add_dropdown(
                "Select Keyframe", options=["None"], initial_value="None"
            )
            self.keyframe_info = self.server.gui.add_text("Keyframes: 0", initial_value="Count: 0")

            @add_keyframe_btn.on_click
            def _(_):
                t = self.app.gui_state["time"]
                self.app.animator.add_keyframe(
                    t, self.app.current_pose, self.app.current_base_pos, self.app.current_base_rpy
                )
                self.keyframe_info.value = f"Count: {len(self.app.animator.keyframes)}"
                self.update_keyframe_dropdown()
                self.keyframe_selector.value = f"{t:.2f}s"
                print(f"[green]Added keyframe at {t:.2f}s[/green]")

            @update_keyframe_btn.on_click
            def _(_):
                if self.keyframe_selector.value == "None":
                    print("[yellow]No keyframe selected to update[/yellow]")
                    return
                try:
                    t = float(self.keyframe_selector.value.replace("s", ""))
                    self.app.animator.add_keyframe(
                        t, self.app.current_pose, self.app.current_base_pos, self.app.current_base_rpy
                    )
                    print(f"[green]Updated keyframe at {t:.2f}s[/green]")
                except ValueError:
                    print("[red]Invalid keyframe selection[/red]")

            @delete_keyframe_btn.on_click
            def _(_):
                if self.keyframe_selector.value == "None":
                    return
                try:
                    t = float(self.keyframe_selector.value.replace("s", ""))
                    idx_to_remove = -1
                    for i, k in enumerate(self.app.animator.keyframes):
                        if np.isclose(k["time"], t):
                            idx_to_remove = i
                            break
                    if idx_to_remove != -1:
                        self.app.animator.remove_keyframe(idx_to_remove)
                        self.keyframe_info.value = f"Count: {len(self.app.animator.keyframes)}"
                        self.update_keyframe_dropdown()
                        print(f"[red]Deleted keyframe at {t:.2f}s[/red]")
                except ValueError:
                    pass

            @clear_keyframes_btn.on_click
            def _(_):
                self.app.animator.clear_keyframes()
                self.keyframe_info.value = "Count: 0"
                self.update_keyframe_dropdown()
                print("[red]Cleared all keyframes[/red]")

            @self.keyframe_selector.on_update
            def _(event):
                if event.target.value == "None":
                    return
                try:
                    t = float(event.target.value.replace("s", ""))
                    if not self.app.gui_state["playing"]:
                        self.app.gui_state["time"] = t
                        self.time_slider.value = t

                        pose, b_pos, b_rpy = self.app.animator.get_state_at_time(t)
                        self.app.robot.update_pose(pose)
                        self.app.robot.update_base(b_pos, b_rpy)
                        self.sync_sliders(pose, b_pos, b_rpy)
                        self.update_ghost_pose(t)

                        self.app.current_pose.update(pose)
                        self.app.current_base_pos[:] = b_pos
                        self.app.current_base_rpy[:] = b_rpy
                except ValueError:
                    pass

        with self.server.gui.add_folder("Ghost / Residual"):
            self.show_ghost_checkbox = self.server.gui.add_checkbox("Show Ghost", initial_value=False)
            self.ghost_mode_dropdown = self.server.gui.add_dropdown(
                "Ghost Mode", options=["Time Offset", "Previous Keyframe"], initial_value="Previous Keyframe"
            )
            self.ghost_offset_slider = self.server.gui.add_slider(
                "Time Offset (s)", min=-1.0, max=1.0, step=0.01, initial_value=-0.1
            )
            ghost_opacity_slider = self.server.gui.add_slider("Opacity", min=0.0, max=1.0, step=0.1, initial_value=0.5)

            @self.show_ghost_checkbox.on_update
            def _(event):
                visible = event.target.value
                self.app.ghost_robot.base.visible = visible
                for joint in self.app.ghost_robot.joints.values():
                    joint.visible = visible
                self.update_ghost_pose(self.app.gui_state["time"])

            @self.ghost_mode_dropdown.on_update
            def _(event):
                self.update_ghost_pose(self.app.gui_state["time"])

            @self.ghost_offset_slider.on_update
            def _(event):
                self.update_ghost_pose(self.app.gui_state["time"])

    def _setup_pose_tab(self):
        with self.server.gui.add_folder("Edit Tools"):
            copy_pose_btn = self.server.gui.add_button("Copy Pose", icon=viser.Icon.COPY)
            paste_pose_btn = self.server.gui.add_button("Paste Pose", icon=viser.Icon.CLIPBOARD)
            mirror_lr_btn = self.server.gui.add_button("Mirror L -> R", icon=viser.Icon.ARROWS_HORIZONTAL)
            mirror_rl_btn = self.server.gui.add_button("Mirror R -> L", icon=viser.Icon.ARROWS_HORIZONTAL)

            clipboard_pose = {}

            @copy_pose_btn.on_click
            def _(_):
                clipboard_pose.clear()
                clipboard_pose.update(self.app.current_pose)
                print("[green]Pose copied to clipboard[/green]")

            @paste_pose_btn.on_click
            def _(_):
                if not clipboard_pose:
                    print("[yellow]Clipboard is empty[/yellow]")
                    return
                self.app.current_pose.update(clipboard_pose)
                self.app.robot.update_pose(self.app.current_pose)
                self.sync_sliders(pose=self.app.current_pose)
                print("[green]Pose pasted[/green]")

            @mirror_lr_btn.on_click
            def _(_):
                self._apply_mirror("L", "R")
                print("[blue]Mirrored Left to Right[/blue]")

            @mirror_rl_btn.on_click
            def _(_):
                self._apply_mirror("R", "L")
                print("[blue]Mirrored Right to Left[/blue]")

        with self.server.gui.add_folder("Robot Control"):
            reset_all_btn = self.server.gui.add_button("Reset All Joints", icon=viser.Icon.ROTATE_2)
            reset_base_btn = self.server.gui.add_button("Reset Base", icon=viser.Icon.ROTATE_2)

            @reset_all_btn.on_click
            def _(_):
                default_pose = self.app.robot.get_default_pose()
                self.app.current_pose.update(default_pose)
                self.app.robot.update_pose(self.app.current_pose)
                self.sync_sliders(pose=self.app.current_pose)

            @reset_base_btn.on_click
            def _(_):
                self.app.current_base_pos[:] = [0.0, 0.0, 0.4]
                self.app.current_base_rpy[:] = [0.0, 0.0, 0.0]
                self.app.robot.update_base(self.app.current_base_pos, self.app.current_base_rpy)
                self.sync_sliders(b_pos=self.app.current_base_pos, b_rpy=self.app.current_base_rpy)

            # Base Sliders
            for i, axis in enumerate(["x", "y", "z"]):
                slider = self.server.gui.add_slider(
                    f"Pos {axis.upper()}", min=-2.0, max=2.0, step=0.01, initial_value=self.app.current_base_pos[i]
                )
                self.base_sliders[f"pos_{axis}"] = slider

                def make_pos_callback(idx):
                    def callback(event):
                        if not self.app.gui_state["playing"]:
                            self.app.current_base_pos[idx] = event.target.value
                            self.app.robot.update_base(self.app.current_base_pos, self.app.current_base_rpy)

                    return callback

                slider.on_update(make_pos_callback(i))

            for i, axis in enumerate(["roll", "pitch", "yaw"]):
                slider = self.server.gui.add_slider(
                    f"Rot {axis.upper()}", min=-3.14, max=3.14, step=0.01, initial_value=self.app.current_base_rpy[i]
                )
                self.base_sliders[f"rot_{axis}"] = slider

                def make_rot_callback(idx):
                    def callback(event):
                        if not self.app.gui_state["playing"]:
                            self.app.current_base_rpy[idx] = event.target.value
                            self.app.robot.update_base(self.app.current_base_pos, self.app.current_base_rpy)

                    return callback

                slider.on_update(make_rot_callback(i))

        # Joint Sliders
        legs = ["FL", "FR", "RL", "RR"]
        joints = ["hip", "thigh", "calf"]

        for leg in legs:
            with self.server.gui.add_folder(f"{leg} Leg"):
                reset_leg_btn = self.server.gui.add_button(f"Reset {leg}", icon=viser.Icon.ROTATE_2)

                @reset_leg_btn.on_click
                def _(event, leg_name=leg):
                    default_pose = self.app.robot.get_default_pose()
                    for j in joints:
                        full_name = f"{leg_name}_{j}"
                        val = default_pose[full_name]
                        self.app.current_pose[full_name] = val
                        if full_name in self.joint_sliders:
                            self.joint_sliders[full_name].value = val
                    self.app.robot.update_pose(self.app.current_pose)

                for joint in joints:
                    joint_name = f"{leg}_{joint}"
                    limits = self.app.robot.limits[joint]
                    slider = self.server.gui.add_slider(
                        label=joint,
                        min=limits[0],
                        max=limits[1],
                        step=0.01,
                        initial_value=self.app.current_pose.get(joint_name, 0.0),
                    )
                    self.joint_sliders[joint_name] = slider

                    def make_slider_callback(name):
                        def callback(event):
                            if not self.app.gui_state["playing"]:
                                self.app.current_pose[name] = event.target.value
                                self.app.robot.update_pose(self.app.current_pose)

                        return callback

                    slider.on_update(make_slider_callback(joint_name))

    def _setup_system_tab(self):
        with self.server.gui.add_folder("File"):
            self.file_name_input = self.server.gui.add_text("Filename", initial_value="animation.json")
            save_btn = self.server.gui.add_button("Save", icon=viser.Icon.DEVICE_FLOPPY)
            load_btn = self.server.gui.add_button("Load", icon=viser.Icon.FOLDER_OPEN)

            @save_btn.on_click
            def _(_):
                filename = self.file_name_input.value
                try:
                    self.app.animator.save_to_file(filename)
                    print(f"[green]Saved animation to {filename}[/green]")
                except Exception as e:
                    print(f"[red]Error saving: {e}[/red]")

            @load_btn.on_click
            def _(_):
                filename = self.file_name_input.value
                try:
                    self.app.animator.load_from_file(filename)
                    self.keyframe_info.value = f"Count: {len(self.app.animator.keyframes)}"
                    self.duration_number.value = self.app.animator.duration
                    self.interp_dropdown.value = self.app.animator.interpolation_method
                    self.update_keyframe_dropdown()
                    print(f"[green]Loaded animation from {filename}[/green]")
                except Exception as e:
                    print(f"[red]Error loading: {e}[/red]")

    def update_play_pause_buttons(self):
        playing = self.app.gui_state["playing"]
        self.play_button.visible = not playing
        self.pause_button.visible = playing

    def update_time_slider(self, time_val):
        self.time_slider.value = time_val

    def update_keyframe_dropdown(self):
        if not self.app.animator.keyframes:
            self.keyframe_selector.options = ["None"]
            self.keyframe_selector.value = "None"
            return
        options = [f"{k['time']:.2f}s" for k in self.app.animator.keyframes]
        self.keyframe_selector.options = options

    def sync_sliders(self, pose=None, b_pos=None, b_rpy=None):
        if pose:
            for name, val in pose.items():
                if name in self.joint_sliders:
                    self.joint_sliders[name].value = val

        if b_pos:
            for i, axis in enumerate(["x", "y", "z"]):
                self.base_sliders[f"pos_{axis}"].value = b_pos[i]

        if b_rpy:
            for i, axis in enumerate(["roll", "pitch", "yaw"]):
                self.base_sliders[f"rot_{axis}"].value = b_rpy[i]

    def update_ghost_pose(self, t):
        if not self.show_ghost_checkbox.value:
            return

        target_time = t
        if self.ghost_mode_dropdown.value == "Time Offset":
            target_time = t + self.ghost_offset_slider.value
            if self.app.gui_state["loop"] and self.app.gui_state["duration"] > 0:
                target_time %= self.app.gui_state["duration"]
        else:  # Previous Keyframe
            prev_time = None
            sorted_keys = sorted(self.app.animator.keyframes, key=lambda x: x["time"])
            epsilon = 0.001
            candidates = [k for k in sorted_keys if k["time"] < t - epsilon]

            if candidates:
                prev_time = candidates[-1]["time"]
            else:
                if self.app.gui_state["loop"] and sorted_keys:
                    prev_time = sorted_keys[-1]["time"]
                else:
                    prev_time = t
            target_time = prev_time

        g_pose, g_b_pos, g_b_rpy = self.app.animator.get_state_at_time(target_time)
        self.app.ghost_robot.update_pose(g_pose)
        self.app.ghost_robot.update_base(g_b_pos, g_b_rpy)

    def _apply_mirror(self, source_side, target_side):
        pairs = [("FL", "FR"), ("RL", "RR")]
        if source_side == "R":
            pairs = [("FR", "FL"), ("RR", "RL")]

        for src_leg, tgt_leg in pairs:
            # Hip: Negate
            src_hip = f"{src_leg}_hip"
            tgt_hip = f"{tgt_leg}_hip"
            if src_hip in self.app.current_pose:
                val = -self.app.current_pose[src_hip]
                self.app.current_pose[tgt_hip] = val

            # Thigh: Copy
            src_thigh = f"{src_leg}_thigh"
            tgt_thigh = f"{tgt_leg}_thigh"
            if src_thigh in self.app.current_pose:
                val = self.app.current_pose[src_thigh]
                self.app.current_pose[tgt_thigh] = val

            # Calf: Copy
            src_calf = f"{src_leg}_calf"
            tgt_calf = f"{tgt_leg}_calf"
            if src_calf in self.app.current_pose:
                val = self.app.current_pose[src_calf]
                self.app.current_pose[tgt_calf] = val

        self.app.robot.update_pose(self.app.current_pose)
        self.sync_sliders(pose=self.app.current_pose)
