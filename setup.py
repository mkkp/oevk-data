from setuptools import setup, find_packages

setup(
    name="oevk-data",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "polars>=0.20.0",
        "duckdb>=0.10.0",
        "xxhash>=3.4.0",
        "requests>=2.31.0",
        "PyGithub>=2.0.0",
    ],
    python_requires=">=3.11",
)
