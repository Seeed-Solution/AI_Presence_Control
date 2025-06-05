### 目标
我希望搭建一个人脸识别的权限控制机的技术，能够识别出本地的人脸，并与云端配置的权限数据库做比对，最终给出 True （在数据库中）/ False（不在数据库中），用于后续进一步配置设备的开启与关闭（这部分由其他用户自己实现）


### 技术架构
AI 传感器（Grove Vision AI V2） ------完整图片(480*480) + 人脸bbox-------> Mqtt
基于 Raspi5+Hailo8 （26Tops）搭建 FaceEmbeding API（python），基于图片和bbox，选择其中面积最大的，做人脸的向量化
NodeRed 从 Mqtt 获取数据，调用 FaceEmbeding API 接口，获取向量，并通过 rest api 访问 Qdrant数据库


### 流程说明
每个嵌入式设备都可以选择匹配的 Collection（集合）
交互上分为两个流程：入库，查询，都基于 nodered 流实现（在 nodered 的 node 中配置（不用更复杂的交互））
 1、入库模式，需要先输入名称，点击确认后，1s 后开始，采集后续 10 帧，计算平均向量后入库。若 一半以上帧不包含人脸，则入库失败
 2、查询模式，对结果进行逐帧比对，若查询到对应人，则返回入库名称


### 相关资料
Grove Vision AI V2 的 rt 返回参见 data/rt_respond.json
处理返回值的 nodered流可以参考：data/access_Vision_ai.json
Hailo face rec 可以参考：data/face_recognition.sh，具体说明详见: https://github.com/hailo-ai/tappas/tree/master/apps/h8/gstreamer/general/face_recognition
Hailo 的 python 示例可以见：data/detection_with_tracker.py，说明详见：https://github.com/hailo-ai/Hailo-Application-Code-Examples/tree/main/runtime/hailo-8/python/detection_with_tracker



