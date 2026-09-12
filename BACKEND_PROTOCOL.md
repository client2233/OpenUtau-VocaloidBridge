# 用户提供的 API 兼容要求

本项目不分发 API 包，也不自动获取它。用户指定的 API 项目根目录必须包含 `v6api/__init__.py`。适配器只在运行时从明确填写的目录导入它，不修改或复制该目录中的代码。

当前适配的 Python 模块为 `v6loader`，以及 `VDM/VDM`、`VDM/VoiceBank`、`DSE/DSE`、`VSM/VSM`、`VSM/Sequence`、`VSM/Track` 和 `VSM/Part`。所需类和方法以 `bridge/worker.py` 的调用为准。目录结构检查不保证接口版本兼容。

配置项为 `api_dir`、`wine`、`wine_prefix`、`windows_python`、`vocaloid_dir`、`common_dir` 和 `timeout_seconds`。路径均由用户填写。Windows 侧适配器、JSON 请求及输出路径通过 Wine 默认 Z: 映射传递；自行修改映射的环境需另行处理。

桥接把 OpenUtau 音符、歌词及 5 ms F0 曲线转换为适配器请求，由我们提供的 `bridge/worker.py` 调用用户提供的 API 包。用户不需要另写外部进程协议入口。

此说明只描述技术兼容要求，不是 API 来源、开发方式或使用权限的证明。使用者和发布者仍须核对适用法律及商业软件许可。示例配置仅作假设示例。

音符请求可含 `velocity`（0..127，默认 64）；桥接从 UST 的 `Velocity` 百分比乘以 0.64、取整并限幅得到此值。它控制后端辅音速度，不代替响度曲线。
