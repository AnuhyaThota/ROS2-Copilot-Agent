import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped

from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from ament_index_python.packages import get_package_share_directory

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


class LLMMobile(Node):
    def __init__(self):
        super().__init__('gem_interface')
        self.req_sub = self.create_subscription(String, 'input_request', self.request_cb, 10)
        self.resp_pub = self.create_publisher(String, 'response', 10)
        self.pose_sub = self.create_subscription(Odometry, "/odom", self.odom_cb, 10)
        self._action_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.pos_x = 0.0
        self.pos_y = 0.0

    def request_cb(self, msg):
        try:
            self.get_logger().info(f'Received request: "{msg.data}"')
            response = String()
            response.data = self.generate(msg.data)
            self.resp_pub.publish(response)
        except Exception as e:
            self.get_logger().error(f"Error in request_cb: {e}")

    def generate(self, user_msg: str) -> str:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

        tools = [types.Tool(function_declarations=[
            get_current_pose_decleration,
            move_decleration,
            generic_chat_decleration,
            detect_object_decleration,
        ])]

        # Give the model some budget to plan multi-hop
        generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=200),
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
            return client.models.generate_content(
                model="gemini-3-flash-preview",
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
                return self.move(**args)
            elif name == "generic_chat":
                return self.generic_chat()
            elif name == "detect_object":
                return self.detect_object()
            else:
                return f"Unknown tool call: {name}"

        # Multi-hop loop
        # Keep asking the model until it stops emitting function calls
        for _ in range(12):  # hard safety cap to prevent infinite loops
            response = model_turn(contents)
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
                function_response_part = types.Part.from_function_response(
                    name=fc.name,
                    response={"result": result},
                )
                contents.append(types.Content(role="user", parts=[function_response_part]))

        return "I hit a tool-call loop limit. Please try rephrasing the request."

    def odom_cb(self, msg):
        self.pos_x = msg.pose.pose.position.x
        self.pos_y = msg.pose.pose.position.y

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

    def move(self, direction, offset):
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

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = PoseStamped()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.pose.position.x = self.pos_x + x
        goal_msg.pose.pose.position.y = self.pos_y + y
        goal_msg.pose.pose.orientation.x = 0.0
        goal_msg.pose.pose.orientation.y = 0.0
        goal_msg.pose.pose.orientation.z = 0.0
        goal_msg.pose.pose.orientation.w = 1.0

        self._action_client.wait_for_server()
        self._send_goal_future = self._action_client.send_goal_async(
            goal_msg, feedback_callback=self.feedback_callback
        )
        self._send_goal_future.add_done_callback(self.goal_response_callback)

        # Return a quick, synchronous acknowledgment the LLM can use
        return {
            "status": "goal_sent",
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
