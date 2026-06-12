from setuptools import find_packages, setup

package_name = 'gem_agent_ros2'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name, ['launch/nav.launch.py']),
        ('share/gem_agent_ros2', ['.env']),
    ],
    install_requires=[
        'setuptools',
        'python-dotenv',
        'google-genai',
    ],
    zip_safe=True,
    maintainer='ros',
    maintainer_email='a.thota1@lse.ac.uk',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'lmr = gem_agent_ros2.lmr:main',

        ],
    },
)
