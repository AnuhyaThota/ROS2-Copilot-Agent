import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped, Twist

from google import genai
from google.genai import types
import os
import threading
import time
import math
from dotenv import load_dotenv
from ament_index_python.packages import get_package_share_directory
from action_msgs.msg import GoalStatus

env_path = os.path.join(get_package_share_directory('gem_agent_ros2'), '.env')
load_dotenv(dotenv_path=env_path)

get_current_pose_decleration = {
    'name': 'get_current_pose',
    'description': 'Get the pose of the robot',
    'parameters': {
        'type': 'object',
        'properties': {},
    },
}

move_decleration = {
    'name': 'move',
    'description': 'Go to a direction',
    'parameters': {
        'type': 'object',
        'properties': {
            'direction': {
                'type': 'string',
                'description': 'motion direction',
                'enum': ['forward', 'ahead', 'backward', 'back', 'left', 'right']
            },
            'offset': {
                'type': 'number',
                'description': 'motion offset (meters)',
            },
        },
        'required': ['direction', 'offset'],
    }
}

# Make this a valid schema (empty object allowed)
generic_chat_decleration = {
    'name': 'generic_chat',
    'description': 'Fallback chat utility when no tool precisely matches',
    'parameters': {
        'type': 'object',
        'properties': {}
    },
}

detect_object_decleration = {
    'name': 'detect_object',
    'description': 'Detect objects in the environment',
    'parameters': {
        'type': 'object',
        'properties': {},
    },
}

check_navigation_health_decleration = {
    'name': 'check_navigation_health',
    'description': 'Check whether navigation prerequisites are healthy before moving',
    'parameters': {
        'type': 'object',
        'properties': {},
    },
}


class LLMMobile(Node):
    def __init__(self):
        super().__init__('gem_interface')
        self.req_sub = self.create_subscription(String, 'input_request', self.request_cb, 10)
        self.resp_pub = self.create_publisher(String, 'response', 10)
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.pose_sub = self.create_subscription(Odometry, "/odom", self.odom_cb, 10)
        self._action_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.last_odom_time = None
        self.point_reached = True

    def request_cb(self, msg):
        self.get_logger().info(f'Received request: "{msg.data}"')
        thread = threading.Thread(target=self._process_request, args=(msg.data,), daemon=True)
        thread.start()

    def _process_request(self, user_msg: str):
        try:
            response = String()
            response.data = self.generate(user_msg)
            self.resp_pub.publish(response)
        except Exception as e:
            self.get_logger().error(f"Error in request processing thread: {e}")

    def generate(self, user_msg: str) -> str:
        api_key = os.getenv("GEMINI_API_KEY")
        model_name = "gemini-3.5-flash"
        if not api_key:
            self.get_logger().error("GEMINI_API_KEY is missing; cannot call LLM")
            return "GEMINI_API_KEY is missing. Unable to process this request."

        client = genai.Client(api_key=api_key)

        tools = [types.Tool(function_declarations=[
            get_current_pose_decleration,
            move_decleration,
            generic_chat_decleration,
            detect_object_decleration,
            check_navigation_health_decleration,
        ])]

        # Give the model some budget to plan multi-hop
        generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=200),
            system_instruction=(
                "You are a mobile robot assistant. "
                "For locomotion requests, call the move tool with direction and offset in meters. "
                "Be execution-focused: treat 'goal_sent' as in-progress, and only consider movement done when "
                "the move tool returns status='succeeded'. "
                "Before retrying failed motion, call check_navigation_health to guide corrective actions. "
                "If move returns any non-succeeded status, reason about the failure and retry with corrective "
                "steps (for example smaller offsets or repeated steps) until success or a clear terminal error."
            ),
            tools=tools,
        )

        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_msg)],
            )
        ]

        # Helper: run one model turn
        def model_turn(curr_contents):
            self.get_logger().info(f"Calling Gemini model '{model_name}'")
            return client.models.generate_content(
                model=model_name,
                contents=curr_contents,
                config=generate_content_config,
            )

        # Helper: execute a single tool call by name/args
        def execute_tool_call(fc):
            name = fc.name
            args = dict(fc.args or {})
            if name == "get_current_pose":
                return self.get_current_pose()
            elif name == "move":
                self.get_logger().info(f"Tool call: move args={args}")
                return self.move(**args)
            elif name == "generic_chat":
                return self.generic_chat()
            elif name == "detect_object":
                return self.detect_object()
            elif name == "check_navigation_health":
                return self.check_navigation_health()
            else:
                return f"Unknown tool call: {name}"

        # Multi-hop loop
        # Keep asking the model until it stops emitting function calls
        for _ in range(12):  # hard safety cap to prevent infinite loops
            try:
                response = model_turn(contents)
            except Exception as e:
                self.get_logger().error(f"Gemini call failed: {e}")
                return f"Gemini request failed: {e}"
            # Append assistant’s raw content to the transcript
            if response and response.candidates and response.candidates[0].content:
                assistant_content = response.candidates[0].content
            else:
                # Nothing sensible returned
                return getattr(response, "text", "") or "I'm not sure how to respond."

            parts = list(assistant_content.parts or [])
            contents.append(assistant_content)

            # Collect all tool calls in this assistant turn (can be 0..n)
            tool_calls = []
            for p in parts:
                # In the Gemini Python SDK, function calls are exposed as p.function_call when present
                fc = getattr(p, "function_call", None)
                if fc:
                    self.get_logger().info(f"Gemini function_call detected: name={fc.name}, args={dict(fc.args or {})}")
                    tool_calls.append(fc)

            # If no tool calls, return any generated text
            if not tool_calls:
                # Prefer response.text if present; else stitch text parts
                final_text = getattr(response, "text", None)
                if final_text:
                    return final_text
                # Fallback: concatenate any text parts in this turn
                texts = [getattr(p, "text", "") for p in parts if getattr(p, "text", None)]
                return "\n".join(t for t in texts if t)

            # Execute each tool call and append function responses
            for fc in tool_calls:
                result = execute_tool_call(fc)
                self.get_logger().info(f"Tool result for {fc.name}: {result}")
                function_response_part = types.Part.from_function_response(
                    name=fc.name,
                    response={"result": result},
                )
                contents.append(types.Content(role="user", parts=[function_response_part]))

        return "I hit a tool-call loop limit. Please try rephrasing the request."

    def odom_cb(self, msg):
        self.pos_x = msg.pose.pose.position.x
        self.pos_y = msg.pose.pose.position.y
        self.last_odom_time = time.monotonic()

    def check_navigation_health(self):
        now = time.monotonic()
        odom_age_sec = None
        odom_fresh = False
        if self.last_odom_time is not None:
            odom_age_sec = now - self.last_odom_time
            odom_fresh = odom_age_sec < 2.0

        action_server_ready = self._action_client.wait_for_server(timeout_sec=0.2)
        pose_finite = math.isfinite(self.pos_x) and math.isfinite(self.pos_y)

        issues = []
        suggestions = []
        if not action_server_ready:
            issues.append("navigate_to_pose action server unavailable")
            suggestions.append("ensure navigation.launch.py is running and nav2 is active")
        if not odom_fresh:
            issues.append("odom is stale or missing")
            suggestions.append("verify localization and /odom publisher in simulation")
        if not pose_finite:
            issues.append("robot pose is non-finite")
            suggestions.append("reset localization or simulation state")

        status = "healthy" if not issues else "degraded"
        report = {
            "status": status,
            "action_server_ready": action_server_ready,
            "odom_fresh": odom_fresh,
            "odom_age_sec": odom_age_sec,
            "pose": {"x": self.pos_x, "y": self.pos_y},
            "pose_finite": pose_finite,
            "issues": issues,
            "suggestions": suggestions,
        }
        self.get_logger().info(f"Navigation health: {report}")
        return report

    def get_current_pose(self):
        return f"{self.pos_x} {self.pos_y}"

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.point_reached = True
            return
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        self.point_reached = True

    def feedback_callback(self, feedback):
        # self.get_logger().info(f'Received feedback: {feedback.feedback}')
        feedback = True

    def drive_cmd_vel(self, direction, offset):
        direction = str(direction).lower()
        offset = float(offset)

        twist = Twist()
        speed = 0.2
        duration = max(0.5, offset / speed)

        if direction in ("forward", "ahead"):
            twist.linear.x = speed
        elif direction in ("backward", "back"):
            twist.linear.x = -speed
        elif direction == "left":
            twist.angular.z = 0.6
        elif direction == "right":
            twist.angular.z = -0.6
        else:
            return {"status": "invalid_direction", "detail": f"unsupported direction '{direction}'"}

        self.get_logger().info(
            f"Publishing cmd_vel for direction={direction}, offset={offset}, duration={duration:.2f}s"
        )
        self.cmd_vel_pub.publish(twist)
        time.sleep(duration)

        stop = Twist()
        self.cmd_vel_pub.publish(stop)

        return {
            "status": "cmd_vel_sent",
            "direction": direction,
            "offset": offset,
            "duration_sec": duration,
        }

    def move(self, direction, offset):
        direction = str(direction).lower()
        offset = float(offset)
        if offset <= 0:
            return {"status": "invalid_offset", "detail": "offset must be > 0"}

        start_x = self.pos_x
        start_y = self.pos_y

        x = 0.0
        y = 0.0

        if direction in ("forward", "ahead"):
            x = offset
        elif direction in ("backward", "back"):
            x = -offset
        elif direction == "left":
            y = offset
        elif direction == "right":
            y = -offset
        else:
            return {"status": "invalid_direction", "detail": f"unsupported direction '{direction}'"}

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = PoseStamped()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.pose.position.x = self.pos_x + x
        goal_msg.pose.pose.position.y = self.pos_y + y
        goal_msg.pose.pose.orientation.x = 0.0
        goal_msg.pose.pose.orientation.y = 0.0
        goal_msg.pose.pose.orientation.z = 0.0
        goal_msg.pose.pose.orientation.w = 1.0
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()

        if not self._action_client.wait_for_server(timeout_sec=3.0):
            self.get_logger().warn("navigate_to_pose action server unavailable; using direct cmd_vel motion")
            return self.drive_cmd_vel(direction, offset)

        self.point_reached = False
        self._send_goal_future = self._action_client.send_goal_async(
            goal_msg, feedback_callback=self.feedback_callback
        )
        self._send_goal_future.add_done_callback(self.goal_response_callback)
        self.get_logger().info(
            f"Goal sent: direction={direction}, offset={offset}, "
            f"target=({goal_msg.pose.pose.position.x:.2f}, {goal_msg.pose.pose.position.y:.2f})"
        )

        deadline = time.monotonic() + 12.0
        while not self._send_goal_future.done() and time.monotonic() < deadline:
            time.sleep(0.05)
        if not self._send_goal_future.done():
            self.get_logger().error("Timed out waiting for goal acceptance")
            return {
                "status": "goal_acceptance_timeout",
                "target": {"x": goal_msg.pose.pose.position.x, "y": goal_msg.pose.pose.position.y},
            }

        goal_handle = self._send_goal_future.result()
        if goal_handle is None or not goal_handle.accepted:
            self.get_logger().error("Goal was rejected by nav2")
            return {
                "status": "goal_rejected",
                "target": {"x": goal_msg.pose.pose.position.x, "y": goal_msg.pose.pose.position.y},
            }

        result_future = goal_handle.get_result_async()
        deadline = time.monotonic() + 120.0
        while not result_future.done() and time.monotonic() < deadline:
            time.sleep(0.1)
        if not result_future.done():
            self.get_logger().error("Timed out waiting for nav2 result")
            return {
                "status": "result_timeout",
                "target": {"x": goal_msg.pose.pose.position.x, "y": goal_msg.pose.pose.position.y},
            }

        result_obj = result_future.result()
        status_code = int(result_obj.status)
        end_x = self.pos_x
        end_y = self.pos_y
        moved = math.hypot(end_x - start_x, end_y - start_y)
        self.get_logger().info(
            f"Nav2 result status={status_code}, moved={moved:.3f} m, "
            f"start=({start_x:.2f},{start_y:.2f}), end=({end_x:.2f},{end_y:.2f})"
        )

        if status_code != GoalStatus.STATUS_SUCCEEDED:
            return {
                "status": "nav2_failed",
                "nav2_status": status_code,
                "moved_m": moved,
                "start": {"x": start_x, "y": start_y},
                "end": {"x": end_x, "y": end_y},
                "target": {"x": goal_msg.pose.pose.position.x, "y": goal_msg.pose.pose.position.y},
            }

        # Detect false-positive success where odom barely changes.
        if moved < min(0.15, offset * 0.2):
            return {
                "status": "succeeded_but_no_progress",
                "moved_m": moved,
                "start": {"x": start_x, "y": start_y},
                "end": {"x": end_x, "y": end_y},
                "target": {"x": goal_msg.pose.pose.position.x, "y": goal_msg.pose.pose.position.y},
            }

        # Return a quick, synchronous acknowledgment the LLM can use
        return {
            "status": "succeeded",
            "moved_m": moved,
            "start": {"x": start_x, "y": start_y},
            "end": {"x": end_x, "y": end_y},
            "target": {"x": goal_msg.pose.pose.position.x, "y": goal_msg.pose.pose.position.y}
        }

    def generic_chat(self):
        return "Sorry, I cannot serve or understand your request. Can you be more specific?"

    def detect_object(self):
        # For initial testing, return a hardcoded list
        self.get_logger().info("detect_object called")
        return ["block", "sofa", "table"]


def main(args=None):
    rclpy.init(args=args)
    node = LLMMobile()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
