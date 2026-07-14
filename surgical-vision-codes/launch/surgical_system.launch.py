from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='surgical_vision',
            executable='lesion_detector',
            name='lesion_detector',
            output='screen'
        ),
        Node(
            package='surgical_vision',
            executable='behavior_manager',
            name='behavior_manager',
            output='screen'
        ),
        Node(
            package='surgical_vision',
            executable='surgeon_console',
            name='surgeon_console',
            output='screen'
        ),
    ])
