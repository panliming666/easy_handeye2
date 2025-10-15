import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.conditions import IfCondition, LaunchConfigurationEquals
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    # 获取包路径
    easy_handeye2_dir = get_package_share_directory('easy_handeye2')

    # 声明参数
    declare_calibration_type = DeclareLaunchArgument(
        'calibration_type',
        default_value='eye_on_base',
        description='标定类型: eye_in_hand 或 eye_on_base'
    )

    declare_calibration_name = DeclareLaunchArgument(
        'name',
        default_value='handeye_calib',
        description='标定名称，用于保存和加载标定结果'
    )

    declare_robot_base_frame = DeclareLaunchArgument(
        'robot_base_frame',
        default_value='base_link',
        description='机器人基座坐标系'
    )

    declare_robot_effector_frame = DeclareLaunchArgument(
        'robot_effector_frame',
        default_value='tool0',
        description='机器人末端执行器坐标系'
    )

    declare_camera_namespace = DeclareLaunchArgument(
        'camera_namespace',
        default_value='camera',
        description='RealSense相机命名空间'
    )

    declare_camera_base_frame = DeclareLaunchArgument(
        'camera_base_frame',
        default_value='camera_link',
        description='相机基座坐标系'
    )

    declare_camera_optical_frame = DeclareLaunchArgument(
        'camera_optical_frame',
        default_value='camera_color_optical_frame',
        description='相机光学坐标系'
    )

    declare_marker_size = DeclareLaunchArgument(
        'marker_size',
        default_value='0.1',
        description='ArUco标记大小(米)'
    )

    declare_marker_id = DeclareLaunchArgument(
        'marker_id',
        default_value='582',
        description='ArUco标记ID'
    )

    declare_enable_real_sense = DeclareLaunchArgument(
        'enable_real_sense',
        default_value='true',
        description='是否启动RealSense相机'
    )

    declare_enable_aruco = DeclareLaunchArgument(
        'enable_aruco',
        default_value='true',
        description='是否启动aruco_ros'
    )

    declare_freehand_robot_movement = DeclareLaunchArgument(
        'freehand_robot_movement',
        default_value='true',
        description='是否使用手动移动机器人模式'
    )

    # RealSense相机启动
    # 注意：这里假设realsense-ros包已安装，实际使用时需要确保包存在
    realsense_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            get_package_share_directory('realsense2_camera'),
            '/launch/rs_launch.py'
        ]),
        condition=IfCondition(LaunchConfiguration('enable_real_sense')),
        launch_arguments={
            'camera_name': LaunchConfiguration('camera_namespace'),
            'enable_color': 'true',
            'enable_depth': 'true',
            'enable_pointcloud': 'false',
            'enable_sync': 'true',
            'align_depth': 'true',
            'color_fps': '30',
            'depth_fps': '30',
            'depth_width': '640',
            'depth_height': '480',
            'color_width': '640',
            'color_height': '480',
            'publish_tf': 'true',
            'tf_publish_rate': '30',
        }.items()
    )

    # aruco_ros启动
    # 注意：这里假设aruco_ros包已安装，实际使用时需要确保包存在
    aruco_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            get_package_share_directory('aruco_ros'),
            '/launch/single.launch'
        ]),
        condition=IfCondition(LaunchConfiguration('enable_aruco')),
        launch_arguments={
            'camera_name': LaunchConfiguration('camera_namespace'),
            'image_topic': 'color/image_raw',
            'camera_info_topic': 'color/camera_info',
            'marker_size': LaunchConfiguration('marker_size'),
            'marker_id': LaunchConfiguration('marker_id'),
            'reference_frame': LaunchConfiguration('camera_optical_frame'),
            'marker_frame': 'aruco_marker',
            'corner_refinement': 'NONE',
            'publish_tf': 'true',
        }.items()
    )

    # 为眼在手上标定创建虚拟变换发布器
    dummy_calib_eih = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='dummy_publisher_eih',
        condition=LaunchConfigurationEquals('calibration_type', 'eye_in_hand'),
        arguments=[
            '--x', '0', '--y', '0', '--z', '0.1',
            '--qx', '0', '--qy', '0', '--qz', '0', '--qw', '1',
            '--frame-id', LaunchConfiguration('robot_effector_frame'),
            '--child-frame-id', LaunchConfiguration('camera_base_frame')
        ]
    )

    # 为眼在基座上标定创建虚拟变换发布器
    dummy_calib_eob = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='dummy_publisher_eob',
        condition=LaunchConfigurationEquals('calibration_type', 'eye_on_base'),
        arguments=[
            '--x', '1', '--y', '0', '--z', '0',
            '--qx', '0', '--qy', '0', '--qz', '0', '--qw', '1',
            '--frame-id', LaunchConfiguration('robot_base_frame'),
            '--child-frame-id', LaunchConfiguration('camera_base_frame')
        ]
    )

    # 根据标定类型确定tracking base frame
    tracking_base_frame = PythonExpression([
        "'", LaunchConfiguration('camera_optical_frame'), "'",
        " if '",
        LaunchConfiguration('calibration_type'),
        "' == 'eye_in_hand' else '",
        LaunchConfiguration('camera_optical_frame'), "'"
    ])

    # 手眼标定服务器
    handeye_server = Node(
        package='easy_handeye2',
        executable='handeye_server',
        name='handeye_server',
        parameters=[{
            'name': LaunchConfiguration('name'),
            'calibration_type': LaunchConfiguration('calibration_type'),
            'tracking_base_frame': tracking_base_frame,
            'tracking_marker_frame': 'aruco_marker',
            'robot_base_frame': LaunchConfiguration('robot_base_frame'),
            'robot_effector_frame': LaunchConfiguration('robot_effector_frame'),
            'freehand_robot_movement': LaunchConfiguration('freehand_robot_movement'),
        }]
    )

    # 手眼标定RQT GUI
    handeye_rqt_calibrator = Node(
        package='easy_handeye2',
        executable='rqt_calibrator.py',
        name='handeye_rqt_calibrator',
        parameters=[{
            'name': LaunchConfiguration('name'),
            'calibration_type': LaunchConfiguration('calibration_type'),
            'tracking_base_frame': tracking_base_frame,
            'tracking_marker_frame': 'aruco_marker',
            'robot_base_frame': LaunchConfiguration('robot_base_frame'),
            'robot_effector_frame': LaunchConfiguration('robot_effector_frame'),
        }]
    )

    # TF变换可视化节点（可选，用于调试）
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', os.path.join(easy_handeye2_dir, 'resource', 'handeye.rviz')],
        condition=IfCondition(LaunchConfiguration('enable_rviz'))
    )

    # 带延迟的启动序列，确保各个组件按顺序启动
    delayed_aruco = TimerAction(
        period=3.0,  # 等待3秒后启动aruco，确保相机已经启动
        actions=[aruco_launch]
    )

    delayed_handeye = TimerAction(
        period=6.0,  # 等待6秒后启动手眼标定，确保相机和aruco都已经启动
        actions=[handeye_server, handeye_rqt_calibrator]
    )

    return LaunchDescription([
        # 声明所有参数
        declare_calibration_type,
        declare_calibration_name,
        declare_robot_base_frame,
        declare_robot_effector_frame,
        declare_camera_namespace,
        declare_camera_base_frame,
        declare_camera_optical_frame,
        declare_marker_size,
        declare_marker_id,
        declare_enable_real_sense,
        declare_enable_aruco,
        declare_freehand_robot_movement,

        # 默认参数声明
        DeclareLaunchArgument('enable_rviz', default_value='true'),

        # 启动节点
        realsense_launch,
        delayed_aruco,
        dummy_calib_eih,
        dummy_calib_eob,
        delayed_handeye,
        rviz_node,
    ])


if __name__ == '__main__':
    generate_launch_description()