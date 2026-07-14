#!/usr/bin/env python3
"""
surgeon_console_node.py
────────────────────────
Keyboard teleoperation interface for the surgical arm.
Reads /autonomy_mode and modifies behavior accordingly.

Subscribed:  /autonomy_mode       (std_msgs/String)
Published:   /arm_command         (std_msgs/String)

FULL    → commands execute immediately at full speed
REDUCED → commands execute at 0.5x, SPACE required to confirm
HOLD    → commands queued, requires typing CONFIRM to resume
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import threading
import sys
import tty
import termios
import os

BANNER = """
╔══════════════════════════════════════════╗
║        SURGICAL ARM CONSOLE              ║
╠══════════════════════════════════════════╣
║  w/s    → move arm +Y / -Y              ║
║  a/d    → move arm -X / +X              ║
║  u/j    → move arm +Z / -Z              ║
║  r/f    → rotate end effector +/−       ║
║  SPACE  → confirm waypoint (CAUTION)    ║
║  CONFIRM→ resume arm (HOLD mode)        ║
║  q      → emergency stop                ║
╚══════════════════════════════════════════╝
"""

KEY_MAP = {
    'w': '+Y', 's': '-Y',
    'a': '-X', 'd': '+X',
    'u': '+Z', 'j': '-Z',
    'r': '+ROT', 'f': '-ROT',
}


class SurgeonConsoleNode(Node):

    def __init__(self):
        super().__init__("surgeon_console")

        self.subscription = self.create_subscription(
            String, "/autonomy_mode",
            self.autonomy_callback, 10
        )
        self.publisher = self.create_publisher(String, "/arm_command", 10)

        # state
        self.mode         = "FULL"
        self.speed_factor = 1.00
        self.reason       = "Initializing"
        self.confirm_pending = False
        self.command_queue   = []
        self.confirmed       = False

        print(BANNER)
        self.print_status()

        # keyboard input in separate thread
        self.input_thread = threading.Thread(
            target=self.keyboard_loop, daemon=True
        )
        self.input_thread.start()

    def autonomy_callback(self, msg: String):
        parts = msg.data.split("|")
        if len(parts) < 3:
            return
        new_mode  = parts[0].strip()
        new_speed = float(parts[1].strip())
        new_reason= parts[2].strip()

        if new_mode != self.mode:
            self.mode         = new_mode
            self.speed_factor = new_speed
            self.reason       = new_reason
            self.print_status()

            if self.mode == "HOLD":
                print("\n  ⚠  ARM FROZEN — type 'CONFIRM' + Enter to resume\n")
            elif self.mode == "REDUCED":
                print("\n  ⚠  CAUTION MODE — press SPACE to confirm each waypoint\n")
            else:
                print("\n  ✓  FULL AUTONOMY — executing commands immediately\n")

    def print_status(self):
        os.system('clear')
        print(BANNER)
        print(f"  Arm status    : ACTIVE")
        print(f"  Autonomy mode : {self.mode}")
        print(f"  Scene reason  : {self.reason}")
        print(f"  Speed factor  : {self.speed_factor:.2f}x")
        print(f"  {'─'*40}")
        if self.mode == "HOLD":
            print("  ⚠  ARM FROZEN — type CONFIRM + Enter")
        elif self.mode == "REDUCED":
            print("  ⚠  Press SPACE to confirm each waypoint")
        else:
            print("  ✓  Full teleoperation active")
        print()

    def send_command(self, direction: str):
        msg = String()
        msg.data = f"MOVE|{direction}|{self.speed_factor}"
        self.publisher.publish(msg)
        print(f"  → CMD: MOVE {direction} at {self.speed_factor:.2f}x speed")

    def keyboard_loop(self):
        """Non-blocking keyboard input loop."""
        fd = sys.stdin.fileno()

        while rclpy.ok():
            # HOLD mode — wait for typed CONFIRM
            if self.mode == "HOLD":
                try:
                    line = input("  > ")
                    if line.strip().upper() == "CONFIRM":
                        print("  ✓  CONFIRM received — flushing queued commands")
                        for cmd in self.command_queue:
                            self.send_command(cmd)
                        self.command_queue.clear()
                except EOFError:
                    break
                continue

            # FULL / REDUCED — single keypress
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                key = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

            if key == 'q':
                print("\n  ⛔  EMERGENCY STOP")
                msg = String()
                msg.data = "STOP|EMERGENCY|0.0"
                self.publisher.publish(msg)
                break

            if key == ' ':
                if self.mode == "REDUCED" and self.confirm_pending:
                    print("  ✓  Waypoint confirmed")
                    for cmd in self.command_queue:
                        self.send_command(cmd)
                    self.command_queue.clear()
                    self.confirm_pending = False
                continue

            if key in KEY_MAP:
                direction = KEY_MAP[key]
                if self.mode == "FULL":
                    self.send_command(direction)
                elif self.mode == "REDUCED":
                    self.command_queue.append(direction)
                    self.confirm_pending = True
                    print(f"  ⏸  Waypoint queued: {direction} — press SPACE to confirm")
                elif self.mode == "HOLD":
                    self.command_queue.append(direction)
                    print(f"  🔒  Command queued (ARM HOLD): {direction}")


def main(args=None):
    rclpy.init(args=args)
    node = SurgeonConsoleNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
