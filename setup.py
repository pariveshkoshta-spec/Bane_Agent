from setuptools import setup, find_packages

setup(
    name='bane-cli',
    version='1.0.0',
    packages=find_packages(),
    py_modules=['cli'],
    install_requires=[
        'typer>=0.9.0',
        'rich>=13.0.0',
        'requests>=2.31.0',
    ],
    entry_points='''
        [console_scripts]
        bane=cli:app
    ''',
)
