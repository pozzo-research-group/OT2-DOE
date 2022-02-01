# SET UP FILE:
# in order to run in notebooks as an import XXXXXXXXXXXXX
# 1. Git clone the repository to a local computer
# 2. go to the outermost XXXXXXXXXXX folder
# 3. use "pip install . "
# 4. import packages into a jupyter notebook using "from XXXX import xxxxxx"

import setuptools

setuptools.setup(
    name='OT2-DOE',
    version='1.0',
    url='https://github.com/pozzo-research-group/OT2-DOE',
    license='MIT',
    author='Edwin Antonio, Maria Politi'
    description='A group of python modules and notebooks made for' + \
    ' high-throughput measurement and analysis of samples made through' + \
    ' a liquid handling robot (Opentrons OT2) ',
    description_content_type='text/markdown; charset=UTF-8; variant=GFM',
    short_description='Library of python functions to communicate with the' + \
    ' Opentrons OT2 liquid handling robot',
    short_description_content_type='text/markdown',
    long_description=open('README.md', 'r').read(),
    long_description_content_type='text/markdown; charset=UTF-8; variant=GFM',
    include_package_data=True,
    packages=setuptools.find_packages(),
    install_requires=['numpy',
                      'pandas',
                      'scipy',
                      'matplotlib'],
    zip_safe=False,
)
