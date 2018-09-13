# Ethereum Sharding Proof of Concept 

This repository contains a proof of concept for a sharding implementation on Ethereum by Vlad Zamfir. 
The project was built during [ETHBerlin](http://ethberlin.com/), over 2 days, and should *not* be considered final nor production grade. There are probably major bugs/issues.

## Getting started [to be updated]

The dependencies of the simulation (run with ```python simulator.py```), are satisfied by this Dockerfile:

```
FROM ubuntu:xenial

# PREPARE FOR BUIDL
RUN apt-get update
RUN apt-get upgrade
RUN apt-get install -y software-properties-common
RUN add-apt-repository ppa:fkrull/deadsnakes #source of python 3.6, use at own risk
RUN apt-get update
RUN apt-get install -y build-essential

# PYTHON3.6
RUN apt-get install -y python3.6
RUN apt-get install -y python3.6-dev
RUN apt-get install -y python3.6-venv
RUN apt-get install -y python3.6-tk

# GET PIP
RUN apt-get install -y wget
RUN wget https://bootstrap.pypa.io/get-pip.py
RUN python3.6 get-pip.py

# LINK PYTHON NAMES
RUN ln -s -f /usr/bin/python3.6 /usr/local/bin/python3
RUN ln -s -f /usr/bin/python3.6 /usr/local/bin/python
RUN ln -s -f /usr/local/bin/pip /usr/local/bin/pip3

# IPYTHON
RUN pip3 install --upgrade ipython

# WEB3
RUN pip3 install --upgrade web3

# MATPLOTLIB
RUN pip3 install numpy
RUN apt-get install -y libxml2
RUN apt-get install -y libxml2-dev
RUN pip3 install requests 
RUN pip3 install ftfy 
#RUN pip3 install zeep 
RUN pip3 install pytz 
RUN pip3 install docker-py 
RUN pip3 install mysql-connector==2.1.6 
RUN pip3 install networkx
RUN apt-get install -y libpng-dev
RUN apt-get install -y freetype2-demos
#RUN apt-get install -y freetype-dev
RUN apt-get install -y pkg-config
#RUN pkg-config --cflags freetype
RUN pip3 install --upgrade matplotlib

```
I build it with ```sudo docker build --tag py3web3mpl . ```, then run with my ```ethshardingpoc``` repo mounted as a volume:
```
sudo docker run -it --net=host --env="DISPLAY" --volume="$HOME/.Xauthority:/root/.Xauthority:rw" --volume "$(pwd)"/Documents/programming/python/ethshardingpoc:/ethshardingpoc py3web3mpl
```

## Known Issues
- Need to make sure entire repository is Python >3.5 compatible.
- `simulator.py` crashing. See [Issue #3](https://github.com/smarx/ethshardingpoc/issues/3)
