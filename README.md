# ROS2 Workspace: Maze Navigation + Gemini Agent + MCP

This workspace contains ROS2 packages for:

- Maze simulation and navigation (`nav2_mobile_robot`)
- Natural-language robot control with Gemini (`gem_agent_ros2`)
- ROS2 MCP server for AI tooling integration (`ros2_mcp`)

## Workspace Layout

- `src/nav2_mobile_robot`: Gazebo maze world, robot model, Nav2 config, launch files
- `src/gem_agent_ros2`: ROS2 node that uses Gemini and ROS topics/actions
- `src/ros2_mcp`: MCP server exposing ROS2 tools over SSE

## Prerequisites

- ROS2 Humble environment (already provided by this devcontainer)
- Built workspace:

```bash
cd /workspaces/my-cmp3103-ws
rosdep install -i --from-paths src/ --rosdistro humble -y
colcon build
source install/setup.bash
```

## Quick Start: Maze World

In terminal 1:

```bash
cd /workspaces/my-cmp3103-ws
source install/setup.bash
ros2 launch nav2_mobile_robot nav2_mobile_robot_gazebo.launch.py
```

This starts Gazebo with `maze.sdf`, robot spawn, and ROS-Gazebo bridges (`/cmd_vel`, `/odom`, `/lidar`, `/tf`).

## Test Topics and Manual Motion

In terminal 2:

```bash
cd /workspaces/my-cmp3103-ws
source install/setup.bash
ros2 topic list | egrep "cmd_vel|odom|lidar|tf"
```

Move forward:

```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.2, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

Rotate:

```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.6}}"
```

Stop:

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
```

## Run Navigation Stack

In separate terminals after simulation is up:

Localization + map server:

```bash
cd /workspaces/my-cmp3103-ws
source install/setup.bash
ros2 launch nav2_mobile_robot amcl.launch.py
```

Nav2:

```bash
cd /workspaces/my-cmp3103-ws
source install/setup.bash
ros2 launch nav2_mobile_robot navigation.launch.py
```

Alternative (mapping instead of AMCL):

```bash
ros2 launch nav2_mobile_robot slam.launch.py
```

## Natural-Language Robot Control (Gemini)

`gem_agent_ros2` listens to:

- request topic: `/input_request` (`std_msgs/String`)
- response topic: `/response` (`std_msgs/String`)

### 1) Configure API key

Set your key in:

- `src/gem_agent_ros2/.env`

Example:

```env
GEMINI_API_KEY=your_actual_key_here
```

The node loads this `.env` automatically at startup.

### 2) Run the Gemini ROS2 node

In terminal 4:

```bash
cd /workspaces/my-cmp3103-ws
source install/setup.bash
ros2 run gem_agent_ros2 lmr
```

### 3) Send natural-language commands

Watch responses:

```bash
ros2 topic echo /response
```

Publish requests:

```bash
ros2 topic pub --once /input_request std_msgs/msg/String "{data: 'move forward 1 meter'}"
ros2 topic pub --once /input_request std_msgs/msg/String "{data: 'move left 0.5 meter'}"
ros2 topic pub --once /input_request std_msgs/msg/String "{data: 'where are you now?'}"
```

## ROS2 MCP Server

For MCP server usage and SSE endpoint details, see:

- `src/ros2_mcp/README.md`

Quick run command:

```bash
cd /workspaces/my-cmp3103-ws
source install/setup.bash
ros2 run ros2_mcp ros2_mcp_server
```

Typical endpoint when running:

- `http://localhost:8000/sse`

## Troubleshooting

- If no movement from natural-language commands, verify action server:

```bash
ros2 action list | grep navigate_to_pose
```

- Verify Gemini node is running:

```bash
ros2 node list | grep gem_interface
```

- Verify topics exist:

```bash
ros2 topic list | grep -E "input_request|response|cmd_vel|odom|lidar"
```

- If simulation issues occur, check `.devcontainer/TROUBLESHOOTING.md`.

## References

1. [cmp3103-ws](https://github.com/UoL-SoCS/cmp3103-ws)
2. [ROS2 MCP package docs](src/ros2_mcp/README.md)
