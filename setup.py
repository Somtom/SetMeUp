from setuptools import setup, find_packages

setup(
    name='setmeup',
    version='0.1',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'setmeup = setmeup.cli:main',
        ]
    }
)
