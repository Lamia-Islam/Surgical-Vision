#!/usr/bin/env python3
"""
moveit_bridge_node.py
──────────────────────
Subscribes to /arm_command and /autonomy_mode,
translates keyboard commands into MoveIt2 joint targets,
applies speed scaling based on autonomy mode.

Subscribed:  /arm_command   (std_msgs/String) "MOVE|+Y|0.5"
             /autonomy_mode (std_msgs/String) "REDUCED|0.5|reason"
Published:   /move_group/goal (via MoveIt2 action client)
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from moveit_msgs.action import MoveGroup
from moveit_msgs.msg import (
    MotionPlanRequest, WorkspaceParameters,
    Constraints, JointConstraint
)
from rclpy.action import ActionClient
from sensor_msgs.msg import JointState
import math


# Step size per keypress (radians)
STEP = 0.1

# Joint names for your arm
JOINT_NAMES = [
    'joint1', 'joint2', 'joint3',
    'joint4', 'joint5', 'joint6'
]

# Which joint each direction moves
DIRECTION_MAP = {
    '+Y': ('joint2',  STEP),
    '-Y': ('joint2', -STEP),
    '+X': ('joint1',  STEP),
    '-X': ('joint1', -STEP),
    '+Z': ('joint3',  STEP),
    '-Z': ('joint3', -STEP),
    '+ROT': ('joint6',  STEP),
    '-ROT': ('joint6', -STEP),
}


class MoveItBridgeNode(Node):

    def __init__(self):
        super().__init__('moveit_bridge')

        # subscribers
        self.cmd_sub = self.create_subscription(
            String, '/arm_command',
            self.command_callback, 10
        )
        self.mode_sub = self.create_subscription(
            String, '/autonomy_mode',
            self.mode_callback, 10
        )
        self.joint_sub = self.create_subscription(
            JointState, '/joint_states',
            self.joint_state_callback, 10
        )

        # MoveIt2 action client
        self._action_client = ActionClient(
            self, MoveGroup, '/move_action'
        )

        # state
        self.speed_factor  = 1.0
        self.current_mode  = 'FULL'
        self.joint_positions = {j: 0.0 for j in JOINT_NAMES}
        self.hold          = False

        self.get_logger().info('MoveIt2 Bridge started — listening to /arm_command')

    def joint_state_callback(self, msg: JointState):
        for name, pos in zip(msg.name, msg.position):
            if name in self.joint_positions:
                self.joint_positions[name] = pos

    def mode_callback(self, msg: String):
        parts = msg.data.split('|')
        if len(parts) < 2:
            return
        self.current_mode  = parts[0].strip()
        self.speed_factor  = float(parts[1].strip())
        self.hold          = (self.current_mode == 'HOLD')

        self.get_logger().info(
            f'Autonomy mode: {self.current_mode} | '
            f'Speed: {self.speed_factor}x | '
            f'Hold: {self.hold}'
        )

    def command_callback(self, msg: String):
        parts = msg.data.split('|')
        if len(parts) < 2:
            return

        cmd_type  = parts[0].strip()
        direction = parts[1].strip()

        if cmd_type == 'STOP':
            self.get_logger().warn('EMERGENCY STOP received')
            return

        if self.hold:
            self.get_logger().warn(
                f'ARM HOLD — command {direction} blocked'
            )
            return

        if direction not in DIRECTION_MAP:
            return

        joint_name, delta = DIRECTION_MAP[direction]
        # apply speed scaling to step size
        scaled_delta = delta * self.speed_factor

        # calculate new target
        target = dict(self.joint_positions)
        target[joint_name] = target[joint_name] + scaled_delta

        self.get_logger().info(
            f'Moving {joint_name} by {scaled_delta:.3f} rad '
            f'(speed: {self.speed_factor}x)'
        )

        self.send_joint_goal(target)

    def send_joint_goal(self, target_positions: dict):
        if not self._action_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('MoveIt2 action server not available')
            return

        # build joint constraints
        constraints = Constraints()
        for joint_name, position in target_positions.items():
            jc = JointConstraint()
            jc.joint_name    = joint_name
            jc.position      = float(position)
            jc.tolerance_above = 0.01
            jc.tolerance_below = 0.01
            jc.weight          = 1.0
            constraints.joint_constraints.append(jc)

        # build motion plan request
        req = MotionPlanRequest()
        req.group_name             = 'arm'
        req.goal_constraints       = [constraints]
        req.num_planning_attempts  = 5
        req.allowed_planning_time  = 2.0
        req.max_velocity_scaling_factor     = self.speed_factor
        req.max_acceleration_scaling_factor = self.speed_factor * 0.5

        goal = MoveGroup.Goal()
        goal.request    = req
        goal.planning_options.plan_only           = False
        goal.planning_options.replan              = True
        goal.planning_options.replan_attempts     = 3

        self._action_client.send_goal_async(goal)


def main(args=None):
    rclpy.init(args=args)
    node = MoveItBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
