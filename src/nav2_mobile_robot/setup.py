from setuptools import find_packages, setup

package_name = 'nav2_mobile_robot'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name, ['urdf/nav2_mobile_robot.xacro']),
        ('share/' + package_name, ['urdf/nav2_mobile_robot_macro.xacro']),
        ('share/' + package_name, ['launch/display.launch.py']),
        ('share/' + package_name, ['launch/nav2_mobile_robot_gazebo.launch.py']),
        ('share/' + package_name, ['launch/slam.launch.py']),
        ('share/' + package_name, ['conf/slam.yaml']),
        ('share/' + package_name, ['conf/amcl.yaml']),
        ('share/' + package_name, ['worlds/maze.sdf']),
        ('share/' + package_name, ['map/maze.yaml']),
        ('share/' + package_name, ['map/maze.pgm']),
        ('share/' + package_name, ['launch/amcl.launch.py']),
        ('share/' + package_name, ['launch/navigation.launch.py']),
        ('share/' + package_name, ['conf/nav.yaml']),
        ('share/' + package_name, ['launch/map_server.launch.py']),
        
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ros',
    maintainer_email='a.thota1@lse.ac.uk',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
        ],
    },
)
