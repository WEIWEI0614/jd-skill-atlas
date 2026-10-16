#!/usr/bin/env python3
"""生成 atlas/data/resources.yaml —— 每个技能的最佳公开学习资源。

所有 URL 均经 HTTP 状态码逐个验证（200/2xx/3xx）；少数站点对自动请求返回 403
（opencv docs / linuxfoundation wiki），它们在浏览器中可正常访问，保留并标注。
"""
from __future__ import annotations

import pathlib
import sys

import yaml

# (url, 说明, 类型)  类型：course / docs / repo / paper / wiki / tool
R: dict[str, list[tuple[str, str, str]]] = {
 # ============================ 机器人进阶 ============================
 "zmp": [
   ("https://underactuated.csail.mit.edu/", "MIT 6.832 欠驱动机器人 · Tedrake（全免费，含 Drake notebook）", "course"),
   ("https://hades.mech.northwestern.edu/index.php/Modern_Robotics", "Modern Robotics 官方主页 · Lynch & Park（预印本免费）", "course"),
   ("https://en.wikipedia.org/wiki/Zero_moment_point", "ZMP 定义与推导", "wiki"),
   ("https://drake.mit.edu/", "Drake 官方文档（含双足与接触的教程）", "docs"),
 ],
 "lipm": [
   ("https://underactuated.csail.mit.edu/simple_legs.html", "欠驱动教材 · 简化腿模型一章（LIPM 的推导起点）", "course"),
   ("https://github.com/RussTedrake/underactuated", "教材全部代码与 notebook（可直接跑）", "repo"),
   ("https://drake.mit.edu/", "Drake 官方文档", "docs"),
 ],
 "wbc": [
   ("https://underactuated.csail.mit.edu/humanoids.html", "欠驱动教材 · 人形机器人一章（全身控制与任务优先级）", "course"),
   ("https://github.com/stack-of-tasks/pinocchio", "Pinocchio · 刚体动力学库（WBC 的数值底座）", "repo"),
   ("https://github.com/RussTedrake/underactuated", "教材代码", "repo"),
 ],
 "contact-dynamics": [
   ("https://mujoco.readthedocs.io/en/stable/", "MuJoCo 官方文档（接触模型参数的权威说明）", "docs"),
   ("https://github.com/google-deepmind/mujoco", "MuJoCo 开源仓库", "repo"),
   ("https://en.wikipedia.org/wiki/Contact_mechanics", "接触力学基础", "wiki"),
   ("https://github.com/stack-of-tasks/pinocchio", "Pinocchio · 含接触力学的刚体库", "repo"),
 ],
 "actuator-control": [
   ("https://simplefoc.com/", "SimpleFOC · 开源 FOC 项目官网（最快跑通三环的路径）", "tool"),
   ("https://docs.odriverobotics.com/", "ODrive 官方文档（工程级 FOC 与力矩控制）", "docs"),
   ("https://github.com/simplefoc/Arduino-FOC", "SimpleFOC 源码（含坐标变换实现）", "repo"),
 ],
 "calibration": [
   ("https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html", "OpenCV 相机标定官方教程（该站屏蔽自动请求，浏览器可正常打开）", "docs"),
   ("https://github.com/ethz-asl/kalibr", "Kalibr · 多相机 + IMU 联合标定的工业级工具", "repo"),
   ("https://en.wikipedia.org/wiki/Camera_resectioning", "相机标定的数学框架（PnP 问题）", "wiki"),
 ],
 "state-estimation": [
   ("https://www.kalmanfilter.net/", "卡尔曼滤波交互式教程（从 1D 讲到 EKF）", "course"),
   ("https://github.com/HKUST-Aerial-Robotics/VINS-Mono", "VINS-Mono · 视觉惯性里程计经典实现", "repo"),
   ("https://github.com/rpng/open_vins", "OpenVINS · 教学友好的 VIO 代码库", "repo"),
   ("https://github.com/ethz-asl/maplab", "maplab · 多传感器建图与定位", "repo"),
 ],
 "retargeting": [
   ("https://github.com/YanjieZe/GMR", "General Motion Retargeting（人体动作 → 机器人的开源实现）", "repo"),
   ("https://github.com/LeCAR-Lab/human2humanoid", "Human2Humanoid · 人体动作迁移到人形机器人", "repo"),
 ],
 "data-flywheel": [
   ("https://github.com/huggingface/lerobot", "LeRobot · 采集 / 训练 / 部署的开源全链路（含 SO-101 机械臂）", "repo"),
   ("https://robotics-transformer-x.github.io/", "Open X-Embodiment · 跨本体数据集与标准", "paper"),
   ("https://github.com/Physical-Intelligence/openpi", "openpi · π0 开源实现（后训练数据流程可参考）", "repo"),
   ("https://huggingface.co/docs/lerobot/index", "LeRobot 官方文档", "docs"),
 ],
 "loco-manipulation": [
   ("https://github.com/LeCAR-Lab/human2humanoid", "全身协调（走 + 操作）的开源实现", "repo"),
   ("https://github.com/google-deepmind/mujoco_menagerie", "MuJoCo Menagerie · 现成的高质量机器人模型", "repo"),
   ("https://github.com/google-deepmind/mujoco", "MuJoCo 引擎", "repo"),
 ],
 "realtime-scheduling": [
   ("https://wiki.linuxfoundation.org/realtime/start", "Linux 实时内核官方 Wiki（该站屏蔽自动请求，浏览器可打开）", "docs"),
   ("https://docs.ros.org/en/iron/Tutorials/Advanced/Real-time-programming.html", "ROS 2 实时编程官方教程", "docs"),
   ("https://en.wikipedia.org/wiki/Real-time_computing", "实时计算的确定性含义", "wiki"),
 ],
 "onboard-compute": [
   ("https://developer.nvidia.com/embedded/jetpack", "NVIDIA JetPack / Jetson 端侧部署套件", "tool"),
   ("https://docs.nvidia.com/deeplearning/tensorrt/", "TensorRT 官方文档（算子融合与量化部署）", "docs"),
 ],
 "force-tactile-fusion": [
   ("https://github.com/facebookresearch/tacto", "Tacto · 触觉仿真（视觉 + 触觉融合研究常用）", "repo"),
   ("https://github.com/facebookresearch/digit-design", "DIGIT · 开源光学触觉传感器（含硬件设计）", "repo"),
   ("https://en.wikipedia.org/wiki/Tactile_sensor", "触觉传感器原理", "wiki"),
 ],
 "dual-system-arch": [
   ("https://www.figure.ai/news/helix", "Figure Helix · 商用双系统架构的公开说明", "docs"),
   ("https://www.physicalintelligence.company/blog/pi0", "Physical Intelligence π0 · 分层策略的公开技术说明", "docs"),
   ("https://github.com/Physical-Intelligence/openpi", "openpi · π0 开源实现", "repo"),
 ],
 "robot-lifecycle": [
   ("https://en.wikipedia.org/wiki/Reliability_engineering", "可靠性工程（串联系统、浴盆曲线）", "wiki"),
   ("https://en.wikipedia.org/wiki/Failure_rate", "失效率与 MTBF 的定义", "wiki"),
   ("https://www.aiag.org/", "AIAG · 汽车行业质量标准发布方（IATF 16949 相关）", "tool"),
 ],
 # ============================ AI Infra 深水区 ============================
 "kv-cache": [
   ("https://docs.vllm.ai/en/latest/", "vLLM 官方文档（KV Cache 管理的工程实现）", "docs"),
   ("https://arxiv.org/abs/2405.04434", "DeepSeek-V2 论文 · MLA 把 KV 压到低秩潜空间", "paper"),
   ("https://github.com/vllm-project/vllm", "vLLM 源码（含 block_manager）", "repo"),
   ("https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture)", "Transformer 架构基础", "wiki"),
 ],
 "paged-attention": [
   ("https://arxiv.org/abs/2309.06180", "PagedAttention 原论文（vLLM）", "paper"),
   ("https://blog.vllm.ai/2023/06/20/vllm.html", "vLLM 官方博客 · 分页显存的原理解释", "docs"),
   ("https://docs.vllm.ai/en/latest/", "vLLM 官方文档", "docs"),
 ],
 "continuous-batching": [
   ("https://www.anyscale.com/blog/continuous-batching-llm-inference", "连续批处理的经典解释（Ray/Anyscale）", "docs"),
   ("https://docs.vllm.ai/en/latest/", "vLLM 调度器与批处理实现", "docs"),
 ],
 "pd-disaggregation": [
   ("https://docs.vllm.ai/en/latest/features/disagg_prefill.html", "vLLM 官方 · 预填充/解码分离部署文档", "docs"),
   ("https://github.com/vllm-project/vllm", "vLLM 源码", "repo"),
 ],
 "speculative-decoding": [
   ("https://docs.vllm.ai/en/latest/features/spec_decode.html", "vLLM 官方 · 投机解码配置与说明", "docs"),
   ("https://arxiv.org/abs/2211.17192", "投机解码原论文 · Fast Inference from Transformers", "paper"),
 ],
 "quantization": [
   ("https://arxiv.org/abs/2210.17323", "GPTQ 论文 · 二阶误差补偿的逐层量化", "paper"),
   ("https://arxiv.org/abs/2306.00978", "AWQ 论文 · 激活感知的权重量化", "paper"),
   ("https://github.com/vllm-project/llm-compressor", "llm-compressor · 生产级量化工具（含 FP8 / INT4）", "repo"),
 ],
 "parallelism": [
   ("https://github.com/NVIDIA/Megatron-LM", "Megatron-LM · TP/PP 的参考实现", "repo"),
   ("https://www.deepspeed.ai/tutorials/zero/", "DeepSpeed ZeRO 官方教程（三阶段分片）", "docs"),
   ("https://huggingface.co/spaces/nanotron/ultrascale-playbook", "Ultra-Scale Playbook · 并行策略决策树（强烈推荐）", "course"),
 ],
 "collective-comm": [
   ("https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/index.html", "NCCL 官方文档（含各原语的语义）", "docs"),
   ("https://github.com/NVIDIA/nccl-tests", "nccl-tests · 实测集合通信带宽的标准工具", "repo"),
 ],
 "prefix-caching": [
   ("https://docs.sglang.ai/", "SGLang 官方文档（RadixAttention 的原产地）", "docs"),
   ("https://github.com/sgl-project/sglang", "SGLang 源码", "repo"),
   ("https://docs.vllm.ai/en/latest/features/automatic_prefix_caching.html", "vLLM 的自动前缀缓存", "docs"),
 ],
 "serving-metrics": [
   ("https://docs.vllm.ai/en/latest/", "vLLM 文档（性能指标与压测方法）", "docs"),
   ("https://github.com/vllm-project/vllm/tree/main/benchmarks", "vLLM 官方压测脚本（照它扫四维就对了）", "repo"),
 ],
 "long-context": [
   ("https://arxiv.org/abs/2309.00071", "YaRN · 位置编码外推的代表方法", "paper"),
   ("https://github.com/huggingface/transformers", "Transformers 源码（各注意力实现都在这里）", "repo"),
   ("https://en.wikipedia.org/wiki/Attention_(machine_learning)", "注意力机制基础", "wiki"),
 ],
 "mixed-precision": [
   ("https://pytorch.org/docs/stable/notes/amp_examples.html", "PyTorch AMP 官方示例（混合精度实践）", "docs"),
   ("https://github.com/Dao-AILab/flash-attention", "FlashAttention · online softmax 解决数值溢出", "repo"),
   ("https://en.wikipedia.org/wiki/Mixed-precision_arithmetic", "混合精度算术（bf16 与 fp16 的范围差异）", "wiki"),
 ],
 "moe": [
   ("https://huggingface.co/blog/moe", "Hugging Face · MoE 架构图解", "docs"),
   ("https://arxiv.org/abs/2412.19437", "DeepSeek-V3 论文 · 工程细节最全的 MoE 报告", "paper"),
   ("https://github.com/deepseek-ai/DeepEP", "DeepEP · MoE 专家并行的通信库", "repo"),
 ],
 "mcp": [
   ("https://modelcontextprotocol.io/", "MCP 官方规范与文档", "docs"),
   ("https://github.com/modelcontextprotocol/servers", "官方与社区 MCP 服务端集合（可直接读实现）", "repo"),
 ],
 "llm-app-platform": [
   ("https://docs.dify.ai/", "Dify 官方文档", "docs"),
   ("https://github.com/langgenius/dify", "Dify 开源仓库", "repo"),
 ],
 # ============================ 生态与流程 ============================
 "dds": [
   ("https://docs.ros.org/en/iron/Concepts/Intermediate/About-Quality-of-Service-Settings.html", "ROS 2 QoS 官方说明（配错就会「看不到数据」）", "docs"),
   ("https://fast-dds.docs.eprosima.com/en/latest/", "Fast DDS 官方文档（ROS 2 默认实现之一）", "docs"),
 ],
 "umi": [
   ("https://github.com/real-stanford/universal_manipulation_interface", "UMI 官方仓库（含硬件设计与采集流程）", "repo"),
   ("https://umi-gripper.github.io/", "UMI 项目主页（含论文与视频）", "paper"),
 ],
 "hardware-bus": [
   ("https://learn.sparkfun.com/tutorials/serial-peripheral-interface-spi/all", "SPI 入门教程（含 CPOL/CPHA 时序）", "course"),
   ("https://learn.sparkfun.com/tutorials/i2c/all", "I2C 入门教程（含地址冲突与上拉电阻）", "course"),
 ],
 "auto-quality-tools": [
   ("https://en.wikipedia.org/wiki/Advanced_product_quality_planning", "APQP · 产品先期质量策划", "wiki"),
   ("https://en.wikipedia.org/wiki/Production_part_approval_process", "PPAP · 生产件批准程序", "wiki"),
   ("https://en.wikipedia.org/wiki/Statistical_process_control", "SPC · 统计过程控制与控制图", "wiki"),
   ("https://www.aiag.org/", "AIAG · 五大工具的发布方（可下载标准目录）", "tool"),
 ],
 "npi": [
   ("https://en.wikipedia.org/wiki/New_product_development", "新产品开发流程概览（EVT/DVT/PVT 的上位框架）", "wiki"),
 ],
 "emc": [
   ("https://en.wikipedia.org/wiki/Electromagnetic_compatibility", "电磁兼容 · EMI/EMS、屏蔽、接地、滤波", "wiki"),
 ],
 "checkpoint-resilience": [
   ("https://pytorch.org/docs/stable/checkpoint.html", "PyTorch 激活重计算（gradient checkpointing）", "docs"),
   ("https://docs.pytorch.org/docs/stable/distributed.checkpoint.html", "PyTorch 分布式检查点（大模型存盘的官方方案）", "docs"),
 ],
 "hf-ecosystem": [
   ("https://huggingface.co/docs", "Hugging Face 官方文档总入口", "docs"),
   ("https://huggingface.co/docs/transformers/index", "Transformers 文档", "docs"),
   ("https://github.com/huggingface/lerobot", "LeRobot（机器人方向的开源生态）", "repo"),
 ],
 "hmi": [
   ("https://github.com/ros2/rviz", "RViz · ROS 2 官方可视化与调试界面", "repo"),
   ("https://en.wikipedia.org/wiki/User_interface_design", "界面设计基础（含实时性与安全交互原则）", "wiki"),
 ],
}


def main() -> int:
    out = pathlib.Path(__file__).resolve().parent.parent / "atlas" / "data" / "resources.yaml"
    doc = {
        "note": "每个技能对应的公开学习资源。所有 URL 均已逐个验证 HTTP 状态码。",
        "kinds": {"course": "课程 / 教材", "docs": "官方文档", "repo": "开源仓库",
                  "paper": "论文", "wiki": "词条 / 速查", "tool": "工具 / 项目"},
        "resources": {
            sid: [{"url": u, "label": l, "kind": k} for u, l, k in items]
            for sid, items in R.items()
        },
    }
    head = (
        "# 学习资源映射（skill id → 公开资源）\n"
        "# ---------------------------------------------------------------------------\n"
        "# 与 skills/*.yaml 解耦：改资源不动词典，改词典不动资源。\n"
        "# 所有 URL 均以 curl 逐个验证过状态码；个别站点（OpenCV docs / Linux Foundation\n"
        "# wiki）对自动请求返回 403，但浏览器访问正常，已在 label 中注明。\n"
        "#\n"
        "# kind 取值：course 课程/教材 · docs 官方文档 · repo 开源仓库 ·\n"
        "#            paper 论文 · wiki 词条/速查 · tool 工具/项目\n"
        "# ---------------------------------------------------------------------------\n\n"
    )
    out.write_text(head + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120),
                   encoding="utf-8")
    total = sum(len(v) for v in R.values())
    print(f"✓ {out}")
    print(f"  {len(R)} 个技能 · {total} 条资源")
    from collections import Counter
    c = Counter(k for items in R.values() for _, _, k in items)
    print("  类型分布：" + " · ".join(f"{k} {v}" for k, v in c.most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
