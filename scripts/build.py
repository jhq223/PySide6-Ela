import re
import sys
import os
import subprocess
import shutil
import sysconfig

if len(sys.argv) > 1:
    qt_install_dir = sys.argv[1].replace("\\", "/")
else:
    # 适配 Github Action 中的环境变量
    qt_install_dir = os.environ.get("QT_DIR", "").replace("\\", "/")
    if not qt_install_dir:
        raise ValueError("请提供 QT_DIR 环境变量或通过参数传入 Qt 安装路径")

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(root_dir)

print(f"使用 Qt 目录: {qt_install_dir}")

print("--- 1. 编译 ElaWidgetTools C++ 静态库 ---")
ela_build_dir = "ElaWidgetTools/build"
os.makedirs(ela_build_dir, exist_ok=True)

# 热修复 CMakeLists.txt
with open("ElaWidgetTools/CMakeLists.txt", "r", encoding="utf8") as f:
    content = f.read()
content = content.replace("add_subdirectory(ElaWidgetToolsExample)", "")
content = re.sub(
    r"SET\(QT_SDK_DIR .* FORCE\)", "# SET(QT_SDK_DIR ... FIXED BY SCRIPT)", content
)
with open("ElaWidgetTools/CMakeLists.txt", "w", encoding="utf8") as f:
    f.write(content)

cmake_args = [
    "cmake",
    "-G",
    "Ninja",
    f"-DQT_SDK_DIR={qt_install_dir}",
    f"-DCMAKE_PREFIX_PATH={qt_install_dir}",
    "-DELAWIDGETTOOLS_BUILD_STATIC_LIB=ON",
    "-DCMAKE_BUILD_TYPE=Release",
]

if sys.platform == "win32":
    cmake_args.extend(
        [
            "-DCMAKE_POLICY_DEFAULT_CMP0091=NEW",
            "-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL",
        ]
    )

cmake_args.append("..")
subprocess.run(cmake_args, cwd=ela_build_dir, check=True)

subprocess.run(
    ["cmake", "--build", ".", "--config", "Release", "-j", str(os.cpu_count())],
    cwd=ela_build_dir,
    check=True,
)

print("--- 2. 生成 Shiboken Bindings ---")
py_env = sys.executable

py_libs_dir = os.path.join(sysconfig.get_config_var("installed_base"), "libs")
if sys.platform == "win32":
    os.environ["LIB"] = f"{py_libs_dir};{os.environ.get('LIB', '')}"
    print(f"已注入 Python Lib 目录到环境变量: {py_libs_dir}")

binding_build_dir = "build_binding"
os.makedirs(binding_build_dir, exist_ok=True)

site_pkgs = (
    subprocess.run(
        [py_env, "-c", "import site; print(site.getsitepackages()[-1])"],
        capture_output=True,
        text=True,
    )
    .stdout.strip()
    .replace("\\", "/")
)

subprocess.run(
    [
        py_env,
        "scripts/gen_xml.py",
        os.path.abspath("ElaWidgetTools/ElaWidgetTools").replace("\\", "/"),
        site_pkgs,
        binding_build_dir,
    ],
    check=True,
)

print("--- 3. 编译 PySide6-Ela Python 扩展 ---")
py_include = (
    subprocess.run(
        [py_env, "-c", "import sysconfig; print(sysconfig.get_path('include'))"],
        capture_output=True,
        text=True,
    )
    .stdout.strip()
    .replace("\\", "/")
)

if sys.platform == "win32":
    ela_lib_path = os.path.abspath(
        "ElaWidgetTools/build/ElaWidgetTools/ElaWidgetTools.lib"
    ).replace("\\", "/")
    # Windows 下寻找 .lib
    lib_ext = ".lib"
    ps_kw = "pyside6.abi3"
    sh_kw = "shiboken6.abi3"
else:
    ela_lib_path = os.path.abspath(
        "ElaWidgetTools/build/ElaWidgetTools/libElaWidgetTools.a"
    ).replace("\\", "/")
    # macOS 下是 .dylib，Linux 下是 .so
    lib_ext = ".dylib" if sys.platform == "darwin" else ".so"
    ps_kw = "libpyside6.abi3"
    sh_kw = "libshiboken6.abi3"

# 跨平台查找 PySide6 和 shiboken6 依赖库
try:
    pyside_lib = next(
        f for f in os.listdir(f"{site_pkgs}/PySide6") if ps_kw in f and lib_ext in f
    )
    shiboken_lib = next(
        f for f in os.listdir(f"{site_pkgs}/shiboken6") if sh_kw in f and lib_ext in f
    )
except StopIteration:
    raise FileNotFoundError(f"找不到对应的动态库！请检查 {site_pkgs} 目录。")

bin_app = ".pyd" if sys.platform == "win32" else ".abi3.so"
ela_include_path = os.path.abspath("ElaWidgetTools/ElaWidgetTools").replace("\\", "/")

# 查找 shiboken6 可执行文件
shiboken_exe = "shiboken6.exe" if sys.platform == "win32" else "shiboken6"
shiboken_bin = os.path.join(site_pkgs, "shiboken6_generator", shiboken_exe).replace(
    "\\", "/"
)

if not os.path.exists(shiboken_bin):
    # 备用回退方案
    fallback_dir = os.path.dirname(py_env)
    if sys.platform == "win32":
        shiboken_bin = os.path.join(fallback_dir, "shiboken6.exe").replace("\\", "/")
    else:
        shiboken_bin = os.path.join(fallback_dir, "shiboken6").replace("\\", "/")

typesystems_dir = os.path.join(site_pkgs, "PySide6", "typesystems").replace("\\", "/")

output_dir = os.path.abspath("OUTPUTDIR").replace("\\", "/")
os.makedirs(output_dir, exist_ok=True)

xml_path = os.path.abspath(f"{binding_build_dir}/bindings.xml").replace("\\", "/")
wrapper_path = os.path.abspath(f"{binding_build_dir}/wrapper.hpp").replace("\\", "/")


# 查找 MSVC 14.29 include 路径（修复 shiboken 解析新版 MSVC STL 报错）
def find_msvc2019_include():
    if sys.platform != "win32":
        return None
    vswhere = os.path.expandvars(
        r"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
    )
    try:
        vs_path = subprocess.check_output(
            [vswhere, "-latest", "-prerelease", "-property", "installationPath"],
            text=True,
        ).strip()
        msvc_base = os.path.join(vs_path, "VC", "Tools", "MSVC")
        versions = sorted(os.listdir(msvc_base))
        for d in versions:
            if d.startswith("14.29"):
                return os.path.join(msvc_base, d, "include").replace("\\", "/")
        return os.path.join(msvc_base, versions[0], "include").replace("\\", "/")
    except Exception as e:
        print(f"vswhere 查找失败: {e}")
        return None


msvc2019_include = find_msvc2019_include()
if msvc2019_include:
    print(f"使用 MSVC 14.29 STL 路径: {msvc2019_include}")
else:
    print("⚠️ 未找到 MSVC 14.29，shiboken 可能报错")

shiboken_cmd = [
    shiboken_bin,
    "--generator-set=shiboken",
    f"--output-directory={output_dir}",
    f"-I{ela_include_path}",
    f"-I{qt_install_dir}/include",
    f"-I{qt_install_dir}/include/QtCore",
    f"-I{qt_install_dir}/include/QtGui",
    f"-I{qt_install_dir}/include/QtWidgets",
    f"--typesystem-paths={typesystems_dir}",
    "--enable-pyside-extensions",
    "--avoid-protected-hack",
]

# 关键：注入 14.29 路径
if msvc2019_include:
    shiboken_cmd.append(f"--system-include-paths={msvc2019_include}")
shiboken_cmd += [wrapper_path, xml_path]

print(f"执行 Shiboken 命令: {' '.join(shiboken_cmd)}")
subprocess.run(shiboken_cmd, check=True)

bind_cmake_args = [
    "cmake",
    "-G",
    "Ninja",
    f"-DdllSUFFIX={bin_app}",
    f"-DMY_QT_INSTALL={qt_install_dir}",
    f"-Dshiboken6Lib={shiboken_lib}",
    f"-DPySide6Lib={pyside_lib}",
    f"-DMY_PYTHON_INCLUDE_PATH={py_include}",
    f"-DMY_SITE_PACKAGES_PATH={site_pkgs}",
    f"-DELA_LIB_PATH={ela_lib_path}",
    f"-DELA_INCLUDE_PATH={ela_include_path}",
    "..",
]

subprocess.run(bind_cmake_args, cwd=binding_build_dir, check=True)
subprocess.run(
    ["cmake", "--build", ".", "--config", "Release", "-j", str(os.cpu_count())],
    cwd=binding_build_dir,
    check=True,
)

print("--- 4. 准备 Wheel 打包 ---")
wheel_dir = "src/PySide6_Ela"
dist_dir = "wheel/dist"
os.makedirs(wheel_dir, exist_ok=True)
os.makedirs(dist_dir, exist_ok=True)

output_lib = f"build_binding/PySide6_Ela{bin_app}"
if os.path.exists(output_lib):
    shutil.copy(output_lib, wheel_dir)
else:
    raise FileNotFoundError(f"未找到生成的二进制文件: {output_lib}")

init_content = """from PySide6 import QtCore, QtWidgets, QtGui
from .PySide6_Ela import *

def __wrapsingleton(T):
    class __Wrapper:
        def __getattr__(self, name):
            return getattr(T.getInstance(), name)
    return __Wrapper()

eTheme = __wrapsingleton(ElaTheme)
eApp = __wrapsingleton(ElaApplication)

def ElaThemeColor(themeMode, themeColor):
    return eTheme.getThemeColor(themeMode, themeColor)
"""

with open(f"{wheel_dir}/__init__.py", "w", encoding="utf8") as f:
    f.write(init_content)

print("--- 正在生成 .pyi 类型提示存根 ---")
try:
    # 临时将 src 目录加入 PYTHONPATH 环境变量，让 stubgen 能找到刚才生成的扩展
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath("src") + os.pathsep + env.get("PYTHONPATH", "")

    if sys.platform == "win32":
        stubgen_bin = os.path.join(os.path.dirname(py_env), "stubgen.exe")
    else:
        stubgen_bin = os.path.join(os.path.dirname(py_env), "stubgen")

    if not os.path.exists(stubgen_bin):
        print(f"⚠️ 未找到 {stubgen_bin}，请确保已安装 mypy (uv sync)")
    else:
        subprocess.run(
            [stubgen_bin, "-p", "PySide6_Ela", "-o", "src"], env=env, check=True
        )

        print("✅ 成功生成 PySide6_Ela 类型提示文件！")
except subprocess.CalledProcessError as e:
    print(f"⚠️ 生成 .pyi 文件失败: {e}")
except Exception as e:
    print(f"⚠️ 发生错误: {e}")


print("--- 5. 生成 Wheel ---")
subprocess.run(["uv", "build", "--wheel", "--out-dir", dist_dir], check=True)
print(f"\n✅ 构建完成！Wheel 文件已保存在: {dist_dir}")
