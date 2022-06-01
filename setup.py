from setuptools import setup

setup(
    name='nflMaps',
    version='0.1',
    url='',
    packages=['nflMaps'],
    license='M.I.T',
    author='Poul Hornsleth',
    author_email='phornsleth@asquared.com',
    description='Maps of NFL Teams and Fan Base',
    install_requires = ['pandas','geopandas','requests','matplotlib','geopy']
)
