import os
import sys
import re

if len(sys.argv) < 3:
    print(
        "Usage: python gen_xml.py <ela_include_path> <site_packages_path> [output_dir]"
    )
    sys.exit(1)

eladir = sys.argv[1]
site_packages = sys.argv[2]
output_dir = sys.argv[3] if len(sys.argv) > 3 else "."

os.makedirs(output_dir, exist_ok=True)


def patch_ela_property_header():
    """
    兼容 Shiboken 对宏内 Q_SIGNAL 的解析问题，避免属性变更信号被识别为普通方法。
    """
    header_path = os.path.join(eladir, "ElaProperty.h")
    if not os.path.exists(header_path):
        return

    with open(header_path, "r", encoding="utf8") as ff:
        content = ff.read()

    if "Q_SIGNALS:Q_SIGNAL" in content:
        return

    patched = re.sub(
        r"Q_SIGNAL(.*?)\\",
        r"Q_SIGNALS:Q_SIGNAL \1\\\npublic:\\",
        content,
    )
    if patched != content:
        with open(header_path, "w", encoding="utf8") as ff:
            ff.write(patched)


def gen_layout_helper(out_dir):
    """
    生成辅助头文件，包含 Shiboken 在生成 Layout 绑定时缺失的 addLayoutOwnership 内部实现。
    """
    helper_code = """#ifndef LAYOUT_OWNERSHIP_HELPER_H
#define LAYOUT_OWNERSHIP_HELPER_H

#include <QLayout>
#include <QLayoutItem>
#include <QWidget>
#include <sbkpython.h>
#include <shiboken.h>

// PySide6 宏兼容 (适配 6.6.2)
#ifndef SbkPySide6_QtWidgetsTypeStructs
#define SbkPySide6_QtWidgetsTypeStructs SbkPySide6_QtWidgetsTypes
#endif
#ifndef SBK_QWidget_IDX
#define SBK_QWidget_IDX SBK_QWIDGET_IDX
#endif
#ifndef SBK_QLayout_IDX
#define SBK_QLayout_IDX SBK_QLAYOUT_IDX
#endif
#ifndef SBK_QLayoutItem_IDX
#define SBK_QLayoutItem_IDX SBK_QLAYOUTITEM_IDX
#endif

static const char msgInvalidParameterAdd[] = "Invalid parameter None passed to addLayoutOwnership().";

void addLayoutOwnership(QLayout *layout, QLayoutItem *item);

#ifndef _RETRIEVEOBJECTNAME_
#define _RETRIEVEOBJECTNAME_ 
static QByteArray retrieveObjectName(PyObject *obj) {
    Shiboken::AutoDecRef objName(PyObject_Str(obj));
    return Shiboken::String::toCString(objName);
}
#endif

inline void addLayoutOwnership(QLayout *layout, QWidget *widget) {
    if (layout == nullptr || widget == nullptr) {
        PyErr_SetString(PyExc_RuntimeError, msgInvalidParameterAdd);
        return;
    }
    QWidget *lw = layout->parentWidget();
    QWidget *pw = widget->parentWidget();
    
    // PySide6 6.6.2 直接传入类型指针，无需 Shiboken::Module::get
    auto widgetType = reinterpret_cast<SbkObjectType*>(SbkPySide6_QtWidgetsTypeStructs[SBK_QWidget_IDX]);
    Shiboken::AutoDecRef pyChild(Shiboken::Conversions::pointerToPython(widgetType, widget));

    if (pw && lw && pw != lw)
        Shiboken::Object::setParent(nullptr, pyChild);

    if (!lw && !pw) {
        Shiboken::AutoDecRef pyParent(Shiboken::Conversions::pointerToPython(widgetType, layout));
        Shiboken::Object::keepReference(reinterpret_cast<SbkObject *>(pyParent.object()), retrieveObjectName(pyParent).constData(), pyChild, true);
    } else {
        if (!lw) lw = pw;
        Shiboken::AutoDecRef pyParent(Shiboken::Conversions::pointerToPython(widgetType, lw));
        Shiboken::Object::setParent(pyParent, pyChild);
    }
}

inline void addLayoutOwnership(QLayout *layout, QLayout *other) {
    if (layout == nullptr || other == nullptr) {
        PyErr_SetString(PyExc_RuntimeError, msgInvalidParameterAdd);
        return;
    }
    QWidget *parent = layout->parentWidget();
    auto layoutType = reinterpret_cast<SbkObjectType*>(SbkPySide6_QtWidgetsTypeStructs[SBK_QLayout_IDX]);
    
    if (!parent) {
        Shiboken::AutoDecRef pyParent(Shiboken::Conversions::pointerToPython(layoutType, layout));
        Shiboken::AutoDecRef pyChild(Shiboken::Conversions::pointerToPython(layoutType, other));
        Shiboken::Object::keepReference(reinterpret_cast<SbkObject *>(pyParent.object()), retrieveObjectName(pyParent).constData(), pyChild, true);
        return;
    }
    for (int i = 0, i_max = other->count(); i < i_max; ++i) {
        QLayoutItem *item = other->itemAt(i);
        if (PyErr_Occurred() || !item) return;
        addLayoutOwnership(layout, item);
    }
    Shiboken::AutoDecRef pyParent(Shiboken::Conversions::pointerToPython(layoutType, layout));
    Shiboken::AutoDecRef pyChild(Shiboken::Conversions::pointerToPython(layoutType, other));
    Shiboken::Object::setParent(pyParent, pyChild);
}

inline void addLayoutOwnership(QLayout *layout, QLayoutItem *item) {
    if (layout == nullptr || item == nullptr) {
        PyErr_SetString(PyExc_RuntimeError, msgInvalidParameterAdd);
        return;
    }
    if (QWidget *w = item->widget()) {
        addLayoutOwnership(layout, w);
    } else {
        if (QLayout *l = item->layout())
            addLayoutOwnership(layout, l);
    }
    auto layoutType = reinterpret_cast<SbkObjectType*>(SbkPySide6_QtWidgetsTypeStructs[SBK_QLayout_IDX]);
    auto itemType = reinterpret_cast<SbkObjectType*>(SbkPySide6_QtWidgetsTypeStructs[SBK_QLayoutItem_IDX]);
    
    Shiboken::AutoDecRef pyParent(Shiboken::Conversions::pointerToPython(layoutType, layout));
    Shiboken::AutoDecRef pyChild(Shiboken::Conversions::pointerToPython(itemType, item));
    Shiboken::Object::setParent(pyParent, pyChild);
}

#endif // LAYOUT_OWNERSHIP_HELPER_H
"""
    with open(os.path.join(out_dir, "layout_helper.hpp"), "w", encoding="utf8") as f:
        f.write(helper_code)


def gen_navigation_specials(is_const):
    const_suffix = " const" if is_const else ""
    return f"""
        <modify-function signature="addFooterNode(const QString &amp;, QString &amp;, int, ElaIconType::IconName){const_suffix}">
            <modify-argument index="2">
                <remove-argument/>
            </modify-argument>
            <inject-code class="target" position="beginning">
                QString footerKey;
                ElaNavigationType::NodeResult cppRes =
                    %CPPSELF.addFooterNode(%1, footerKey, %3, %4);

                #ifndef SBK_QString_IDX
                #define SBK_QString_IDX SBK_QSTRING_IDX
                #endif
                #ifndef SbkPySide6_ElaTypeStructs
                #define SbkPySide6_ElaTypeStructs SbkPySide6_ElaTypes
                #endif

                PyObject* pyRes = Shiboken::Conversions::copyToPython(
                    PepType_SETP(reinterpret_cast&lt;SbkEnumType *&gt;(SbkPySide6_ElaTypeStructs[SBK_ELANAVIGATIONTYPE_NODERESULT_IDX]))-&gt;converter,
                    &amp;cppRes);

                PyObject* pyFooterKey = Shiboken::Conversions::copyToPython(
                    SbkPySide6_QtCoreTypeConverters[SBK_QString_IDX],
                    &amp;footerKey);

                return Py_BuildValue("(NN)", pyRes, pyFooterKey);
            </inject-code>
        </modify-function>
        <modify-function signature="addFooterNode(const QString &amp;, QWidget *, QString &amp;, int, ElaIconType::IconName)">
            <modify-argument index="3">
                <remove-argument/>
            </modify-argument>
            <inject-code class="target" position="beginning">
                QString footerKey;
                ElaNavigationType::NodeResult cppRes =
                    %CPPSELF.addFooterNode(%1, %2, footerKey, %4, %5);

                #ifndef SBK_QString_IDX
                #define SBK_QString_IDX SBK_QSTRING_IDX
                #endif
                #ifndef SbkPySide6_ElaTypeStructs
                #define SbkPySide6_ElaTypeStructs SbkPySide6_ElaTypes
                #endif

                PyObject* pyRes = Shiboken::Conversions::copyToPython(
                    PepType_SETP(reinterpret_cast&lt;SbkEnumType *&gt;(SbkPySide6_ElaTypeStructs[SBK_ELANAVIGATIONTYPE_NODERESULT_IDX]))-&gt;converter,
                    &amp;cppRes);

                PyObject* pyFooterKey = Shiboken::Conversions::copyToPython(
                    SbkPySide6_QtCoreTypeConverters[SBK_QString_IDX],
                    &amp;footerKey);

                return Py_BuildValue("(NN)", pyRes, pyFooterKey);
            </inject-code>
        </modify-function>
        <modify-function signature="addExpanderNode(const QString &amp;, QString &amp;, ElaIconType::IconName){const_suffix}">
            <modify-argument index="2">
                <remove-argument/>
            </modify-argument>
            <inject-code class="target" position="beginning">
                QString expanderKey;
                ElaNavigationType::NodeResult cppRes =
                    %CPPSELF.addExpanderNode(%1, expanderKey, %3);

                #ifndef SBK_QString_IDX
                #define SBK_QString_IDX SBK_QSTRING_IDX
                #endif
                #ifndef SbkPySide6_ElaTypeStructs
                #define SbkPySide6_ElaTypeStructs SbkPySide6_ElaTypes
                #endif

                PyObject* pyRes = Shiboken::Conversions::copyToPython(
                    PepType_SETP(reinterpret_cast&lt;SbkEnumType *&gt;(SbkPySide6_ElaTypeStructs[SBK_ELANAVIGATIONTYPE_NODERESULT_IDX]))-&gt;converter,
                    &amp;cppRes);

                PyObject* pyExpanderKey = Shiboken::Conversions::copyToPython(
                    SbkPySide6_QtCoreTypeConverters[SBK_QString_IDX],
                    &amp;expanderKey);

                return Py_BuildValue("(NN)", pyRes, pyExpanderKey);
            </inject-code>
        </modify-function>
        <modify-function signature="addExpanderNode(const QString &amp;, QString &amp;, const QString &amp;, ElaIconType::IconName){const_suffix}">
            <modify-argument index="2">
                <remove-argument/>
            </modify-argument>
            <inject-code class="target" position="beginning">
                QString expanderKey;
                ElaNavigationType::NodeResult cppRes =
                    %CPPSELF.addExpanderNode(%1, expanderKey, %3, %4);

                #ifndef SBK_QString_IDX
                #define SBK_QString_IDX SBK_QSTRING_IDX
                #endif
                #ifndef SbkPySide6_ElaTypeStructs
                #define SbkPySide6_ElaTypeStructs SbkPySide6_ElaTypes
                #endif

                PyObject* pyRes = Shiboken::Conversions::copyToPython(
                    PepType_SETP(reinterpret_cast&lt;SbkEnumType *&gt;(SbkPySide6_ElaTypeStructs[SBK_ELANAVIGATIONTYPE_NODERESULT_IDX]))-&gt;converter,
                    &amp;cppRes);

                PyObject* pyExpanderKey = Shiboken::Conversions::copyToPython(
                    SbkPySide6_QtCoreTypeConverters[SBK_QString_IDX],
                    &amp;expanderKey);

                return Py_BuildValue("(NN)", pyRes, pyExpanderKey);
            </inject-code>
        </modify-function>
        <modify-function signature="addCategoryNode(const QString &amp;, QString &amp;)">
            <modify-argument index="2" direction="out"/>
        </modify-function>
        <modify-function signature="addCategoryNode(const QString &amp;, QString &amp;, const QString &amp;)">
            <modify-argument index="2" direction="out"/>
        </modify-function>
        <modify-function signature="addPageNode(const QString &amp;, QWidget *, int, ElaIconType::IconName)" rename="addPageNodeKeyPoints"/>
        <modify-function signature="addPageNode(const QString &amp;, QWidget *, const QString &amp;, int, ElaIconType::IconName)" rename="addPageNodeKeyPoints"/>
"""


def gen_defs():
    with open(os.path.join(eladir, "ElaDef.h"), "r", encoding="utf8") as ff:
        header_content = ff.read()

    block_pattern = re.compile(
        r"Q_BEGIN_ENUM_CREATE\s*\(\s*(\w+)\s*\)\s*(.*?)\s*Q_END_ENUM_CREATE\s*\(\s*\1\s*\)",
        re.DOTALL,
    )
    enum_pattern = re.compile(
        r"enum\s+(\w+)\s*\{(.*?)\};.*?Q_ENUM_CREATE\s*\(\s*\1\s*\)",
        re.DOTALL,
    )
    qflags_pattern = re.compile(
        r"Q_DECLARE_FLAGS\s*\(\s*(\w+)\s*,\s*(\w+(?:::\w+)?)\s*\)"
    )

    flags = {}
    enums_by_namespace = []

    for block_match in block_pattern.finditer(header_content):
        namespace = block_match.group(1)
        if namespace == "CLASS":
            continue

        block_content = block_match.group(2)
        enums = [m.group(1) for m in enum_pattern.finditer(block_content)]
        enums_by_namespace.append((namespace, enums))

        for qflags_match in qflags_pattern.finditer(block_content):
            flags_name = qflags_match.group(1)
            base_enum_name = qflags_match.group(2).split("::")[-1]
            flags[base_enum_name] = flags_name

    output = ""
    for namespace, enums in enums_by_namespace:
        output += f'    <namespace-type name="{namespace}">\n'
        for enum_name in enums:
            if enum_name in flags:
                output += (
                    f'        <enum-type name="{enum_name}" flags="{flags[enum_name]}" />\n'
                )
            else:
                output += f'        <enum-type name="{enum_name}" />\n'
        output += "    </namespace-type>\n"

    return output


def gen_widgets():
    xmls = []
    headers = [
        f for f in os.listdir(eladir) if f.startswith("Ela") and f.endswith(".h")
    ]
    for h in headers:
        if h in ["ElaDef.h", "ElaProperty.h", "ElaSingleton.h"]:
            continue
        with open(os.path.join(eladir, h), "r", encoding="utf-8") as f:
            content = f.read()
        classes = re.findall(r"class ELA_EXPORT (\w+)", content)
        for cls in classes:
            needs_layout_helper = cls in ["ElaFlowLayout", "ElaNavigationBar"]
            needs_navigation_specials = cls in ["ElaNavigationBar", "ElaWindow"]

            if not needs_layout_helper and not needs_navigation_specials:
                xmls.append(f'    <object-type name="{cls}" />')
                continue

            block = [f'    <object-type name="{cls}">']
            if needs_layout_helper:
                block.extend(
                    [
                        "        <extra-includes>",
                        '            <include file-name="layout_helper.hpp" location="local"/>',
                        "        </extra-includes>",
                    ]
                )
            if needs_navigation_specials:
                block.append(gen_navigation_specials(cls == "ElaWindow").rstrip())
            block.append("    </object-type>")
            xmls.append("\n".join(block))
    return "\n".join(xmls)


def main():
    print(f"Generating typesystem.xml to {output_dir}...")

    # 0. 预处理 ElaProperty.h（兼容 Shiboken 的 Q_SIGNAL 宏解析）
    patch_ela_property_header()

    # 1. 生成 C++ 辅助文件
    gen_layout_helper(output_dir)

    xml_enums = gen_defs()
    xml_widgets = gen_widgets()

    xmlbase = f"""<?xml version="1.0"?>
<typesystem package="PySide6_Ela">
    <load-typesystem name="typesystem_widgets.xml" generate="no"/>
    <load-typesystem name="typesystem_gui.xml" generate="no"/>
{xml_enums}
{xml_widgets}
</typesystem>"""

    # 2. 生成 bindings.xml
    with open(os.path.join(output_dir, "bindings.xml"), "w", encoding="utf8") as f:
        f.write(xmlbase)

    headers = [
        f for f in os.listdir(eladir) if f.startswith("Ela") and f.endswith(".h")
    ]

    # 3. 生成 wrapper.hpp
    wrapper_content = "#ifndef PYSIDE6_ELA_WRAPPER_H\n#define PYSIDE6_ELA_WRAPPER_H\n#define _CRT_USE_BUILTIN_OFFSETOF\n"
    for h in headers:
        wrapper_content += f'#include "{h}"\n'
    wrapper_content += "#endif\n"

    with open(os.path.join(output_dir, "wrapper.hpp"), "w", encoding="utf8") as f:
        f.write(wrapper_content)

    print("XML, wrapper.hpp and layout_helper.hpp generated successfully.")


if __name__ == "__main__":
    main()
