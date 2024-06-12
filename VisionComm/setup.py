from setuptools import setup, find_packages

setup(
    name='VisionComm',
    version='0.1',
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        'numpy',
        'pandas',
        'requests',
        'opencv-python',
        'tensorflow'
    ],
)
