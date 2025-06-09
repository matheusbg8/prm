from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution, Command, LaunchConfiguration
from launch.actions import ExecuteProcess, RegisterEventHandler, DeclareLaunchArgument, OpaqueFunction
from launch.event_handlers import OnProcessExit

from launch_ros.substitutions import FindPackageShare
from launch_ros.actions import Node, PushRosNamespace


import os

# Comando para controlar o robô: ros2 run teleop_twist_keyboard teleop_twist_keyboard

def launch_setup(context, *args, **kwargs):

    # Obtem a string com nome do robo passada por argumento para o launch
    robot_name = LaunchConfiguration('robot_name').perform(context)

    # ------------------------------------------------------
    # Caminho para o arquivo Xacro do robô
    # ------------------------------------------------------
    # Constrói o caminho absoluto para o arquivo `robot.urdf.xacro`,
    # localizado na pasta `description` do pacote `prm`.
    urdf_path = PathJoinSubstitution([
        FindPackageShare("prm"),         # Diretório do pacote `prm`
        "description",                   # Subpasta onde está o modelo
        "robot.urdf.xacro"               # Nome do arquivo Xacro
    ])

    # ------------------------------------------------------
    # Processamento do Xacro para gerar o URDF final
    # ------------------------------------------------------
    # Executa o comando `xacro <caminho>` em tempo de lançamento,
    # resultando no conteúdo URDF expandido como uma string.
    robot_urdf_final = Command([
        "xacro ", urdf_path,
        " robot_name:=", robot_name
    ]) # Importante manter os espacos em branco entre os comandos

    # ------------------------------------------------------
    # Nodo robot_state_publisher
    # ------------------------------------------------------
    # Publica as transformações dos links do robô com base no URDF.
    # Requer o parâmetro 'robot_description' com o conteúdo do modelo.
    diff_drive_params = PathJoinSubstitution([
        FindPackageShare("prm"),
        "config",
        "diff_drive_controller_velocity.yaml"
    ])
    
    robot_state_publisher_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        parameters=[
            {"robot_description": robot_urdf_final}
        ],
    )

    # ------------------------------------------------------
    # Preparação do sistema de controle das rodas do robô
    # ------------------------------------------------------

    # Inicialização do sistema de controle das juntas do robo
    # leitura do estado delas...
    load_joint_state_controller = ExecuteProcess(
        name="activate_joint_state_broadcaster",
        cmd=[
            "ros2", "control", "load_controller",
            "--set-state", "active",
            "joint_state_broadcaster",
        ],
        shell=False,
        output="screen",
    )

    # Inicialização do sistema de controle das rodas/motores do robo
    # o controle das rodas depende do estado das juntas
    start_diff_controller = Node(
        package="controller_manager",
        executable="spawner",
        name="spawner_diff_drive_base_controller",
        # namespace=robot_name,
        arguments=[
            "diff_drive_base_controller"
        ],
        parameters=[diff_drive_params],
        output="screen",
    )

    # Redireciona as mensagens do topico /diff_drive_base_controller/odom para /odom (Conveniencia)
    relay_odom = Node(
        name="relay_odom",
        package="topic_tools",
        executable="relay",
        parameters=[
            {
                "input_topic": "diff_drive_base_controller/odom",
                "output_topic": "odom",
            }
        ],
        output="screen",
    )

    # Redireciona as mensagens do topico /cmd_vel para /diff_drive_base_controller/cmd_vel_unstamped (Conveniencia)
    relay_cmd_vel = Node(
        name="relay_cmd_vel",
        package="topic_tools",
        executable="relay",
        parameters=[
            {
                "input_topic": "cmd_vel",
                "output_topic": "diff_drive_base_controller/cmd_vel_unstamped",
            }
        ],
        output="screen",
    )

    # ------------------------------------------------------
    # RViz: visualização do robô
    # ------------------------------------------------------
    # Carrega o arquivo de configuração do RViz a partir do pacote `prm`.
    rviz_config_file = PathJoinSubstitution([
        FindPackageShare("prm"),
        "rviz",
        "rviz_config.rviz"
    ])

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="screen",
        arguments=["-d", rviz_config_file],  # Define o arquivo de configuração a ser carregado
    )

    # ------------------------------------------------------
    # Spawn do robô no simulador Gazebo
    # ------------------------------------------------------
    # Cria a entidade no mundo simulado utilizando a descrição do robô.
    spawn_entity = Node(
        package="ros_gz_sim",
        executable="create",
        output="screen",
        arguments=[
            "-name", robot_name,          # Nome da entidade no simulador
            "-topic", "robot_description", # Descrição do robô a ser utilizada
            "-z", "1.0",                   # Altura inicial do robô
            "-x", "-2.0",                  # Posição no eixo X
            "--ros-args", "--log-level", "warn"
        ],
        parameters=[{"use_sim_time": True}],  # Usa o tempo simulado
    )

    # ------------------------------------------------------
    # Ponte Gazebo <-> ROS 2 (ros_gz_bridge)
    # ------------------------------------------------------
    # Estabelece a comunicação entre os tópicos do Gazebo e os tipos de mensagem do ROS 2.
    # Sintaxe do bridge: <topico no gazebo>@<tipo do gazebo>@<tipo do ros compativel>
    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name=f"bridge_{robot_name}",
        arguments=[
            f"/{robot_name}/scan@sensor_msgs/msg/LaserScan@ignition.msgs.LaserScan",
            f"/{robot_name}/imu@sensor_msgs/msg/Imu@ignition.msgs.IMU",
            # Camera normal
            # f"/{robot_name}/robot_cam@sensor_msgs/msg/Image@ignition.msgs.Image",
            # f"/{robot_name}/camera_info@sensor_msgs/msg/CameraInfo@ignition.msgs.CameraInfo",
            # Camera de segmentacao semantica
            f"/{robot_name}/robot_cam/labels_map@sensor_msgs/msg/Image@ignition.msgs.Image",
            f"/{robot_name}/robot_cam/colored_map@sensor_msgs/msg/Image@ignition.msgs.Image",
            f"/{robot_name}/robot_cam/camera_info@sensor_msgs/msg/CameraInfo@ignition.msgs.CameraInfo",            
            # Camera de detectao bounding box
            # f"/{robot_name}/boxes_visible_2d_image@sensor_msgs/msg/Image@ignition.msgs.Image",
            # f"/{robot_name}/camera_info@sensor_msgs/msg/CameraInfo@ignition.msgs.CameraInfo",
            # Mensagem com anotacoes nao e suportado pelo ros_gz_bridge
            # Ground Truth de Posicao
            f"/model/{robot_name}/pose@geometry_msgs/msg/Pose[ignition.msgs.Pose",
        ],
        output="screen",
    )

#  Nodo que publica odometria ground truth
    odom_gt= Node(
        package="prm",
        executable="ground_truth_odometry",
        name="odom_gt",
        parameters=[{"robot_name": robot_name}],
        output="screen",
    )

#  Nodo que publica o mapa
    robo_mapper= Node(
        package="prm",
        executable="robo_mapper",
        name="robo_mapper",
        parameters=[{"robot_name": robot_name}],
        output="screen",
    )

#  Casos vocês queiram carregar o controle do robô junto:
#  Não esquecer de descomentar a linha no LaunchDescription
#    controle= Node(
#        package="prm",
#        executable="controle_robo",
#        name="controle_do_robo",
#        arguments="",
#        output="screen",
#    )

    # ------------------------------------------------------
    # Definição da descrição completa do lançamento
    # ------------------------------------------------------
    # Inclui todos os nós definidos acima no lançamento.
    return [
        bridge,
        # PushRosNamespace(robot_name),
        robot_state_publisher_node,
        spawn_entity,
        RegisterEventHandler(
            event_handler=OnProcessExit(  
                target_action=spawn_entity,  # Após carregar o robo no simulador
                on_exit=[load_joint_state_controller], # Carrega o sistema de leitura das juntas
            )
        ),
        RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=load_joint_state_controller, # Após carregar o sistema de leitura das juntas
                on_exit=[start_diff_controller], # Carrega o sistema de controle das rodas/motores
            )
        ),
        odom_gt,
        robo_mapper,
        rviz_node
  #      relay_odom, # Nodos de redirecionamento de mensagens (Estamos usando apenas odom_gt agora)
        # relay_cmd_vel # Nodos de redirecionamento de mensagens
  #      controle        
    ]

def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            name='robot_name',
            default_value='prm_robot',
            description='Nome do robô (modelo e prefixo de sensores)'
        ),
        OpaqueFunction(function=launch_setup)
    ])