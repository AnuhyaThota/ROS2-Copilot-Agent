#!/bin/bash

set -xe

echo "=== Starting dev container post-create setup ==="

function add_config_if_not_exist {
    if ! grep -F -q "$1" $HOME/.bashrc; then
        echo "$1" >> $HOME/.bashrc
        echo "Added to .bashrc: $1"
    else
        echo "Already in .bashrc: $1"
    fi
}

function verify_ros_setup {
    echo "=== Verifying ROS setup ==="
    if [ -f "/opt/ros/humble/setup.bash" ]; then
        echo "✓ ROS Humble found at /opt/ros/humble/setup.bash"
    else
        echo "✗ ROS Humble setup not found!"
        return 1
    fi
    
    if [ -f "/opt/ros/lcas/install/setup.bash" ]; then
        echo "✓ L-CAS packages found at /opt/ros/lcas/install/setup.bash"
    else
        echo "✗ L-CAS packages setup not found!"
        return 1
    fi
    return 0
}

function ensure_python_package {
    local package_name="$1"
    if /usr/bin/python3 -m pip show "$package_name" >/dev/null 2>&1; then
        echo "✓ Python package already installed: $package_name"
    else
        echo "Installing Python package: $package_name"
        /usr/bin/python3 -m pip install --user "$package_name"
    fi
}

# Verify ROS installation before proceeding
verify_ros_setup

echo "=== Adding ROS environment to .bashrc ==="
add_config_if_not_exist "source /opt/ros/humble/setup.bash"
add_config_if_not_exist "source /opt/ros/lcas/install/setup.bash"
add_config_if_not_exist "alias rviz_sensors='rviz2 -d /opt/ros/lcas/install/limo_description/share/limo_description/rviz/model_sensors_real.rviz'"
add_config_if_not_exist "alias tidybot_sim='ros2 launch uol_tidybot tidybot.launch.py'"

echo "=== Sourcing ROS environment ==="
source /opt/ros/humble/setup.bash
source /opt/ros/lcas/install/setup.bash

echo "=== Verifying uol_tidybot package availability ==="
if ros2 pkg list | grep -q "uol_tidybot"; then
    echo "✓ uol_tidybot package found"
else
    echo "✗ WARNING: uol_tidybot package not found in ROS package list"
    echo "Available packages containing 'tidybot' or 'limo':"
    ros2 pkg list | grep -i -E "(tidybot|limo)" || echo "  No tidybot or limo packages found"
fi

echo "=== Building workspace ==="
rosdep update --rosdistro ${ROS_DISTRO:-humble}
sudo apt-get update
rosdep install -r -i --from-paths -y src/
colcon build --symlink-install --continue-on-error

# Check if build was successful
if [ $? -eq 0 ]; then
    echo "✓ Workspace build completed successfully"
else
    echo "⚠ Workspace build completed with warnings/errors"
fi

LOCAL_SETUP_FILE=`pwd`/install/setup.bash
add_config_if_not_exist "if [ -r $LOCAL_SETUP_FILE ]; then source $LOCAL_SETUP_FILE; fi"

echo "=== Final verification ==="
echo "ROS_DISTRO: ${ROS_DISTRO:-not set}"
echo "Workspace directory: $(pwd)"
echo "Available launch files for uol_tidybot:"
find /opt/ros/lcas/install -name "*tidybot*.launch.py" 2>/dev/null || echo "  No tidybot launch files found"

echo "=== Setting up desktop background ==="
sleep 10
DISPLAY=:1 xfconf-query -c xfce4-desktop -p $(xfconf-query -c xfce4-desktop -l | grep "workspace0/last-image") -s /usr/share/backgrounds/xfce/lcas.jpg  || echo "⚠ Desktop background setup failed (this is not critical)"

echo "=== Post-create setup completed ==="
echo ""
echo "To test robot spawning, try:"
echo "  tidybot_sim"
echo "or"
echo "  ros2 launch uol_tidybot tidybot.launch.py"
echo ""
