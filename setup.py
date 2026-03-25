"""py2app build script — creates SKP Converter.app"""
from setuptools import setup

setup(
    name="SKP Converter",
    app=["converter_app.py"],
    data_files=[],
    options={
        "py2app": {
            "argv_emulation": False,
            "includes": ["img_to_skm", "PIL"],
            "packages": ["PIL"],
            "plist": {
                "CFBundleName": "SKP Converter",
                "CFBundleDisplayName": "SKP Converter",
                "CFBundleIdentifier": "com.local.skp-converter",
                "CFBundleVersion": "1.0",
                "CFBundleShortVersionString": "1.0",
                "NSHighResolutionCapable": True,
                "LSMinimumSystemVersion": "12.0",
            },
        }
    },
    setup_requires=["py2app"],
)
