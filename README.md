# OpenUtau Vocaloid Bridge

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
