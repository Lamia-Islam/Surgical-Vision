#!/usr/bin/env python3
"""
behavior_manager_node.py
─────────────────────────
Subscribes to /scene_state, maps verdict → autonomy mode,
publishes arm constraints to /autonomy_mode.

Subscribed:  /scene_state   (std_msgs/String) "VERDICT|SCORE|REASON"
Published:   /autonomy_mode (std_msgs/String) "MODE|SPEED_FACTOR|REASON"

Modes:
  PASS    → FULL    | 1.00x speed | execute immediately
  CAUTION → REDUCED | 0.50x speed | confirm each waypoint
  FAIL    → HOLD    | 0.00x speed | freeze, require CONFIRM
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


AUTONOMY_MAP = {
    "PASS":    ("FULL",    1.00),
    "CAUTION": ("REDUCED", 0.50),
    "FAIL":    ("HOLD",    0.00),
}


class BehaviorManagerNode(Node):

    def __init__(self):
        super().__init__("behavior_manager")

        # subscriber
        self.subscription = self.create_subscription(
            String,
            "/scene_state",
            self.scene_state_callback,
            10
        )

        # publisher
        self.publisher = self.create_publisher(String, "/autonomy_mode", 10)

        # state
        self.current_mode  = "FULL"
        self.speed_factor  = 1.00
        self.last_verdict  = None

        self.get_logger().info("BehaviorManager started — listening to /scene_state")

    def scene_state_callback(self, msg: String):
        # parse "VERDICT|SCORE|REASON"
        parts = msg.data.split("|")
        if len(parts) < 3:
            self.get_logger().warn(f"Malformed message: {msg.data}")
            return

        verdict = parts[0].strip()
        score   = parts[1].strip()
        reason  = parts[2].strip()

        if verdict not in AUTONOMY_MAP:
            self.get_logger().warn(f"Unknown verdict: {verdict}")
            return

        mode, speed = AUTONOMY_MAP[verdict]

        # only log + publish if mode changed
        if verdict != self.last_verdict:
            self.get_logger().info(
                f"SCENE: {verdict} ({score}/10) → "
                f"MODE: {mode} | SPEED: {speed}x | {reason}"
            )
            self.last_verdict = verdict
            self.current_mode = mode
            self.speed_factor = speed

            if mode == "HOLD":
                self.get_logger().warn(
                    "⚠  ARM FROZEN — type CONFIRM in console to resume"
                )

        # always publish current autonomy mode
        out = String()
        out.data = f"{mode}|{speed}|{reason}"
        self.publisher.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = BehaviorManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

