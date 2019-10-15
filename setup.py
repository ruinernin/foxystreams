import setuptools


setuptools.setup(
    name="foxydebrid",
    version="0.0.1",
    packages=['foxydebrid'],
    package_dir={'foxydebrid':'plugin.video.foxystreams/resources/lib/foxydebrid'},
    install_requires=['requests'],
)
