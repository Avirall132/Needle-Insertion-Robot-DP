"""
Tests for UR7e controller module (controllers/ur_controller.py).
"""

import math
import pytest
from controllers.ur_controller import URController, NUM_JOINTS


def test_ur_controller_simulation_initial_state():
    ctrl = URController(simulation_mode=True)
    assert not ctrl.is_connected

    # Connection in simulation mode
    success = ctrl.connect("192.168.1.10")
    assert success is True
    assert ctrl.is_connected is True

    # Initial joint positions should be 0.0 for all 6 joints
    joints = ctrl.get_joint_positions()
    assert len(joints) == NUM_JOINTS
    assert all(abs(j) < 1e-5 for j in joints)

    # Initial TCP pose should have 6 values
    tcp = ctrl.get_tcp_pose()
    assert len(tcp) == 6

    # Robot and safety mode in simulation (UR RTDE mode 7 = RUNNING, mode 1 = NORMAL)
    assert ctrl.get_robot_mode() == 7
    assert ctrl.get_safety_mode() == 1


def test_ur_controller_joint_jogging():
    ctrl = URController(simulation_mode=True)
    ctrl.connect("192.168.1.10")

    # Jog Joint 0 in positive direction by 0.1 rad
    success = ctrl.jog_joint(joint_index=0, direction=1.0, speed=0.1)
    assert success is True

    joints = ctrl.get_joint_positions()
    assert len(joints) == NUM_JOINTS


def test_ur_controller_joint_limits():
    ctrl = URController(simulation_mode=True)
    ctrl.connect("192.168.1.10")

    # Jog Joint 1
    success = ctrl.jog_joint(joint_index=1, direction=1.0, speed=0.1)
    joints = ctrl.get_joint_positions()
    # Position should not exceed 2*pi
    assert joints[1] <= 2.0 * math.pi + 1e-4


def test_ur_controller_stop():
    ctrl = URController(simulation_mode=True)
    ctrl.connect("192.168.1.10")

    ctrl.stop()
    assert ctrl.is_connected is True


def test_ur_controller_disconnect():
    ctrl = URController(simulation_mode=True)
    ctrl.connect("192.168.1.10")
    assert ctrl.is_connected is True

    ctrl.disconnect()
    assert ctrl.is_connected is False

    # Calling get_robot_mode when disconnected should raise RuntimeError
    with pytest.raises(RuntimeError):
        ctrl.get_robot_mode()
