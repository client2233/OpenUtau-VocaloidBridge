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
6. 在音轨选择相应声库、**ENUNU 渲染器**和 **Default 音素器**。
7. 每个音符输入一个 ASCII 拼音音节，例如 `ni3 hao3`，然后编辑音高、播放或导出。

目录选择器也接受 Wine 前缀中的 Linux 路径，保存时转换为 Windows 路径。目录结构检查不保证 API 版本兼容；此示例不会使不兼容或未授权的接口变得可用。

## 运行行为与限制

- 插件模式下关闭设置窗口仅隐藏，桥接继续运行；再次点击插件菜单可显示窗口。
- 点击 **停止桥接** 可手动停止；退出调用它的 OpenUtau 后会停止它启动的服务。
- 桥接启动成功后，插件会通知 OpenUtau 重新调度预渲染；需启用 OpenUtau 的预渲染设置。
- 服务使用本机 15555 和 15556 端口。真正的端口冲突需先停止旧服务，插件不会接管外部进程。
- 音高曲线（含滑音和 OpenUtau 颤音）映射为后端 PIT，PBS 固定为 12 半音；DYN 由 OpenUtau 在渲染后调整响度。实验性 VEL 通过 UST 传给后端音符 velocity：100 → 64，0 → 0，200 → 127，用于辅音速度，非音量。真实渲染对照中 127 相对默认 64 有明显波形差异，但 0 几乎无差异；尚未验证所有声库和音节的辅音时长。可运行 `python3 bridge/test_api_velocity.py` 复测。注意部分 OpenUtau 版本的 ENUNU 导出会先取整 velocity，可能只能传出 0/100/200，桥接无法恢复已丢失的中间值。GEN/BRE/TEN/VOI 连续曲线及 Voice Color 暂未接入。
- 当前适配传统中文声库和拼音；数字声调忽略，ü 使用 `v` 或 `u:`。不支持 AI 声库和句内变速，其他引擎表现参数未充分实现或验证。

独立打开设置窗口可运行 `python enunu/configure.py`；未指定父进程时，关闭窗口会停止服务。

不要提交本机配置、Windows Python、第三方 API、日志或授权数据；相关目录及文件已列入 `.gitignore`。发布包仍应单独检查。卸载菜单插件可删除 `Plugins/VocaloidBridge/`；生成的声库描述位于 `Singers/VOCALOID-Wine-*`，与真正的声库数据分开。

## 许可证

项目代码使用 [LGPL 2.1](LICENSE)。第三方依赖和外部 API 的许可独立于本项目，见 [THIRD_PARTY.md](THIRD_PARTY.md) 和 [LEGAL.md](LEGAL.md)。
