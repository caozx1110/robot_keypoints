import json
import numpy as np
from scipy.interpolate import interp1d
from scipy.spatial.transform import Rotation as R, Slerp


class Animator:
    def __init__(self):
        # 关键帧列表: [{"time": t, "pose": {...}, "base": {"pos": [x,y,z], "rpy": [r,p,y]}}, ...]
        self.keyframes = []
        self.duration = 2.0
        self.interpolators = {}
        self.needs_update = False
        self.interpolation_method = "linear"  # linear, cubic, zero, slinear, quadratic

    def set_interpolation_method(self, method):
        if method in ["linear", "cubic", "zero", "slinear", "quadratic"]:
            self.interpolation_method = method
            self.needs_update = True

    def add_keyframe(self, time, pose, base_pos, base_rpy):
        existing_idx = next((i for i, k in enumerate(self.keyframes) if np.isclose(k["time"], time)), None)

        frame_data = {"time": time, "pose": pose.copy(), "base": {"pos": list(base_pos), "rpy": list(base_rpy)}}

        if existing_idx is not None:
            self.keyframes[existing_idx] = frame_data
        else:
            self.keyframes.append(frame_data)
            self.keyframes.sort(key=lambda x: x["time"])

        self.needs_update = True

    def remove_keyframe(self, index):
        if 0 <= index < len(self.keyframes):
            self.keyframes.pop(index)
            self.needs_update = True

    def clear_keyframes(self):
        self.keyframes = []
        self.needs_update = True

    def _update_interpolators(self):
        if len(self.keyframes) < 2:
            self.interpolators = {}
            return

        times = [k["time"] for k in self.keyframes]

        # 1. Joint Interpolation
        joint_names = self.keyframes[0]["pose"].keys()
        self.interpolators["joints"] = {}
        for name in joint_names:
            values = [k["pose"][name] for k in self.keyframes]
            self.interpolators["joints"][name] = interp1d(
                times, values, kind=self.interpolation_method, fill_value="extrapolate"
            )

        # 2. Base Position Interpolation
        base_pos_list = [k["base"]["pos"] for k in self.keyframes]
        base_pos_arr = np.array(base_pos_list)  # (N, 3)
        # interp1d expects x to be 1D, y to be (..., N) if axis is not default
        # But here y is (N, 3). axis=0 means interpolation along the first axis (time).
        # Wait, interp1d(x, y, axis=0) means x corresponds to the first axis of y.
        # Correct.
        self.interpolators["base_pos"] = interp1d(
            times, base_pos_arr, axis=0, kind=self.interpolation_method, fill_value="extrapolate"
        )

        # 3. Base Rotation Interpolation (Slerp)
        # Convert RPY to Quaternions
        base_rpy_list = [k["base"]["rpy"] for k in self.keyframes]
        rotations = R.from_euler("xyz", base_rpy_list, degrees=False)
        self.interpolators["base_rot"] = Slerp(times, rotations)

        self.needs_update = False

    def get_state_at_time(self, time):
        """
        Returns: (pose_dict, base_pos, base_rpy)
        """
        if not self.keyframes:
            return {}, [0, 0, 0], [0, 0, 0]

        if len(self.keyframes) == 1:
            k = self.keyframes[0]
            return k["pose"], k["base"]["pos"], k["base"]["rpy"]

        if self.needs_update:
            self._update_interpolators()

        # Clamp time for Slerp (it doesn't support extrapolation well by default)
        # Ensure times are numpy array for clip
        times_arr = np.array([k["time"] for k in self.keyframes])
        t_clamped = np.clip(time, times_arr[0], times_arr[-1])

        # Joints
        pose = {}
        for name, func in self.interpolators["joints"].items():
            pose[name] = float(func(time))  # interp1d handles extrapolation

        # Base Pos
        base_pos = self.interpolators["base_pos"](time).tolist()

        # Base Rot
        base_rot = self.interpolators["base_rot"](t_clamped)
        base_rpy = base_rot.as_euler("xyz", degrees=False).tolist()

        return pose, base_pos, base_rpy

    def save_to_file(self, filename):
        data = {
            "duration": self.duration,
            "interpolation_method": self.interpolation_method,
            "keyframes": self.keyframes,
        }
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

    def load_from_file(self, filename):
        with open(filename, "r") as f:
            data = json.load(f)
        self.duration = data.get("duration", 2.0)
        self.interpolation_method = data.get("interpolation_method", "linear")
        self.keyframes = data.get("keyframes", [])
        self.needs_update = True
