from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution, FindExecutable, LaunchConfiguration
from launch.actions import SetEnvironmentVariable, ExecuteProcess, DeclareLaunchArgument
from launch.conditions import IfCondition

from launch_ros.substitutions import FindPackageShare
from launch_ros.actions import Node

import os

def generate_launch_description():
    # ------------------------------------------------------
    # Configuração de variáveis de ambiente para o Gazebo
    # ------------------------------------------------------
    # A variável GZ_SIM_SYSTEM_PLUGIN_PATH é usada para localizar plugins no Gazebo.
    # Ela é composta pelo caminho atual e pelo conteúdo de LD_LIBRARY_PATH.
    gz_env = {
        'GZ_SIM_SYSTEM_PLUGIN_PATH': ':'.join([
            os.environ.get('GZ_SIM_SYSTEM_PLUGIN_PATH', default=''),
            os.environ.get('LD_LIBRARY_PATH', default='')
        ])
    }

    # Nível de verbosidade do Gazebo (0: silencioso, 4: mais detalhado)
    gz_verbosity = '3'

    # ------------------------------------------------------
    # Caminho para o mundo a ser carregado
    # ------------------------------------------------------

    # Verifica argumento com o nome do mundo que será simulado
    world_file_arg = DeclareLaunchArgument(
        'world',
        default_value='arena.sdf',
        description='Nome do arquivo .sdf do mundo a ser carregado'
    )

    # Encontra o diretório de instalação do pacote 'prm'.
    pkg_share = FindPackageShare("prm").find("prm")

    # Nome do arquivo do mundo (SDF) a ser carregado

    # Recupera dos parametros ou utiliza o default
    world_file_name =  world_file_name = LaunchConfiguration('world')

    # Caminho completo para o arquivo do mundo
    world_path = PathJoinSubstitution([
        pkg_share,
        "world",
        world_file_name
    ])

# Alguns teste utilizando cenários já existentes no gazebo
#    world_path='/usr/share/ignition/ignition-gazebo6/worlds/sensors_demo.sdf'
#    world_path='/usr/share/ignition/ignition-gazebo6/worlds/heightmap.sdf'
#    world_path='/usr/share/ignition/ignition-gazebo6/worlds/fuel.sdf'
#    world_path='/usr/share/ignition/ignition-gazebo6/worlds/actor_crowd.sdf'
#    world_path='/usr/share/ignition/ignition-gazebo6/worlds/auv_controls.sdf'
#    world_path='/usr/share/ignition/ignition-gazebo6/worlds/buoyancy.sdf'
#    world_path='/usr/share/ignition/ignition-gazebo6/worlds/fuel_textured_mesh.sdf'
#    world_path='/usr/share/ignition/ignition-gazebo6/worlds/visualize_lidar.sdf'
#    world_path='/usr/share/ignition/ignition-gazebo6/worlds/segmentation_camera.sdf'
#    world_path='/usr/share/ignition/ignition-gazebo6/worlds/boundingbox_camera.sdf'
#    world_path='/usr/share/ignition/ignition-gazebo6/worlds/spherical_coordinates.sdf'
#    world_path='/usr/share/ignition/ignition-gazebo6/worlds/rolling_shapes.sdf'

    # ------------------------------------------------------
    # Inicialização do simulador Gazebo
    # ------------------------------------------------------
    # Executa o comando: ign gazebo -r -v <verbosity> <world_path>
    # Inicia o Gazebo em modo headless (sem GUI), com nível de log definido.
    gazebo = ExecuteProcess(
        cmd=['ruby', FindExecutable(name="ign"), 'gazebo', '-r', '-v', gz_verbosity, world_path],
        output='screen',
        additional_env=gz_env,
        shell=False,
    )

    # ------------------------------------------------------
    # Configuração do caminho de recursos do Gazebo
    # ------------------------------------------------------
    # Define a variável de ambiente IGN_GAZEBO_RESOURCE_PATH para que o Gazebo
    # consiga localizar os modelos personalizados armazenados no pacote.
    gz_models_path = ":".join([
        pkg_share,
        os.path.join(pkg_share, "models")
    ])

    gz_set_env = SetEnvironmentVariable(
        name="IGN_GAZEBO_RESOURCE_PATH",
        value=gz_models_path,
    )

    # ------------------------------------------------------
    # Ponte Gazebo <-> ROS 2
    # ------------------------------------------------------
    # Estabelece comunicação entre a câmera do céu no Gazebo e o ROS 2.
    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="ros_gz_bridge_world",
        arguments=[
            "/sky_cam@sensor_msgs/msg/Image@ignition.msgs.Image",
            # Necessário para controladores como diff_drive_controller
            "/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock"
        ],
        output="screen",
    )

    # ------------------------------------------------------
    # Descrição completa do lançamento
    # ------------------------------------------------------
    # Inclui as configurações de ambiente, a ponte e o lançamento do Gazebo.
    return LaunchDescription([
        world_file_arg,
        gz_set_env,
        bridge,
        gazebo
    ])
