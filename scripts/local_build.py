import os
import sys
import subprocess

PYSIDE_VER = "6.6.2"


def get_vcvars_cmd():
    if sys.platform != "win32":
        return ""

    vswhere_path = r"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
    vswhere_path = os.path.expandvars(vswhere_path)

    cmd = [vswhere_path, "-latest", "-prerelease", "-property", "installationPath"]
    try:
        vs_path = subprocess.check_output(cmd, text=True).strip()
        vcvars = os.path.join(vs_path, "VC", "Auxiliary", "Build", "vcvars64.bat")
        if os.path.exists(vcvars):
            return f'call "{vcvars}" && '
    except:
        pass
    return ""


def main():
    print("=== PySide6-Ela 本地编译构建 ===")
    print(f"PySide6 版本：{PYSIDE_VER}")

    # 1. 设置平台相关的 aqt 参数和实际产出目录名
    if sys.platform == "win32":
        qt_arch = "win64_msvc2019_64"
        qt_dir_name = "msvc2019_64"
        host_os = "windows"
    else:
        qt_arch = "gcc_64"
        qt_dir_name = "gcc_64"
        host_os = "linux"

    qt_install_dir = os.path.abspath(f".qt/{PYSIDE_VER}/{qt_dir_name}").replace(
        "\\", "/"
    )

    # 2. 检查并下载 Qt
    if not os.path.exists(qt_install_dir):
        print("本地缺失对应的 Qt C++ 库，使用 aqtinstall 下载中...")
        subprocess.run(
            [
                "aqt",
                "install-qt",
                host_os,
                "desktop",
                PYSIDE_VER,
                qt_arch,
                "--outputdir",
                ".qt",
                "-b",
                "https://mirrors.sjtug.sjtu.edu.cn/qt/",
            ],
            check=True,
        )
    else:
        print(f"检测到本地 Qt 缓存: {qt_install_dir}，跳过下载。")

    # 3. 准备调用核心构建脚本
    build_script = os.path.abspath("scripts/build.py")

    env_setup = get_vcvars_cmd()

    cmd = f'{env_setup}"{sys.executable}" "{build_script}" "{qt_install_dir}" "{PYSIDE_VER}"'

    print(f"执行构建命令: {cmd}")
    subprocess.run(cmd, shell=True, check=True)

    print(
        "\n✅ 构建完成！请使用 uv 安装并测试：uv pip install wheel/dist/*.whl --force-reinstall"
    )


if __name__ == "__main__":
    main()
