from setuptools import setup
import os
from glob import glob

package_name = 'surgical_vision'

setup(
    name=package_name,
    version='1.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch',
            glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Lamia Islam',
    maintainer_email='lamiaislamzy@gmail.com',
    description='ROS2 Humble pipeline for intraoperative wound assessment using a five-part ABCDE vision framework and variable-autonomy surgical arm gating.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'lesion_detector = surgical_vision.lesion_detector_node:main',
            'behavior_manager = surgical_vision.behavior_manager_node:main',
            'surgeon_console = surgical_vision.surgeon_console_node:main',
            'moveit_bridge = surgical_vision.moveit_bridge_node:main',
        ],
    },
)
