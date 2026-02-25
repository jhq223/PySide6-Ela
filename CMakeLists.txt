cmake_minimum_required(VERSION 3.18)
project(PySide6_Ela)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# 限定编译为 Release，否则 Windows 下 Python 找不到 _d.lib 调试库
set(CMAKE_BUILD_TYPE Release)

# 1. 接收从 Python 构建脚本传进来的变量
# MY_QT_INSTALL, ELA_INCLUDE_PATH, ELA_LIB_PATH, dllSUFFIX, 等...

# 2. 配置 Qt6
set(CMAKE_PREFIX_PATH ${MY_QT_INSTALL})
find_package(Qt6 REQUIRED COMPONENTS Core Widgets Gui)
qt_standard_project_setup()

# 3. 收集 Shiboken 生成的 C++ 源文件
set(SHIBOKEN_OUTPUT_FOLDER "${CMAKE_CURRENT_SOURCE_DIR}/OUTPUTDIR")
file(GLOB SHIBOKEN_GENERATED_SOURCES 
    "${SHIBOKEN_OUTPUT_FOLDER}/PySide6_Ela/*.cpp" 
    "${SHIBOKEN_OUTPUT_FOLDER}/PySide6_Ela/*.h"
)

# 4. 创建 Python C++ 扩展库
add_library(PySide6_Ela SHARED
    ${CMAKE_CURRENT_SOURCE_DIR}/build_binding/wrapper.hpp
    ${SHIBOKEN_GENERATED_SOURCES}
)

# 5. 设置包含目录 (头文件)
target_include_directories(PySide6_Ela PRIVATE
    "${MY_PYTHON_INCLUDE_PATH}"
    "${CMAKE_CURRENT_SOURCE_DIR}"
    "${ELA_INCLUDE_PATH}"
    "${CMAKE_CURRENT_SOURCE_DIR}/build_binding"
    "${MY_SITE_PACKAGES_PATH}/PySide6/include"
    "${MY_SITE_PACKAGES_PATH}/PySide6/include/QtWidgets"
    "${MY_SITE_PACKAGES_PATH}/PySide6/include/QtGui"
    "${MY_SITE_PACKAGES_PATH}/PySide6/include/QtCore"
    "${MY_SITE_PACKAGES_PATH}/shiboken6_generator/include"
)

# 6. 使用 Python Stable ABI (适配 >= 3.9)
target_compile_definitions(PySide6_Ela PRIVATE "-DPy_LIMITED_API=0x03090000")

# 7. 解决 Windows 下后缀名必须为 .pyd 的要求
set_target_properties(PySide6_Ela PROPERTIES SUFFIX "${dllSUFFIX}")
if(WIN32)
    set_target_properties(PySide6_Ela PROPERTIES PREFIX "")
endif()

# 8. 链接库目录与依赖
target_link_directories(PySide6_Ela PRIVATE
    "${MY_SITE_PACKAGES_PATH}/shiboken6"
    "${MY_SITE_PACKAGES_PATH}/PySide6"
)

target_link_libraries(PySide6_Ela PRIVATE
    Qt6::Widgets
    Qt6::Core
    Qt6::Gui
    ${MY_SITE_PACKAGES_PATH}/shiboken6/${shiboken6Lib}
    ${MY_SITE_PACKAGES_PATH}/PySide6/${PySide6Lib}
    ${ELA_LIB_PATH}
)
