from setuptools import setup, find_packages

setup(
    name="api_testing_framework",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        'requests>=2.25.1',
        'PyYAML>=5.4.1'
    ],
    entry_points={
        'console_scripts': [
            'api_tester=api_testing.main:main'
        ]
    }
)
