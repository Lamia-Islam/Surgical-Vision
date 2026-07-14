#!/usr/bin/env python3
"""
lesion_detector_node.py
───────────────────────
ROS2 node: reads images from a folder (simulating live feed),
runs ABCDE analysis, publishes scene state to /scene_state.

Topic published:
  /scene_state  (std_msgs/String)
  Format: "VERDICT|SCORE|REASON"
  Example: "FAIL|7|Asymmetry critical, Diameter exceeded"
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

import os
import sys
import time

# point to our analyzer
sys.path.insert(0, os.path.dirname(__file__))
from abcde_analyzer import analyze_wound

IMAGE_DIR = os.path.expanduser(
    "/mnt/c/Users/Lenovo/OneDrive/Desktop/ROS/files/"
    "wound_analyzer_project2/wound_analyzer/sample_images"
)


def build_reason(report) -> str:
    """Human-readable reason string from ABCDE scores."""
    flags = []
    if report.A_score > 0: flags.append("Asymmetry irregular")
    if report.B_score > 0: flags.append("Border unclear")
    if report.C_score > 0: flags.append("Tissue color abnormal")
    if report.D_score > 0: flags.append("Diameter exceeded")
    if report.E_score > 0: flags.append("Rapid evolution detected")
    return ", ".join(flags) if flags else "All parameters normal"


def verdict_short(verdict: str) -> str:
    if "PASS"    in verdict: return "PASS"
    if "CAUTION" in verdict: return "CAUTION"
    return "FAIL"


class LesionDetectorNode(Node):

    def __init__(self):
        super().__init__("lesion_detector")

        # publisher
        self.publisher_ = self.create_publisher(String, "/scene_state", 10)

        # timer — analyze one image every 2 seconds
        self.timer = self.create_timer(2.0, self.timer_callback)

        # load image list
        self.images = sorted([
            os.path.join(IMAGE_DIR, f)
            for f in os.listdir(IMAGE_DIR)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ])
        self.index = 0

        self.get_logger().info(
            f"LesionDetector started — {len(self.images)} images queued"
        )

    def timer_callback(self):
        if not self.images:
            self.get_logger().error("No images found in sample_images/")
            return

        # cycle through images (simulates continuous feed)
        img_path = self.images[self.index % len(self.images)]
        self.index += 1

        report = analyze_wound(img_path)
        if report is None:
            self.get_logger().warn(f"Could not analyze: {img_path}")
            return

        verdict = verdict_short(report.verdict)
        score   = report.total_score
        reason  = build_reason(report)

        # publish
        msg      = String()
        msg.data = f"{verdict}|{score}|{reason}"
        self.publisher_.publish(msg)

        self.get_logger().info(
            f"[{os.path.basename(img_path)}] "
            f"{verdict} | {score}/10 | {reason}"
        )


def main(args=None):
    rclpy.init(args=args)
    node = LesionDetectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

