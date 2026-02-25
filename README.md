# PySide6-Ela

✨ **Python binding for ElaWidgetTools based on PySide6** ✨

PySide6-Ela 是对优秀的 C++ 组件库 [ElaWidgetTools](https://github.com/Liniyous/ElaWidgetTools) 的 Python 封装。它利用 Shiboken6 生成高性能的 Python 绑定，让你在 Python 环境下也能享受流畅、美观的 Fluent Design 风格 UI。

---

## 🚀 特性

- **原生体验**：基于 ElaWidgetTools C++ 核心，性能卓越。
- **易于使用**：完全适配 PySide6，符合 Python 开发习惯。
- **自动布局**：内置对 ElaFlowLayout 等高级布局的支持。
- **跨平台**：提供 Windows 和 Linux 的预编译 Wheel 包。

---

## 📦 安装

推荐使用 `uv` 或 `pip` 进行安装：

```bash
pip install PySide6-Ela
```

## 🛠️ 快速上手

```python
from PySide6 import QtWidgets
from PySide6_Ela import eApp, ElaWindow

import sys

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    eApp.init() # 初始化 Ela 环境
    
    window = ElaWindow()
    window.setWindowTitle("PySide6-Ela Demo")
    window.show()
    
    sys.exit(app.exec())
```

## 🏗️ 编译说明
如果你希望从源代码编译：

克隆仓库并包含子模块：

```bash
git clone --recursive https://github.com/jhq223/PySide6-Ela.git
```

使用 uv 安装依赖：
```bash
uv sync
```

运行本地构建脚本：

```bash
uv run scripts/local_build.py
```

## 📄 开源协议
本项目采用 [LGPL v3.0](LICENSE) 协议。ElaWidgetTools 核心库遵循其自身的开源协议。