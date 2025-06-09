#!/usr/bin/env python3
import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Pose
from nav_msgs.msg import Odometry
from tf2_ros import TransformBroadcaster
from geometry_msgs.msg import TransformStamped

from builtin_interfaces.msg import Time
from rclpy.time import Time as RclpyTime

class GroundTruthOdomPublisher(Node):
    def __init__(self):
        super().__init__('ground_truth_odom_publisher')

        # Declara o parâmetro 'robot_name' com valor padrão
        self.declare_parameter('robot_name', 'prm_robot')
        robot_name = self.get_parameter('robot_name').get_parameter_value().string_value

        # Assinatura no tópico de pose vinda do simulador
        self.create_subscription(Pose, f'/model/{robot_name}/pose', self.pose_callback, 10)

        # Publicador de odometria ground truth
        self.odom_pub = self.create_publisher(Odometry, f'{robot_name}/odom_gt', 10)

        # Broadcaster de TF: odom_gt -> base_link
        self.tf_broadcaster = TransformBroadcaster(self)

        # Base frame
        self.base_frame = f'{robot_name}_base_link'
        self.odom_frame = f'{robot_name}_odom_gt'

    def pose_callback(self, msg: Pose):
        now = self.get_clock().now().to_msg()

        # Publica a odometria no tópico robot_name/odom_gt
        odom_msg = Odometry()
        odom_msg.header.stamp = now
        odom_msg.header.frame_id = self.odom_frame
        odom_msg.child_frame_id = self.base_frame

        odom_msg.pose.pose = msg

        self.odom_pub.publish(odom_msg)

        # Publica também o TF correspondente
        tf_msg = TransformStamped()
        tf_msg.header.stamp = now
        tf_msg.header.frame_id = self.odom_frame
        tf_msg.child_frame_id = self.base_frame
        tf_msg.transform.translation.x = msg.position.x
        tf_msg.transform.translation.y = msg.position.y
        tf_msg.transform.translation.z = msg.position.z
        tf_msg.transform.rotation = msg.orientation

        self.tf_broadcaster.sendTransform(tf_msg)

def main(args=None):
    rclpy.init(args=args)
    node = GroundTruthOdomPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
