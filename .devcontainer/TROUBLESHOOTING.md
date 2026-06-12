# Dev Container Troubleshooting Guide

## Robot Spawning Issues

If you're experiencing issues with the robot not spawning when running `ros2 launch uol_tidybot tidybot.launch.py`, try the following troubleshooting steps:

### 1. Check Post-Create Setup Logs

The post-create script provides detailed logging. Check the VS Code Dev Container logs to see if there were any errors during setup:

1. Open Command Palette (`Ctrl+Shift+P`)
2. Search for "Dev Containers: Show Container Log"
3. Look for error messages or warnings in the setup process

### 2. Verify ROS Environment

Open a terminal in the dev container and run:

```bash
# Check if ROS is properly sourced
echo $ROS_DISTRO
# Should output: humble

# Check if the tidybot package is available
ros2 pkg list | grep tidybot

# List all available packages to see what's installed
ros2 pkg list | grep -E "(limo|tidybot|gazebo)"
```

### 3. Test Launch Command Manually

Try running the launch command with verbose output:

```bash
ros2 launch uol_tidybot tidybot.launch.py --show-args
```

If the package is not found, try:

```bash
# Re-source the environment
source /opt/ros/humble/setup.bash
source /opt/ros/lcas/install/setup.bash

# Try the alias
tidybot_sim
```

### 4. Check Gazebo Dependencies

The robot spawning relies on Gazebo. Verify it's working:

```bash
# Check if Gazebo is available
which gzserver
which gzclient

# Test Gazebo directly
gazebo --version
```

### 5. Fresh Container Restart

If issues persist, try:

1. **Rebuild Container**: 
   - Command Palette → "Dev Containers: Rebuild Container"
   
2. **Clean Restart**:
   - Close VS Code
   - Delete container: `docker container prune`
   - Delete images: `docker image rm lcas.lincoln.ac.uk/devcontainer/ros2-teaching:4`
   - Reopen in VS Code and rebuild

### 6. Check Display/Desktop Issues

If Gazebo client fails to start:

1. Ensure you've opened the desktop interface (Port 5801)
2. Check if the virtual display is working:
   ```bash
   echo $DISPLAY
   # Should show :1
   
   # Test X11
   xdpyinfo
   ```

### 7. Common Error Messages

**"Package 'uol_tidybot' not found"**
- The L-CAS packages might not be properly installed in the container
- Try rebuilding the container from scratch

**"Failed to contact master"**
- ROS environment not properly sourced
- Re-run the sourcing commands manually

**"Gazebo server failed to start"**
- Display/GPU issues
- Check if the desktop interface is accessible

### 8. Manual Environment Reset

If automatic setup failed, manually run:

```bash
cd /home/runner/work/my-cmp3103-ws/my-cmp3103-ws
source /opt/ros/humble/setup.bash
source /opt/ros/lcas/install/setup.bash
colcon build --symlink-install
source install/setup.bash
ros2 launch uol_tidybot tidybot.launch.py
```

### Getting Help

If none of these steps work, please:

1. Share the complete log output from the post-create script
2. Include the output of the verification commands above
3. Mention your host operating system and Docker version