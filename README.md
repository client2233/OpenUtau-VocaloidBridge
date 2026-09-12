# OpenUtau Vocaloid Bridge

用于 Linux 原生 OpenUtau 的插件入口和合成适配层，无需修改或重新编译 OpenUtau。

> 本项目为独立第三方项目，非 Yamaha 或 OpenUtau 官方插件。下文仅以“用户已合法取得一个兼容 API”的**假设条件**说明配置与使用，不指向或提供具体第三方 API 项目。本仓库不捆绑、自动查找、下载或推荐该 API，也不分发编辑器、引擎 DLL、声库或激活数据。假设示例不表示相关 API 实际存在、可获得或已获权利人许可，亦不能替代适用法律和软件许可审查。详见 [项目声明](LEGAL.md)。

## 编译

需要 .NET 10 SDK，以及已安装的 OpenUtau（包含 `OpenUtau.Core.dll`）。

在项目根目录执行，将路径替换为自己的 OpenUtau 安装目录：

```sh
dotnet build openutau-plugin -c Release \
  -p:OpenUtauDirectory=/opt/openutau
```

编译结果：

```text
openutau-plugin/bin/Release/net10.0/OpenUtau.Plugin.VocaloidBridge.dll
```

## 安装

Linux 端需要 Python 3.10+、Tkinter 及 `requirements.txt` 中的依赖。Tkinter 由发行版安装；Python 依赖可使用虚拟环境：

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python openutau-plugin/install.py
```

默认安装到 `${XDG_DATA_HOME:-$HOME/.local/share}/OpenUtau/Plugins/VocaloidBridge/`。自定义 OpenUtau 用户数据目录：

```sh
python openutau-plugin/install.py --data-dir /example/OpenUtau-data
```

安装器会记录当前 Python 和项目路径。请保留项目目录；移动项目或更换 Python 环境后重新运行安装器。不要手动复制 OpenUtau 核心 DLL 或专有引擎 DLL 到插件目录。

## 配置与使用：假设示例

以下步骤**假设**用户已经有权使用一个满足 [API 兼容要求](BACKEND_PROTOCOL.md) 的 Python 接口包，以及能正常运行且授权有效的 Wine 编辑器和传统中文声库。项目不提供这些条件的获取途径，也不认定购买编辑器就包含第三方接口调用许可。

1. 重启 OpenUtau，双击歌唱片段进入钢琴窗。
2. 打开 **批量编辑 → 外部 → VOCALOID / Wine 设置**。
3. 填写下列字段。`/example/…` 均为虚构占位路径，须替换为用户自己的路径。

| 字段 | 填写内容 |
| --- | --- |
| API 项目目录（用户提供） | 假设接口包的根目录，例如 `/example/user-provided-api`；其下须有 `v6api/__init__.py` |
| Wine 程序 | 本机 Wine 可执行文件，例如 `/usr/bin/wine` |
| Wine 前缀 | 用户已有的前缀，例如 `/example/existing-wine-prefix`；目录中应有 `system.reg` |
| Windows Python | 用户单独安装的 x64 Windows Python 可执行文件，例如 `/example/python.exe`；不是 Linux Python |
| V6 编辑器 / DLL 目录 | 用户所安装编辑器的 DLL 目录 |
| V6 公共资源目录 | 用户所安装软件的公共资源目录 |
| 单次合成超时 | 单次后端执行等待时间，默认 120 秒 |
| OpenUtau 用户数据目录 | 与插件安装时使用的用户数据目录一致 |

4. 点击 **保存设置 → 刷新外部声库 → 安装 / 更新声库描述**。
5. 重启 OpenUtau，让生成的声库描述生效；重新打开插件窗口，有效配置时会自动启动桥接，也可点击 **启动桥接**。
6. 在音轨选择相应声库、**ENUNU 渲染器**和 **Default 音素器**。打开过插件菜单后，插件会通过公开的音轨接口为自己的声库启用完整表情传递；普通 ENUNU 声库仍使用原渲染器。表情使用后端名称和原生范围：同名覆盖，不同名新增，旧的 V 前缀参数定义移除。此操作可撤销，保存工程时会保留。
7. 每个音符输入一个 ASCII 拼音音节，例如 `ni3 hao3`。连音音符填 `-`，延续前一个字而不重新咬字；必须紧接前一个发声音符，不能用于首音或休止之后。然后编辑音高、播放或导出。

目录选择器也接受 Wine 前缀中的 Linux 路径，保存时转换为 Windows 路径。目录结构检查不保证 API 版本兼容；此示例不会使不兼容或未授权的接口变得可用。

## 运行行为与限制

- 插件模式下关闭设置窗口仅隐藏，桥接继续运行；再次点击插件菜单可显示窗口。
- 点击 **停止桥接** 可手动停止；退出调用它的 OpenUtau 后会停止它启动的服务。
- 桥接启动成功后，插件会通知 OpenUtau 重新调度预渲染；需启用 OpenUtau 的预渲染设置。
- 服务使用本机 15555 和 15556 端口。真正的端口冲突需先停止旧服务，插件不会接管外部进程。
- 本机验证传统中文声库和拼音；数字声调忽略，ü 使用 `v` 或 `u:`。完整插件通道按 OpenUtau 时间轴转换为毫秒，支持句内变速；独立使用旧 ENUNU/UST 通道仍不支持句内变速，也不传完整表情。
- 本项目没有引擎实际 F0 分析结果，完整通道不提供“加载渲染音高”功能；正常音高编辑、播放和导出不受此限制。

## 表情参数

通常只需调整音高、BRI（亮度）、BRE（气声）和 DYN（后端动态），其余保留默认值。

按后端名称提供参数，不再借用 TEN/TENC、GEN/GENC、BREC 或 VOIC。同名参数覆盖原定义，不同名参数新增；旧的 `V…` 重复定义移除。DYN 只控制后端，不再额外叠加 OpenUtau 响度处理，VOL 不参与插件输出处理。

OpenUtau 的表情列表由工程统一管理，原有其他参数仍可能出现在菜单中，但插件只使用下表中的参数和音高编辑结果。同名覆盖也会改变该工程其他音轨的表情定义，建议不同渲染器分开使用工程。旧工程的表情数值不会自动换算，升级前保留副本并重新检查曲线。

<details>
<summary>完整参数（后端原生范围）</summary>

以下为假设兼容条件下的映射定义。除 VEL 为音符数值外，其余表中参数为曲线；OPE、ACC、DEC 在音符起点采样。

| 参数 | 后端字段 | 范围 / 默认 |
| --- | --- | --- |
| DYN | `dynamics` | 0～127 / 64 |
| BRI | `brightness` | 0～127 / 64 |
| BRE | `breathiness` | 0～127 / 0 |
| CHR | `character` | −64～63 / 0 |
| PBS | `pitchBendSens` | 0～24 / 12 |
| CLE | `clearness` | 0～127 / 0 |
| GWL | `growl` | 0～127 / 0 |
| POR | `portamento` | 0～127 / 64 |
| AIR | `air` | 0～127 / 0 |
| EXC | `exciter` | −64～63 / 0 |
| VEL | 音符 `velocity` | 0～127 / 64；辅音速度 |
| OPE | 音符 `exp.opening` | 0～127 / 127 |
| ACC | 音符 `exp.accent` | 0～100 / 50 |
| DEC | 音符 `exp.decay` | 0～100 / 50 |

音符音高、音高点、PITD 和颤音转换为最终音高曲线，按 5 ms 采样，不额外叠加后端自动颤音。PBS 改变允许的偏移范围；PBS=0 且有非零音高偏移时会报错。参数含义可参考 [官方参考手册](https://rsc-net.vocaloid.com/assets/pdf_files/bb/VOCALOID_Reference_Manual_ENG.pdf)，不保证与编辑器的全部处理链完全相同。

在本机已配置的传统声库的相同基线重复渲染对照中，BRI、BRE、Character、CLE、GWL、POR、DYN、AIR、Exciter、Opening、Accent、Decay 均有明确 PCM 差异。完整 OpenUtau Core → ZMQ → Wine 的链路、变速对齐、精确 VEL、缓存复用/失效、停止服务后的及时返回，以及普通声库隔离也有回归检查。已配置声库的基础拼音和音高渲染均通过；此结果不代表任意接口版本或声库都兼容。

当前没有确认可用的 XSY 曲线/第二声库入口；AI 专属 Expression、Take 和编辑器效果器链不在支持范围。音符 Opening 与独立 Mouth/Voice Color 偏移不可混为同一个接口。其余 Classic 专用表情（例如 MOD、LPF、NORM）没有映射，不会因为出现在工程里就自动传给后端。

</details>

升级本版本需要重新编译和安装**插件 DLL**，并重启 OpenUtau 与桥接；不需要重新编译 OpenUtau。每次启动 OpenUtau 后打开一次插件菜单以启用本次进程的完整通道。

### 检查

无需后端的适配器检查：

```sh
python3 bridge/test_score.py
python3 bridge/test_expressions.py
python3 bridge/test_host.py
python3 enunu/test_protocol.py
```

安装版 OpenUtau Core 的隔离链路检查（先编译主插件；Smoke 构造器检查针对本机验证版本）：

```sh
dotnet build openutau-plugin/Smoke -c Release -p:OpenUtauDirectory=/opt/openutau
python3 openutau-plugin/test_renderer.py --dotnet /example/dotnet
```

前述假设兼容条件满足时，可以额外执行真实后端检查；它们只创建临时请求/音频，不修改外部 API 源码：

```sh
python3 bridge/test_api_expressions.py
python3 bridge/test_api_render.py
python3 openutau-plugin/test_renderer.py --dotnet /example/dotnet --real
```

独立打开设置窗口可运行 `python enunu/configure.py`；未指定父进程时，关闭窗口会停止服务。

不要提交本机配置、Windows Python、第三方 API、日志或授权数据；相关目录及文件已列入 `.gitignore`。发布包仍应单独检查。卸载菜单插件可删除 `Plugins/VocaloidBridge/`；生成的声库描述位于 `Singers/VOCALOID-Wine-*`，与真正的声库数据分开。

## 许可证

项目代码使用 [LGPL 2.1](LICENSE)。第三方依赖和外部 API 的许可独立于本项目，见 [THIRD_PARTY.md](THIRD_PARTY.md) 和 [LEGAL.md](LEGAL.md)。
