from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    # Get the path to the other launch file
    sim_launch_file = os.path.join(
        get_package_share_directory('nav2_mobile_robot'),
        'nav2_mobile_robot_gazebo.launch.py'
    )
    nav_launch_file = os.path.join(
        get_package_share_directory('nav2_mobile_robot'),
        'navigation.launch.py'
    )
    slam_launch_file = os.path.join(
        get_package_share_directory('nav2_mobile_robot'),
        'slam.launch.py'
    )

    return LaunchDescription([
        # Include the other launch file
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(sim_launch_file)
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(nav_launch_file)
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(slam_launch_file)
        ),
    ])