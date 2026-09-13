# 用户提供的 API 兼容要求

本项目不分发 API 包，也不自动获取它。用户指定的 API 项目根目录必须包含 `v6api/__init__.py`。适配器只在运行时从明确填写的目录导入它，不修改或复制该目录中的代码。

当前适配的 Python 模块为 `v6loader`，以及 `VDM/VDM`、`VDM/VoiceBank`、`DSE/DSE`、`VSM/VSM`、`VSM/Sequence`、`VSM/Track` 和 `VSM/Part`。所需类和方法以 `bridge/worker.py` 的调用为准。目录结构检查不保证接口版本兼容。

配置项为 `api_dir`、`wine`、`wine_prefix`、`windows_python`、`vocaloid_dir`、`common_dir` 和 `timeout_seconds`。路径均由用户填写。Linux 通过 Wine 默认 Z: 映射传递适配器、JSON 请求及输出路径，自行修改映射的环境需另行处理；Windows 直接使用本机路径启动 Python，`wine` 和 `wine_prefix` 不参与启动。

桥接把 OpenUtau 音符、歌词及 5 ms F0 曲线转换为适配器请求，由我们提供的 `bridge/worker.py` 调用用户提供的 API 包。用户不需要另写外部进程协议入口。

此说明只描述技术兼容要求，不是 API 来源、开发方式或使用权限的证明。使用者和发布者仍须核对适用法律及商业软件许可。示例配置仅作假设示例。

完整插件通道通过 OpenUtau 公共 `URenderSettings.Renderer` 属性安装 `IRenderer`，取得原生 `RenderPhrase` 的曲线和毫秒时间轴。沿用 ENUNU 音轨标识以兼容原生验证；通过同一 ZMQ 服务的新 `render` 请求传递完整 JSON。它不依赖未合并的外部渲染器插件 API，不修改 Core、不调用私有 Core 方法。测试中的反射仅用于构建 Core 的内部测试对象。

请求包含：

- `notes`：`position_ms`、`duration_ms`、`tone`、拼音 `lyric`、可选 `phoneme`、`velocity`（0..127，默认 64）。可选 `expressions` 支持 `opening`（0..127）、`accent`/`decay`（0..100）。
  连音歌词使用 `-`；必须紧接前一个发声音符。适配器传递原生 `phoneme="-"` 并关闭该音符的音素保护，不把它转换成拼音或重复声母。
- `pitch_curve`：`frame_period_ms`、F0 Hz 数组 `f0`、可选 `sensitivity`（PBS，0..24，默认 12）；PBS 可以是标量或与 F0 等长的数组，0 无法表示非零音高偏移。
- `controller_curves`：控制器名到 `{frame_period_ms, values}` 的映射。`brightness`、`breathiness`、`clearness`、`growl`、`portamento`、`dynamics`、`air` 为 0..127；`character`、`exciter` 为 −64..63。

适配器将连续曲线量化为控制器事件，压缩连续相同值；不会直接调用 DLL 符号。Python API 来源及代码不由本项目提供。DYN/BRE/BRI 等前端映射见 README。

旧 ENUNU/UST 通道仅传音符、歌词、音高和 UST Velocity。其 VEL 百分比乘以 0.64、取整并限幅；部分 Core 版本在 UST 导出前先取整，完整插件通道不受此限制。
