#!/usr/bin/env python3
import rclpy
from rclpy.node import Node

from sensor_msgs.msg import LaserScan, Imu, Image
from nav_msgs.msg import Odometry, OccupancyGrid
from geometry_msgs.msg import Twist, Pose

from std_msgs.msg import Header

from scipy.spatial.transform import Rotation as R

from cv_bridge import CvBridge
import cv2
import numpy as np

# Necessario para publicar o frame map:
from tf2_ros import TransformBroadcaster, StaticTransformBroadcaster
from geometry_msgs.msg import TransformStamped


class RoboMapper(Node):

    def __init__(self):
        super().__init__('robo_mapper')

        # Declara o parâmetro 'robot_name' com valor padrão
        self.declare_parameter('robot_name', 'prm_robot')
        robot_name = self.get_parameter('robot_name').get_parameter_value().string_value

        self.map_frame_id = f'{robot_name}_map'
        self.odom_gt_frame_id = f'{robot_name}_odom_gt'
        
        # Subscribers
        self.create_subscription(LaserScan, f'{robot_name}/scan', self.scan_callback, 10)
        self.create_subscription(Pose, f'/model/{robot_name}/pose', self.odom_callback, 10)
        self.create_subscription(Image, f'{robot_name}/robot_cam/colored_map', self.camera_callback, 10)

        # Utilizado para converter imagens ROS -> OpenCV
        self.bridge = CvBridge()

        # Timer para enviar comandos continuamente
        self.timer = self.create_timer(0.5, self.atualiza_mapa)

        # Estado atual do robo:
        self.x = 0
        self.y = 0
        self.heading = 0

        # Atributos de configuração do mapa
        # Parâmetros do mapa
        self.grid_size = 50  # 50x50 células
        self.resolution = 0.25  # 25 cm por célula

        # Matriz do mapa (-1 = desconhecido)
        self.grid_map = -np.ones((self.grid_size, self.grid_size), dtype=np.int8)

        # Publisher do mapa
        self.map_pub = self.create_publisher(OccupancyGrid, f'{robot_name}/grid_map', 10)

        # Publicando o frame map para vizualização no RVis
        # Utilizar o comando: ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 map odom
        # ou o código abaixo:
        self.tf_static_broadcaster = StaticTransformBroadcaster(self)

        static_tf = TransformStamped()
        static_tf.header.stamp = self.get_clock().now().to_msg()
        static_tf.header.frame_id = self.map_frame_id
        static_tf.child_frame_id = self.odom_gt_frame_id
        static_tf.transform.translation.x = 0.0
        static_tf.transform.translation.y = 0.0
        static_tf.transform.translation.z = 0.0
        static_tf.transform.rotation.w = 1.0  # identidade (Quaternions!!)
        self.tf_static_broadcaster.sendTransform(static_tf)


    def scan_callback(self, msg: LaserScan):
        pass

    def odom_callback(self, msg: Pose):
        # Extrair posição
        self.x = msg.position.x
        self.y = msg.position.y

        # Extrair orientação (quaternion)
        orientation_q = msg.orientation
        quat = [orientation_q.x, orientation_q.y, orientation_q.z, orientation_q.w]

        # Converter de quaternion para Euler (roll, pitch, yaw)
        r = R.from_quat(quat)
        euler = r.as_euler('xyz', degrees=False)

        # Armazenar heading (Z - yaw)
        self.heading = euler[2]


    def camera_callback(self, msg: Image):
        # Converte mensagem ROS para imagem OpenCV (BGR)
        # frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        pass

    def world_to_grid(self, x, y):
        origin_offset = self.grid_size * self.resolution / 2
        gx = int((x + origin_offset) / self.resolution)
        gy = int((y + origin_offset) / self.resolution)
        return gx, gy

    def atualiza_mapa(self):
        # Marcar a posição atual do robô no mapa
        gx, gy = self.world_to_grid(self.x, self.y)
        if 0 <= gx < self.grid_size and 0 <= gy < self.grid_size:
            self.grid_map[gy, gx] = 100  # 100 = célula ocupada (por exemplo, robô)

        # Publicar o mapa
        self.publish_occupancy_grid()

        # Imprimir estado (Opcional)
        #print(f"Posição atual do robô: x = {self.x:.2f}, y = {self.y:.2f}, heading = {self.heading:.2f} rad")

    def publish_occupancy_grid(self):
        grid_msg = OccupancyGrid()
        grid_msg.header.stamp = self.get_clock().now().to_msg()
        grid_msg.header.frame_id = self.map_frame_id

        # Metadados do mapa
        grid_msg.info.resolution = self.resolution
        grid_msg.info.width = self.grid_size
        grid_msg.info.height = self.grid_size

        # Origem do mapa (canto inferior esquerdo do grid no mundo)
        origin = Pose()
        origin.position.x = - (self.grid_size * self.resolution) / 2
        origin.position.y = - (self.grid_size * self.resolution) / 2
        origin.position.z = 0.0
        origin.orientation.w = 1.0
        grid_msg.info.origin = origin

        # Convertendo numpy array para lista 1D em row-major
        grid_msg.data = self.grid_map.flatten().tolist()

        # Publicar
        self.map_pub.publish(grid_msg)

def main(args=None):
    rclpy.init(args=args)
    node = RoboMapper()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
