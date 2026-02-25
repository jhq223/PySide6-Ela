from setuptools import setup
from setuptools.dist import Distribution


class BinaryDistribution(Distribution):
    """强制 setuptools 将此包视为二进制扩展包，以生成带平台标签的 wheel"""

    def has_ext_modules(self):
        return True


setup(distclass=BinaryDistribution)
