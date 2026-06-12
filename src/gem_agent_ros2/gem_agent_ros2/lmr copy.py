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
          'properties': {
            
          },
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
                },
                'offset': {
                    'type': 'number',
                    'description': 'motion offset',
                },
            },
            'required': ['direction', 'offset'],
        }  
    }


generic_chat_decleration = {
        'name': 'generic_chat',
        'description': 'chat',
        'parameters': {},
    }



detect_object_decleration = {
    'name': 'detect_object',
    'description': 'Detect objects in the environment',
    'parameters': {
        'type': 'object',
        'properties': {},
    },
}

get_object_position_declaration = {
    'name': 'get_object_position',
    'description': 'Get the position of an object',
    'parameters': {
        'type': 'object',
        'properties': {
            'object_name': {
                'type': 'string',
                'description': 'Name of the object'
            },
        },
        'required': ['object_name'],
    },
}

plan_path_declaration = {
    'name': 'plan_path',
    'description': 'Plan a path to a target position',
    'parameters': {
        'type': 'object',
        'properties': {
            'target_x': {
                'type': 'number',
                'description': 'Target x coordinate'
            },
            'target_y': {
                'type': 'number',
                'description': 'Target y coordinate'
            },
        },
        'required': ['target_x', 'target_y'],
    },
}

execute_task_declaration = {
    'name': 'execute_task',
    'description': 'Execute a high-level task',
    'parameters': {
        'type': 'object',
        'properties': {
            'task': {
                'type': 'string',
                'description': 'The high-level task to execute'
            },
        },
        'required': ['task'],
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
            self.get_logger().info(f'Received request: \"{msg.data}\"')
            response = String()
            response.data = self.generate(msg.data)
            self.resp_pub.publish(response)
        except Exception as e:
            self.get_logger().error(f"Error in request_cb: {e}")

    def generate(self, msg):
        client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY"),
        )

        tools = [
            types.Tool(function_declarations=[  
                get_current_pose_decleration,
                move_decleration,
                generic_chat_decleration,
                detect_object_decleration,
                get_object_position_declaration,
                plan_path_declaration,
                execute_task_declaration,
            ]),
        ]

        generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_budget=1000,
            ),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=False
            ),
            # Force the model to call 'any' function, instead of chatting.
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode='AUTO')
            ),
            tools=tools,
        )

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=msg),
                ],
            ),
        ]

        model = "gemini-2.5-pro"

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )

        print("Gemini response:", response)

        tool_call = response.candidates[0].content.parts[0].function_call

        if tool_call.name == "get_current_pose":
            result = self.get_current_pose()
        elif tool_call.name == "move":
            result = self.move(**tool_call.args)
        elif tool_call.name == "generic_chat":
            result = self.generic_chat()
        elif tool_call.name == "detect_object":
            result = self.detect_object()
        elif tool_call.name == "get_object_position":
            result = self.get_object_position(**tool_call.args)
        elif tool_call.name == "plan_path":
            result = self.plan_path(**tool_call.args)
        elif tool_call.name == "execute_task":
            result = self.execute_task(**tool_call.args)
        else:
            result = "Unknown tool call"

        function_response_part = types.Part.from_function_response(
            name=tool_call.name,
            response={"result": result},
        )

        contents.append(response.candidates[0].content)
        contents.append(types.Content(role="user", parts=[function_response_part]))

        final_response = client.models.generate_content(
            model=model,
            config=generate_content_config,
            contents=contents,
        )

        return final_response.text

    def odom_cb(self, msg):        
        self.pos_x = msg.pose.pose.position.x
        self.pos_y = msg.pose.pose.position.y

    def get_current_pose(self):
        return str(self.pos_x) + " " + str(self.pos_y)

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
        #self.get_logger().info(f'Received feedback: {feedback.feedback}')
        feedback = True
        
    def move(self, direction, offset):
        x = 0.0
        y = 0.0

        if( direction == "forward" or direction == "ahead"):
            x = offset
        elif( direction == "backward" or direction == "back"):
            x = -offset 
        elif( direction == "left" ):
            y = offset
        elif( direction == "right" ):
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
        self._send_goal_future = self._action_client.send_goal_async(goal_msg, feedback_callback=self.feedback_callback)
        self._send_goal_future.add_done_callback(self.goal_response_callback)

    def generic_chat(self):
        return "Sorry, I can not serve or understand your request. Can be more specific?"
    
    def detect_object(self):
    # For initial testing, return a hardcoded list
        print("detect_object called")
        return ["block", "sofa", "table"]
    
    def get_object_position(self, object_name):
    # Hardcoded positions for testing
        positions = {
            "block": (1.0, 2.0),
            "sofa": (3.5, -1.2),
            "table": (0.0, 0.0)
        }
        pos = positions.get(object_name.lower(), None)
        if pos:
            return f"{object_name} is at position x={pos[0]}, y={pos[1]}"
        else:
            return f"Position of {object_name} is unknown."
        
    def plan_path(self, target_x, target_y):
        # Stub: returns a simple straight-line path as a list of waypoints
        # In a real implementation, you would call a planner or nav2 service
        current_x, current_y = self.pos_x, self.pos_y
        waypoints = [
            {"x": current_x, "y": current_y},
            {"x": (current_x + target_x) / 2, "y": (current_y + target_y) / 2},
            {"x": target_x, "y": target_y}
        ]
        return f"Planned path: {waypoints}"
    
    def execute_task(self, task):
        print(f"Executing high-level task: {task}")
        return f"Started executing: {task}"





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