from setuptools import setup, find_packages

setup(
    name="VideoFormater",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        'ffmpeg-python',
        'pyqt6',
        'moviepy',
        'opencv-python',
        'numpy',
        'pyobjc-framework-Cocoa',
        'pyobjc-framework-Quartz'
    ],
    author="MSAM.media",
    description="Ein Python-Tool zur Video-Formatierung und Konvertierung",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/MSAMmedia/VideoFormater",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
    ],
    python_requires='>=3.6',
    entry_points={
        'console_scripts': [
            'videoformater=VideoFormater:main',
        ],
    },
)